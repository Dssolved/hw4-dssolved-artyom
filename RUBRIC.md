# HW4 - Three routes to a hard answer — rubric

This is the rubric the marker uses, copied from the course record. Every level
description is here, so you can aim at it.

Two Performance Indicators are assessed by this task and each has its own rubric. PI 1.1 is evaluated on the formal decomposition, which carries 25% of the task across three dimensions; PI 1.3 is evaluated on the strategy comparison and its justification, which carries 75% across five. Dimension weights differ within each indicator according to how much of it that dimension carries, and sum to 100%. Everything is marked by hand from SUBMISSION.md, read against the student's code: a number in a table with no code that produces it earns nothing.

Bands: Unsatisfactory 0–49% · Developing 50–69% · Satisfactory 70–89% · Exemplary 90–100%
of a dimension's points.

## PI 1.1 — design on paper (Part A): 1 pt

### Subproblem Identification and Boundaries — 0.4 pts · marked in Part A

Breaks the multi-hop task into named subproblems whose boundaries do not overlap, so that each can be reasoned about on its own.

| Level | Points from | Description |
|---|---:|---|
| Unsatisfactory | 0 | Treats the task as one undifferentiated problem, or the stated subproblems merely restate the brief. |
| Developing | 0.2 | Names subproblems, but they overlap or are cut so coarsely that the split does nothing for the solution. |
| Satisfactory | 0.28 | Identifies well-defined, non-overlapping subproblems that together cover the whole task. |
| Exemplary | 0.36 | Identifies a clean, minimal set of subproblems and shows that it is both complete and mutually exclusive. |

### Specification of Inputs, Outputs and Data Flow — 0.35 pts · marked in Part A

States for each subproblem what it receives and what it returns, and how the pieces connect, in enough detail that another student could implement one of them alone.

| Level | Points from | Description |
|---|---:|---|
| Unsatisfactory | 0 | Inputs and outputs are not specified; the data flow between subproblems is absent. |
| Developing | 0.175 | Inputs and outputs are described loosely, leaving the interface between subproblems ambiguous. |
| Satisfactory | 0.245 | Each subproblem has stated inputs, outputs and types, and the flow between them is given explicitly. |
| Exemplary | 0.315 | Interfaces are specified precisely enough to be implemented independently, with the failure behaviour of each named. |

### Constraints, Assumptions and Justification of the Split — 0.25 pts · marked in Part A

Makes explicit what must hold for the decomposition to be valid, and argues why the task was cut this way rather than another - before any measurement exists to settle it.

| Level | Points from | Description |
|---|---:|---|
| Unsatisfactory | 0 | No constraints or assumptions are recorded, and no reason is offered for the chosen decomposition. |
| Developing | 0.125 | Lists generic assumptions, and asserts the decomposition is reasonable without comparing it to any alternative. |
| Satisfactory | 0.175 | Records the constraints and assumptions bearing on each subproblem, and justifies the split on stated grounds. |
| Exemplary | 0.225 | Identifies the assumption the solution is most sensitive to, and defends the split against a specific alternative that was rejected. |

## PI 1.3 — the tools, the three strategies and the choice between them (Parts B and C): 3 pts

### Correct Application of the Candidate Strategies — 0.75 pts · marked in Part B

All three strategies - a single direct call, chain-of-thought with self-consistency over k samples, and a tool-calling loop with a lookup tool and a calculator - implemented and run against the same twenty questions with the same model.

| Level | Points from | Description |
|---|---:|---|
| Unsatisfactory | 0 | Fewer than three strategies run, or the implementations do not do what they are named as doing. |
| Developing | 0.375 | Three strategies run, but they differ in model, question set or prompt, so the comparison is not like for like. |
| Satisfactory | 0.525 | All three strategies correctly implemented and run against an identical question set and model. |
| Exemplary | 0.675 | All three correctly implemented, held identical in every respect but the strategy itself, with the controls stated. |

### Grounding in Computational Principles — 0.75 pts · marked in Part C

Explains the behaviour of each strategy from the principle that produces it - why sampling k times reduces variance and what it costs, why delegating arithmetic to a calculator bounds an error the model cannot bound itself.

| Level | Points from | Description |
|---|---:|---|
| Unsatisfactory | 0 | No reference to any underlying principle; the strategies are treated as interchangeable black boxes. |
| Developing | 0.375 | Names the relevant principles but describes them loosely and does not connect them to the observed behaviour. |
| Satisfactory | 0.525 | Explains each strategy's behaviour from the computational principle underneath it, and links the principle to what the run showed. |
| Exemplary | 0.675 | Explains the principles precisely, including where each stops applying, and predicts behaviour the run then confirms. |

### Empirical Evidence for the Choice — 0.6 pts · marked in Part B

Accuracy, token cost and wall-clock latency measured for all three strategies under stated, identical conditions, with the accuracy scoring rule given and k declared.

| Level | Points from | Description |
|---|---:|---|
| Unsatisfactory | 0 | Measurements are missing, or cannot be reproduced from the code submitted. |
| Developing | 0.3 | Some measurements reported, but the scoring rule or the run conditions are unstated, so the comparison cannot be checked. |
| Satisfactory | 0.42 | All three measures reported under stated identical conditions, reproducible from the code, with the accuracy rule and k given. |
| Exemplary | 0.54 | As satisfactory, and the measurement design itself is justified - why twenty questions, why this accuracy rule. |

### Defence of the Selected Solution — 0.6 pts · marked in Part C

Names which strategy is appropriate for this problem and defends it against the alternatives, stating the conditions under which the answer would change.

| Level | Points from | Description |
|---|---:|---|
| Unsatisfactory | 0 | No selection is defended, or the selection contradicts the evidence presented. |
| Developing | 0.3 | A strategy is selected and defended by pointing at the winning number, without argument from principle or cost. |
| Satisfactory | 0.42 | Selects an appropriate strategy and defends it from the measurements and the principles together, weighing accuracy against cost. |
| Exemplary | 0.54 | Defends the selection against the specific alternatives it beat and states the conditions - budget, latency, question type - that would reverse it. |

### Limits and Sensitivity of the Conclusion — 0.3 pts · marked in Part C

States what this comparison cannot settle, and tempers the claim to match what twenty questions on one run can actually support.

| Level | Points from | Description |
|---|---:|---|
| Unsatisfactory | 0 | The conclusion is stated as though the measurement settled the question completely. |
| Developing | 0.15 | Limitations appear in a closing sentence but do not weaken the claim that was made from the numbers. |
| Satisfactory | 0.21 | Names what the comparison cannot settle - run-to-run variance, the size of the question set - and tempers the claim accordingly. |
| Exemplary | 0.27 | Quantifies the uncertainty, or reruns to estimate it, and says at what question-set size the ranking would become reliable. |
