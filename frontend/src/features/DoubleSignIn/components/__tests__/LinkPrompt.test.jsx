import { describe, it, expect, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

import LinkPrompt from "../LinkPrompt.jsx";
import {
  GA_CATEGORIES,
  GA_EVENTS,
  GA_FORM_EVENTS,
  GA_LABELS,
  GA_STEPS,
  MIGRATION_ANALYTICS,
  MIGRATION_END_POINTS,
} from "../../../../utils/constants.jsx";

let mockLanguage = "en";
const mockTrackEvent = vi.hoisted(() => vi.fn());
const localizedHelpLinks = {
  en: "https://example.test/en/sign-in-method",
  fr: "https://example.test/fr/methode-connexion",
};

vi.mock("@gcds-core/components-react", () => ({
  GcdsContainer: ({ children }) => <div>{children}</div>,
  GcdsText: ({ children }) => <div>{children}</div>,
  GcdsDetails: ({ children }) => <div>{children}</div>,
  GcdsInput: ({ children }) => <div>{children}</div>,
  GcdsStepper: ({ children }) => <div>{children}</div>,
  GcdsLink: ({ children, href, onGcdsClick }) => (
    <a
      href={href}
      onClick={(event) => {
        event.preventDefault();
        onGcdsClick?.(event);
      }}
    >
      {children}
    </a>
  ),
  GcdsCheckboxes: ({ children }) => <div>{children}</div>,
  GcdsGrid: ({ children }) => <div>{children}</div>,
  GcdsButton: ({ children, href, onGcdsClick }) => (
    <a
      href={href}
      onClick={(event) => {
        event.preventDefault();
        onGcdsClick?.(event);
      }}
    >
      {children}
    </a>
  ),
  GcdsHeading: ({ children }) => <h1>{children}</h1>,
  GcdsIcon: () => <div />,
  GcdsNotice: ({ children }) => <div>{children}</div>,
}));

vi.mock("react-router", () => ({
  useParams: () => ({ language: mockLanguage }),
  useLocation: () => ({ pathname: "/test-path" }),
}));

vi.mock("../../../../utils/functions.jsx", () => ({
  getPageContent: (_language, page) => {
    if (page === "LinkPrompt") {
      return {
        title: "Link your account",
        text_2: "Continue with {RP_Name}",
        text_3: "You can link now.",
        btn_1: "Link now",
        btn_1_gckey_only: "Link with GCKey",
        notice_title: "Notice",
        link_1: "Learn more",
        link_1_url: localizedHelpLinks[_language],
        subtitle: "Skip linking {RP_Name}",
        text_4: "You can skip.",
        text_4_gckey_only: "You can skip if you did not use GCKey.",
        link_2: "Skip for now",
      };
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

describe("LinkPrompt", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockLanguage = "en";
    updateLinkStateAPI.getRPAuthUrl.mockResolvedValue({
      rp_client_id: "rp-123",
      rp_client_name_en: "Example RP",
      rp_client_name_fr: "Exemple RP",
    });
  });

  it("renders RP name and builds links", async () => {
    render(<LinkPrompt />);

    await waitFor(() => {
      expect(updateLinkStateAPI.getRPAuthUrl).toHaveBeenCalled();
    });

    expect(screen.getByText("Link your account")).toBeInTheDocument();
    expect(screen.getByText("Continue with Example RP")).toBeInTheDocument();

    const linkNow = screen.getByText("Link now");
    expect(linkNow).toHaveAttribute(
      "href",
      `${MIGRATION_END_POINTS.login}?lang=en`,
    );

    const skipLink = screen.getByText("Skip for now");
    expect(skipLink).toHaveAttribute("href", MIGRATION_END_POINTS.skip);
  });

  it("adds RP analytics to the start migration click", async () => {
    render(<LinkPrompt />);

    await waitFor(() => {
      expect(updateLinkStateAPI.getRPAuthUrl).toHaveBeenCalled();
    });

    fireEvent.click(screen.getByText("Link now"));

    expect(mockTrackEvent).toHaveBeenCalledWith({
      category: GA_CATEGORIES.formSubmit,
      action: GA_EVENTS.click,
      label: `${GA_LABELS.button}_StartMigration`,
      form_id: MIGRATION_ANALYTICS.flowId,
      step: GA_STEPS.step1,
      rp_id: "rp-123",
      rp_name: "Example RP",
    });
  });

  it("tracks skipped migration completion with RP analytics", async () => {
    render(<LinkPrompt />);

    await waitFor(() => {
      expect(updateLinkStateAPI.getRPAuthUrl).toHaveBeenCalled();
    });

    fireEvent.click(screen.getByText("Skip for now"));

    expect(mockTrackEvent).toHaveBeenNthCalledWith(1, {
      category: GA_CATEGORIES.formSubmit,
      action: GA_EVENTS.click,
      label: `${GA_LABELS.link}_SkipMigration`,
      form_id: MIGRATION_ANALYTICS.flowId,
      step: GA_STEPS.step1,
      rp_id: "rp-123",
      rp_name: "Example RP",
    });
    expect(mockTrackEvent).toHaveBeenNthCalledWith(2, {
      category: GA_CATEGORIES.formSubmit,
      action: GA_FORM_EVENTS.formSubmitComplete,
      label: `${GA_LABELS.link}_MigrationComplete`,
      form_id: MIGRATION_ANALYTICS.flowId,
      step: MIGRATION_ANALYTICS.steps.complete,
      type: MIGRATION_ANALYTICS.completionTypes.skipped,
      status: "success",
      rp_id: "rp-123",
      rp_name: "Example RP",
    });
  });

  it("links the info notice to the English sign-in method help page", async () => {
    render(<LinkPrompt />);

    const learnMoreLink = await screen.findByText("Learn more");

    expect(learnMoreLink).toHaveAttribute("href", localizedHelpLinks.en);
  });

  it("links the info notice to the French sign-in method help page", async () => {
    mockLanguage = "fr";

    render(<LinkPrompt />);

    const learnMoreLink = await screen.findByText("Learn more");

    expect(learnMoreLink).toHaveAttribute("href", localizedHelpLinks.fr);
  });

  it("uses GCKey-only text when RP config is gckey only", async () => {
    updateLinkStateAPI.getRPAuthUrl.mockResolvedValue({
      rp_client_name_en: "Example RP",
      is_gckey_only: true,
    });

    render(<LinkPrompt />);

    await waitFor(() => {
      expect(updateLinkStateAPI.getRPAuthUrl).toHaveBeenCalled();
    });

    expect(screen.getByText("Link with GCKey")).toBeInTheDocument();
    expect(
      screen.getByText("You can skip if you did not use GCKey."),
    ).toBeInTheDocument();
  });
});
