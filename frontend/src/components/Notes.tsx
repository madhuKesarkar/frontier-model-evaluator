// frontend-spec §3 fairness note, and an honest label for where the data came from.

export function FairnessNote() {
  return (
    <p className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
      <span className="font-semibold">How to read this:</span> models are compared as reached
      through each access mode (Claude via Claude Code on Pro, GPT via Codex on Go), not as flagship
      paid APIs. Token counts use different tokenizers; compare API-equivalent cost instead. Nothing
      here was billed.
    </p>
  );
}

export function DataSourceBanner({
  source,
  label,
}: {
  source: string | null;
  label: string | null;
}) {
  if (source === "recorded") {
    return (
      <p
        role="note"
        className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900"
      >
        <span className="font-semibold">Synthetic demo data</span>
        {label ? ` (${label})` : ""}: recorded responses with planted flaws, used to exercise the
        screens. These are <strong>not</strong> real model results.
      </p>
    );
  }
  if (source === "live") {
    return (
      <p className="rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-900">
        <span className="font-semibold">Live run</span>
        {label ? ` (${label})` : ""}: real responses from the models through the owner&apos;s
        subscriptions.
      </p>
    );
  }
  return null;
}
