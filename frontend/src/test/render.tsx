import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { ReactElement } from "react";

/** Renders a page at a route with a fresh query client (no retries). */
export function renderAt(path: string, pattern: string, page: ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path={pattern} element={page} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
