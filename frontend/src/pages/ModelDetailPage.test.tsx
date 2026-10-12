import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { modelDetail } from "../test/fixtures";
import { renderAt } from "../test/render";
import { ModelDetailPage } from "./ModelDetailPage";

afterEach(() => vi.unstubAllGlobals());

function stubApi() {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      if (url.endsWith("/models/gpt-go")) return Promise.resolve(Response.json(modelDetail()));
      if (url.includes("/defects")) return Promise.resolve(Response.json({ count: 0, items: [] }));
      if (url.endsWith("/results")) return Promise.resolve(Response.json([]));
      return Promise.resolve(Response.json({ detail: "Not found" }, { status: 404 }));
    }),
  );
}

describe("ModelDetailPage (S2)", () => {
  it("FE-AC-05: the CLI access mode is visible in the header next to the token panel", async () => {
    stubApi();
    renderAt("/models/gpt-go", "/models/:key", <ModelDetailPage />);
    expect(await screen.findByTestId("access-mode")).toHaveTextContent("codex_cli");
    expect(screen.getByRole("heading", { name: "GPT via Codex" })).toBeInTheDocument();
    expect(screen.getByTestId("token-panel")).toBeInTheDocument();
  });

  it("shows the not-evaluated empty state for an unknown model", async () => {
    stubApi();
    renderAt("/models/nope", "/models/:key", <ModelDetailPage />);
    expect(await screen.findByText(/hasn.t been evaluated yet/)).toBeInTheDocument();
  });
});
