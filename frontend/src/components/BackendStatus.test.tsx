import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { BackendStatus } from "./BackendStatus";

function renderWithClient() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <BackendStatus />
    </QueryClientProvider>,
  );
}

function mockFetchOnce(response: Response | Error) {
  const fn = vi.fn();
  if (response instanceof Error) fn.mockRejectedValueOnce(response);
  else fn.mockResolvedValueOnce(response);
  return fn;
}

afterEach(() => vi.unstubAllGlobals());

describe("BackendStatus (Phase 0.3 placeholder)", () => {
  it("shows a loading state, then 'connected' when GET /api/v1/health returns ok", async () => {
    const fetchMock = mockFetchOnce(Response.json({ status: "ok" }));
    vi.stubGlobal("fetch", fetchMock);

    renderWithClient();

    expect(screen.getByText("Checking backend…")).toBeInTheDocument();
    expect(await screen.findByText("Backend connected (status: ok)")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/health", expect.anything());
  });

  it("shows an error with Retry when the backend is unreachable, and recovers on Retry", async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new TypeError("Failed to fetch"))
      .mockResolvedValueOnce(Response.json({ status: "ok" }));
    vi.stubGlobal("fetch", fetchMock);

    renderWithClient();

    expect(await screen.findByRole("alert")).toHaveTextContent("Backend not reachable");
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("Backend connected (status: ok)")).toBeInTheDocument();
  });

  it("treats a non-2xx response as an error even when its body is valid JSON", async () => {
    // A JSON body (as FastAPI returns for errors) ensures only the status check can catch this.
    vi.stubGlobal(
      "fetch",
      mockFetchOnce(Response.json({ detail: "Internal error" }, { status: 500 })),
    );

    renderWithClient();

    expect(await screen.findByRole("alert")).toHaveTextContent("Backend not reachable");
  });
});
