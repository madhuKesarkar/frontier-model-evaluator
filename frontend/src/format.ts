export const CATEGORY_LABEL: Record<string, string> = {
  code_generation: "Code Generation",
  reasoning: "Reasoning & Analysis",
  structured_output: "Structured Output",
  test_design: "Test Design (QA)",
  long_context: "Long-Context Faithfulness",
  tool_use: "Tool Use",
};
export const CATEGORIES = Object.keys(CATEGORY_LABEL);
export const TIERS = ["simple", "mid", "complex"] as const;
export const TIER_LABEL: Record<string, string> = {
  simple: "Simple",
  mid: "Mid",
  complex: "Complex",
};
export const VERDICT_LABEL: Record<string, string> = {
  recommended: "Recommended",
  conditional: "Conditional",
  not_recommended: "Not recommended",
};

export const fmtScore = (v: number | null | undefined) => (v == null ? "—" : v.toFixed(1));
export const fmtTokens = (v: number | null | undefined) =>
  v == null ? null : Math.round(v).toLocaleString("en-US");
export const fmtCost = (v: number | null | undefined) =>
  v == null ? "n/a" : `$${v < 0.01 ? v.toFixed(4) : v.toFixed(3)}`;
export const fmtMs = (v: number | null | undefined) =>
  v == null ? "n/a" : v >= 1000 ? `${(v / 1000).toFixed(1)} s` : `${v} ms`;
