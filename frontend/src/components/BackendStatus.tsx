import { useQuery } from "@tanstack/react-query";

import { getHealth } from "../api/client";

/**
 * Placeholder for Phase 0: shows whether the backend is reachable.
 * Follows frontend-spec §4 states: loading, success, and error with Retry.
 */
export function BackendStatus() {
  const { isPending, isError, data, refetch, isFetching } = useQuery({
    queryKey: ["health"],
    queryFn: ({ signal }) => getHealth(signal),
    retry: false,
  });

  if (isPending) {
    return (
      <p role="status" className="text-slate-600">
        Checking backend…
      </p>
    );
  }

  if (isError) {
    return (
      <div role="alert" className="space-y-2">
        <p className="text-red-700">
          Backend not reachable. Start it with{" "}
          <code className="rounded bg-slate-100 px-1">
            uvicorn app.main:app --host 127.0.0.1 --port 8000
          </code>{" "}
          in <code className="rounded bg-slate-100 px-1">backend/</code>.
        </p>
        <button
          type="button"
          onClick={() => void refetch()}
          disabled={isFetching}
          className="rounded bg-slate-800 px-3 py-1 text-white disabled:opacity-50"
        >
          {isFetching ? "Retrying…" : "Retry"}
        </button>
      </div>
    );
  }

  return (
    <p role="status" className="text-green-700">
      Backend connected (status: {data.status})
    </p>
  );
}
