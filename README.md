# HW4 — Three routes to a hard answer: decompose, choose, justify

*Build tools for an LLM, then test if they were worth it.*

**Course:** CSS-4007 · Artificial Intelligence · Narxoz University
**Week:** 5 — *Reasoning and Tools*
**Due:** Tuesday 20 October 2026, 09:00 (UTC+5)

## What this homework is about

In week 5 you learned that a model never runs a function itself. It only *asks*
for one, in a format you describe, and your code decides what actually runs.

In this homework you build that yourself:

- two **tools**: `lookup`, which finds facts in some documents, and `calculate`,
  which does arithmetic;
- the **loop** that passes the model's requests to your tools and sends the
  results back.

Then you check whether the tools were worth building. You give the same twenty
questions to the same model in three different ways and compare the results:

| Strategy | How it works |
|---|---|
| **S1 — direct** | Put all the documents and the question in the prompt. One call. |
| **S2 — think and vote** | Same prompt, but ask the model to reason step by step. Ask 5 times and take the most common answer. |
| **S3 — tools** | No documents in the prompt. The model only gets your two tools and must use them. |

The homework has three parts:

| Part | What you do |
|---|---|
| **A — Easy** | Plan on paper. No code. |
| **B — Medium** | Build the tools and the loop, and run all three strategies. |
| **C — Hard** | Explain your results and choose the best strategy. |

## 0. How to work

1. **Fork** this repository (the **Fork** button, top right). Keep your fork
   **public**.
2. Clone *your fork* and work there. Do not open pull requests to this one.
3. Write your answers in **`SUBMISSION.md`**. It already has a heading and an
   empty table for everything you need to fill in.
4. **Finish Part A and commit it before you write any code.** Your git history
   shows the order, so the commit with Part A must come before your first `.py`
   file.
5. Save the output of every run in an `outputs/` folder and commit it. Every
   number in `SUBMISSION.md` must come from your own code and your own runs.
6. Push to your fork and submit the link on the LMS before the deadline.

This repository gives you data and an empty `SUBMISSION.md`. **There is no
code.** You write all of it. One way to organise it:

```text
tools.py        your two tools
strategies.py   the three strategies (S1, S2, S3)
run.py          runs the twenty questions and saves results to outputs/
tests/          tests for your tools
outputs/        your saved results and logs
```

## 1. Setup

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # then put your OpenAI key in .env
```

You need one OpenAI API key (`OPENAI_API_KEY`). Use the model **`gpt-5.6-luna`**
for everything.

**Never commit your key.** `.env` is already in `.gitignore`. Your fork is
public, and bots find leaked keys on GitHub within minutes. Do not print the
key in any output you save either. If you do leak a key, cancel it at once and
say so in `SUBMISSION.md`.

**Cost.** The documents are small (about 2,300 tokens), but S2 sends them 5
times per question. Test your code on 2 or 3 questions first, and run all
twenty only when it works. Write down what the full run cost you.

## 2. The data

| File | What is in it |
|---|---|
| `data/corpus.jsonl` | 17 short documents, one per line, each with an `id`, `title` and `text` |
| `data/questions.json` | the 20 questions, each with the correct `answer`, `value`, `unit` and number of `decimals`, and the `sources` (document ids) that contain the facts |

The documents describe the **Nine Rivers Region**, a place made up for this
homework. No model has seen it before, so any correct fact in an answer must
come from the documents.

- **NR-01 to NR-12**: one profile for each of the twelve districts.
- **NR-00**: explains how to read the profiles.
- **NR-15**: the price of water.
- **NR-13, NR-14, NR-16**: read these carefully.

**Read all 17 documents before you start.** They are short, and they contain
some deliberate traps:

- two districts have very similar names;
- two profiles are **old (archived)** and must not be used;
- one profile has a typo that a later notice corrects;
- one district gives its water use in a different unit from the others.

Each question has one correct answer: a name (or `yes` / `no`) plus a number.
The correct answers are in the file so that you can check the model's
answers. **Never put a correct answer into a prompt.**

## 3. Part A — Plan on paper (Easy)

No code and no model in this part. Write it in `SUBMISSION.md` and commit it
**before** any code.

### A1 — Split the task into steps

How do you get from a question like *"Which district is denser, Brightwater or
Millbrook, and by how much?"* to an answer? Break the task into small, named
steps. For each step, write:

- **what goes in and what comes out** (with types, for example `str` and
  `float`), clearly enough that a classmate could code it without asking you;
- **what happens when it goes wrong**: nothing found, two things found, a
  number that cannot be read, an unknown unit;
- **what you are assuming**: which year's numbers, what to do with old
  profiles and corrections, when to round;
- **who does the step**: a tool, your loop, or the model.

Then show **how the steps connect**: which step's output goes into which. A list
or a simple diagram is enough.

### A2 — Describe your two tools

Some of your steps become the two tools. For each tool, write its definition
exactly as you will send it to the model: its `name`, its `description`, and
its `parameters` (a JSON schema listing the inputs and which are required).

Then fill in a small table for each tool:

- what it returns when it works;
- what it returns for each kind of error;
- the worst thing it could do if the model sent it strange or dangerous input.

**You decide how `lookup` works.** For example, it could take a district name
and a field (like `population`) and return one number. Or it could take a search
phrase and return matching sentences. Whatever you choose:

- its result must say which document the fact came from;
- it must handle the old (archived) profiles and the correction notice.

Write each tool's `description` for the model: the model reads it to decide
when and how to use the tool.

### A3 — Walk through one question by hand

Take question **Q-09**. Using your tool definitions, write out the whole
conversation that should happen between the model and your tools, as JSON:

1. the question (the user message);
2. each tool request the model makes (with its `id`, tool name and inputs);
3. each result your tool sends back (with the `id` it answers);
4. the final answer.

Then do the arithmetic yourself and show that the answer is right. Read NR-05
and NR-16 first.

### A4 — Why did you split it this way?

Describe one *other* way you could have split the task. For example: one big
"answer the question" tool, no lookup tool at all, or a separate tool for each
calculation. Explain why you did not choose it.

## 4. Part B — Build it and run it (Medium)

Now write the code you planned in Part A. If you change your plan while
coding, say what you changed and why in `SUBMISSION.md`. Do not edit Part A
itself.

### B1 — Build the two tools

**`lookup`**
- Reads `data/corpus.jsonl` and works the way you described in A2.
- Returns a limited amount of text, not whole documents.
- **Never crashes.** If something goes wrong, it returns an error message the
  model can understand, for example:
  `{"error": "no district named Ossbrige; did you mean Ossbridge or Ossford?"}`

**`calculate`**
- Works out an arithmetic expression like `44675 / 921.4`.
- **Must not use `eval` or `exec`.** These run *any* Python code the model
  writes, which is dangerous. Use Python's `ast` module to read the expression
  and allow only numbers and the operators you choose.
- Decides what to do with division by zero and with very large numbers.

### B2 — Test the tools (without the model)

Write at least **five tests for each tool** in `tests/`, and run them with
`pytest`. The tests must not need an API key. Include at least these:

- `lookup` finds a correct 2025 number;
- `lookup` handles a misspelled name, the two similar district names, and an
  archived profile;
- `calculate` gets `48317 * 1.0947` right;
- `calculate` **refuses** each of these without running them, freezing or
  crashing:
  - `__import__('os').system('echo hi')`
  - `(1).__class__`
  - `9**9**9`

Paste the `pytest` output into `SUBMISSION.md`.

### B3 — Build the loop

Send your tool definitions to `gpt-5.6-luna` (Chat Completions API, with
`tools=[...]`, as in the week 5 slides). Your loop must:

- read each tool request's `arguments` (it arrives as a **string** of JSON) and
  check it is valid before running anything;
- add the model's message with its `tool_calls` to the conversation unchanged,
  and send back a result for **every** `tool_call_id`;
- stop after a fixed number of rounds (choose the number and explain it), and
  mark the question as unanswered if it hits that limit;
- save a log for every question in `outputs/`: each tool call, its inputs, its
  result and how long it took.

Run Q-09 and compare the real conversation with the one you wrote by hand in
A3. What is different?

### B4 — Run the three strategies

Run **S1, S2 and S3** on all twenty questions. Keep everything the same except
the strategy: same model, same questions, same answer format. Write down every
setting you kept fixed.

- **S1 and S2** get all the documents in the prompt. **S3** does not; it only
  gets your tools.
- In **S2**, ask **5 times** (k = 5) and take the most common answer. The 5
  answers need to vary, so set `temperature` if the model allows it. If it
  does not, say so.
- Make every strategy end its reply with the same line, so one piece of code
  can check all the answers:
  `ANSWER: <name or yes/no> | <number>`
- **Before your first full run**, write down how you will decide whether an
  answer is correct. A simple rule: the name must match exactly, and the number
  must match `value` rounded to `decimals` (allow a difference of 1 in the last
  digit).

Do the full run **twice**. For each run and strategy, fill in:

| Run | Strategy | Correct /20 | Unanswered | Input tokens | Output tokens | Median seconds per question | Total seconds | Cost ($) |
|---|---|---:|---:|---:|---:|---:|---:|---:|

Count tokens from the `usage` field of **every** call: all 5 samples in S2 and
every round of the loop in S3. Then fill in the table of all 20 questions,
marking ✓ or ✗ for each strategy.

## 5. Part C — Explain and choose (Hard)

Write this part in your own words, using your own numbers and logs.

### C1 — Does the tool description matter?

Pick five questions. Run S3 on them again, but change your `lookup` description
to one vague line, like `"Looks things up."`. Keep everything else the same.
What changed: the number of calls, the inputs, the answers? Why?

### C2 — Explain three mistakes

Pick one wrong answer from each strategy. If a strategy got everything right,
pick its most expensive question instead. For each one, show what the model did
(quote your log) and explain **why** it happened. Questions to think about:

- Why does asking 5 times and voting fix some mistakes but not others?
- Why does a calculator tool remove mistakes the model cannot avoid on its own?
- Why did the loop need that many rounds, and why does each round cost more
  tokens than the one before?

### C3 — Which strategy would you use?

Choose the strategy you would actually use for this problem. Compare accuracy,
tokens and time, and explain why you did **not** choose each of the other two.

Then name at least two situations that would change your choice, for example a
small budget, a strict time limit, 1,000 times more documents, or questions with
no arithmetic. Say which strategy you would pick in each.

### C4 — How sure can you be?

- How different were your two runs?
- Is the difference between your two best strategies bigger than that?
- How many questions would you need before you trusted the result?

### Final questions

Answer each in 2–4 sentences, using your own results where you can.

1. When the model sends a `tool_calls` message, what has actually run so far?
2. Why does `arguments` arrive as a string, and what goes wrong if you pass it
   straight into your function?
3. How many tokens do your two tool definitions add to every S3 request?
   Measure it.
4. How much more did S2 cost than S1? Give the number from your table and
   explain it.
5. Which question needed the most rounds in S3, and why?
6. What would you change in `lookup` if there were 100,000 documents?
7. What stops your `calculate` from running dangerous code? Could the model
   still make it misbehave?
8. For which kind of question did tools help most, and for which did they not
   help at all?

## 6. Checklist

- [ ] Part A committed before the first `.py` file (check with `git log --stat --reverse`)
- [ ] Part A: steps, how they connect, both tool definitions with their tables, Q-09 by hand, one alternative split
- [ ] `calculate` uses `ast`, not `eval`, and refuses the three dangerous inputs
- [ ] At least five tests per tool, and the `pytest` output pasted
- [ ] The loop answers every `tool_call_id`, has a round limit, and saves a log per question
- [ ] S1, S2 and S3 run on all twenty questions, twice, with both tables filled in
- [ ] Your rule for a correct answer written before the first full run
- [ ] Part C: the vague-description test, three mistakes explained, your choice, how sure you are
- [ ] Final questions answered
- [ ] `outputs/` committed, and `.env` **not** committed (`git log --all -- .env` shows nothing)
- [ ] Your fork is public, and its link is on the LMS

## 7. Honesty

You may discuss ideas with classmates, but your code and your written answers
must be your own. **At the top of `SUBMISSION.md`, say which AI tools you used
and for what.** Using them is fine; hiding it is not.

An AI can write a calculator for you in seconds. It cannot know which of *your*
questions failed, or why *your* loop called `lookup` nine times on Q-09. Your
answers in Part C must quote your own logs, question ids and numbers.
