import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

import LinkSuccess from "../LinkSuccess.jsx";
import {
  GA_CATEGORIES,
  GA_EVENTS,
  GA_FORM_EVENTS,
  GA_LABELS,
  GA_STEPS,
  MIGRATION_ANALYTICS,
} from "../../../../utils/constants.jsx";

const mockTrackEvent = vi.hoisted(() => vi.fn());

vi.mock("@gcds-core/components-react", () => ({
  GcdsContainer: ({ children }) => <div>{children}</div>,
  GcdsText: ({ children }) => <div>{children}</div>,
  GcdsDetails: ({ children }) => <div>{children}</div>,
  GcdsInput: ({ children }) => <div>{children}</div>,
  GcdsStepper: ({ children }) => <div>{children}</div>,
  GcdsLink: ({ children, href }) => <a href={href}>{children}</a>,
  GcdsCheckboxes: ({ children }) => <div>{children}</div>,
  GcdsGrid: ({ children }) => <div>{children}</div>,
  GcdsButton: ({ children, onGcdsClick }) => (
    <button onClick={onGcdsClick}>{children}</button>
  ),
  GcdsHeading: ({ children }) => <h1>{children}</h1>,
}));

vi.mock("react-router", () => ({
  useParams: () => ({ language: "en" }),
  useLocation: () => ({ pathname: "/test-path" }),
}));

vi.mock("../../../../utils/functions.jsx", () => ({
  getPageContent: (_language, page) => {
    if (page === "LinkSuccess") {
      return {
        title: "All set",
        text_1: "You linked {RP_Name}",
        text_2: "Next steps",
        list_text_1: "One",
        list_text_2: "Two",
        btn_1: "Continue",
      };
    }
    if (page === "Error") {
      return {};
    }
    return {};
  },
}));

vi.mock("../MigrationStepper.jsx", () => ({
  MigrationStepper: () => <div data-testid="migration-stepper" />,
}));

vi.mock("../../../../utils/gatag.jsx", () => ({
  useTrackPage: vi.fn(),
  useTrackEvent: () => mockTrackEvent,
}));

vi.mock("../../api/UpdateLinkState.jsx", () => ({
  updateLinkStateAPI: {
    getRPAuthUrl: vi.fn(),
  },
}));

import { updateLinkStateAPI } from "../../api/UpdateLinkState.jsx";

describe("LinkSuccess", () => {
  const originalLocation = window.location;

  beforeEach(() => {
    vi.clearAllMocks();
    updateLinkStateAPI.getRPAuthUrl.mockResolvedValue({
      rp_client_id: "rp-123",
      rp_client_name_en: "Example RP",
      rp_redirect_url: "https://rp.example.test/continue",
    });
    Object.defineProperty(window, "location", {
      value: { replace: vi.fn() },
      writable: true,
    });
  });

  afterEach(() => {
    Object.defineProperty(window, "location", {
      value: originalLocation,
      writable: true,
    });
  });

  it("renders RP name and continues to RP on click", async () => {
    render(<LinkSuccess />);

    await waitFor(() => {
      expect(updateLinkStateAPI.getRPAuthUrl).toHaveBeenCalled();
    });

    expect(screen.getByText("All set")).toBeInTheDocument();
    expect(screen.getByText("You linked Example RP")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Continue"));
    expect(mockTrackEvent).toHaveBeenNthCalledWith(1, {
      category: GA_CATEGORIES.formSubmit,
      action: GA_EVENTS.click,
      label: `${GA_LABELS.button}_MigrationConfirmation`,
      step: GA_STEPS.step2,
      rp_id: "rp-123",
      rp_name: "Example RP",
    });
    expect(mockTrackEvent).toHaveBeenNthCalledWith(2, {
      category: GA_CATEGORIES.formSubmit,
      action: GA_FORM_EVENTS.formSubmitComplete,
      label: `${GA_LABELS.button}_MigrationComplete`,
      form_id: MIGRATION_ANALYTICS.flowId,
      step: MIGRATION_ANALYTICS.steps.complete,
      type: MIGRATION_ANALYTICS.completionTypes.linked,
      status: "success",
      rp_id: "rp-123",
      rp_name: "Example RP",
    });
    expect(window.location.replace).toHaveBeenCalledWith(
      "https://rp.example.test/continue",
    );
  });
});
