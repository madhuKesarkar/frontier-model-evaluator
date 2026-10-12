import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { api, type Profile, type Verdict } from "../api/client";
import { Empty, ErrorState, Loading } from "../components/States";
import { CATEGORY_LABEL, TIERS, TIER_LABEL, VERDICT_LABEL, fmtCost, fmtMs } from "../format";

// Verdicts use the reserved status colours, always with an icon and a text label.
const VERDICT_STYLE: Record<string, { cls: string; icon: string }> = {
  recommended: { cls: "bg-green-50 text-green-900 ring-green-300", icon: "✓" },
  conditional: { cls: "bg-amber-50 text-amber-900 ring-amber-300", icon: "!" },
  not_recommended: { cls: "bg-red-50 text-red-900 ring-red-300", icon: "✗" },
};

const label = (c: string) => CATEGORY_LABEL[c] ?? c;

function ProfileSummary({ p }: { p: Profile }) {
  const weighted = Object.entries(p.weights).filter(([, w]) => w > 0);
  return (
    <dl className="grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2" data-testid="profile-summary">
      <div>
        <dt className="inline text-slate-600">Weights: </dt>
        <dd className="inline">{weighted.map(([c, w]) => `${label(c)} ${w}`).join(", ")}</dd>
      </div>
      <div>
        <dt className="inline text-slate-600">Must-have: </dt>
        <dd className="inline">{p.must_have.map(label).join(", ") || "none"}</dd>
      </div>
      <div>
        <dt className="inline text-slate-600">Task mix: </dt>
        <dd className="inline">
          {TIERS.map((t) => `${TIER_LABEL[t]} ${p.tier_mix[t] ?? 0}%`).join(" · ")}
        </dd>
      </div>
      <div>
        <dt className="inline text-slate-600">Limits: </dt>
        <dd className="inline">
          {[
            p.max_cost_per_task_usd != null && `max ${fmtCost(p.max_cost_per_task_usd)} per task`,
            p.max_p95_latency_ms != null && `p95 ≤ ${fmtMs(p.max_p95_latency_ms)}`,
          ]
            .filter(Boolean)
            .join(", ") || "none"}
        </dd>
      </div>
    </dl>
  );
}

function VerdictCard({ v }: { v: Verdict }) {
  const style = VERDICT_STYLE[v.verdict] ?? { cls: "bg-slate-50 ring-slate-300", icon: "?" };
  return (
    <li
      className="space-y-3 rounded-md border border-slate-200 p-4"
      data-testid={`verdict-${v.model_key}`}
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-lg font-semibold">{v.display_name}</h3>
        <span className={`rounded px-2 py-1 text-sm font-semibold ring-1 ring-inset ${style.cls}`}>
          <span aria-hidden="true">{style.icon} </span>
          {VERDICT_LABEL[v.verdict] ?? v.verdict}
        </span>
      </div>
      <dl className="flex flex-wrap gap-x-6 text-sm">
        <div>
          <dt className="inline text-slate-600">Fit score </dt>
          <dd className="inline font-medium tabular-nums">
            {v.fit_score == null ? "—" : `${v.fit_score.toFixed(2)} / 5`}
          </dd>
        </div>
        <div>
          <dt className="inline text-slate-600">Expected cost / task </dt>
          <dd className="inline tabular-nums">{fmtCost(v.expected_cost_per_task_usd)}</dd>
        </div>
        <div>
          <dt className="inline text-slate-600">p95 latency </dt>
          <dd className="inline tabular-nums">{fmtMs(v.p95_latency_ms)}</dd>
        </div>
      </dl>
      <div>
        <h4 className="text-sm font-semibold">Why</h4>
        <ul className="list-disc pl-5 text-sm">
          {v.reasons.map((r, i) => (
            <li key={i}>{r.text}</li>
          ))}
        </ul>
      </div>
      <div className="grid gap-3 text-sm sm:grid-cols-2">
        <div>
          <h4 className="font-semibold">Strengths</h4>
          <p>{v.strengths.map(label).join(", ") || "None above 4.0 in the weighted categories"}</p>
        </div>
        <div>
          <h4 className="font-semibold">Risks</h4>
          <p>{v.risks.map(label).join(", ") || "None below 3.5 in the weighted categories"}</p>
        </div>
      </div>
      <Link
        to={`/models/${v.model_key}#defects`}
        className="inline-block text-sm font-medium text-blue-800 underline underline-offset-2"
      >
        {v.cited_defect_ids.length > 0
          ? `See the ${v.cited_defect_ids.length} cited defect${v.cited_defect_ids.length === 1 ? "" : "s"} for ${v.display_name}`
          : `Open ${v.display_name} details`}
      </Link>
    </li>
  );
}

/** S4 Fit for my app — templates only in the demo (frontend-spec §4, D-19). */
export function FitPage() {
  const [selected, setSelected] = useState<string | null>(null);
  const templates = useQuery({
    queryKey: ["templates"],
    queryFn: ({ signal }) => api.templates(signal),
  });
  const fit = useMutation({ mutationFn: (id: string) => api.fit(id) });

  const choose = (id: string) => {
    setSelected(id);
    fit.mutate(id);
  };

  return (
    <section aria-labelledby="fit-title" className="space-y-5">
      <div>
        <h1 id="fit-title" className="text-2xl font-semibold">
          Fit for my app
        </h1>
        <p className="text-sm text-slate-600">
          Pick the kind of application you are building. Each model gets a verdict with the reasons
          behind it.
        </p>
      </div>

      {templates.isPending ? (
        <Loading what="templates" />
      ) : templates.isError ? (
        <ErrorState message={templates.error.message} onRetry={() => void templates.refetch()} />
      ) : templates.data.length === 0 ? (
        <Empty>No templates are available.</Empty>
      ) : (
        <div role="group" aria-label="Application templates" className="flex flex-wrap gap-3">
          {templates.data.map((t) => (
            <button
              key={t.id}
              type="button"
              aria-pressed={selected === t.id}
              onClick={() => t.id && choose(t.id)}
              disabled={fit.isPending}
              className={`rounded-md border px-4 py-2 text-sm font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:opacity-60 ${
                selected === t.id
                  ? "border-blue-700 bg-blue-700 text-white"
                  : "border-slate-300 bg-white text-slate-800 hover:border-blue-700"
              }`}
            >
              {t.name}
            </button>
          ))}
        </div>
      )}

      {fit.isPending && <Loading what="verdicts" />}
      {fit.isError && selected && (
        <ErrorState message={fit.error.message} onRetry={() => fit.mutate(selected)} />
      )}
      {fit.isSuccess && (
        <div className="space-y-4" aria-live="polite">
          <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
            <h2 className="mb-1 font-semibold">{fit.data.profile.name}</h2>
            <ProfileSummary p={fit.data.profile} />
          </div>
          {fit.data.verdicts.length === 0 ? (
            <Empty>
              No evaluated models yet. Runs are started from the command line (
              <code>make eval</code>).
            </Empty>
          ) : (
            <ul className="grid gap-4 lg:grid-cols-2">
              {fit.data.verdicts.map((v) => (
                <VerdictCard key={v.model_key} v={v} />
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}
