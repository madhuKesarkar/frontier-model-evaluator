# specs/

The four specifications are the source of truth for this project (course reader, Ch. 5). The goal spec guides the other three, and the API contract connects frontend and backend. A decision that changes one document may need edits in several.

| Document | Question it answers |
|---|---|
| [`goal-spec.md`](goal-spec.md) | Who is this for, what should they accomplish, what is in scope, and how will we recognise success? |
| [`frontend-spec.md`](frontend-spec.md) | What screens, actions and visible states support those journeys? |
| [`backend-spec.md`](backend-spec.md) | What data, rules, evaluation method and operating constraints support them? |
| [`api-contract-spec.md`](api-contract-spec.md) | What exact messages connect the two halves, including failures? |

The implementation plan, with its "done when" checks, lives in [`../claude-plan.md`](../claude-plan.md).

**Review prompt** (adapted from Example 5.5): *Read all four specs without implementing anything. Trace running an evaluation, opening a model, checking fit, reviewing a disagreement, and exporting, across all four. List contradictions, missing user-visible states, assumptions and unresolved decisions. Explain each in plain language and name every document affected. Ask me to resolve product choices before updating the specs.*
