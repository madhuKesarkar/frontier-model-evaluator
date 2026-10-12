import type { ReactNode } from "react";

// frontend-spec §4: every screen has loading, empty and error states.

export function Loading({ what }: { what: string }) {
  return (
    <p role="status" aria-live="polite" className="py-8 text-slate-600">
      Loading {what}…
    </p>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div role="alert" className="space-y-3 rounded-md border border-red-200 bg-red-50 p-4">
      <p className="text-red-800">
        <span className="font-semibold">Something went wrong.</span> {message}
      </p>
      <button
        type="button"
        onClick={onRetry}
        className="rounded bg-slate-800 px-3 py-1.5 text-sm text-white hover:bg-slate-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
      >
        Retry
      </button>
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-md border border-dashed border-slate-300 p-6 text-slate-600">
      {children}
    </div>
  );
}
