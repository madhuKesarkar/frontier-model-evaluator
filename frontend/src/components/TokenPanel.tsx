import type { ModelDetail, UsageRecord } from "../api/client";
import { TIERS, TIER_LABEL, fmtCost, fmtMs, fmtTokens } from "../format";
import { TokenValue } from "./Badges";

/** Task tokens = reported input minus the access mode's own overhead (backend-spec §3). */
function taskInput(u: UsageRecord): number | null {
  if (u.input_tokens == null) return null;
  return u.overhead_tokens == null ? u.input_tokens : u.input_tokens - u.overhead_tokens;
}

function Cells({ u, testid }: { u: UsageRecord; testid: string }) {
  return (
    <>
      <td className="px-2 py-1.5" data-testid={`${testid}-task-input`}>
        <TokenValue value={fmtTokens(taskInput(u))} estimated={u.input_tokens_estimated} />
      </td>
      <td className="px-2 py-1.5" data-testid={`${testid}-overhead`}>
        <TokenValue value={fmtTokens(u.overhead_tokens)} />
      </td>
      <td className="px-2 py-1.5" data-testid={`${testid}-output`}>
        <TokenValue value={fmtTokens(u.output_tokens)} estimated={u.output_tokens_estimated} />
      </td>
      <td className="px-2 py-1.5 tabular-nums">{fmtCost(u.api_equiv_cost_usd)}</td>
    </>
  );
}

/** S2 token panel: per tier, average and total task / overhead / output tokens and cost. */
export function TokenPanel({ detail }: { detail: ModelDetail }) {
  const head = ["Task input", "Overhead", "Output", "API-equiv. cost"];
  return (
    <div className="space-y-3">
      <div className="overflow-x-auto rounded-md border border-slate-200">
        <table className="w-full text-sm" data-testid="token-panel">
          <caption className="sr-only">Tokens and cost per tier</caption>
          <thead className="bg-slate-50 text-left text-slate-700">
            <tr>
              <th scope="col" rowSpan={2} className="px-2 py-1.5 align-bottom font-medium">
                Tier
              </th>
              <th scope="colgroup" colSpan={4} className="px-2 pt-1.5 font-medium">
                Average per task
              </th>
              <th
                scope="colgroup"
                colSpan={4}
                className="border-l border-slate-200 px-2 pt-1.5 font-medium"
              >
                Total
              </th>
              <th scope="col" rowSpan={2} className="px-2 py-1.5 align-bottom font-medium">
                p50 latency
              </th>
            </tr>
            <tr>
              {[...head, ...head].map((h, i) => (
                <th
                  key={i}
                  scope="col"
                  className={`px-2 pb-1.5 text-xs font-normal text-slate-600 ${i === 4 ? "border-l border-slate-200" : ""}`}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {TIERS.map((t) => {
              const tier = detail.tokens_by_tier[t];
              return (
                <tr key={t} className="border-t border-slate-200" data-testid={`tokens-${t}`}>
                  <th scope="row" className="px-2 py-1.5 text-left font-normal">
                    {TIER_LABEL[t]}
                  </th>
                  {tier ? (
                    <>
                      <Cells u={tier.avg} testid={`${t}-avg`} />
                      <Cells u={tier.total} testid={`${t}-total`} />
                      <td className="px-2 py-1.5 tabular-nums">{fmtMs(tier.avg.latency_ms)}</td>
                    </>
                  ) : (
                    <td colSpan={9} className="px-2 py-1.5 text-slate-600">
                      No results for this tier.
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-slate-600">
        Task input is the prompt as the model saw it; overhead is what the access mode adds itself
        (for example a CLI system prompt). Tokenizers differ between providers, so compare cost
        rather than raw token counts. <strong>n/a</strong> means the access mode did not report the
        value; <strong>estimated</strong> means it was counted with a tokenizer.
      </p>
    </div>
  );
}
