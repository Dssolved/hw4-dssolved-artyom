"""Run the three strategies on the twenty questions and save everything to outputs/.

    python run.py --run 1 --questions Q-09               # try one question first
    python run.py --run 1                                # all strategies, all 20 questions
    python run.py --run 1 --strategies S3 --resume       # continue after a crash
    python run.py --run 1 --summary-only                 # rebuild the tables from the saved files
    python run.py --run c1 --strategies S3 --vague-lookup --questions Q-01 Q-04 Q-09 Q-14 Q-18

Per question one file is written to outputs/run<N>/<strategy>/<question id>.json.
For S3 it holds every round, every tool call, its inputs, its result and how long it took.
"""
import argparse
import copy
import json
import statistics
import time
from pathlib import Path

from dotenv import load_dotenv

import strategies
import tools

ROOT = Path(__file__).resolve().parent
QUESTIONS_PATH = ROOT / "data" / "questions.json"

# gpt-5.6-luna price in dollars per million tokens (the rates used in HW1).
RATE_IN, RATE_OUT = 0.20, 1.20

VAGUE_DESCRIPTION = "Looks things up."


# --------------------------------------------------------------------------
# My rule for a correct answer (written down before the first full run)
# --------------------------------------------------------------------------
def is_correct(answer, question):
    """The name must be the same (capital letters do not matter). The number, rounded to the
    `decimals` of the question, must be within 1 in the last digit of `value`."""
    if not answer:
        return False
    if answer["name"].strip().casefold() != str(question["answer"]).strip().casefold():
        return False
    d = question["decimals"]
    return abs(round(answer["number"], d) - question["value"]) <= 10 ** (-d) * 1.0001


def cost(prompt_tokens, completion_tokens):
    return (prompt_tokens * RATE_IN + completion_tokens * RATE_OUT) / 1_000_000


# --------------------------------------------------------------------------
def load_questions():
    return json.load(open(QUESTIONS_PATH, encoding="utf-8"))


def run_question(client, strategy, question, args, tool_defs):
    started = time.perf_counter()
    try:
        if strategy == "S1":
            result = strategies.run_s1(client, question["question"])
        elif strategy == "S2":
            result = strategies.run_s2(client, question["question"], k=args.k)
        else:
            result = strategies.run_s3(client, question["question"], max_rounds=args.max_rounds,
                                       tool_defs=tool_defs)
    except Exception as exc:                                  # an API error must not stop the whole run
        result = {"strategy": strategy, "reply": "", "answer": None, "unanswered": True,
                  "prompt_tokens": 0, "completion_tokens": 0, "calls": 0,
                  "error": f"{type(exc).__name__}: {exc}"}
    result["seconds"] = round(time.perf_counter() - started, 3)
    result["question_id"] = question["id"]
    result["correct"] = is_correct(result["answer"], question)
    result["expected"] = {"answer": question["answer"], "value": question["value"], "decimals": question["decimals"]}
    return result


def summarise(out_dir, questions, strategy_names):
    rows, matrix = [], {}
    for s in strategy_names:
        results = []
        for q in questions:
            path = out_dir / s / f"{q['id']}.json"
            if path.exists():
                results.append(json.load(open(path, encoding="utf-8")))
        if not results:
            continue
        pt = sum(r["prompt_tokens"] for r in results)
        ct = sum(r["completion_tokens"] for r in results)
        secs = [r["seconds"] for r in results]
        rows.append({"strategy": s, "questions": len(results),
                     "correct": sum(r["correct"] for r in results),
                     "unanswered": sum(r["unanswered"] for r in results),
                     "prompt_tokens": pt, "completion_tokens": ct,
                     "median_seconds": round(statistics.median(secs), 2),
                     "total_seconds": round(sum(secs), 1), "cost": round(cost(pt, ct), 4)})
        matrix[s] = {r["question_id"]: r["correct"] for r in results}
    return rows, matrix


def print_summary(out_dir, questions, strategy_names, run_label):
    rows, matrix = summarise(out_dir, questions, strategy_names)
    names = {"S1": "S1 direct", "S2": f"S2 think and vote (k = {strategies.K})", "S3": "S3 tools"}
    lines = ["| Run | Strategy | Correct /20 | Unanswered | Input tokens | Output tokens | Median seconds per question | Total seconds | Cost ($) |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for r in rows:
        lines.append(f"| {run_label} | {names[r['strategy']]} | {r['correct']} (of {r['questions']}) | {r['unanswered']} | "
                     f"{r['prompt_tokens']:,} | {r['completion_tokens']:,} | {r['median_seconds']} | {r['total_seconds']} | {r['cost']:.4f} |")
    lines += ["", "| Question | " + " | ".join(matrix) + " |", "|---|" + ":---:|" * len(matrix)]
    for q in questions:
        cells = []
        for s in matrix:
            v = matrix[s].get(q["id"])
            cells.append("" if v is None else ("✓" if v else "✗"))
        lines.append(f"| {q['id']} | " + " | ".join(cells) + " |")
    text = "\n".join(lines)
    print("\n" + text)
    (out_dir / "summary.md").write_text(text + "\n", encoding="utf-8")
    json.dump(rows, open(out_dir / "summary.json", "w", encoding="utf-8"), indent=1)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run", default="1", help="label of this run: outputs/run<label>/")
    p.add_argument("--strategies", nargs="+", default=["S1", "S2", "S3"], choices=["S1", "S2", "S3"])
    p.add_argument("--questions", nargs="+", default=None, help="question ids, for example Q-09 (default: all 20)")
    p.add_argument("--k", type=int, default=strategies.K)
    p.add_argument("--max-rounds", type=int, default=strategies.MAX_ROUNDS)
    p.add_argument("--resume", action="store_true", help="skip questions that already have a saved result")
    p.add_argument("--summary-only", action="store_true")
    p.add_argument("--vague-lookup", action="store_true", help="C1: replace the lookup description by a vague one")
    p.add_argument("--out", default=None)
    args = p.parse_args()

    questions = load_questions()
    if args.questions:
        questions = [q for q in questions if q["id"] in args.questions]
    out_dir = Path(args.out) if args.out else ROOT / "outputs" / f"run{args.run}"
    out_dir.mkdir(parents=True, exist_ok=True)

    tool_defs = copy.deepcopy(tools.TOOLS)
    if args.vague_lookup:
        tool_defs[0]["function"]["description"] = VAGUE_DESCRIPTION

    if not args.summary_only:
        load_dotenv()
        from openai import OpenAI
        client = OpenAI(timeout=180, max_retries=2)           # reads OPENAI_API_KEY from the environment
        for s in args.strategies:
            (out_dir / s).mkdir(exist_ok=True)
            for q in questions:
                path = out_dir / s / f"{q['id']}.json"
                if args.resume and path.exists():
                    continue
                result = run_question(client, s, q, args, tool_defs)
                json.dump(result, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
                got = result["answer"] and f"{result['answer']['name']} | {result['answer']['number']}"
                print(f"{s} {q['id']}: {'OK ' if result['correct'] else 'BAD'} got {got} "
                      f"(expected {q['answer']} | {q['value']}) "
                      f"{result['prompt_tokens']}+{result['completion_tokens']} tokens, {result['seconds']} s"
                      + (f" ERROR {result['error']}" if result.get("error") else ""))
    print_summary(out_dir, load_questions() if not args.questions else questions, args.strategies,
                  args.run)


if __name__ == "__main__":
    main()
