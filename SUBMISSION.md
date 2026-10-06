# HW4 — submission

**AI assistance:** I used Claude (Anthropic) for the whole of Part A: to read the documents and questions with me, to draft the steps, the tool definitions, the hand walk-through of Q-09 and the argument against the alternative split, and to check my assumptions against the question file. In Part B, Claude wrote the first version of the code (`tools.py`, `strategies.py`, `run.py` and the tests); I run it and the numbers in the result tables come from my own runs. In Part C, Claude drafts the text from my logs and numbers.

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

The plan held and Part A is unchanged. I made five small additions and one change that the API forced on me:

1. **Round limit.** Part A did not give a number. I chose 10 (see B3).
2. **`lookup` accepts any district name for the tariff.** In A2 I said to use `region`. The tool also accepts a real district name for `water_tariff_2025_tenge_per_m3` and returns the same value with a note, because a model would often write "Millbrook" there. `region` with any other field is an error.
3. **`calculate` has a third limit.** Besides length (200 characters) and size (1e15), it refuses an expression with more than 100 nodes ("too complicated"). This is for safety only.
4. **Step 3 also refuses extra arguments.** The loop checks that the arguments are a JSON object with all required keys and no unknown key, before it runs a tool (planned in A1, now written down as a rule).
5. **S2 samples are sequential.** Part A did not say how the 5 samples are sent. I send them one after another, like the rounds of S3, so that the time of S2 is the sum of its 5 calls.
6. **`reasoning_effort = "none"` in every call (the forced change).** My first test of Q-09 failed for S3 with a 400 error from the API: *"Function tools with reasoning_effort are not supported for gpt-5.6-luna in /v1/chat/completions. To use function tools, use /v1/responses or set reasoning_effort to 'none'."* The homework asks for Chat Completions, so I set `reasoning_effort="none"`. I set it in **all three strategies**, not only in S3, because otherwise S3 would work without reasoning and S1 and S2 with it, and the comparison would not be like for like. The same test also showed a second problem that this fixes: S1 ("direct") used 251 output tokens for a one-line answer, and S2 used 3,302 output tokens for five short replies, so the model was reasoning in hidden tokens even in "direct" mode. With `none`, S1 is really direct and the reasoning of S2 is only its visible step-by-step text, which is what the strategy is supposed to test. I deleted that first test run and ran everything again.

### B2 — Tests

```text
================================================== test session starts ===================================================
platform win32 -- Python 3.13.5, pytest-9.1.1, pluggy-1.6.0 -- F:\desktop\Учёба-практика\University\4 course\AI\hw4\hw4-dssolved-artyom\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: F:\desktop\Учёба-практика\University\4 course\AI\hw4\hw4-dssolved-artyom
plugins: anyio-4.15.1
collected 35 items

tests/test_answers.py::test_parse_answer PASSED                                                                     [  2%]
tests/test_answers.py::test_vote_takes_the_most_common_answer PASSED                                                [  5%]
tests/test_answers.py::test_my_rule_for_a_correct_answer PASSED                                                     [  8%]
tests/test_calculate.py::test_multiplication_is_right PASSED                                                        [ 11%]
tests/test_calculate.py::test_order_of_operations_brackets_and_unary_minus PASSED                                   [ 14%]
tests/test_calculate.py::test_density_example_and_rounding PASSED                                                   [ 17%]
tests/test_calculate.py::test_division_by_zero_is_an_error PASSED                                                   [ 20%]
tests/test_calculate.py::test_dangerous_input_is_refused_and_never_run[__import__('os').system('echo hi')] PASSED   [ 22%]
tests/test_calculate.py::test_dangerous_input_is_refused_and_never_run[(1).__class__] PASSED                        [ 25%]
tests/test_calculate.py::test_dangerous_input_is_refused_and_never_run[9**9**9] PASSED                              [ 28%]
tests/test_calculate.py::test_refusal_messages_say_why PASSED                                                       [ 31%]
tests/test_calculate.py::test_other_things_that_are_not_arithmetic_are_refused PASSED                               [ 34%]
tests/test_calculate.py::test_limits PASSED                                                                         [ 37%]
tests/test_calculate.py::test_wrong_argument_types PASSED                                                           [ 40%]
tests/test_lookup.py::test_finds_a_correct_2025_number PASSED                                                       [ 42%]
tests/test_lookup.py::test_every_field_of_every_district_can_be_read PASSED                                         [ 45%]
tests/test_lookup.py::test_misspelled_name_gets_a_suggestion_and_is_not_silently_fixed PASSED                       [ 48%]
tests/test_lookup.py::test_two_similar_names_are_kept_apart PASSED                                                  [ 51%]
tests/test_lookup.py::test_archived_profile_is_ignored PASSED                                                       [ 54%]
tests/test_lookup.py::test_correction_notice_is_applied PASSED                                                      [ 57%]
tests/test_lookup.py::test_unit_is_converted_to_megalitres PASSED                                                   [ 60%]
tests/test_lookup.py::test_tariff_and_region PASSED                                                                 [ 62%]
tests/test_lookup.py::test_bad_arguments_give_errors_not_crashes PASSED                                             [ 65%]
tests/test_lookup.py::test_unknown_water_unit_is_an_error_not_a_guess PASSED                                        [ 68%]
tests/test_lookup.py::test_correction_that_does_not_match_is_ignored PASSED                                         [ 71%]
tests/test_lookup.py::test_run_tool_checks_the_arguments_first PASSED                                               [ 74%]
tests/test_loop.py::test_q09_flow_every_tool_call_id_is_answered_and_the_answer_is_read PASSED                      [ 77%]
tests/test_loop.py::test_tokens_are_added_up_over_all_rounds PASSED                                                 [ 80%]
tests/test_loop.py::test_bad_arguments_get_an_error_with_the_same_id_and_the_loop_goes_on PASSED                    [ 82%]
tests/test_loop.py::test_round_limit_marks_the_question_unanswered PASSED                                           [ 85%]
tests/test_loop.py::test_reply_without_the_final_line_is_unanswered_but_not_a_limit_problem PASSED                  [ 88%]
tests/test_loop.py::test_s1_and_s2_send_all_documents_and_s3_sends_none PASSED                                      [ 91%]
tests/test_loop.py::test_every_call_of_every_strategy_uses_the_same_reasoning_setting PASSED                        [ 94%]
tests/test_tools_definitions.py::test_definitions_are_the_same_as_in_part_a PASSED                                  [ 97%]
tests/test_tools_definitions.py::test_definitions_have_the_required_shape PASSED                                    [100%]

=================================================== 35 passed in 0.19s ===================================================
```

### B3 — The loop

- Round limit, and why: **10 rounds** (a round is one call to the model). When the model sends its requests together, as in A3, Q-09 needs 3 rounds, and I expected 3 to 4 for most questions. The hardest questions (Q-17, Q-20) need 6 or more facts and 3 or more calculations, so a model that sends one request at a time could need 10 or more calls. 10 is more than twice the usual number, so a normal question is never cut off. It also stops a loop that does not end, which matters because every round sends the whole conversation again, so the cost of a question grows faster than the number of rounds. A question that reaches the limit is marked *unanswered*. In the two full runs the loop used 3 or 4 rounds on every question (run 1: 10 questions with 4 rounds and 10 with 3; run 2: 8 with 4 and 12 with 3), and the limit was never reached, so it was set with a safe margin (2.5 times the most that was needed) and never cut off a question.
- Where the logs are: `outputs/run1/` and `outputs/run2/`, one JSON file per question and strategy (`outputs/run1/S3/Q-09.json`, and so on). For S3 each file lists every round, every tool call with its id, name, inputs (the raw `arguments` string), result and the seconds it took. `outputs/run*/summary.md` and `summary.json` have the totals.
- Real Q-09 conversation compared with my A3 version, what is different: (`outputs/run1/S3/Q-09.json`, 3 rounds, 3,266 + 224 tokens, 3.98 s.) The shape is the one I planned: in round 1 the model sent **four `lookup` requests in one message** (Brightwater population and area, Millbrook population and area), my loop answered all four ids, and the Brightwater area came back as **921.4** with the NR-16 note, as in A3. The differences are:
  1. **The calculations.** In A3 I expected three `calculate` calls with `decimals: 3` (each density, then Millbrook minus Brightwater). The model sent three calls without `decimals`: the two densities and `44675 / 921.4 - 37203 / 758.6`, which is **Brightwater minus Millbrook**, so the result was **−0.5557**. The model read the minus sign correctly ("Millbrook has the higher 2025 population density") and wrote the positive number 0.556. So it rounded the number itself, which the tool could have done (it was right here, but this is the step where it could go wrong).
  2. **The number of rounds is not fixed.** Run 2 on the same question took **4 rounds**: the two densities in round 2, and the difference alone in round 3 (with `decimals: 3`). The model chose a different order, and every extra round sends the whole conversation again (round 4 of run 2 had 1,318 prompt tokens, round 3 of run 1 had 1,297, and in total 4,538 prompt tokens against 3,266).
  3. **The ids** are random strings (like `call_AamfJ42W`), not `call_1`, `call_2` as in my hand-written version, and the model's first message has `content: null`, as I expected.
  4. **The answer line** was exactly as planned: `ANSWER: Millbrook | 0.556`.

### B4 — Three strategies

**What I kept the same:**

- **Model:** `gpt-5.6-luna`, Chat Completions API, for every call in every strategy.
- **Questions:** the same 20 questions in the same order. The user message is the question, word for word, in all three strategies.
- **Answer format:** the same `FORMAT_RULES` text (the same words) is at the start of the system message of S1, S2 and S3, and one function (`parse_answer`) reads the last `ANSWER: <name or yes/no> | <number>` line for all of them. The same scoring rule marks all of them.
- **Sampling and reasoning:** `reasoning_effort="none"` in every call of every strategy (the API needs it for function tools, see change 6 above), and no `temperature`, `top_p` or maximum length anywhere, so everything else uses the API defaults. The default sampling is random, which gives S2 five different samples without depending on whether this model accepts another temperature.
- **S2:** k = 5, five separate calls sent one after another, same prompt each time. The answer is the most common `(name, number to 3 decimals)`; for a tie, the answer that came first.
- **S1 and S2 documents:** all 17 documents (NR-00 to NR-16) in the system message, in file order, unchanged, with the archived profiles and the correction notice. **S3** has no documents, only the two tools.
- **S3:** round limit 10, the tools from A2, tool results returned as JSON.
- **What differs between the strategies, and only this:** one sentence in the system message (S1 "answer directly", S2 "think step by step", S3 "use the tools"), the documents (S1 and S2 yes, S3 no), the tools (S3 only) and the number of calls (S1 one, S2 five, S3 as many as the loop needs).
- **Timing:** the three strategies run one after another on the same computer. A time is the whole question from the first request to the last reply (the waiting for the API plus the time of my tools), measured with `time.perf_counter`. The client uses a timeout of 180 s and the library's 2 automatic retries.
- **Tokens and cost:** summed from `usage.prompt_tokens` and `usage.completion_tokens` of every call (the 5 samples of S2 and every round of S3). Cost = input tokens × $0.20 / 1M + output tokens × $1.20 / 1M, the rates that I used for `gpt-5.6-luna` in HW1.
- **Unanswered:** a question where no readable `ANSWER:` line came out: the round limit was reached, the API gave an error, or the model did not write the line. For S2 it means that none of the 5 samples had a readable line.

**My rule for a correct answer** (written before the first full run):

An answer is correct when **both** are true:

1. **The name is the same** as `answer` in `questions.json` (capital letters and spaces at the ends do not matter). This includes `yes` and `no`.
2. **The number is right to one unit in the last digit.** I round the model's number to the `decimals` of the question, and the result must be at most 1 unit of the last digit away from `value`. Example: `decimals` = 1 and `value` = 0.6, so 0.556 (rounds to 0.6) and 0.7 are correct, and 0.077 (rounds to 0.1) is wrong.

The name and the number are both needed. A right name with a wrong number is wrong. This matters: for Q-09 the uncorrected Brightwater area gives the right district but the number 0.1 instead of 0.6, and a rule that checks the name only would not notice the difference. An answer that is not in the `ANSWER:` form is wrong (and counted as unanswered). The rule is in `run.py` (`is_correct`) and tested in `tests/test_answers.py`. I chose it because the question file gives `value` and `decimals`; one unit in the last digit leaves room for a different (but correct) way to round, and nothing else.

| Run | Strategy | Correct /20 | Unanswered | Input tokens | Output tokens | Median seconds per question | Total seconds | Cost ($) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | S1 direct | 3 | 0 | 45,160 | 249 | 1.09 | 21.7 | 0.0093 |
| 1 | S2 think and vote (k = 5) | 16 | 0 | 226,100 | 13,854 | 10.56 | 216.7 | 0.0618 |
| 1 | S3 tools | 20 | 0 | 78,624 | 4,642 | 5.05 | 98.8 | 0.0213 |
| 2 | S1 direct | 5 | 0 | 45,160 | 252 | 1.09 | 23.3 | 0.0093 |
| 2 | S2 think and vote (k = 5) | 17 | 0 | 226,100 | 14,148 | 9.83 | 206.8 | 0.0622 |
| 2 | S3 tools | 19 | 0 | 76,079 | 4,774 | 5.01 | 97.0 | 0.0209 |

The two runs used the same code and settings; the S1, S2 and S3 results of a run were produced one strategy after another on the same computer. Unanswered is 0 everywhere: every question gave a readable `ANSWER:` line in every strategy, the round limit was never reached, and there was no API error. The input tokens of S1 and S2 are the same in both runs because the prompts are the same (S2 sends the S1 prompt 5 times: 226,100 / 45,160 = 5.01). The cost uses $0.20 per million input tokens and $1.20 per million output tokens.

**Per question (run 1):**

| Question | S1 | S2 | S3 |
|---|:---:|:---:|:---:|
| Q-01 | ✗ | ✓ | ✓ |
| Q-02 | ✗ | ✓ | ✓ |
| Q-03 | ✗ | ✓ | ✓ |
| Q-04 | ✗ | ✓ | ✓ |
| Q-05 | ✗ | ✗ | ✓ |
| Q-06 | ✓ | ✓ | ✓ |
| Q-07 | ✗ | ✓ | ✓ |
| Q-08 | ✗ | ✓ | ✓ |
| Q-09 | ✗ | ✓ | ✓ |
| Q-10 | ✓ | ✓ | ✓ |
| Q-11 | ✗ | ✓ | ✓ |
| Q-12 | ✗ | ✗ | ✓ |
| Q-13 | ✗ | ✓ | ✓ |
| Q-14 | ✗ | ✓ | ✓ |
| Q-15 | ✗ | ✓ | ✓ |
| Q-16 | ✓ | ✓ | ✓ |
| Q-17 | ✗ | ✓ | ✓ |
| Q-18 | ✗ | ✗ | ✓ |
| Q-19 | ✗ | ✓ | ✓ |
| Q-20 | ✗ | ✗ | ✓ |

**Per question (run 2)**, for the check of the run-to-run difference in C4: the answers that changed compared with run 1 are S1 Q-01 (✗ → ✓), S1 Q-13 (✗ → ✓), S2 Q-18 (✗ → ✓) and S3 Q-17 (✓ → ✗). Every other cell is the same as in run 1. Run 2 summary: S1 5/20, S2 17/20, S3 19/20.

---

## Part C — Explain and choose (Hard)

### C1 — Does the tool description matter?

I ran S3 again on five questions with only the first line of the `lookup` description changed to `"Looks things up."` (command: `python run.py --run c1 --strategies S3 --vague-lookup --questions Q-03 Q-08 Q-09 Q-14 Q-17`; logs in `outputs/runc1/S3/`). Everything else was the same: the parameter descriptions and the list of fields, the `calculate` tool, the system message, the model and the settings. I chose the five questions because each depends on something that the full description promises: units (Q-03, Lindenmoor), a correction (Q-09, NR-16), the tariff with `region` (Q-08, Q-17) and an archived profile (Q-14, Tarnvale). "Calls (your description)" is from run 1 (run 2 had the same number of calls on these five questions); "calls" are tool calls, lookups + calculations.

| Question | Calls (your description) | Calls (vague) | Answer (yours) | Answer (vague) |
|---|---|---|---|---|
| Q-03 | 7 (4 lookup, 3 calculate), 4 rounds | 5 (4 lookup, 1 calculate), 3 rounds | Lindenmoor \| 5.34 ✓ | Lindenmoor \| 5.34 ✓ |
| Q-08 | 4 (3 lookup, 1 calculate), 3 rounds | 4 (3 lookup, 1 calculate), 3 rounds | Brightwater \| 72.456 ✓ | Brightwater \| 72.456 ✓ |
| Q-09 | 7 (4 lookup, 3 calculate), 3 rounds | 5 (4 lookup, 1 calculate), 3 rounds | Millbrook \| 0.556 ✓ | Millbrook \| 0.556 ✓ |
| Q-14 | 7 (4 lookup, 3 calculate), 4 rounds | 7 (4 lookup, 3 calculate), 3 rounds | Ashgrove \| 4.853 ✓ | Ashgrove \| 4.853 ✓ |
| Q-17 | 8 (5 lookup, 3 calculate), 4 rounds | 8 (5 lookup, 3 calculate), 4 rounds | Harrowfield \| 884.457 ✓ | Harrowfield \| 884.457 ✓ |
| **Total** | 33 calls, 18 rounds, 20,784 + 1,288 tokens, 26.1 s | 29 calls, 16 rounds, 15,981 + 1,154 tokens, 29.8 s | 5 of 5 | 5 of 5 |

**What changed:**

- **The answers: nothing.** All five answers are the same as before and correct, and none of the 29 tool calls returned an error. The **lookups were the same**: the same districts, the same fields, and for the tariff the model still wrote `"district": "region"` (Q-08, Q-17) and still asked for `water_use_2025_megalitres` of Lindenmoor, with the unit conversion done by the tool.
- **The calculations changed in two questions.** For Q-03 and Q-09 the model sent **one** combined `calculate` (for example `(2151.4 * 1000000 / 29051 / 365) - (1739 * 1000000 / 24117 / 365)`) instead of three (the two values and then their difference), so there were 4 fewer calls (33 → 29). The number of rounds went down by 2 in total (18 → 16): one in Q-03 and one in Q-14, where the model also finished a round earlier. With the full description the model wrote separate expressions for each district and then the difference, which is easier to check in the log.
- **The tokens: 23% fewer input tokens** (20,784 → 15,981). 122 tokens per question are the shorter description itself (round 1 had 829 prompt tokens with my description and 707 with the vague one on the five questions, so my description is about 127 tokens). The rest comes from the fewer rounds, because every round sends the whole conversation again.
- **The time** was longer in total (26.1 s → 29.8 s) in spite of fewer rounds; with only 5 questions and one run, I do not trust this difference (the two normal runs differed by 1 s on the same questions: 26.1 and 25.1).

**Why so little changed:** my description says *when* and *how* to call the tool, and the model did not need it here, for three reasons. (1) **The facts are enforced in code, not by the description.** The archived-profile rule, the correction NR-16 and the unit conversion are done inside `lookup`, and the result carries its `unit`, `source` and `note`; the model gets the corrected area 921.4 and the megalitres whatever the description says. The description only *tells* the model about them. (2) **The other text in the request still said what to do:** the parameter descriptions (the exact district names, and "Use 'region' only for water_tariff_2025_tenge_per_m3") and the list of fields in the schema were not changed, and the system message of S3 says to call `lookup` for every fact and `calculate` for every calculation. (3) The model is good at working out what a tool called `lookup` with those parameters does.

**What this does not show:** it is five questions and one run for the vague version, so a difference of 1 or 2 calls is not a result. I changed only the first line, not the parameter descriptions; a tool with a vague name and no parameter descriptions would probably give much more different results, and a weaker model would need the description more. The part that is probably a real effect is the fewer separate calculations and the 122 tokens, and both are small.
### C2 — Three mistakes explained

I took one wrong answer from each strategy. The logs are in `outputs/run1/` and `outputs/run2/`.

#### S1 direct: run 1, Q-20 (wrong)

The question asks which of Ossbridge, Ashgrove and Harrowfield had the largest 2025 budget per resident, and by how many tenge per resident it exceeds the lowest. The expected answer is `Ashgrove | 2993`. The log (`outputs/run1/S1/Q-20.json`) shows the whole reply:

```text
ANSWER: Ossbridge | 0.000
```

It used 2,265 prompt tokens and **12 output tokens**. The model did not write a single calculation: with the reasoning switched off (`reasoning_effort="none"`) and the instruction to answer directly, it had to produce the name and a number in the first token, and it gave a name and a number with no connection to the documents. S1 was wrong on 17 of 20 questions in run 1 and on 15 of 20 in run 2, and every S1 reply was one line of about 12 tokens. The only questions that S1 got right in both runs are Q-06, Q-10 and Q-16: a sum of two populations, a difference of two years and a sum of areas, where the numbers are in the text and one addition or subtraction is enough. The other correct S1 answers (Q-01 and Q-13) were right in one run only, which is consistent with luck. The reason is the principle behind the strategy: a model writes one token at a time, and a number that depends on several divisions can only come out right if the intermediate numbers are written down first; "direct" gives it no place to write them.

#### S2 think and vote: run 1, Q-05 (wrong, in both runs)

Q-05: Stonecairn or Coldharbour, budget per resident, and the difference in tenge per resident. Expected: `Coldharbour | 14235` (`decimals` = 0). The five samples of run 1 (`outputs/run1/S2/Q-05.json`) all gave the right name and five different numbers: 14258.292, 14203.307, 14268.032, 14268.614, 14229.359. The reason is in the written steps. Sample 1 wrote:

```text
2,366,900,000 ÷ 11,407 = 207,452.000
```

but the real value is 207,495.398, so the division is wrong from the fourth digit. Sample 0 wrote `= 207,513.013...` for the same division. The model *wrote out* the right steps, but it does not calculate a long division, it predicts the digits, and it makes a different small error each time.

Why voting did not fix it: with random errors, voting helps when the samples **repeat the same answer**, and here no number appeared twice, so every number got 1 vote out of 5 and my rule (ties go to the first one) took sample 0. Averaging would be better than voting (the mean of the five is 14245.5, closer to 14235 than most samples), but it still would not reach the tolerance of 1 tenge, because the error of a single sample is about ±30 and the mean of 5 still has about ±13. Q-20 fails for the same reason in both runs (five different numbers between 2958.7 and 3016.1 for the true 2993), and Q-12 (63.1 to 64.9 for the true 64.4). What I can measure from the logs is what voting is worth: the **single-sample** accuracy of S2 (all 200 samples, each marked with my rule) is 0.80 in run 1 and 0.81 in run 2, and the voted accuracy is 0.80 and 0.85. So voting gave about **+2 points** (161/200 for one sample against 33/40 for the vote), while writing the steps down (S1 to S2) gave about +60 points. Voting gave a right answer although some samples were wrong on Q-07, Q-08 and Q-17 (run 1) and on Q-08, Q-14, Q-15, Q-17 and Q-18 (run 2), where most samples were right and gave the same number. It also failed in the other direction: on Q-18 in run 1, 4 of 5 samples were right, but they were five different numbers (40011, 40012.3, 40013.279, 40013, 40012), so no number had a majority and my tie rule took the first one, 40011, which is wrong. On Q-12 and Q-20 in run 2 only 1 sample of 5 was right and the vote lost it.

#### S3 tools: run 2, Q-17 (wrong)

Q-17: which district's households paid more for water per resident at the 2025 tariff, Harrowfield or Ossbridge, and by how many tenge per resident. Expected `Harrowfield | 884`. In run 2 S3 answered `Harrowfield | 884457.162` (`outputs/run2/S3/Q-17.json`). The tools worked: the five lookups returned 7146 and 3862 megalitres, the two populations and the tariff 142.35, and `calculate` returned exact numbers. The mistake is in the **formula** the model wrote in round 2:

```text
calculate {"expression": "7146 * 1000000 * 142.35 / 90212", "decimals": 3}
-> {"result": 11276028.687979426, "rounded": 11276028.688}
```

It multiplied the megalitres by 1,000,000 (the factor for litres) instead of 1,000 (the factor for cubic metres), but the tariff is per **cubic metre**. The answer is exactly 1,000 times too big. In run 1 the same question gave `7146 * 1000 * 142.35 / 90212` and the right answer (884.457). The model did not notice that "11,276,028.688 tenge per resident" is an absurd amount for a household water bill: its final text repeats it without comment. The calculator did what it was asked, so the mistake is **not an arithmetic mistake but a planning mistake** (step 1 of my plan). I predicted this in A2 and A4: after the calculator, the remaining risk is a correct answer to a wrong formula written by the model, and this is the only wrong S3 answer in 40.

#### The three questions

**Why does asking 5 times and voting fix some mistakes but not others?** Voting reduces *random* error: if each sample is right with a probability above one half, and the errors are independent, the majority is right more often than one sample (for example, 4 of 5 samples right gives the right vote). It does nothing when the five answers are all different (Q-05, Q-20: no majority exists), when the same wrong answer repeats (a systematic mistake, as in a wrong formula), or when the precision needed is higher than what the model's digit prediction can give. It also costs k times the input: S2 sent 226,100 input tokens against 45,160 for S1. My measurement (+2 points for 5 times the input) says that for this task the vote is a weak tool, and that writing the steps down is the part that works.

**Why does a calculator tool remove mistakes the model cannot avoid on its own?** A language model produces digits by prediction, so the error of a long multiplication or division is not bounded: in S2 the same division gave 207,513 and 207,452 for a true 207,495. `calculate` performs the operation in code, so the error is the precision of a floating-point number (about 1e-12 relative), the same every time and independent of how long the numbers are. That is why S3 got right every question that S2 got wrong: Q-05, Q-12, Q-18 and Q-20 in run 1, and Q-05, Q-12 and Q-20 in run 2. The bound has a limit: the calculator cannot check *what* it is asked to calculate (Q-17), and `lookup` is trusted blindly (my assumption from A1).

**Why did the loop need that many rounds, and why does each round cost more than the one before?** A round is one call to the model, and the steps depend on each other: the facts must come first (round 1, all lookups together), then the calculations that use them (round 2), then the text with the final line (round 3). When the model also splits a calculation in two (the densities first, then their difference, as in Q-09 run 2, or the budget per resident first, then the maximum and the minimum, as in Q-20), there is a fourth round. So 3 or 4 rounds were needed in all 40 questions (8 to 10 questions with 4 rounds in each run). Each round costs more because the API does not remember anything: every call sends the system message, the tool definitions, the question and **all earlier messages**, including every tool result. For Q-20 (the most expensive question, 10 tool calls) the prompt tokens of the four rounds were **836, 1298, 1457 and 1525** in both runs: the difference of each round is the size of the messages added in the round before, and the total is 5,116 prompt tokens, about 1.5 times what four calls of the first size would cost (4 × 836 = 3,344), because the history is paid for again in every call.

### C3 — Which strategy I would use, and what would change it

**I would use S3 (tools).** The numbers of the two runs:

| | S1 direct | S2 think and vote | S3 tools |
|---|---:|---:|---:|
| Correct (run 1 / run 2) | 3 / 5 | 16 / 17 | 20 / 19 |
| Correct, both runs | 8 of 40 (20%) | 33 of 40 (82.5%) | 39 of 40 (97.5%) |
| Input + output tokens (run 1) | 45,160 + 249 | 226,100 + 13,854 | 78,624 + 4,642 |
| Median seconds per question (run 1 / 2) | 1.09 / 1.09 | 10.56 / 9.83 | 5.05 / 5.01 |
| Total seconds (run 1 / 2) | 21.7 / 23.3 | 216.7 / 206.8 | 98.8 / 97.0 |
| Cost (run 1 / 2) | $0.0093 / $0.0093 | $0.0618 / $0.0622 | $0.0213 / $0.0209 |
| Cost per correct answer | $0.0023 | $0.0038 | **$0.0011** |

S3 is the most accurate, 2.9 times cheaper than S2 and 2.2 times faster than S2, and it is the cheapest **per correct answer**. Why not the others:

- **Why not S1:** it is the cheapest and the fastest (1 s), but it is right only when the answer is a number that is already in the text (Q-06, Q-10, Q-16). For anything with a division it produced a number with no calculation (12 output tokens). A cheap answer that is wrong 4 times in 5 is not a saving.
- **Why not S2:** it works (about 82%), but it fails on the three questions that need the most precise arithmetic (Q-05, Q-12, Q-20, in both runs) and voting cannot repair that. It sends the 2,300-token document set 5 times per question, so it costs 6.6 times S1 and 2.9 times S3. About 73% of its cost is repeated input, so it pays 5 times for the same documents. It is also the slowest (10 s per question).
- **S3's price:** about 1.7 times the input tokens of S1 (the tool definitions and the growing history of 3–4 rounds), and 5 s instead of 1 s. Its tools took 0.007 s in total in run 1: the time is the waiting for the model, once per round.

**What would change my choice:**

1. **A small budget and questions with no real arithmetic** (the answer is in the text, or needs one addition): **S1.** It gets Q-06, Q-10 and Q-16 right for $0.0093 per 20 questions, and S3 would cost twice that for no gain.
2. **A strict time limit** of about 2 seconds per answer: only **S1** fits (median 1.09 s; S3 needs about 5 s, S2 about 10 s). I would accept the lower accuracy or I would drop the arithmetic from the questions.
3. **1,000 times more documents** (about 2.3 million tokens): S1 and S2 stop working, because the documents do not fit in the context window (and S2 would pay for them 5 times). **S3** still works if `lookup` uses an index (a database or a search index), because the model only sees the answer to each lookup, about 100 tokens.
4. **A wrong answer is very expensive:** **S3 with a vote on top** (k = 3), because the one S3 mistake I saw (Q-17) was a random planning mistake (the same model got it right in run 1), which a vote can fix, while a vote on S2 cannot fix its precision errors.
5. **The documents change format often, or I cannot trust my parser:** **S2**, because it does not depend on `lookup`. S3 is only as good as the parsing (my most sensitive assumption in Part A); none of the 254 real tool calls returned an error and S3 was right on 39 of 40 questions, but I tested the parser on this one corpus.

### C4 — How sure I can be

**How different were my two runs?** The same code and prompts gave: S1 **3** and **5** correct, S2 **16** and **17**, S3 **20** and **19**. Each strategy changed by 1 or 2 questions: S1 on Q-01 and Q-13, S2 on Q-18, S3 on Q-17. The questions that fail are mostly the same: S2 failed Q-05, Q-12 and Q-20 in both runs, so these are systematic, not noise. Tokens and costs were almost the same (S2 input is identical because the prompt is identical), and the total times differed by 2 to 7%.

**Is the difference between my two best strategies bigger than that?** Only just. S3 minus S2 was +4 questions in run 1 and +2 in run 2, which is of the same size as the run-to-run change inside one strategy (1 to 2 questions). The 95% Wilson confidence intervals over the 40 question-runs are S1 10–35%, S2 68–91%, S3 87–99.6%, so S1 is clearly different from the other two, but S2 and S3 overlap (68–91% and 87–99.6%). At question level S3 won on 4 questions (Q-05, Q-12, Q-20, and Q-18 in run 1) and S2 won on 1 (Q-17 in run 2), and a sign test on those 5 questions gives p = 0.375, which proves nothing. If I count each of the 40 question-runs as independent, 7 against 1 gives p = 0.07, but that is too optimistic, because the same questions are repeated. So I believe S3 is better than S2, mainly because the failures of S2 are on the questions with the most precise arithmetic and my principle explains them, but **20 questions do not prove it**. The comparison with S1 is not in doubt.

**How many questions would I need before I trusted the result?** With a paired design, if S3 really beat S2 by about 15 points (what I saw: S3 right and S2 wrong on 7 of 40 question-runs, the opposite on 1 of 40, a gap of 15 points), I would need about **67 questions** to see it with 80% power at the 5% level, and about **115 questions** if the real gap were 10 points. That is 3 to 6 times the 20 questions I had, and I would also want 5 or more runs of each strategy, because the model is not deterministic.

**What this comparison cannot settle:**

- It is one model (`gpt-5.6-luna`), one made-up region, one set of prompts and 20 questions that were built with traps. A different model, or the same model with its reasoning switched on, could do much better in S1 and S2. I switched reasoning off in all strategies (`reasoning_effort="none"`), because the API requires it for function tools in Chat Completions, and this probably lowers S1 and S2 more than S3. A fair statement is "S3 beats S1 and S2 when the model cannot reason", not "tools beat reasoning".
- Only 2 runs, so I cannot estimate the variance well.
- S2's voting rule (the most common name and number to 3 decimals) is strict; a vote on the name and the median of the numbers would probably score higher. I did not change the rule after seeing results.
- The cost uses the HW1 prices; the real price list may be different, but this changes all strategies in the same way.
- My own parser, `lookup`, is part of S3. Its result, 39 of 40, includes the work I did on the traps of this corpus (archived profiles, correction, units); S1 and S2 have to meet the same traps alone.

### Final questions

1. **When the model sends a `tool_calls` message, what has actually run so far?** Nothing. The message is only text: a request that says a tool name and an `arguments` string. The model cannot run my code. My loop reads the request, decides if it is valid, runs the tool (or refuses) and sends the result back. In the real runs the model made 254 requests (126 in run 1, 128 in run 2) and each one was run by `run_tool` in my loop.
2. **Why does `arguments` arrive as a string, and what goes wrong if you pass it straight into your function?** Because the model writes text; the API gives the JSON that the model wrote as a string, and it does not guarantee that the string is valid JSON or that it has the right keys and types. If I passed the string into `lookup(arguments)` it would be one wrong argument; if I called `lookup(**arguments)` on a string or a bad object it would raise an exception and stop the loop, and the model would never get a result for that `tool_call_id`, which makes the next API request fail. `run_tool` parses the string, checks that it is an object with the right keys, and returns an error message that the model can read. In my real runs all 254 argument strings were valid JSON, so this protection never had to work; it is tested with a fake model (`tests/test_loop.py`).
3. **How many tokens do your two tool definitions add to every S3 request? Measure it.** **607 tokens.** I measured it with `measure_tools.py` (`outputs/tool_tokens.json`): the same two messages (the S3 system message and Q-09) were sent twice, once without tools (216 prompt tokens, from `usage.prompt_tokens`) and once with the two definitions (823), and the difference is 607. As a second opinion, tiktoken `o200k_base` counts 621 tokens for the two definitions written as JSON, 2% more, which is close because the API writes the definitions in its own compact format. The cost is paid again in **every round**: S3 made 70 model calls in run 1 and 68 in run 2, so the definitions were part of about 70 × 607 = 42,490 input tokens in run 1, which is **54% of the 78,624 input tokens of S3** (and about $0.0085 of its $0.0213). Only about 127 of the 607 tokens are the text of the `lookup` description (see C1); the rest is the names, the parameter descriptions, the list of fields and the `calculate` definition. So a short, precise definition is not only a matter of clarity, but also of cost.
4. **How much more did S2 cost than S1?** In run 1 S2 cost **$0.0618** against **$0.0093** for S1, which is **6.6 times**; in run 2 $0.0622 against $0.0093, 6.7 times. The input tokens are exactly 5 times (226,100 against 45,160), because S2 sends the same prompt (with the 17 documents, about 2,250 tokens) in 5 separate calls. The output is 56 times bigger (13,854 against 249 tokens), because S2 writes the calculations and S1 writes one line. Output is also six times more expensive per token, so about 73% of S2's cost is input ($0.0452) and 27% is output ($0.0166).
5. **Which question needed the most rounds in S3, and why?** Many questions needed the maximum of 4 rounds (10 in run 1, 8 in run 2). The one with the most work was **Q-20** (4 rounds in both runs, 10 tool calls, 5,116 prompt tokens in run 1): the model needs six facts (budget and population of three districts) in round 1, then three budgets per resident in round 2, then the largest minus the smallest in round 3, and the answer in round 4. Each step needs the results of the one before, so they cannot be sent together. Q-11 also had 10 tool calls and 4 rounds.
6. **What would you change in `lookup` if there were 100,000 documents?** My `lookup` reads and parses the whole corpus at the start with regular expressions written for three sentence templates, which does not work for 100,000 documents written in many styles. I would parse the documents once, offline, into a table (a database) with the columns district, field, value, unit, source document and edition, with the archived flag and the corrections as data, and `lookup` would be a query on an index. For facts that are not in a fixed table, I would add a search step (BM25 or embeddings, like HW3) that returns a few short passages. I would also limit the size of what is returned, cache common lookups, and test the parser on a sample of documents, because with this many documents I cannot check them by hand, and a parsing mistake is the one thing the model cannot notice.
7. **What stops your `calculate` from running dangerous code? Could the model still make it misbehave?** The expression is never run as Python. `ast.parse` reads it into a tree, and my code walks the tree and accepts only numbers, `+ - * /`, brackets and a unary minus; everything else (function calls, attributes, names, `**`) is refused before anything is calculated. There are limits on length (200 characters), size (1e15) and number of nodes (100). Three tests check `__import__('os').system('echo hi')`, `(1).__class__` and `9**9**9`, and the first test makes sure `os.system` is never called. The model can still make it misbehave in a different way: it can ask for a **wrong but allowed calculation**, and `calculate` returns the exact number for it. That is what happened in Q-17 (run 2), the only wrong S3 answer.
8. **For which kind of question did tools help most, and for which did they not help at all?** They helped most on questions with long or several divisions and tight precision: Q-05, Q-12, Q-18 and Q-20, where S3 was right and S2 was wrong in at least one run (Q-05, Q-12 and Q-20 in both runs), and S1 was wrong almost always. They did not help at all on the three questions that every strategy got right in both runs: **Q-06, Q-10 and Q-16** (a sum of two numbers, a difference of two years, a sum of two areas), where S1 was enough. They also did not protect against a wrong formula (Q-17 in run 2).
