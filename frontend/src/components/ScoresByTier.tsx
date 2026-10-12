import { Bar, BarChart, CartesianGrid, Legend, Tooltip, XAxis, YAxis } from "recharts";
import { ResponsiveContainer } from "recharts";

import type { ScoreCell } from "../api/client";
import { CATEGORY_LABEL, TIERS, TIER_LABEL, fmtScore } from "../format";
import { ScoreChip } from "./Badges";

// Ordinal ramp, light → dark = Simple → Complex. Validated with the dataviz
// palette checker (light surface, all checks pass).
const TIER_COLOR: Record<string, string> = {
  simple: "#86b6ef",
  mid: "#2a78d6",
  complex: "#104281",
};

/** S2 category scores with Simple / Mid / Complex sub-scores, as a chart and a table. */
export function ScoresByTier({ scores }: { scores: ScoreCell[] }) {
  const data = scores.map((s) => ({
    name: CATEGORY_LABEL[s.category] ?? s.category,
    simple: s.by_tier.simple ?? null,
    mid: s.by_tier.mid ?? null,
    complex: s.by_tier.complex ?? null,
  }));

  return (
    <div className="space-y-4">
      <figure aria-label="Score by category and tier (chart; the same values are in the table below)">
        <div className="h-72 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} barGap={2} margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
              <CartesianGrid vertical={false} stroke="#e2e8f0" />
              <XAxis dataKey="name" tick={{ fontSize: 12, fill: "#475569" }} interval={0} />
              <YAxis
                domain={[0, 5]}
                ticks={[0, 1, 2, 3, 4, 5]}
                tick={{ fontSize: 12, fill: "#475569" }}
                width={28}
              />
              <Tooltip
                formatter={(v) => (typeof v === "number" ? v.toFixed(1) : "—")}
                cursor={{ fill: "#f1f5f9" }}
              />
              <Legend
                wrapperStyle={{ fontSize: 12 }}
                itemSorter={null}
                formatter={(value: string) => <span style={{ color: "#334155" }}>{value}</span>}
              />
              {TIERS.map((t) => (
                <Bar
                  key={t}
                  dataKey={t}
                  name={TIER_LABEL[t]}
                  fill={TIER_COLOR[t]}
                  radius={[4, 4, 0, 0]}
                  isAnimationActive={false}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>
      </figure>

      <table className="w-full text-sm" data-testid="scores-table">
        <caption className="sr-only">Score by category and tier</caption>
        <thead className="bg-slate-50 text-left text-slate-700">
          <tr>
            <th scope="col" className="px-2 py-1.5 font-medium">
              Category
            </th>
            <th scope="col" className="px-2 py-1.5 font-medium">
              Score
            </th>
            {TIERS.map((t) => (
              <th key={t} scope="col" className="px-2 py-1.5 font-medium">
                {TIER_LABEL[t]}
              </th>
            ))}
            <th scope="col" className="px-2 py-1.5 font-medium">
              Scored tasks
            </th>
          </tr>
        </thead>
        <tbody>
          {scores.map((s) => (
            <tr key={s.category} className="border-t border-slate-200">
              <th scope="row" className="px-2 py-1.5 text-left font-normal">
                {CATEGORY_LABEL[s.category] ?? s.category}
              </th>
              <td className="px-2 py-1.5">
                <ScoreChip score={s.score} />
              </td>
              {TIERS.map((t) => (
                <td key={t} className="px-2 py-1.5 tabular-nums">
                  {fmtScore(s.by_tier[t])}
                </td>
              ))}
              <td className="px-2 py-1.5 tabular-nums">
                {s.scored_results}
                {s.unscored_results > 0 && (
                  <span className="text-slate-600"> ({s.unscored_results} unscored)</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
