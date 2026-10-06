"""Final question 3: how many tokens do the two tool definitions add to every S3 request?

Two calls with the same messages (the S3 system message and Q-09), one without tools and
one with the two tool definitions. The difference in `usage.prompt_tokens` is the cost of the
definitions. It also counts the definitions alone with tiktoken, as a second opinion.

    python measure_tools.py
"""
import json
from pathlib import Path

from dotenv import load_dotenv

import strategies
import tools

ROOT = Path(__file__).resolve().parent


def measure(client):
    question = next(q for q in json.load(open(ROOT / "data" / "questions.json", encoding="utf-8"))
                    if q["id"] == "Q-09")["question"]
    messages = [{"role": "system", "content": strategies.system_message("S3")},
                {"role": "user", "content": question}]
    without, with_tools = strategies.Usage(), strategies.Usage()
    strategies.call_model(client, messages, without)
    strategies.call_model(client, messages, with_tools, tools.TOOLS)
    result = {"prompt_tokens_without_tools": without.prompt,
              "prompt_tokens_with_tools": with_tools.prompt,
              "tokens_added_by_the_two_definitions": with_tools.prompt - without.prompt}
    try:
        import tiktoken
        enc = tiktoken.get_encoding("o200k_base")
        result["tiktoken_o200k_of_the_definitions_as_json"] = len(enc.encode(json.dumps(tools.TOOLS)))
    except Exception as exc:                                  # the vocabulary file may not download
        result["tiktoken"] = f"not available ({type(exc).__name__})"
    return result


if __name__ == "__main__":
    load_dotenv()
    from openai import OpenAI
    out = measure(OpenAI(timeout=180, max_retries=2))
    (ROOT / "outputs").mkdir(exist_ok=True)
    json.dump(out, open(ROOT / "outputs" / "tool_tokens.json", "w", encoding="utf-8"), indent=1)
    print(json.dumps(out, indent=1))
