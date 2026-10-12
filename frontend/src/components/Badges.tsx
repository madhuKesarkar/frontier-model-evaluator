// Scores 1 (red) to 5 (green), always shown with the number (frontend-spec §2).
// Uses the reserved status palette; colour never carries meaning alone.
interface Band {
  bg: string;
  dot: string;
  label: string;
}
const ACCEPTABLE: Band = { bg: "bg-amber-50", dot: "#fab219", label: "Acceptable" };
const SCORE_STYLE: Record<number, Band> = {
  1: { bg: "bg-red-50", dot: "#d03b3b", label: "Fail" },
  2: { bg: "bg-orange-50", dot: "#ec835a", label: "Poor" },
  3: ACCEPTABLE,
  4: { bg: "bg-green-50", dot: "#0ca30c", label: "Good" },
  5: { bg: "bg-green-100", dot: "#0ca30c", label: "Excellent" },
};

export function ScoreChip({ score }: { score: number | null | undefined }) {
  if (score == null) {
    return (
      <span
        className="inline-block min-w-12 rounded px-2 py-0.5 text-center text-slate-500"
        title="Not evaluated"
      >
        —
      </span>
    );
  }
  const band = SCORE_STYLE[Math.min(5, Math.max(1, Math.round(score)))] ?? ACCEPTABLE;
  return (
    <span
      className={`inline-flex min-w-12 items-center justify-center gap-1.5 rounded px-2 py-0.5 font-medium text-slate-900 tabular-nums ${band.bg}`}
      title={`${score.toFixed(1)} of 5 — ${band.label}`}
    >
      <span aria-hidden="true" className="h-2 w-2 rounded-full" style={{ background: band.dot }} />
      {score.toFixed(1)}
    </span>
  );
}

const SEVERITY: Record<string, { cls: string; label: string }> = {
  S1: { cls: "bg-red-100 text-red-900 ring-red-300", label: "S1 Critical" },
  S2: { cls: "bg-orange-100 text-orange-900 ring-orange-300", label: "S2 Major" },
  S3: { cls: "bg-amber-100 text-amber-900 ring-amber-300", label: "S3 Minor" },
  S4: { cls: "bg-slate-100 text-slate-800 ring-slate-300", label: "S4 Cosmetic" },
};

export function SeverityBadge({ severity }: { severity: string }) {
  const s = SEVERITY[severity] ?? {
    cls: "bg-slate-100 text-slate-800 ring-slate-300",
    label: severity,
  };
  return (
    <span
      className={`inline-block rounded px-1.5 py-0.5 text-xs font-semibold ring-1 ring-inset ${s.cls}`}
    >
      {s.label}
    </span>
  );
}

/** FE-AC-04: estimated or unreported values are labelled, never shown as 0. */
export function TokenValue({ value, estimated }: { value: string | null; estimated?: boolean }) {
  if (value == null) {
    return (
      <span
        className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600"
        title="Not reported by this access mode"
      >
        n/a
      </span>
    );
  }
  return (
    <span className="tabular-nums">
      {value}
      {estimated && (
        <span
          className="ml-1 rounded bg-amber-100 px-1 py-0.5 text-xs text-amber-900"
          title="Estimated with a tokenizer"
        >
          estimated
        </span>
      )}
    </span>
  );
}
