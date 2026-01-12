import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

import LinkSuccess from "../LinkSuccess.jsx";

vi.mock("@cdssnc/gcds-components-react", () => ({
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
    expect(window.location.replace).toHaveBeenCalledWith(
      "https://rp.example.test/continue",
    );
  });
});
