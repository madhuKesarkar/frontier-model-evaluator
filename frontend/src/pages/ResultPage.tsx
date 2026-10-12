import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { api, ApiError } from "../api/client";
import { ScoreChip, SeverityBadge, TokenValue } from "../components/Badges";
import { Empty, ErrorState, Loading } from "../components/States";
import { CATEGORY_LABEL, TIER_LABEL, fmtCost, fmtMs, fmtTokens } from "../format";

/** S2 task drill-down: full prompt, response, checks, judges, tokens, cost and latency. */
export function ResultPage() {
  const id = Number(useParams().id);
  const query = useQuery({
    queryKey: ["result", id],
    queryFn: ({ signal }) => api.result(id, signal),
    enabled: Number.isInteger(id),
  });

  if (!Number.isInteger(id)) return <Empty>That result doesn&apos;t exist.</Empty>;
  if (query.isPending) return <Loading what="the result" />;
  if (query.isError) {
    if (query.error instanceof ApiError && query.error.status === 404)
      return <Empty>That result doesn&apos;t exist.</Empty>;
    return <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />;
  }
  const r = query.data;
  const u = r.usage;

  return (
    <article className="space-y-6">
      <header className="space-y-2">
        <Link
          to={`/models/${r.model_key}`}
          className="text-sm text-blue-800 underline underline-offset-2"
        >
          ← Back to {r.model_key}
        </Link>
        <h1 className="text-2xl font-semibold">
          <span className="font-mono text-lg">{r.task.task_id}</span> {r.task.title}
        </h1>
        <p className="flex flex-wrap items-center gap-3 text-sm text-slate-700">
          <span>{CATEGORY_LABEL[r.category] ?? r.category}</span>·
          <span>{TIER_LABEL[r.tier] ?? r.tier}</span>·<span>Status: {r.status}</span>·
          <span className="inline-flex items-center gap-1">
            Score <ScoreChip score={r.score} /> ({r.score_source ?? "unscored"})
          </span>
          {r.needs_review && (
            <span className="rounded bg-amber-100 px-1.5 py-0.5 text-xs text-amber-900">
              needs review
            </span>
          )}
        </p>
        <dl className="flex flex-wrap gap-x-6 gap-y-1 text-sm">
          <div className="flex gap-1">
            <dt className="text-slate-600">Input</dt>
            <dd>
              <TokenValue value={fmtTokens(u.input_tokens)} estimated={u.input_tokens_estimated} />
            </dd>
          </div>
          <div className="flex gap-1">
            <dt className="text-slate-600">Overhead</dt>
            <dd>
              <TokenValue value={fmtTokens(u.overhead_tokens)} />
            </dd>
          </div>
          <div className="flex gap-1">
            <dt className="text-slate-600">Output</dt>
            <dd>
              <TokenValue
                value={fmtTokens(u.output_tokens)}
                estimated={u.output_tokens_estimated}
              />
            </dd>
          </div>
          <div className="flex gap-1">
            <dt className="text-slate-600">Cost</dt>
            <dd>{fmtCost(u.api_equiv_cost_usd)}</dd>
          </div>
          <div className="flex gap-1">
            <dt className="text-slate-600">Latency</dt>
            <dd>{fmtMs(u.latency_ms)}</dd>
          </div>
        </dl>
      </header>

      <section aria-labelledby="prompt-h" className="space-y-2">
        <h2 id="prompt-h" className="text-lg font-semibold">
          Prompt{" "}
          <span className="text-sm font-normal text-slate-600">(suite v{r.task.version})</span>
        </h2>
        <pre className="max-h-96 overflow-auto rounded bg-slate-50 p-3 text-xs whitespace-pre-wrap">
          {r.task.prompt}
        </pre>
      </section>

      <section aria-labelledby="response-h" className="space-y-2">
        <h2 id="response-h" className="text-lg font-semibold">
          Response
        </h2>
        <pre className="max-h-96 overflow-auto rounded bg-slate-50 p-3 text-xs whitespace-pre-wrap">
          {r.response_text ?? "No response recorded."}
        </pre>
      </section>

      <section aria-labelledby="checks-h" className="space-y-2">
        <h2 id="checks-h" className="text-lg font-semibold">
          Checks
        </h2>
        {r.checks.length === 0 ? (
          <p className="text-sm text-slate-600">No deterministic checks for this task.</p>
        ) : (
          <ul className="space-y-2">
            {r.checks.map((c, i) => (
              <li key={i} className="rounded border border-slate-200 p-2 text-sm">
                <span
                  className={
                    c.passed ? "font-semibold text-green-800" : "font-semibold text-red-800"
                  }
                >
                  {c.passed ? "✓ Passed" : "✗ Failed"}
                </span>{" "}
                <span className="font-mono text-xs">{c.checker}</span>
                {c.output && (
                  <pre className="mt-1 text-xs whitespace-pre-wrap text-slate-700">{c.output}</pre>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="judges-h" className="space-y-2">
        <h2 id="judges-h" className="text-lg font-semibold">
          Judge
        </h2>
        {r.judges.length === 0 ? (
          <p className="text-sm text-slate-600">Not judged (scored by checks only).</p>
        ) : (
          <ul className="space-y-2">
            {r.judges.map((j, i) => (
              <li key={i} className="rounded border border-slate-200 p-2 text-sm">
                <span className="font-medium">{j.judge_model_key}</span> scored{" "}
                <ScoreChip score={j.score} />
                {j.rationale && <p className="mt-1 text-slate-700">{j.rationale}</p>}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="rdefects-h" className="space-y-2">
        <h2 id="rdefects-h" className="text-lg font-semibold">
          Defects from this result
        </h2>
        {r.defects.length === 0 ? (
          <p className="text-sm text-slate-600">None.</p>
        ) : (
          <ul className="space-y-1">
            {r.defects.map((d) => (
              <li key={d.id} className="flex items-center gap-2 text-sm">
                <SeverityBadge severity={d.severity} /> {d.title}
              </li>
            ))}
          </ul>
        )}
      </section>
    </article>
  );
}
