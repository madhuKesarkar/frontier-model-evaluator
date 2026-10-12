import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderAt } from "../test/render";
import { LeaderboardPage } from "./LeaderboardPage";

afterEach(() => vi.unstubAllGlobals());

const EMPTY = { run_id: null, run_label: null, run_source: null, rows: [] };

describe("LeaderboardPage (S1)", () => {
  it("FE-AC-13: a failed request shows a plain-language error and Retry recovers", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        Response.json({ detail: "Database not set up yet: run make migrate" }, { status: 503 }),
      )
      .mockResolvedValueOnce(Response.json(EMPTY));
    vi.stubGlobal("fetch", fetchMock);
    renderAt("/", "/", <LeaderboardPage />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Database not set up yet: run make migrate",
    );
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText(/No results loaded yet/)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("FE-AC-13: filter values are kept when a request fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(Response.json(EMPTY))
        .mockResolvedValue(Response.json({ detail: "boom" }, { status: 500 })),
    );
    renderAt("/", "/", <LeaderboardPage />);
    await screen.findByText(/No results loaded yet/);
    await userEvent.selectOptions(screen.getByLabelText("Tier"), "complex");
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByLabelText("Tier")).toHaveValue("complex");
  });
});
