# Frontend Spec — Frontier Model Evaluator

> Defines the screens, actions and visible states that support the journeys in goal-spec.md.
> Status: **DRAFT v0.3** — awaiting review. Message shapes are defined in api-contract-spec.md.

## 1. Technology (proposed — review before accepting)
<!-- Framework and libraries, with the reason for each and the simpler alternative considered. -->
| Choice | Why | Alternative considered |
|---|---|---|
| React + TypeScript, built with Vite | Same stack as the course's Musafir build. A plain single-page app is enough for a local, single-user tool. | Next.js: adds server rendering we don't need |
| Tailwind CSS | Fast, consistent styling with design tokens | Plain CSS |
| TanStack Query | Handles loading, error and refetch states for API calls | Hand-written fetch state |
| Recharts | Bar charts for scores and tokens | Chart.js |

The frontend talks only to the local backend at `http://localhost:8000/api/v1`. It never holds any provider key.

## 2. Visual Design
<!-- Fonts, colours, layout preferences. -->
- `[NEEDS CLARIFICATION]` (OQ-4) Font and palette. Placeholder: a system sans-serif font, neutral background and one accent colour.
- Scores use one consistent colour scale from 1 (red) to 5 (green), always shown with the number. Colour never carries meaning on its own.
- Defect severity badges: S1 Critical, S2 Major, S3 Minor, S4 Cosmetic, always with text.
- Layout: desktop-first. Minimum supported width `[NEEDS CLARIFICATION]` (proposed 1024 px; a phone layout is out of scope).

## 3. Navigation
A top navigation bar shows: **Leaderboard** (home) · **Compare** · **Fit for my app** · **Runs** · **Review queue** (with a count badge) · **History**.

A persistent **fairness note** appears on the Leaderboard, Model detail and Compare screens: *"Models are compared as reached through each access mode (Claude via Claude Code on Pro, GPT via Codex on Go, Gemini Flash on the free tier), not as flagship paid APIs. Token counts use different tokenizers; compare API-equivalent cost instead."*

## 4. Screens

Every screen defines three states: **loading** (a skeleton or spinner, with controls disabled), **empty** (an explanation plus the next action), and **error** (a plain-language message, a Retry button, and any entered values kept).

### S1 Leaderboard (home)
- A table with one row per evaluated model. Columns: model name and access mode, overall score, one 1–5 score per category, average API-equivalent cost per task, p50 latency, and open S1+S2 defect count.
- Filters: tier (All / Simple / Mid / Complex), category, run (default: the latest completed run).
- Every column is sortable. Clicking a row opens **S2** for that model.
- A **"Check fit for my app"** button opens **S4**.
- **Export** button (CSV or JSON) for the current view.
- Empty: "No completed runs yet." plus a **Start a run** button that opens S5.

### S2 Model detail
- **Header:** display name, provider, access mode, model ID, last run date, overall score.
- **Category scores:** a 1–5 bar per category, with Simple / Mid / Complex sub-scores shown as both a chart and a table.
- **Token panel:** per tier, the average and total for input, output and overhead tokens, plus API-equivalent cost. Values that were estimated or not reported show an **"estimated"** or **"n/a"** badge, never 0. The three most expensive tasks are highlighted.
- **Defects:** a list filterable by type, severity, category, tier and status. Expanding a defect shows the prompt, a response excerpt, expected vs actual, severity, source and status.
- **Task drill-down:** a table of results. Opening a result shows the full prompt, full response, each checker's outcome, each judge's score and rationale, tokens, cost and latency.
- **Export** of the defects list.
- Empty (the model exists but hasn't been run): "This model hasn't been evaluated yet." plus **Start a run**.

### S3 Compare
- Select 2–4 models (selecting a 5th is disabled, with a hint).
- Side-by-side category scores, API-equivalent cost per tier, and defect counts by type.
- Empty (fewer than 2 selected): "Select at least two models."

### S4 Fit for my app
- Choose a **template** (Test-case generation tool, Customer support chatbot, Code assistant) or **Custom**.
- Profile form: weight 0–5 per category, must-have categories, tier mix as three percentages that must total 100, optional maximum API-equivalent cost per task, optional maximum p95 latency. **Save profile** as a named, reusable profile.
- Validation is shown next to the field: a tier mix that doesn't total 100, a negative limit, or all weights set to 0.
- **Results:** one card per model showing the verdict (Recommended / Conditional / Not recommended), the fit score, top strengths, top risks, and the defects or limits that caused the verdict, each linking to S2.

### S5 Runs
- **New run form:** models (only enabled models are selectable), categories, tiers, repeats (1–3), and call cap (default 50). A **preflight** panel shows whether each access mode is ready (for example "Codex CLI: not signed in"). Models whose access mode isn't ready are disabled, with the reason shown.
- **Progress view:** each model shows done / total, status (`pending`, `running`, `paused_quota`, `done`, `error`), calls used against the cap, and the API-equivalent cost so far. Buttons: **Resume** (for paused runs) and **Cancel**.
- **Manual queue:** for `manual` access mode tasks, show the prompt with a **Copy** button, a textarea for the reply, and **Submit**. A submitted task leaves the queue and is scored.
- Only one run may be active at a time. Starting a second shows the backend's message and a link to the active run.

### S6 Review queue
- Lists results flagged `needs_review` (judges disagree by more than 1, or a single-judge result) and defects with status `open`.
- For a result: set the final score from 1 to 5, with an optional note.
- For a defect: Confirm, mark False positive, or change severity.
- Empty: "Nothing to review."

### S7 History
- A table of past runs: date, models, suite version, status, calls used, API-equivalent cost.
- Select two runs to see per-category score changes per model, with each run's suite version.

## 5. Flows
- **Main journey:** Leaderboard → click a model → S2 → expand a defect → read its evidence.
- **Fit journey (≤ 3 clicks, SM-5):** Leaderboard → *Check fit for my app* (1) → choose a template (2) → verdicts for all models are visible.
- **Run journey:** Runs → New run → preflight shows ready modes → Start → progress → (quota pause → Resume) → done → Leaderboard updates.
- **Review journey:** Review queue → open an item → decide → the item leaves the queue → scores and verdicts recalculate.

## 6. Acceptance Criteria
Format: Given / When / Then. Each criterion has at least one test (see claude-plan.md §4).
- **FE-AC-01** Given a completed run with three models, when the user opens the Leaderboard, then each model shows a 1–5 score for each of the six categories.
- **FE-AC-02** Given the Leaderboard, when the user clicks a model row, then S2 opens for that model within 2 seconds on the seeded local database.
- **FE-AC-03** Given S2's defects list, when the user filters by severity S1 and tier Complex, then only matching defects are shown and the count updates.
- **FE-AC-04** Given a token value marked estimated or not reported, when shown in S2, then it displays an "estimated" or "n/a" badge and never 0.
- **FE-AC-05** Given S2 for a CLI access-mode model, when the token panel loads, then task tokens and overhead tokens are shown separately for each tier, and the access mode is visible in the header.
- **FE-AC-06** Given three selected models, when the user opens Compare, then category scores, API-equivalent cost per tier and defect counts by type are shown side by side.
- **FE-AC-07** Given the home screen, when the user clicks *Check fit for my app* and chooses a template, then a verdict with reasons is visible for every evaluated model (3 clicks or fewer).
- **FE-AC-08** Given a tier mix that does not total 100, when the user submits the profile form, then an inline error appears and no request is sent.
- **FE-AC-09** Given a model whose access mode fails preflight, when the user opens New run, then that model cannot be selected and the reason is shown.
- **FE-AC-10** Given a running run whose model hits its quota, when the progress view refreshes, then that model shows `paused_quota` and a Resume button.
- **FE-AC-11** Given a manual-mode task, when the user pastes a reply and submits, then the task leaves the manual queue and its result appears in S2 after scoring.
- **FE-AC-12** Given a result in the review queue, when the user sets a final score, then the item leaves the queue and the Leaderboard reflects the new score after refresh.
- **FE-AC-13** Given any screen, when its API request fails, then the error state shows a plain-language message and a Retry button, and any form values are kept.
- **FE-AC-14** Given each main screen, when checked with axe-core, then there are no serious or critical WCAG 2.1 AA violations, and every action can be reached by keyboard.
- **FE-AC-15** Given the Leaderboard view, when exported to CSV, then the rows and values match what the table shows.
- **FE-AC-16** Given any defect in S2, when expanded, then it shows the prompt excerpt, response excerpt, expected vs actual, severity, source and status, and links to the full result (SM-6).

## 7. Open Questions
- OQ-4 Visual preferences and sketches (see §2).
- FE-OQ-1 Minimum supported width: is 1024 px acceptable?
