"""The three strategies, and the loop that connects the model to the tools.

S1 direct:           all documents + question, one call.
S2 think and vote:   same prompt, "think step by step", k separate calls, majority vote.
S3 tools:            no documents; the model gets `lookup` and `calculate` and a loop.

What is the same in all three (the controls): the model, the user message (the
question, word for word), the answer format and its rules (FORMAT_RULES), and the
settings (reasoning_effort is "none" in every call; no temperature, top_p or
max tokens is set anywhere).
The only things that differ are the one strategy sentence in the system message,
the documents (S1/S2 have them, S3 does not) and the tools (only S3).
"""
import json
import re
import time
from collections import Counter
from pathlib import Path

import tools

MODEL = "gpt-5.6-luna"
K = 5                      # S2: number of samples
# gpt-5.6-luna refuses function tools in Chat Completions while reasoning is on (400 error), so
# reasoning_effort="none" is set in EVERY call of EVERY strategy: the only way to keep them like for like.
REASONING_EFFORT = "none"
MAX_ROUNDS = 10            # S3: most model calls in one question
CORPUS_PATH = Path(__file__).resolve().parent / "data" / "corpus.jsonl"

FORMAT_RULES = """You answer questions about the Nine Rivers Region, a made-up region with twelve districts. Be exact, and never round a number before the final line.

End your reply with ONE final line in exactly this form, and write nothing after it:
ANSWER: <name or yes/no> | <number>
- <name or yes/no> is the district name, spelled as in the question, or yes or no, whichever the question asks for.
- <number> is the number the question asks for: positive, in plain digits, no units, no thousands separators, with at most 3 decimal places."""

S1_RULE = "Answer directly: write only the final line, with no explanation."
S2_RULE = "Think step by step. Write each calculation out, then give the final line."
S3_RULE = ("You have no documents. Use the tools: call `lookup` for every fact and `calculate` for every calculation, "
           "and never use numbers from memory. You may call several tools at once. "
           "When you have all the numbers, write a short answer and then the final line.")


def load_documents():
    return [json.loads(line) for line in open(CORPUS_PATH, encoding="utf-8") if line.strip()]


def document_block(records=None):
    records = records or load_documents()
    return "\n\n".join(f"[{r['id']}] {r['title']}\n{r['text']}" for r in records)


def system_message(strategy, records=None):
    if strategy == "S1":
        return f"{FORMAT_RULES}\n\n{S1_RULE}\n\nDOCUMENTS:\n\n{document_block(records)}"
    if strategy == "S2":
        return f"{FORMAT_RULES}\n\n{S2_RULE}\n\nDOCUMENTS:\n\n{document_block(records)}"
    return f"{FORMAT_RULES}\n\n{S3_RULE}"


# --------------------------------------------------------------------------
# The final line
# --------------------------------------------------------------------------
ANSWER_RE = re.compile(r"ANSWER:\s*([^|\n]+?)\s*\|\s*([-+]?\d[\d,]*(?:\.\d+)?|[-+]?\.\d+)", re.IGNORECASE)


def parse_answer(text):
    """Last `ANSWER: <name> | <number>` line -> {"name": str, "number": float}, or None."""
    if not text:
        return None
    matches = ANSWER_RE.findall(text)
    if not matches:
        return None
    name, number = matches[-1]
    try:
        return {"name": name.strip().strip("*_` ").strip(), "number": float(number.replace(",", ""))}
    except ValueError:
        return None


def vote(answers):
    """Most common answer among the parsed ones (ties: the one seen first).
    Two answers are the same if the name is the same and the number is the same to 3 decimals."""
    parsed = [a for a in answers if a]
    if not parsed:
        return None
    key = lambda a: (a["name"].casefold(), round(a["number"], 3))
    counts = Counter(key(a) for a in parsed)
    best = counts.most_common(1)[0][0]
    for a in parsed:
        if key(a) == best:
            return {**a, "votes": counts[best], "of": len(parsed)}


# --------------------------------------------------------------------------
# Calls and token counting
# --------------------------------------------------------------------------
class Usage:
    def __init__(self):
        self.prompt = self.completion = self.calls = 0

    def add(self, resp):
        self.calls += 1
        if getattr(resp, "usage", None):
            self.prompt += resp.usage.prompt_tokens
            self.completion += resp.usage.completion_tokens


def call_model(client, messages, usage, tool_defs=None):
    kwargs = {"model": MODEL, "messages": messages, "reasoning_effort": REASONING_EFFORT}
    if tool_defs:
        kwargs["tools"] = tool_defs
    resp = client.chat.completions.create(**kwargs)
    usage.add(resp)
    return resp


def _result(strategy, reply, answer, usage, **extra):
    return {"strategy": strategy, "reply": reply, "answer": answer, "unanswered": answer is None,
            "prompt_tokens": usage.prompt, "completion_tokens": usage.completion, "calls": usage.calls, **extra}


# --------------------------------------------------------------------------
# S1 and S2
# --------------------------------------------------------------------------
def run_s1(client, question, records=None):
    usage = Usage()
    messages = [{"role": "system", "content": system_message("S1", records)},
                {"role": "user", "content": question}]
    reply = call_model(client, messages, usage).choices[0].message.content or ""
    return _result("S1", reply, parse_answer(reply), usage)


def run_s2(client, question, k=K, records=None):
    usage = Usage()
    messages = [{"role": "system", "content": system_message("S2", records)},
                {"role": "user", "content": question}]
    samples = []
    for _ in range(k):
        reply = call_model(client, messages, usage).choices[0].message.content or ""
        samples.append({"reply": reply, "answer": parse_answer(reply)})
    chosen = vote([s["answer"] for s in samples])
    return _result("S2", samples[0]["reply"] if samples else "", chosen, usage, k=k, samples=samples)


# --------------------------------------------------------------------------
# S3: the loop
# --------------------------------------------------------------------------
def run_s3(client, question, max_rounds=MAX_ROUNDS, tool_defs=None):
    """The loop. Each round: ask the model; if it asks for tools, run every request and
    send back one result per tool_call_id; if it does not, that reply is the answer."""
    tool_defs = tool_defs or tools.TOOLS
    usage = Usage()
    messages = [{"role": "system", "content": system_message("S3")},
                {"role": "user", "content": question}]
    trace = []
    for round_no in range(1, max_rounds + 1):
        before = (usage.prompt, usage.completion)
        resp = call_model(client, messages, usage, tool_defs)
        msg = resp.choices[0].message
        requests = list(msg.tool_calls or [])
        entry = {"round": round_no, "content": msg.content, "tool_calls": [],
                 "prompt_tokens": usage.prompt - before[0], "completion_tokens": usage.completion - before[1]}
        trace.append(entry)
        if not requests:                                     # no tools asked for: this is the answer
            reply = msg.content or ""
            return _result("S3", reply, parse_answer(reply), usage, rounds=round_no, trace=trace,
                           round_limit_reached=False)
        # the assistant message goes into the conversation unchanged
        messages.append({"role": "assistant", "content": msg.content,
                         "tool_calls": [{"id": tc.id, "type": "function",
                                         "function": {"name": tc.function.name,
                                                      "arguments": tc.function.arguments}} for tc in requests]})
        for tc in requests:                                  # one result for EVERY id
            started = time.perf_counter()
            content = tools.run_tool(tc.function.name, tc.function.arguments)
            seconds = time.perf_counter() - started
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": content})
            entry["tool_calls"].append({"id": tc.id, "name": tc.function.name,
                                        "arguments": tc.function.arguments, "result": content,
                                        "seconds": round(seconds, 6)})
    # the model still wanted tools after the last allowed round: unanswered
    return _result("S3", "", None, usage, rounds=max_rounds, trace=trace, round_limit_reached=True)


STRATEGIES = {"S1": run_s1, "S2": run_s2, "S3": run_s3}
