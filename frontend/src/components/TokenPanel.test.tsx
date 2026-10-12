import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { modelDetail } from "../test/fixtures";
import { TokenPanel } from "./TokenPanel";

describe("TokenPanel (S2 token panel)", () => {
  it("FE-AC-04: estimated values carry an 'estimated' badge", () => {
    render(<TokenPanel detail={modelDetail()} />);
    const avgOutput = screen.getByTestId("mid-avg-output");
    expect(avgOutput).toHaveTextContent("420");
    expect(within(avgOutput).getByText("estimated")).toBeInTheDocument();
    // Reported values have no badge.
    expect(within(screen.getByTestId("simple-avg-output")).queryByText("estimated")).toBeNull();
  });

  it("FE-AC-04: unreported values show 'n/a' and never 0", () => {
    render(<TokenPanel detail={modelDetail()} />);
    for (const id of ["complex-avg-task-input", "complex-avg-overhead", "complex-total-overhead"]) {
      const cell = screen.getByTestId(id);
      expect(cell).toHaveTextContent(/^n\/a$/);
      expect(cell.textContent).not.toMatch(/\b0\b/);
    }
  });

  it("FE-AC-05: task tokens and overhead tokens are shown separately for each tier", () => {
    render(<TokenPanel detail={modelDetail()} />);
    for (const tier of ["simple", "mid", "complex"]) {
      expect(screen.getByTestId(`tokens-${tier}`)).toBeInTheDocument();
      expect(screen.getByTestId(`${tier}-avg-task-input`)).toBeInTheDocument();
      expect(screen.getByTestId(`${tier}-avg-overhead`)).toBeInTheDocument();
    }
    // Task input = reported input (2,100) minus overhead (1,900).
    expect(screen.getByTestId("simple-avg-task-input")).toHaveTextContent(/^200$/);
    expect(screen.getByTestId("simple-avg-overhead")).toHaveTextContent(/^1,900$/);
    expect(screen.getByTestId("simple-total-task-input")).toHaveTextContent(/^600$/);
  });
});
