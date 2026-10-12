import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { Link, useLocation, useParams } from "react-router-dom";

import { api, ApiError } from "../api/client";
import { ScoreChip } from "../components/Badges";
import { DefectsSection } from "../components/DefectsSection";
import { FairnessNote } from "../components/Notes";
import { ScoresByTier } from "../components/ScoresByTier";
import { Empty, ErrorState, Loading } from "../components/States";
import { TokenPanel } from "../components/TokenPanel";
import { CATEGORY_LABEL, TIER_LABEL, fmtCost, fmtMs } from "../format";

function Section({
  id,
  title,
  children,
}: {
  id: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section aria-labelledby={id} className="space-y-3">
      <h2 id={id} className="text-lg font-semibold">
        {title}
      </h2>
      {children}
    </section>
  );
}

function ResultsTable({ modelKey, costliest }: { modelKey: string; costliest: string[] }) {
  const query = useQuery({
    queryKey: ["results", modelKey],
    queryFn: ({ signal }) => api.results(modelKey, signal),
  });
  if (query.isPending) return <Loading what="task results" />;
  if (query.isError)
    return <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />;
  return (
    <div className="overflow-x-auto rounded-md border border-slate-200">
      <table className="w-full text-sm">
        <caption className="sr-only">Every task result for this model</caption>
        <thead className="bg-slate-50 text-left text-slate-700">
          <tr>
            {["Task", "Category", "Tier", "Score", "Cost", "Latency", ""].map((h, i) => (
              <th key={i} scope="col" className="px-2 py-1.5 font-medium">
                {h || <span className="sr-only">Details</span>}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {query.data.map((r) => (
            <tr key={r.result_id} className="border-t border-slate-200">
              <th scope="row" className="px-2 py-1.5 text-left font-normal">
                <span className="font-mono text-xs">{r.task_id}</span> {r.title}
                {costliest.includes(r.task_id) && (
                  <span className="ml-2 rounded bg-blue-50 px-1.5 py-0.5 text-xs text-blue-900 ring-1 ring-blue-200 ring-inset">
                    most expensive
                  </span>
                )}
                {r.needs_review && (
                  <span className="ml-2 rounded bg-amber-100 px-1.5 py-0.5 text-xs text-amber-900">
                    needs review
                  </span>
                )}
              </th>
              <td className="px-2 py-1.5">{CATEGORY_LABEL[r.category] ?? r.category}</td>
              <td className="px-2 py-1.5">{TIER_LABEL[r.tier] ?? r.tier}</td>
              <td className="px-2 py-1.5">
                <ScoreChip score={r.score} />
              </td>
              <td className="px-2 py-1.5 tabular-nums">{fmtCost(r.usage.api_equiv_cost_usd)}</td>
              <td className="px-2 py-1.5 tabular-nums">{fmtMs(r.usage.latency_ms)}</td>
              <td className="px-2 py-1.5">
                <Link
                  to={`/results/${r.result_id}`}
                  className="text-blue-800 underline underline-offset-2"
                  aria-label={`Open result for ${r.task_id}`}
                >
                  Open
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** S2 Model detail (frontend-spec §4). */
export function ModelDetailPage() {
  const { key = "" } = useParams();
  const query = useQuery({
    queryKey: ["model", key],
    queryFn: ({ signal }) => api.model(key, signal),
    retry: (count, err) => !(err instanceof ApiError && err.status === 404) && count < 1,
  });
  // Links such as /models/x#defects (from Fit) scroll to that section once it renders.
  const { hash } = useLocation();
  const loaded = query.isSuccess;
  useEffect(() => {
    if (loaded && hash) document.getElementById(hash.slice(1))?.scrollIntoView();
  }, [loaded, hash]);

  if (query.isPending) return <Loading what="the model" />;
  if (query.isError) {
    if (query.error instanceof ApiError && query.error.status === 404) {
      return (
        <Empty>
          This model hasn&apos;t been evaluated yet.{" "}
          <Link to="/" className="underline">
            Back to the leaderboard
          </Link>
        </Empty>
      );
    }
    return <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />;
  }

  const d = query.data;
  return (
    <div className="space-y-8">
      <header className="space-y-3">
        <Link to="/" className="text-sm text-blue-800 underline underline-offset-2">
          ← Leaderboard
        </Link>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold">{d.model.display_name}</h1>
            <dl
              className="mt-2 grid grid-cols-2 gap-x-6 gap-y-1 text-sm sm:grid-cols-4"
              data-testid="model-header"
            >
              <div>
                <dt className="text-slate-600">Provider</dt>
                <dd>{d.model.provider}</dd>
              </div>
              <div>
                <dt className="text-slate-600">Access mode</dt>
                <dd data-testid="access-mode">{d.model.access_mode}</dd>
              </div>
              <div>
                <dt className="text-slate-600">Model ID</dt>
                <dd className="font-mono text-xs">{d.model.model_id}</dd>
              </div>
              <div>
                <dt className="text-slate-600">Last run</dt>
                <dd>{d.last_run_at ? new Date(d.last_run_at).toLocaleString() : "—"}</dd>
              </div>
            </dl>
          </div>
          <div className="text-right">
            <div className="text-sm text-slate-600">Overall</div>
            <div className="text-xl">
              <ScoreChip score={d.overall} />
            </div>
            <div className="mt-1 text-xs text-slate-600">
              p50 {fmtMs(d.p50_latency_ms)} · p95 {fmtMs(d.p95_latency_ms)} · open S1+S2:{" "}
              {d.open_s1_s2_defects}
            </div>
          </div>
        </div>
        <FairnessNote />
      </header>

      <Section id="scores" title="Scores by category and tier">
        <ScoresByTier scores={d.scores} />
      </Section>

      <Section id="tokens" title="Token usage and cost by tier">
        <TokenPanel detail={d} />
      </Section>

      <Section id="defects" title="Defects">
        <DefectsSection modelKey={key} />
      </Section>

      <Section id="results" title="Task results">
        <ResultsTable modelKey={key} costliest={d.costliest_task_ids} />
      </Section>
    </div>
  );
}
