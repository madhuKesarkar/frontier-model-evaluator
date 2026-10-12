import type { ModelDetail, UsageRecord } from "../api/client";

export function usage(over: Partial<UsageRecord> = {}): UsageRecord {
  return {
    input_tokens: 2100,
    input_tokens_estimated: false,
    output_tokens: 300,
    output_tokens_estimated: false,
    reasoning_tokens: null,
    cached_tokens: null,
    overhead_tokens: 1900,
    api_equiv_cost_usd: 0.0031,
    latency_ms: 3100,
    ...over,
  };
}

/** A CLI-mode model whose tiers exercise reported, estimated and unreported tokens. */
export function modelDetail(): ModelDetail {
  return {
    run_id: 1,
    model: {
      key: "gpt-go",
      provider: "openai",
      access_mode: "codex_cli",
      model_id: "gpt-x",
      display_name: "GPT via Codex",
      enabled: true,
    },
    last_run_at: "2026-10-14T08:30:00Z",
    overall: 4.2,
    p50_latency_ms: 5000,
    p95_latency_ms: 12000,
    open_s1_s2_defects: 2,
    scores: [],
    costliest_task_ids: [],
    tokens_by_tier: {
      simple: { avg: usage(), total: usage({ input_tokens: 6300, overhead_tokens: 5700 }) },
      // Output counted with a tokenizer: shown with an "estimated" badge.
      mid: {
        avg: usage({ output_tokens: 420, output_tokens_estimated: true }),
        total: usage({ output_tokens: 1260, output_tokens_estimated: true }),
      },
      // Access mode did not report input or overhead: "n/a", never 0.
      complex: {
        avg: usage({ input_tokens: null, overhead_tokens: null }),
        total: usage({ input_tokens: null, overhead_tokens: null }),
      },
    },
  };
}
