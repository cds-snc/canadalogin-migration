import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

import { MigrationStepper } from "../MigrationStepper.jsx";

vi.mock("react-router", () => ({
  useParams: () => ({ language: "en" }),
}));

vi.mock("../../../../utils/functions.jsx", () => ({
  getPageContent: () => ({
    aria_label: "Migration steps",
    step_title: "Step {n}",
    step_1: "Start",
    step_2: "Link",
    step_3: "Done",
    sr_current_prefix: "Current step:",
    sr_completed_prefix: "Completed step:",
    sr_step_prefix: "Step:",
  }),
}));

describe("MigrationStepper", () => {
  it("renders steps and marks current step", () => {
    render(<MigrationStepper currentStep={2} />);
    expect(screen.getByLabelText("Migration steps")).toBeInTheDocument();
    const current = screen.getByText("Step 2");
    expect(current.closest("li")).toHaveAttribute("aria-current", "step");
  });
});
