import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

import LinkPrompt from "../LinkPrompt.jsx";
import {
  GA_CATEGORIES,
  GA_FORM_EVENTS,
  MIGRATION_ANALYTICS,
  MIGRATION_END_POINTS,
} from "../../../../utils/constants.jsx";

let mockLanguage = "en";
const mockTrackEvent = vi.hoisted(() => vi.fn());
const mockLegacyClick = vi.hoisted(() => vi.fn());
const localizedHelpLinks = {
  en: "https://example.test/en/sign-in-method",
  fr: "https://example.test/fr/methode-connexion",
};

vi.mock("@gcds-core/components-react", () => ({
  GcdsContainer: ({ children, ...props }) => <div {...props}>{children}</div>,
  GcdsText: ({ children, ...props }) => <div {...props}>{children}</div>,
  GcdsDetails: ({ children }) => <div>{children}</div>,
  GcdsInput: ({ children }) => <div>{children}</div>,
  GcdsStepper: ({ children }) => <div>{children}</div>,
  GcdsLink: ({ children, id, href, onGcdsClick, ...props }) => (
    <a
      id={id}
      href={href}
      aria-disabled={props["aria-disabled"]}
      onClick={onGcdsClick}
    >
      {children}
    </a>
  ),
  GcdsCheckboxes: ({ children }) => <div>{children}</div>,
  GcdsGrid: ({ children }) => <div>{children}</div>,
  GcdsButton: ({ children, href, onGcdsClick, disabled, ...props }) =>
    href ? (
      <a
        href={href}
        aria-disabled={props["aria-disabled"]}
        onClick={(event) => {
          const gcdsClick = new CustomEvent("gcdsClick", {
            cancelable: true,
          });
          onGcdsClick?.(gcdsClick);
          mockLegacyClick(gcdsClick);
          // jsdom cannot navigate. Assert cancellation on the custom event.
          event.preventDefault();
        }}
      >
        {children}
      </a>
    ) : (
      <button
        disabled={disabled}
        aria-busy={props["aria-busy"]}
        onClick={onGcdsClick}
      >
        {children}
      </button>
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
    return {
      skip_failed:
        _language === "fr" ? "Veuillez réessayer." : "Please try again.",
    };
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
    skipLinking: vi.fn(),
  },
}));

import { updateLinkStateAPI } from "../../api/UpdateLinkState.jsx";
import { redirectToRecovery } from "../../../../utils/recoveryErrors.js";
import { MigrationReturnContext } from "../../utils/MigrationReturnContext.js";

vi.mock("../../../../utils/recoveryErrors.js", async (importOriginal) => ({
  ...(await importOriginal()),
  redirectToRecovery: vi.fn(),
}));

describe("LinkPrompt", () => {
  const originalLocation = window.location;
  afterEach(() =>
    Object.defineProperty(window, "location", {
      value: originalLocation,
      writable: true,
    }),
  );
  beforeEach(() => {
    vi.resetAllMocks();
    window.sessionStorage.clear();
    window.history.replaceState(null, "");
    mockLanguage = "en";
    Object.defineProperty(window, "location", {
      value: { assign: vi.fn(), replace: vi.fn() },
      writable: true,
    });
    updateLinkStateAPI.skipLinking.mockResolvedValue({
      redirect_url: "https://rp.example/continue",
    });
    document.title = "";
    updateLinkStateAPI.getRPAuthUrl.mockResolvedValue({
      rp_client_id: "rp-123",
      rp_client_name_en: "Example RP",
      rp_client_name_fr: "Exemple RP",
    });
  });

  it("waits for RP config before rendering the final page content", async () => {
    let resolveRpData;
    updateLinkStateAPI.getRPAuthUrl.mockReturnValue(
      new Promise((resolve) => {
        resolveRpData = resolve;
      }),
    );

    render(<LinkPrompt />);

    expect(screen.queryByText("Link your account")).not.toBeInTheDocument();
    expect(screen.queryByText("Link now")).not.toBeInTheDocument();

    await act(async () => {
      resolveRpData({
        rp_client_id: "rp-123",
        rp_client_name_en: "Example RP",
      });
    });

    expect(await screen.findByText("Link your account")).toBeInTheDocument();
    expect(screen.getByRole("main")).toBeInTheDocument();
    expect(screen.getByText("Continue with Example RP")).toBeInTheDocument();
  });

  it("renders RP name and builds links", async () => {
    render(<LinkPrompt />);

    await waitFor(() => {
      expect(updateLinkStateAPI.getRPAuthUrl).toHaveBeenCalled();
    });

    expect(await screen.findByText("Link your account")).toBeInTheDocument();
    expect(screen.getByText("Continue with Example RP")).toBeInTheDocument();
    expect(document.title).toBe("Link your account - CanadaLogin");

    const linkNow = screen.getByText("Link now");
    expect(linkNow).toHaveAttribute(
      "href",
      `${MIGRATION_END_POINTS.login}?lang=en`,
    );

    const skipLink = screen.getByRole("link", { name: "Skip for now" });
    expect(skipLink).toHaveAttribute("id", "skip-create-new-account-link");
    expect(skipLink).toHaveAttribute("href", "#skip-create-new-account-link");
  });

  it("builds both migration actions with the French language", async () => {
    mockLanguage = "fr";

    render(<LinkPrompt />);

    expect(await screen.findByText("Link now")).toHaveAttribute(
      "href",
      `${MIGRATION_END_POINTS.login}?lang=fr`,
    );
    fireEvent.click(screen.getByRole("link", { name: "Skip for now" }));
    await waitFor(() =>
      expect(updateLinkStateAPI.skipLinking).toHaveBeenCalledWith("fr"),
    );
  });

  it("adds RP analytics to the start migration click", async () => {
    render(<LinkPrompt />);

    await waitFor(() => {
      expect(updateLinkStateAPI.getRPAuthUrl).toHaveBeenCalled();
    });

    fireEvent.click(await screen.findByText("Link now"));

    expect(mockTrackEvent).toHaveBeenCalledWith({
      category: GA_CATEGORIES.formSubmit,
      action: GA_FORM_EVENTS.formSubmitComplete,
      label: MIGRATION_ANALYTICS.eventLabels.startedLinking,
      form_id: MIGRATION_ANALYTICS.flowId,
      type: MIGRATION_ANALYTICS.types.startedLinking,
      status: "success",
      rp_client_id: "rp-123",
      rp_name: "Example RP",
    });
  });

  it("tracks skipped migration completion with RP analytics", async () => {
    render(<LinkPrompt />);

    await waitFor(() => {
      expect(updateLinkStateAPI.getRPAuthUrl).toHaveBeenCalled();
    });

    // Returning false means the click handler cancelled native navigation.
    expect(fireEvent.click(await screen.findByText("Skip for now"))).toBe(
      false,
    );

    await waitFor(() =>
      expect(window.location.assign).toHaveBeenCalledWith(
        "https://rp.example/continue",
      ),
    );
    expect(updateLinkStateAPI.skipLinking).toHaveBeenCalledWith("en");
    expect(mockTrackEvent).toHaveBeenCalledTimes(1);
    expect(mockTrackEvent).toHaveBeenCalledWith({
      category: GA_CATEGORIES.formSubmit,
      action: GA_FORM_EVENTS.formSubmitComplete,
      label: MIGRATION_ANALYTICS.eventLabels.skippedLinking,
      form_id: MIGRATION_ANALYTICS.flowId,
      type: MIGRATION_ANALYTICS.types.skippedLinking,
      status: "success",
      rp_client_id: "rp-123",
      rp_name: "Example RP",
    });
  });

  it("keeps both choices locked when Back restores a legacy navigation", async () => {
    render(<LinkPrompt />);
    const linkNow = await screen.findByText("Link now");
    const skipLink = screen.getByRole("link", { name: "Skip for now" });

    fireEvent.click(linkNow);
    expect(mockLegacyClick.mock.lastCall[0].defaultPrevented).toBe(false);
    expect(linkNow).toHaveAttribute("aria-disabled", "true");
    expect(skipLink).toHaveAttribute("aria-disabled", "true");
    expect(skipLink.parentElement).toHaveAttribute("aria-busy", "true");

    fireEvent.click(linkNow);
    expect(mockLegacyClick.mock.lastCall[0].defaultPrevented).toBe(true);
    fireEvent.click(skipLink);
    expect(updateLinkStateAPI.skipLinking).not.toHaveBeenCalled();
    expect(mockTrackEvent).toHaveBeenCalledTimes(1);

    fireEvent(
      window,
      new PageTransitionEvent("pageshow", { persisted: false }),
    );
    fireEvent.click(linkNow);
    expect(mockLegacyClick.mock.lastCall[0].defaultPrevented).toBe(true);
    expect(mockTrackEvent).toHaveBeenCalledTimes(1);

    fireEvent(window, new PageTransitionEvent("pageshow", { persisted: true }));
    expect(linkNow).toHaveAttribute("aria-disabled", "true");
    expect(skipLink).toHaveAttribute("aria-disabled", "true");
    fireEvent.click(linkNow);
    fireEvent.click(skipLink);
    expect(mockLegacyClick.mock.lastCall[0].defaultPrevented).toBe(true);
    expect(mockTrackEvent).toHaveBeenCalledTimes(1);
    expect(updateLinkStateAPI.skipLinking).not.toHaveBeenCalled();
  });

  it("cancels legacy navigation during a pending skip, including after Back", async () => {
    let resolveSkip;
    updateLinkStateAPI.skipLinking.mockReturnValue(
      new Promise((resolve) => {
        resolveSkip = resolve;
      }),
    );
    render(<LinkPrompt />);
    const linkNow = await screen.findByText("Link now");
    const skipLink = screen.getByRole("link", { name: "Skip for now" });

    fireEvent.click(skipLink);
    fireEvent.click(linkNow);
    expect(mockLegacyClick.mock.lastCall[0].defaultPrevented).toBe(true);
    fireEvent(window, new PageTransitionEvent("pageshow", { persisted: true }));
    fireEvent.click(linkNow);
    expect(mockLegacyClick.mock.lastCall[0].defaultPrevented).toBe(true);
    expect(linkNow).toHaveAttribute("aria-disabled", "true");
    expect(skipLink).toHaveAttribute("aria-disabled", "true");
    expect(updateLinkStateAPI.skipLinking).toHaveBeenCalledTimes(1);
    expect(mockTrackEvent).not.toHaveBeenCalled();

    await act(async () =>
      resolveSkip({ redirect_url: "https://rp.example/continue" }),
    );
    expect(window.location.assign).toHaveBeenCalledTimes(1);
    expect(mockTrackEvent).toHaveBeenCalledTimes(1);
  });

  it("blocks both actions synchronously while a return status check is pending", async () => {
    let allowed = true;
    render(
      <MigrationReturnContext.Provider
        value={{
          checking: false,
          resumeVersion: 0,
          canActivate: () => allowed,
        }}
      >
        <LinkPrompt />
      </MigrationReturnContext.Provider>,
    );
    const linkNow = await screen.findByText("Link now");
    // Simulate pageshow starting a check before React has rendered checking=true.
    allowed = false;
    fireEvent.click(screen.getByRole("link", { name: "Skip for now" }));
    fireEvent.click(linkNow);
    expect(mockLegacyClick.mock.lastCall[0].defaultPrevented).toBe(true);
    expect(updateLinkStateAPI.skipLinking).not.toHaveBeenCalled();
    expect(mockTrackEvent).not.toHaveBeenCalled();
  });

  it("allows changing the choice only after the return check confirms incomplete", async () => {
    const ui = (resumeVersion) => (
      <MigrationReturnContext.Provider
        value={{ checking: false, resumeVersion, canActivate: () => true }}
      >
        <LinkPrompt />
      </MigrationReturnContext.Provider>
    );
    const { rerender } = render(ui(0));
    fireEvent.click(await screen.findByText("Link now"));
    fireEvent(window, new PageTransitionEvent("pageshow", { persisted: true }));
    fireEvent.click(screen.getByRole("link", { name: "Skip for now" }));
    expect(updateLinkStateAPI.skipLinking).not.toHaveBeenCalled();

    rerender(ui(1));
    fireEvent.click(screen.getByRole("link", { name: "Skip for now" }));
    await waitFor(() =>
      expect(updateLinkStateAPI.skipLinking).toHaveBeenCalledTimes(1),
    );
  });

  it("does not release a pending Skip POST after an incomplete return check", async () => {
    let resolveSkip;
    updateLinkStateAPI.skipLinking.mockReturnValue(
      new Promise((resolve) => {
        resolveSkip = resolve;
      }),
    );
    const ui = (resumeVersion) => (
      <MigrationReturnContext.Provider
        value={{ checking: false, resumeVersion, canActivate: () => true }}
      >
        <LinkPrompt />
      </MigrationReturnContext.Provider>
    );
    const { rerender } = render(ui(0));
    fireEvent.click(await screen.findByRole("link", { name: "Skip for now" }));
    rerender(ui(1));
    fireEvent.click(screen.getByRole("link", { name: "Skip for now" }));
    fireEvent.click(screen.getByText("Link now"));
    expect(mockLegacyClick.mock.lastCall[0].defaultPrevented).toBe(true);
    expect(updateLinkStateAPI.skipLinking).toHaveBeenCalledTimes(1);
    await act(async () =>
      resolveSkip({ redirect_url: "https://rp.example/continue" }),
    );
  });

  it("blocks duplicate actions and waits for success before tracking or redirecting", async () => {
    let resolveSkip;
    updateLinkStateAPI.skipLinking.mockReturnValue(
      new Promise((resolve) => {
        resolveSkip = resolve;
      }),
    );
    render(<LinkPrompt />);
    const skipLink = await screen.findByRole("link", { name: "Skip for now" });
    expect(fireEvent.click(skipLink)).toBe(false);
    expect(fireEvent.click(skipLink)).toBe(false);
    expect(skipLink.parentElement).toHaveAttribute("aria-busy", "true");
    expect(updateLinkStateAPI.skipLinking).toHaveBeenCalledTimes(1);
    expect(mockTrackEvent).not.toHaveBeenCalled();
    expect(window.location.assign).not.toHaveBeenCalled();
    await act(async () =>
      resolveSkip({ redirect_url: "https://rp.example/continue" }),
    );
    expect(mockTrackEvent).toHaveBeenCalledTimes(1);
    expect(window.location.assign).toHaveBeenCalledWith(
      "https://rp.example/continue",
    );
  });

  it.each(["en", "fr"])(
    "keeps a completed %s Skip locked until the return guard shows recovery",
    async (language) => {
      mockLanguage = language;
      render(<LinkPrompt />);
      const skipLink = await screen.findByRole("link", {
        name: "Skip for now",
      });
      fireEvent.click(skipLink);
      await waitFor(() =>
        expect(window.location.assign).toHaveBeenCalledTimes(1),
      );
      fireEvent(
        window,
        new PageTransitionEvent("pageshow", { persisted: true }),
      );
      fireEvent.click(skipLink);
      fireEvent.click(screen.getByText("Link now"));
      expect(mockLegacyClick.mock.lastCall[0].defaultPrevented).toBe(true);
      expect(updateLinkStateAPI.skipLinking).toHaveBeenCalledTimes(1);
      expect(window.location.assign).toHaveBeenCalledTimes(1);
      expect(mockTrackEvent).toHaveBeenCalledTimes(1);
    },
  );

  it.each([false, true])(
    "keeps an active skip locked on pageshow (persisted: %s)",
    async (persisted) => {
      let resolveSkip;
      updateLinkStateAPI.skipLinking.mockReturnValue(
        new Promise((resolve) => {
          resolveSkip = resolve;
        }),
      );
      render(<LinkPrompt />);
      const skipLink = await screen.findByRole("link", {
        name: "Skip for now",
      });

      fireEvent.click(skipLink);
      fireEvent(window, new PageTransitionEvent("pageshow", { persisted }));
      fireEvent.click(skipLink);

      expect(skipLink.parentElement).toHaveAttribute("aria-busy", "true");
      expect(updateLinkStateAPI.skipLinking).toHaveBeenCalledTimes(1);
      expect(window.location.assign).not.toHaveBeenCalled();

      await act(async () =>
        resolveSkip({ redirect_url: "https://rp.example/continue" }),
      );
      expect(window.location.assign).toHaveBeenCalledTimes(1);
    },
  );

  it.each(["en", "fr"])(
    "shows an accessible %s error and permits a manual retry",
    async (language) => {
      mockLanguage = language;
      updateLinkStateAPI.skipLinking.mockRejectedValueOnce(
        new Error("Forbidden"),
      );
      render(<LinkPrompt />);
      const skipLink = await screen.findByRole("link", {
        name: "Skip for now",
      });
      fireEvent.click(skipLink);
      expect(await screen.findByRole("alert")).toHaveTextContent(
        language === "fr" ? "Veuillez réessayer." : "Please try again.",
      );
      expect(skipLink.parentElement).toHaveAttribute("aria-busy", "false");
      expect(mockTrackEvent).not.toHaveBeenCalled();
      expect(window.location.assign).not.toHaveBeenCalled();
      fireEvent.click(skipLink);
      await waitFor(() =>
        expect(window.location.assign).toHaveBeenCalledWith(
          "https://rp.example/continue",
        ),
      );
      expect(updateLinkStateAPI.skipLinking).toHaveBeenCalledTimes(2);
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    },
  );

  it("reuses a completed skip if navigation fails and the user retries", async () => {
    window.location.assign.mockImplementationOnce(() => {
      throw new Error("Navigation failed");
    });
    render(<LinkPrompt />);
    const skipLink = await screen.findByRole("link", { name: "Skip for now" });

    fireEvent.click(skipLink);
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    fireEvent.click(skipLink);

    expect(window.location.assign).toHaveBeenCalledTimes(2);
    expect(window.location.assign).toHaveBeenLastCalledWith(
      "https://rp.example/continue",
    );
    expect(updateLinkStateAPI.skipLinking).toHaveBeenCalledTimes(1);
    expect(mockTrackEvent).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
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
      rp_client_id: "rp-123",
      rp_client_name_en: "Example RP",
      is_gckey_only: true,
    });

    render(<LinkPrompt />);

    await waitFor(() => {
      expect(updateLinkStateAPI.getRPAuthUrl).toHaveBeenCalled();
    });

    expect(await screen.findByText("Link with GCKey")).toBeInTheDocument();
    expect(
      screen.getByText("You can skip if you did not use GCKey."),
    ).toBeInTheDocument();
  });

  it.each([
    [
      { status: 400, data: { code: "missing-rp-context" } },
      "missing-rp-context",
    ],
    [
      { status: 503, data: { code: "service-unavailable" } },
      "service-unavailable",
    ],
  ])("hides linking actions when RP loading fails", async (error, reason) => {
    updateLinkStateAPI.getRPAuthUrl.mockRejectedValue(error);
    render(<LinkPrompt />);

    await waitFor(() =>
      expect(redirectToRecovery).toHaveBeenCalledWith(reason, "en"),
    );
    expect(screen.queryByText("Skip for now")).not.toBeInTheDocument();
    expect(screen.queryByText("Link now")).not.toBeInTheDocument();
  });

  it("rejects an empty RP response before showing linking actions", async () => {
    updateLinkStateAPI.getRPAuthUrl.mockResolvedValue({});
    render(<LinkPrompt />);

    await waitFor(() =>
      expect(redirectToRecovery).toHaveBeenCalledWith(
        "missing-rp-context",
        "en",
      ),
    );
    expect(screen.queryByText("Skip for now")).not.toBeInTheDocument();
  });
});
