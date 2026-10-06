# HW4 — submission

**AI assistance:** I used Claude (Anthropic) for the whole of Part A: to read the documents and questions with me, to draft the steps, the tool definitions, the hand walk-through of Q-09 and the argument against the alternative split, and to check my assumptions against the question file. I will state in each later part what Claude did there. All numbers in the result tables come from my own runs.

---

## Part A — Plan on paper (Easy)

> Commit this whole part before any `.py` file exists.

### A1 — The steps

The task is: *from one question in plain English to one line `ANSWER: <name or yes/no> | <number>`*. I cut it into six steps. The sample question is "Which district is denser, Brightwater or Millbrook, and by how much?".

| # | Step | What goes in (types) | What comes out (types) | When it goes wrong | Tool, loop, or model? |
|---|---|---|---|---|---|
| 1 | **Plan**: read the question, decide which facts to fetch and which formula to use | `question: str` | a plan: list of `(district: str, field: str)` pairs, a formula, and a reporting rule (which name wins, or yes/no, or a percent) | The question names something that is not one of the 12 districts or not a field I support: the model says it cannot answer and does not invent a number. A misspelled name is not fixed here; step 2 refuses it. | model |
| 2 | **Look up one fact** | `district: str`, `field: str` (from a fixed list) | `{"district": str, "field": str, "value": float, "unit": str, "source": list[str], "note": str or None}` or `{"error": str}` | *Nothing found:* unknown district gives an error with a suggestion ("did you mean Ossbridge or Ossford?"); unknown field gives an error with the list of valid fields. *Two things found:* two similar names (Ossbridge / Ossford) must be written in full, a short or unclear name ("Oss") is refused with both candidates; two profiles for one district (Tarnvale, Kelmarsh have a 2025 and an archived one) gives the 2025 profile only; a profile and its correction notice gives the corrected value, with both ids in `source`. *Number cannot be read:* if a figure is not found in the profile, the error names the document. *Unknown unit:* water use in a unit other than megalitres or cubic metres gives an error, never a guess. | tool `lookup` |
| 3 | **Run a tool request safely** | one `tool_call`: `id: str`, `name: str`, `arguments: str` (a JSON string) | exactly one tool message per id: `{"role": "tool", "tool_call_id": str, "content": str}` (the tool's JSON) | `arguments` is not valid JSON, or is not an object; the tool name is unknown; a required key is missing or an extra key is sent; the tool raises an exception. In every case the loop sends back an error message with the same `tool_call_id` and does not crash. If the round limit is reached, the question is marked *unanswered*. | loop |
| 4 | **Calculate** | `expression: str`, `decimals: int or None` | `{"result": float, "rounded": float or None}` or `{"error": str}` | Division by zero gives an error. Anything that is not a number, `+ - * /`, brackets or a unary minus is refused (calls, attributes, `**`, names). Expression longer than 200 characters, or a result bigger than 1e15, gives an error. An expression that cannot be read gives an error. | tool `calculate` |
| 5 | **Write the answer** | the numbers from step 4 and the reporting rule from step 1 | final text ending with `ANSWER: <name or yes/no> \| <number>` | The model forgets the last line or writes text in the number (step 6 then returns `None`, and the answer counts as wrong). Two values are equal, so no district is "higher": the model says so in words, and the question is marked by my rule. Rounding mistakes are avoided because `decimals` is done by the tool. | model |
| 6 | **Read the final line** | `reply: str` | `(name: str, number: float)` or `None` | No `ANSWER:` line, or a number that cannot be read (for example "about 5"): returns `None`. An empty reply (round limit): *unanswered*. | my code (`run.py`) |

**How the steps connect:**

```text
question ──► [1 plan: model] ──► tool requests ──► [3 loop: check + route] ──┬──► [2 lookup] ──► facts ──┐
                 ▲                                                          └──► [4 calculate] ◄─────────┤
                 │                                                                          │             │
                 └────────────  results come back as tool messages (same ids)  ◄────────────┴─────────────┘
                                                                                                │
        (when the model has all numbers)  [5 write the answer: model] ──► reply ──► [6 read the last line: code] ──► (name, number)
```

In words: step 1 produces requests for step 2 (facts). Every request goes through step 3, which only checks the *shape* (valid JSON, right keys, right types) and sends the result back with the same id. The facts come back to the model, which writes the expressions for step 4 (also through step 3). The numbers from step 4 go into step 5, and step 6 reads its last line.

**Why the split is complete and has no overlap:** every part of the sample question belongs to exactly one step.

| Part of the sample question | Step |
|---|---|
| "Brightwater or Millbrook", "denser", "by how much": what to fetch and compute | 1 |
| population and area of each district, with the right year, the correction and the unit | 2 |
| valid JSON, known tool, required keys, one answer per id | 3 |
| 44675 / 921.4, 37203 / 758.6 and their difference | 4 |
| which name wins, the rounding of the number, the final line | 5 |
| turning the final line into `(name, number)` | 6 |

The boundary between 3 and the two tools is: step 3 checks the **shape** of a request, and the tools check its **meaning**. Valid JSON with a district that does not exist is a step 2 problem, not a step 3 problem.

**What I am assuming:**

- **Years.** "Population" means the 2025 census, "2020 census" means the 2020 figure written in the *same 2025 profile*, budgets are for fiscal year 2025, water use is household use over calendar year 2025 (NR-00). School numbers are for the 2025/26 school year.
- **Archived profiles (NR-13, NR-14) are never used.** They are from 2019, they are superseded, and they have different years (a 2019 estimate, water from 2018). `lookup` ignores them and says so in `note` when it applies.
- **Corrections win.** NR-00 says corrections take precedence. NR-16 replaces the Brightwater area 912.4 with **921.4**. `lookup` applies it, not the model. This matters for Q-09: with the typo, the density difference is 0.077 (answer "0.1"); with the correction it is 0.556 (answer "0.6").
- **Units.** `lookup` returns water use in **megalitres**. Lindenmoor's profile gives 2,151,400 cubic metres, so `lookup` divides by 1,000 and returns 2,151.4 megalitres, with a note. One megalitre is 1,000 cubic metres (NR-15), and one cubic metre is 1,000 litres. Budgets are in million tenge, so "per resident" means × 1,000,000 ÷ population.
- **Water per resident per day** = megalitres × 1,000,000 litres ÷ population ÷ 365 (2025 is not a leap year). I checked that this convention reproduces the values in `questions.json`.
- **The tariff** is 142.35 tenge per cubic metre from 1 January 2025, in every district (NR-15), and only on household use. The 2024 tariff (131.80) is not used.
- **Percent growth** from 2020 to 2025 = (pop2025 / pop2020 − 1) × 100. Loss is the same number with the opposite sign. A "percentage points" difference is the difference between two percentages. Q-18 projects with the same growth factor: pop2030 = pop2025 × pop2025 / pop2020.
- **Rounding** happens only at the end. `calculate` keeps full precision; the model asks for a rounded copy with `decimals` for the final number. The final answer is given with 3 decimal places (fewer if the number is whole), and it is the scoring rule, written in Part B, that rounds it to the precision of each question.
- **The assumption my solution is most sensitive to:** that the value `lookup` returns is correct. In S3 the model never sees the documents, so a parsing mistake in my code (a wrong regular expression, a missed correction, a unit not converted) would give a wrong number that looks right, and the model has no way to notice it. For this reason `lookup` gets its own tests (B2), and the facts are read from `corpus.jsonl` by code, not typed by hand.

### A2 — The two tools

#### `lookup`

```json
{
  "type": "function",
  "function": {
    "name": "lookup",
    "description": "Look up ONE fact about ONE district of the Nine Rivers Region in the official 2025 profiles. Returns a single number, its unit and the ids of the documents it came from. Call it once for every number you need; never guess or remember numbers. Old archived (2019) profiles are never used, and published corrections are already applied (the 'note' field tells you when). Water use is always returned in megalitres, even if a profile uses another unit. The water tariff is the same in every district: use district 'region'. This tool does no arithmetic: use 'calculate' for that.",
    "parameters": {
      "type": "object",
      "properties": {
        "district": {
          "type": "string",
          "description": "Exact district name: Ossbridge, Ossford, Tarnvale, Kelmarsh, Brightwater, Stonecairn, Harrowfield, Lindenmoor, Redfen, Ashgrove, Millbrook or Coldharbour. Use 'region' only for water_tariff_2025_tenge_per_m3."
        },
        "field": {
          "type": "string",
          "enum": [
            "founded_year",
            "area_km2",
            "population_2020",
            "population_2025",
            "budget_2025_million_tenge",
            "water_use_2025_megalitres",
            "schools",
            "pupils_2025_26",
            "paved_road_km",
            "water_tariff_2025_tenge_per_m3"
          ],
          "description": "The fact to read. population_2020 and population_2025 are census counts; budget is in million tenge; pupils_2025_26 and schools are for the 2025/26 school year."
        }
      },
      "required": [
        "district",
        "field"
      ],
      "additionalProperties": false
    }
  }
}
```

| Case | What the tool returns |
|---|---|
| success | `{"district": "Brightwater", "field": "area_km2", "value": 921.4, "unit": "km2", "source": ["NR-05", "NR-16"], "note": "NR-16 corrects the area in NR-05 from 912.4 to 921.4; the corrected value is returned"}` |
| unknown district | `{"error": "no district named 'Ossbrige'; did you mean 'Ossbridge'?", "valid_districts": ["Ossbridge", "..."]}` (the tool never silently fixes a name) |
| short or ambiguous name | `{"error": "'Oss' could mean Ossbridge or Ossford; use the full name"}` |
| unknown field | `{"error": "unknown field 'popluation'; valid fields: founded_year, area_km2, ..."}` |
| missing or wrong-type argument | `{"error": "'field' is required"}` or `{"error": "'district' must be a string"}` |
| archived-only fact asked | not possible: archived years have no field in the list; the tool returns the 2025 value and, when an archived profile exists, `note` says it was ignored |
| fact cannot be read from the profile | `{"error": "cannot read 'water_use_2025_megalitres' in NR-08: unknown unit '...'"}` |

**Worst thing it could do with strange or dangerous input:** the input is only compared with a fixed list of names and fields, and is never used in a file path, a command or `eval`, so the worst case is an error message. A very long string is cut off by a length limit (100 characters) and refused. The data are loaded once from one fixed file. The real risk is not the input but a wrong parse of the documents, which would return a wrong number without any error (see the sensitive assumption above).

#### `calculate`

```json
{
  "type": "function",
  "function": {
    "name": "calculate",
    "description": "Evaluate ONE arithmetic expression exactly and return the number. Allowed: numbers, + - * / and parentheses, and a minus sign in front of a number. No variables, no functions, no powers. Write the real numbers from 'lookup' into the expression, for example '44675 / 921.4'. Use it for every calculation, even a simple one, and do not do arithmetic in your head. Intermediate results are not rounded; give 'decimals' to get a rounded copy in 'rounded'.",
    "parameters": {
      "type": "object",
      "properties": {
        "expression": {
          "type": "string",
          "description": "The arithmetic expression, at most 200 characters, for example '(37203 / 34590 - 1) * 100'."
        },
        "decimals": {
          "type": "integer",
          "minimum": 0,
          "maximum": 10,
          "description": "Optional. Number of decimal places for the 'rounded' value."
        }
      },
      "required": [
        "expression"
      ],
      "additionalProperties": false
    }
  }
}
```

| Case | What the tool returns |
|---|---|
| success | `{"result": 48.48599956587801, "rounded": 48.486}` (`rounded` is `null` if `decimals` was not given) |
| division by zero | `{"error": "division by zero"}` |
| not allowed (call, attribute, name, `**`, string, ...) | `{"error": "not allowed: function call"}` (the expression is never run) |
| cannot be read | `{"error": "cannot read the expression: unexpected end of expression"}` |
| too long, too large, or not finite | `{"error": "expression longer than 200 characters"}` / `{"error": "number too large (limit 1e15)"}` |
| wrong arguments | `{"error": "'expression' must be a string"}` / `{"error": "'decimals' must be an integer from 0 to 10"}` |

**Worst thing it could do with strange or dangerous input:** with `eval`, the model (or any text it copies) could run any Python code: `__import__('os').system(...)` would run a shell command. I read the expression with the `ast` module instead and allow only numbers, `+ - * /`, brackets and a unary minus; every other kind of node is refused before anything is calculated. I do not allow `**` at all, so `9**9**9` cannot freeze the program, and `(1).__class__` is refused because it is an attribute. Limits on length (200 characters) and on size (1e15) stop huge numbers. After that, the worst thing left is a correct answer to a wrong formula that the model wrote.

### A3 — Q-09 by hand

The conversation I expect, in the Chat Completions message format. The model batches its requests, so there are three rounds: four lookups, three calculations, and the final answer. Read NR-05, NR-11 and NR-16: the Brightwater area is corrected to 921.4.

```json
[
  {
    "role": "user",
    "content": "Which district has the higher population density in 2025, Brightwater or Millbrook, and by how many residents per square kilometre?"
  },
  {
    "role": "assistant",
    "content": null,
    "tool_calls": [
      {
        "id": "call_1",
        "type": "function",
        "function": {
          "name": "lookup",
          "arguments": "{\"district\": \"Brightwater\", \"field\": \"population_2025\"}"
        }
      },
      {
        "id": "call_2",
        "type": "function",
        "function": {
          "name": "lookup",
          "arguments": "{\"district\": \"Brightwater\", \"field\": \"area_km2\"}"
        }
      },
      {
        "id": "call_3",
        "type": "function",
        "function": {
          "name": "lookup",
          "arguments": "{\"district\": \"Millbrook\", \"field\": \"population_2025\"}"
        }
      },
      {
        "id": "call_4",
        "type": "function",
        "function": {
          "name": "lookup",
          "arguments": "{\"district\": \"Millbrook\", \"field\": \"area_km2\"}"
        }
      }
    ]
  },
  {
    "role": "tool",
    "tool_call_id": "call_1",
    "content": "{\"district\": \"Brightwater\", \"field\": \"population_2025\", \"value\": 44675, \"unit\": \"residents\", \"source\": [\"NR-05\"], \"note\": null}"
  },
  {
    "role": "tool",
    "tool_call_id": "call_2",
    "content": "{\"district\": \"Brightwater\", \"field\": \"area_km2\", \"value\": 921.4, \"unit\": \"km2\", \"source\": [\"NR-05\", \"NR-16\"], \"note\": \"NR-16 corrects the area in NR-05 from 912.4 to 921.4; the corrected value is returned\"}"
  },
  {
    "role": "tool",
    "tool_call_id": "call_3",
    "content": "{\"district\": \"Millbrook\", \"field\": \"population_2025\", \"value\": 37203, \"unit\": \"residents\", \"source\": [\"NR-11\"], \"note\": null}"
  },
  {
    "role": "tool",
    "tool_call_id": "call_4",
    "content": "{\"district\": \"Millbrook\", \"field\": \"area_km2\", \"value\": 758.6, \"unit\": \"km2\", \"source\": [\"NR-11\"], \"note\": null}"
  },
  {
    "role": "assistant",
    "content": null,
    "tool_calls": [
      {
        "id": "call_5",
        "type": "function",
        "function": {
          "name": "calculate",
          "arguments": "{\"expression\": \"44675 / 921.4\", \"decimals\": 3}"
        }
      },
      {
        "id": "call_6",
        "type": "function",
        "function": {
          "name": "calculate",
          "arguments": "{\"expression\": \"37203 / 758.6\", \"decimals\": 3}"
        }
      },
      {
        "id": "call_7",
        "type": "function",
        "function": {
          "name": "calculate",
          "arguments": "{\"expression\": \"37203 / 758.6 - 44675 / 921.4\", \"decimals\": 3}"
        }
      }
    ]
  },
  {
    "role": "tool",
    "tool_call_id": "call_5",
    "content": "{\"result\": 48.48599956587801, \"rounded\": 48.486}"
  },
  {
    "role": "tool",
    "tool_call_id": "call_6",
    "content": "{\"result\": 49.041655681518584, \"rounded\": 49.042}"
  },
  {
    "role": "tool",
    "tool_call_id": "call_7",
    "content": "{\"result\": 0.5556561156405735, \"rounded\": 0.556}"
  },
  {
    "role": "assistant",
    "content": "Millbrook is denser: 49.042 residents per km2, against 48.486 for Brightwater (using the corrected Brightwater area of 921.4 km2). The difference is 0.556 residents per km2.\nANSWER: Millbrook | 0.556"
  }
]
```

**My arithmetic:**

- Brightwater: 44,675 ÷ 921.4. 921.4 × 48 = 44,227.2, the remainder is 447.8, and 447.8 ÷ 921.4 = 0.48600 (921.4 × 0.486 = 447.80), so the density is **48.486** residents per km².
- Millbrook: 37,203 ÷ 758.6. 758.6 × 49 = 37,171.4, the remainder is 31.6, and 31.6 ÷ 758.6 = 0.04166, so the density is **49.042** residents per km².
- Millbrook is denser. The difference is 49.04166 − 48.48600 = **0.55566**, which is **0.6** to one decimal place.
- What the typo would do: with the uncorrected area 912.4, Brightwater would be 44,675 ÷ 912.4 = 48.964 and the difference 0.077, so the answer would be "Millbrook | 0.1". The name would still be right but the number wrong, which is why the correction notice matters and why a check on the name alone would hide the mistake.

### A4 — Why I split it this way

Another way to split it: **one tool per kind of calculation**, for example `density(district)`, `growth(district)`, `per_capita(district, field)`. Each tool would fetch the facts and do the arithmetic inside. I did not choose it for four reasons. (1) The 20 questions need many different formulas (density, growth, water per day, budget per pupil, a projection, a sum of two areas), so I would need about ten tools, and every tool definition is sent to the model on every request, so the token cost grows with each new tool and the model has more tools to choose from. (2) A new kind of question would need new code and new tests, while one `calculate` tool covers any formula made from `+ - * /`. (3) The arithmetic would be hidden inside tools, so the log would not show which numbers were used, and I could not see where a mistake came from. (4) The price is that the model must write the formula itself, so a wrong formula is possible; I accept it, because the log shows the formula and the numbers, so I can find the mistake. A second option I rejected is a `lookup` that returns matching sentences from the documents: it is easier to write, but the model would have to read units and corrections out of text, which is exactly where the traps are (Lindenmoor's cubic metres, the NR-16 correction).

---

## Part B — Build it and run it (Medium)

### What I changed from Part A while coding

<!-- what changed in your plan, and why. "None" is an answer too. -->

### B2 — Tests

```text
<!-- pytest output -->
```

### B3 — The loop

- Round limit, and why:
- Where the logs are:
- Real Q-09 conversation compared with my A3 version, what is different:

### B4 — Three strategies

**What I kept the same:**

<!-- model, temperature, k, prompts, answer format, anything else -->

**My rule for a correct answer** (written before the first full run):

| Run | Strategy | Correct /20 | Unanswered | Input tokens | Output tokens | Median seconds per question | Total seconds | Cost ($) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | S1 direct | | | | | | | |
| 1 | S2 think and vote (k = ) | | | | | | | |
| 1 | S3 tools | | | | | | | |
| 2 | S1 direct | | | | | | | |
| 2 | S2 think and vote (k = ) | | | | | | | |
| 2 | S3 tools | | | | | | | |

**Per question (run 1):**

| Question | S1 | S2 | S3 |
|---|:---:|:---:|:---:|
| Q-01 | | | |
| Q-02 | | | |
| Q-03 | | | |
| Q-04 | | | |
| Q-05 | | | |
| Q-06 | | | |
| Q-07 | | | |
| Q-08 | | | |
| Q-09 | | | |
| Q-10 | | | |
| Q-11 | | | |
| Q-12 | | | |
| Q-13 | | | |
| Q-14 | | | |
| Q-15 | | | |
| Q-16 | | | |
| Q-17 | | | |
| Q-18 | | | |
| Q-19 | | | |
| Q-20 | | | |

---

## Part C — Explain and choose (Hard)

### C1 — Does the tool description matter?

| Question | Calls (your description) | Calls (vague) | Answer (yours) | Answer (vague) |
|---|---:|---:|---|---|
| | | | | |

### C2 — Three mistakes explained

### C3 — Which strategy I would use, and what would change it

### C4 — How sure I can be

### Final questions

1.
2.
3.
4.
5.
6.
7.
8.