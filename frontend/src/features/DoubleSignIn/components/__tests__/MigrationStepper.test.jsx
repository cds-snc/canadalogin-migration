import { beforeEach, describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

import { MigrationStepper } from "../MigrationStepper.jsx";

let mockLanguage = "en";

vi.mock("react-router", () => ({
  useParams: () => ({ language: mockLanguage }),
}));

vi.mock("../../../../utils/functions.jsx", () => ({
  getPageContent: (language) =>
    language === "fr"
      ? {
          aria_label: "Étapes de migration",
          step_title: "Étape {n}",
          step_1: "Commencer",
          step_2: "Lier",
          step_3: "Terminer",
          sr_current_prefix: "Étape actuelle :",
          sr_completed_prefix: "Étape terminée :",
          sr_step_prefix: "Étape :",
        }
      : {
          aria_label: "Migration steps",
          step_title: "Step {n}",
          step_1: "Start",
          step_2: "Link",
          step_3: "Done",
          sr_current_prefix: "Current step:",
          sr_completed_prefix: "Completed step:",
          sr_step_prefix: "Step:",
        },
}));

describe("MigrationStepper", () => {
  beforeEach(() => {
    mockLanguage = "en";
  });

  it("renders steps and marks current step", () => {
    render(<MigrationStepper currentStep={2} />);
    expect(screen.getByLabelText("Migration steps")).toBeInTheDocument();
    const current = screen.getByText("Step 2");
    expect(current.closest("li")).toHaveAttribute("aria-current", "step");
    expect(screen.getByText("Link")).toBeInTheDocument();
  });

  it("hides descriptions when showDescriptions is false", () => {
    render(<MigrationStepper currentStep={2} showDescriptions={false} />);
    expect(screen.queryByText("Start")).not.toBeInTheDocument();
    expect(screen.queryByText("Link")).not.toBeInTheDocument();
    expect(screen.queryByText("Done")).not.toBeInTheDocument();
  });

  it("renders French desktop step title and descriptions", () => {
    mockLanguage = "fr";
    render(<MigrationStepper currentStep={2} />);
    expect(screen.getByLabelText("Étapes de migration")).toBeInTheDocument();
    expect(screen.getByText("Étape 2")).toBeInTheDocument();
    expect(screen.getByText("Lier")).toBeInTheDocument();
  });
});
