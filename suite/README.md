# suite/

Versioned evaluation tasks (backend-spec §2, §4). `v1/` is the demo suite (D-12): 6 categories × 3 tiers × 1 task = 18 tasks.

| Prefix | Category | Simple | Mid | Complex |
|---|---|---|---|---|
| CG | Code Generation | CG-S-01 | CG-M-01 | CG-C-01 |
| RA | Reasoning & Analysis | RA-S-01 | RA-M-01 | RA-C-01 |
| SO | Instruction Following & Structured Output | SO-S-01 | SO-M-01 | SO-C-01 |
| TD | Test Design (QA) | TD-S-01 | TD-M-01 | TD-C-01 |
| LC | Long-Context Faithfulness | LC-S-01 | LC-M-01 | LC-C-01 |
| TU | Tool Use | TU-S-01 | TU-M-01 | TU-C-01 |

## Task file fields
- `prompt`: exactly what the model receives.
- `checkers`: deterministic checks first, then `llm_judge` where judgement is needed. Each has an `on_fail` defect type and severity (backend-spec §7).
  - `unit_tests`: pytest code run against the model's code (saved as `solution.py`) in the Docker sandbox.
  - `json_schema`: the response's JSON must validate against `schema`. This schema can be stricter than the prompt (e.g. `const`), and is never shown to the model.
  - `exact_match`: compares an extracted value with `expected`, case-insensitive with whitespace collapsed. `extract` is `answer_line: "ANSWER:"` (the last such line) or `json_pointer` (`*` collects an array's items, joined by commas; `sort: true` sorts them). `numeric: true` compares numbers.
  - `regex`: the response must match `pattern`.
  - `llm_judge`: a judge from another provider scores 1–5 using `rubric`.
- `reference_response`: a correct answer, **never sent to models**. `tests/test_suite_v1.py` proves every reference passes its task's deterministic checks.
- The content hash covers prompt + checkers + rubric (backend-spec §2). Any edit changes the hash, so results stay tied to the exact version.

No confidential or personal data (goal-spec §8). Names, emails and orders are fictional.
