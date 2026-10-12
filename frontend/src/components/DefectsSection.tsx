import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useId, useState } from "react";
import { Link } from "react-router-dom";

import { api, type Defect } from "../api/client";
import {
  CATEGORIES,
  CATEGORY_LABEL,
  DEFECT_STATUSES,
  DEFECT_TYPES,
  SEVERITIES,
  TIERS,
  TIER_LABEL,
  humanize,
} from "../format";
import { SeverityBadge } from "./Badges";
import { Empty, ErrorState, Loading } from "./States";

type Filters = { severity: string; type: string; tier: string; category: string; status: string };
const NO_FILTERS: Filters = { severity: "", type: "", tier: "", category: "", status: "" };

const selectClass =
  "rounded border border-slate-300 bg-white px-2 py-1 text-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600";

function FilterSelect(props: {
  label: string;
  value: string;
  options: { value: string; label: string }[];
  onChange: (v: string) => void;
}) {
  // Explicit for/id so the accessible name is just the label, not "Tier All".
  const id = useId();
  return (
    <div className="flex items-center gap-2 text-sm">
      <label htmlFor={id}>{props.label}</label>
      <select
        id={id}
        className={selectClass}
        value={props.value}
        onChange={(e) => props.onChange(e.target.value)}
      >
        <option value="">All</option>
        {props.options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  );
}

function Excerpt({ label, text }: { label: string; text: string | null | undefined }) {
  return (
    <div>
      <dt className="text-xs font-semibold tracking-wide text-slate-600 uppercase">{label}</dt>
      <dd>
        {text ? (
          <pre
            tabIndex={0}
            aria-label={label}
            className="mt-1 max-h-48 overflow-auto focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600 rounded bg-slate-50 p-2 text-xs whitespace-pre-wrap"
          >
            {text}
          </pre>
        ) : (
          <span className="text-sm text-slate-600">Not recorded</span>
        )}
      </dd>
    </div>
  );
}

/** FE-AC-16: an expanded defect shows its evidence and links to the full result. */
function DefectItem({ d }: { d: Defect }) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  return (
    <li className="rounded-md border border-slate-200" data-testid="defect">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((o) => !o)}
        className="flex w-full flex-wrap items-center gap-3 px-3 py-2 text-left hover:bg-slate-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600"
      >
        <SeverityBadge severity={d.severity} />
        <span className="font-medium">{d.title}</span>
        <span className="text-sm text-slate-600">
          {d.task_id} · {TIER_LABEL[d.tier] ?? d.tier} · {humanize(d.type)}
        </span>
        <span aria-hidden="true" className="ml-auto text-slate-500">
          {open ? "▲" : "▼"}
        </span>
      </button>
      {open && (
        <div id={panelId} className="space-y-3 border-t border-slate-200 px-3 py-3">
          <dl className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm sm:grid-cols-4">
            <div>
              <dt className="text-slate-600">Severity</dt>
              <dd>{d.severity}</dd>
            </div>
            <div>
              <dt className="text-slate-600">Category</dt>
              <dd>{CATEGORY_LABEL[d.category] ?? d.category}</dd>
            </div>
            <div>
              <dt className="text-slate-600">Source</dt>
              <dd>{d.source}</dd>
            </div>
            <div>
              <dt className="text-slate-600">Status</dt>
              <dd>{humanize(d.status)}</dd>
            </div>
          </dl>
          <dl className="grid gap-3 md:grid-cols-2">
            <Excerpt label="Expected" text={d.expected} />
            <Excerpt label="Actual" text={d.actual} />
            <Excerpt label="Prompt excerpt" text={d.evidence.prompt_excerpt} />
            <Excerpt label="Response excerpt" text={d.evidence.response_excerpt} />
          </dl>
          {d.evidence.checker_output && (
            <dl>
              <Excerpt label="Checker output" text={d.evidence.checker_output} />
            </dl>
          )}
          <Link
            to={`/results/${d.result_id}`}
            className="inline-block text-sm font-medium text-blue-800 underline underline-offset-2"
          >
            Open the full result for {d.task_id}
          </Link>
        </div>
      )}
    </li>
  );
}

/** S2 defects list, filterable by severity, type, category, tier and status. */
export function DefectsSection({ modelKey }: { modelKey: string }) {
  const [filters, setFilters] = useState<Filters>(NO_FILTERS);
  const set = (k: keyof Filters) => (v: string) => setFilters((f) => ({ ...f, [k]: v }));
  const query = useQuery({
    queryKey: ["defects", modelKey, filters],
    queryFn: ({ signal }) => api.defects(modelKey, filters, signal),
    placeholderData: keepPreviousData,
  });

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-4" role="group" aria-label="Defect filters">
        <FilterSelect
          label="Severity"
          value={filters.severity}
          onChange={set("severity")}
          options={SEVERITIES.map((s) => ({ value: s, label: s }))}
        />
        <FilterSelect
          label="Tier"
          value={filters.tier}
          onChange={set("tier")}
          options={TIERS.map((t) => ({ value: t, label: TIER_LABEL[t] ?? t }))}
        />
        <FilterSelect
          label="Category"
          value={filters.category}
          onChange={set("category")}
          options={CATEGORIES.map((c) => ({ value: c, label: CATEGORY_LABEL[c] ?? c }))}
        />
        <FilterSelect
          label="Type"
          value={filters.type}
          onChange={set("type")}
          options={DEFECT_TYPES.map((t) => ({ value: t, label: humanize(t) }))}
        />
        <FilterSelect
          label="Status"
          value={filters.status}
          onChange={set("status")}
          options={DEFECT_STATUSES.map((s) => ({ value: s, label: humanize(s) }))}
        />
      </div>

      {query.isPending ? (
        <Loading what="defects" />
      ) : query.isError ? (
        <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
      ) : (
        <>
          <p
            role="status"
            aria-live="polite"
            className="text-sm text-slate-700"
            data-testid="defect-count"
          >
            {query.data.count} {query.data.count === 1 ? "defect" : "defects"}
            {Object.values(filters).some(Boolean) ? " match these filters" : " found"}
          </p>
          {query.data.count === 0 ? (
            <Empty>No defects match these filters.</Empty>
          ) : (
            <ul className="space-y-2">
              {query.data.items.map((d) => (
                <DefectItem key={d.id} d={d} />
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}
