import { useQuery } from "@tanstack/react-query";
import { type ReactNode, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api, type LeaderboardRow } from "../api/client";
import { ScoreChip } from "../components/Badges";
import { DataSourceBanner, FairnessNote } from "../components/Notes";
import { Empty, ErrorState, Loading } from "../components/States";
import { CATEGORIES, CATEGORY_LABEL, TIERS, TIER_LABEL, fmtCost, fmtMs } from "../format";

type SortKey = "name" | "overall" | "cost" | "latency" | "defects" | `cat:${string}`;

function sortValue(row: LeaderboardRow, key: SortKey): number | string | null {
  if (key === "name") return row.model.display_name.toLowerCase();
  if (key === "overall") return row.overall ?? null;
  if (key === "cost") return row.avg_cost_per_task_usd ?? null;
  if (key === "latency") return row.p50_latency_ms ?? null;
  if (key === "defects") return row.open_s1_s2_defects;
  const cat = key.slice(4);
  return row.scores.find((s) => s.category === cat)?.score ?? null;
}

const selectClass =
  "rounded border border-slate-300 bg-white px-2 py-1 text-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600";

interface SortState {
  key: SortKey;
  desc: boolean;
}

function SortHeader(props: {
  k: SortKey;
  sort: SortState;
  onSort: (s: SortState) => void;
  children: ReactNode;
}) {
  const { k, sort, onSort, children } = props;
  const active = sort.key === k;
  return (
    <th
      scope="col"
      aria-sort={active ? (sort.desc ? "descending" : "ascending") : "none"}
      className="px-2 py-2 text-left align-bottom font-medium"
    >
      <button
        type="button"
        onClick={() => onSort({ key: k, desc: active ? !sort.desc : k !== "name" })}
        className="inline-flex items-center gap-1 rounded text-left hover:text-blue-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600"
      >
        {children}
        <span aria-hidden="true" className="text-xs text-slate-500">
          {active ? (sort.desc ? "▼" : "▲") : "↕"}
        </span>
      </button>
    </th>
  );
}

/** S1 Leaderboard (frontend-spec §4). */
export function LeaderboardPage() {
  const navigate = useNavigate();
  const [tier, setTier] = useState("");
  const [category, setCategory] = useState("");
  const [sort, setSort] = useState<SortState>({ key: "overall", desc: true });

  const query = useQuery({
    queryKey: ["leaderboard", tier, category],
    queryFn: ({ signal }) => api.leaderboard({ tier, category }, signal),
  });

  const rows = useMemo(() => {
    const list = [...(query.data?.rows ?? [])];
    list.sort((a, b) => {
      const va = sortValue(a, sort.key);
      const vb = sortValue(b, sort.key);
      if (va === vb) return 0;
      if (va === null) return 1; // missing values always last
      if (vb === null) return -1;
      const cmp = va < vb ? -1 : 1;
      return sort.desc ? -cmp : cmp;
    });
    return list;
  }, [query.data, sort]);

  const shownCategories = category ? [category] : CATEGORIES;

  return (
    <section aria-labelledby="lb-title" className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 id="lb-title" className="text-2xl font-semibold">
            Leaderboard
          </h1>
          <p className="text-sm text-slate-600">
            Scores are 1 (fail) to 5 (excellent). Click a model to see its tokens, defects and
            evidence.
          </p>
        </div>
        <Link
          to="/fit"
          className="rounded bg-blue-700 px-4 py-2 text-sm font-medium text-white hover:bg-blue-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
        >
          Check fit for my app
        </Link>
      </div>

      <FairnessNote />

      <div className="flex flex-wrap gap-4" role="group" aria-label="Filters">
        <label className="flex items-center gap-2 text-sm">
          Tier
          <select className={selectClass} value={tier} onChange={(e) => setTier(e.target.value)}>
            <option value="">All tiers</option>
            {TIERS.map((t) => (
              <option key={t} value={t}>
                {TIER_LABEL[t]}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2 text-sm">
          Category
          <select
            className={selectClass}
            value={category}
            onChange={(e) => setCategory(e.target.value)}
          >
            <option value="">All categories</option>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {CATEGORY_LABEL[c]}
              </option>
            ))}
          </select>
        </label>
        <p className="self-center text-sm text-slate-600">Run: latest completed</p>
      </div>

      {query.isPending ? (
        <Loading what="the leaderboard" />
      ) : query.isError ? (
        <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
      ) : query.data.rows.length === 0 ? (
        <Empty>
          No results loaded yet. Runs are started from the command line (<code>make eval</code>);
          see the README.
        </Empty>
      ) : (
        <>
          <DataSourceBanner source={query.data.run_source} label={query.data.run_label} />
          <div className="overflow-x-auto rounded-md border border-slate-200">
            <table className="w-full text-sm">
              <caption className="sr-only">
                Models ranked by score. Column headers sort the table.
              </caption>
              <thead className="bg-slate-50 text-slate-700">
                <tr>
                  <SortHeader sort={sort} onSort={setSort} k="name">
                    Model
                  </SortHeader>
                  <SortHeader sort={sort} onSort={setSort} k="overall">
                    Overall
                  </SortHeader>
                  {shownCategories.map((c) => (
                    <SortHeader key={c} sort={sort} onSort={setSort} k={`cat:${c}`}>
                      {CATEGORY_LABEL[c]}
                    </SortHeader>
                  ))}
                  <SortHeader sort={sort} onSort={setSort} k="cost">
                    Avg cost / task
                  </SortHeader>
                  <SortHeader sort={sort} onSort={setSort} k="latency">
                    p50 latency
                  </SortHeader>
                  <SortHeader sort={sort} onSort={setSort} k="defects">
                    Open S1+S2
                  </SortHeader>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr
                    key={row.model.key}
                    data-testid={`row-${row.model.key}`}
                    onClick={() => void navigate(`/models/${row.model.key}`)}
                    className="cursor-pointer border-t border-slate-200 hover:bg-blue-50"
                  >
                    <th scope="row" className="px-2 py-2 text-left font-normal">
                      <Link
                        to={`/models/${row.model.key}`}
                        className="font-medium text-blue-800 underline-offset-2 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600"
                      >
                        {row.model.display_name}
                      </Link>
                      <div className="text-xs text-slate-600">{row.model.access_mode}</div>
                    </th>
                    <td className="px-2 py-2">
                      <ScoreChip score={row.overall} />
                    </td>
                    {shownCategories.map((c) => {
                      const cell = row.scores.find((s) => s.category === c);
                      return (
                        <td key={c} className="px-2 py-2" data-category={c}>
                          <ScoreChip score={cell?.score} />
                        </td>
                      );
                    })}
                    <td className="px-2 py-2 tabular-nums">{fmtCost(row.avg_cost_per_task_usd)}</td>
                    <td className="px-2 py-2 tabular-nums">{fmtMs(row.p50_latency_ms)}</td>
                    <td className="px-2 py-2 tabular-nums">{row.open_s1_s2_defects}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-slate-600">
            Cost is the API-equivalent price of the tokens used; nothing was billed.
          </p>
        </>
      )}
    </section>
  );
}
