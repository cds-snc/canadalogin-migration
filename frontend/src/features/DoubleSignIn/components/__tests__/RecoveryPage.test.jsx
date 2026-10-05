import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { createMemoryRouter } from "react-router";
import { RouterProvider } from "react-router/dom";
import { appRoutes } from "../../../../routes.jsx";
import { updateLinkStateAPI } from "../../api/UpdateLinkState.jsx";
import {
  getRecoveryPath,
  getRecoveryReason,
} from "../../../../utils/recoveryErrors.js";

vi.mock("../../../../components/Providers/UserProvider.tsx", () => ({
  UserProvider: () => {
    throw new Error("Recovery pages must not load the user session");
  },
}));

vi.mock("../../api/UpdateLinkState.jsx", () => ({
  updateLinkStateAPI: { getRecoveryRPDetails: vi.fn() },
}));

vi.mock("../../../../components/Layout/Header.jsx", () => ({
  default: ({ langHref, currentLang, showBreadcrumbs }) => (
    <header>
      <a href={langHref}>{currentLang === "fr" ? "English" : "Français"}</a>
      {showBreadcrumbs ? "Session breadcrumbs" : null}
    </header>
  ),
}));

vi.mock("../../../../components/Layout/Footer.jsx", () => ({
  default: () => <footer />,
}));

vi.mock("@gcds-core/components-react", () => ({
  GcdsContainer: ({ children }) => <div>{children}</div>,
  GcdsHeading: ({ children }) => <h1>{children}</h1>,
  GcdsText: ({ children }) => <p>{children}</p>,
  GcdsLink: ({ children, href }) => <a href={href}>{children}</a>,
  GcdsButton: ({ children, href, onGcdsClick }) =>
    href ? (
      <a href={href}>{children}</a>
    ) : (
      <button onClick={onGcdsClick}>{children}</button>
    ),
  GcdsIcon: () => <span />,
}));

describe("public recovery pages", () => {
  const originalLocation = window.location;
  beforeEach(() => {
    vi.clearAllMocks();
    Object.defineProperty(window, "location", {
      value: { ...originalLocation, replace: vi.fn() },
      writable: true,
    });
  });
  afterEach(() => {
    Object.defineProperty(window, "location", {
      value: originalLocation,
      writable: true,
    });
  });

  it.each([
    ["en", "missing-rp-context", "Service not found"],
    ["en", "session-ended", "Your session has ended"],
    ["en", "migration-completed", "This step is already complete"],
    ["en", "service-unavailable", "This service is temporarily unavailable"],
    ["fr", "missing-rp-context", "Service introuvable"],
    ["fr", "session-ended", "Votre session est terminée"],
    ["fr", "migration-completed", "Cette étape est déjà terminée"],
    ["fr", "service-unavailable", "Ce service est temporairement indisponible"],
  ])(
    "renders %s/%s without authentication",
    async (language, reason, title) => {
      const router = createMemoryRouter(appRoutes, {
        initialEntries: [`/${language}/error/${reason}`],
      });
      render(<RouterProvider router={router} />);

      expect(
        await screen.findByRole("heading", { level: 1, name: title }),
      ).toBeInTheDocument();
      expect(document.title).toContain(title);
      expect(document.documentElement.lang).toBe(language);
      expect(screen.getByRole("main")).toHaveAttribute("id", "main-content");
      expect(
        screen.getByRole("link", {
          name: language === "en" ? "Français" : "English",
        }),
      ).toHaveAttribute(
        "href",
        `/${language === "en" ? "fr" : "en"}/error/${reason}`,
      );
      expect(screen.queryByText("Session breadcrumbs")).not.toBeInTheDocument();
      expect(document.body.textContent).not.toMatch(
        /Redis|client.?id|HTTP|exception/i,
      );
    },
  );

  it.each([
    [
      "en",
      "This step is already complete",
      "You have already linked your old sign-in method or chosen to create a new account.",
      "To continue, return to the website of the service you want to access and sign in again.",
      "Get help with CanadaLogin",
      "https://login.canada.ca/en/users/",
    ],
    [
      "fr",
      "Cette étape est déjà terminée",
      "Vous avez déjà lié votre ancienne méthode de connexion ou choisi de créer un nouveau compte.",
      "Pour continuer, retournez sur le site Web du service auquel vous voulez accéder et connectez-vous de nouveau.",
      "Obtenir de l’aide avec ConnexionCanada",
      "https://connexion.canada.ca/fr/utilisateurs/",
    ],
  ])(
    "explains how to continue after a completed migration step in %s without offering another migration action",
    async (language, title, description, nextStep, helpLabel, helpUrl) => {
      const reason = getRecoveryReason({
        data: { code: "migration-completed" },
      });
      expect(reason).toBe("migration-completed");
      const recoveryPath = getRecoveryPath(reason, language);
      expect(recoveryPath).toBe(`/${language}/error/migration-completed`);
      const router = createMemoryRouter(appRoutes, {
        initialEntries: [recoveryPath],
      });
      render(<RouterProvider router={router} />);

      expect(
        await screen.findByRole("heading", { name: title }),
      ).toBeInTheDocument();
      const main = within(screen.getByRole("main"));
      expect(main.getByText(description)).toBeInTheDocument();
      expect(main.getByText(nextStep)).toBeInTheDocument();
      expect(main.getAllByRole("link")).toHaveLength(1);
      expect(main.getByRole("link", { name: helpLabel })).toHaveAttribute(
        "href",
        helpUrl,
      );
      expect(main.queryByRole("button")).not.toBeInTheDocument();
    },
  );

  it("uses a safe generic message for an unknown reason", async () => {
    const router = createMemoryRouter(appRoutes, {
      initialEntries: ["/en/error/unrecognized"],
    });
    render(<RouterProvider router={router} />);
    expect(
      await screen.findByRole("heading", {
        name: "This service is temporarily unavailable",
      }),
    ).toBeInTheDocument();
    expect(document.body.textContent).not.toContain("unrecognized");
  });

  it.each([
    ["en", "Access your account", "You can now continue to your account."],
    [
      "fr",
      "Accéder à votre compte",
      "Vous pouvez maintenant accéder à votre compte.",
    ],
  ])(
    "offers the same access button in %s without another migration action",
    async (language, label, nextStep) => {
      const destination = `https://service.example/${language}/continue?lang=${language}&state=preserved`;
      updateLinkStateAPI.getRecoveryRPDetails.mockResolvedValue({
        rp_client_id: "rp-123",
        rp_redirect_url: destination,
      });
      const router = createMemoryRouter(appRoutes, {
        initialEntries: [
          `/${language}/error/migration-completed?rp_client_id=rp-123`,
        ],
      });
      render(<RouterProvider router={router} />);
      const button = await screen.findByRole("button", { name: label });
      expect(screen.getByText(nextStep)).toBeInTheDocument();
      expect(updateLinkStateAPI.getRecoveryRPDetails).toHaveBeenCalledWith(
        language,
      );
      expect(
        screen.getByRole("link", {
          name: language === "en" ? "Français" : "English",
        }),
      ).toHaveAttribute(
        "href",
        `/${language === "en" ? "fr" : "en"}/error/migration-completed?rp_client_id=rp-123`,
      );
      fireEvent.click(button);
      fireEvent.click(button);
      expect(window.location.replace).toHaveBeenCalledExactlyOnceWith(
        destination,
      );
      expect(updateLinkStateAPI.getRecoveryRPDetails).toHaveBeenCalledTimes(1);
    },
  );

  it.each([
    {
      rp_client_id: "different-rp",
      rp_redirect_url: "https://service.example",
    },
    { rp_client_id: "rp-123" },
    // eslint-disable-next-line no-script-url -- Verify untrusted destinations are rejected.
    { rp_client_id: "rp-123", rp_redirect_url: "javascript:alert(1)" },
    {
      rp_client_id: "rp-123",
      rp_redirect_url: "https://user:secret@service.example",
    },
    null,
  ])(
    "keeps restart instructions if the destination is missing, unsafe or belongs to another RP",
    async (data) => {
      updateLinkStateAPI.getRecoveryRPDetails.mockResolvedValue(data);
      const router = createMemoryRouter(appRoutes, {
        initialEntries: ["/en/error/migration-completed?rp_client_id=rp-123"],
      });
      await act(async () => render(<RouterProvider router={router} />));
      expect(screen.queryByRole("button")).not.toBeInTheDocument();
      expect(
        screen.getByText(
          "To continue, return to the website of the service you want to access and sign in again.",
        ),
      ).toBeInTheDocument();
      expect(window.location.replace).not.toHaveBeenCalled();
    },
  );

  it("keeps recovery visible when RP configuration cannot be read", async () => {
    updateLinkStateAPI.getRecoveryRPDetails.mockRejectedValue({ status: 401 });
    const router = createMemoryRouter(appRoutes, {
      initialEntries: ["/en/error/migration-completed?rp_client_id=rp-123"],
    });
    await act(async () => render(<RouterProvider router={router} />));
    expect(
      screen.getByRole("heading", { name: "This step is already complete" }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(window.location.replace).not.toHaveBeenCalled();
  });

  it.each([
    "/en/error/migration-completed",
    "/en/error/session-ended?rp_client_id=rp-123",
    "/fr/error/service-unavailable?rp_client_id=rp-123",
  ])("does not request an access destination for %s", async (path) => {
    const router = createMemoryRouter(appRoutes, { initialEntries: [path] });
    await act(async () => render(<RouterProvider router={router} />));
    expect(updateLinkStateAPI.getRecoveryRPDetails).not.toHaveBeenCalled();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("ignores an older language response and uses the new language destination", async () => {
    let resolveEnglish;
    updateLinkStateAPI.getRecoveryRPDetails
      .mockReturnValueOnce(
        new Promise((resolve) => {
          resolveEnglish = resolve;
        }),
      )
      .mockResolvedValueOnce({
        rp_client_id: "rp-123",
        rp_redirect_url: "https://service.example/fr",
      });
    const router = createMemoryRouter(appRoutes, {
      initialEntries: ["/en/error/migration-completed?rp_client_id=rp-123"],
    });
    render(<RouterProvider router={router} />);
    await waitFor(() =>
      expect(updateLinkStateAPI.getRecoveryRPDetails).toHaveBeenCalledWith(
        "en",
      ),
    );
    await act(() =>
      router.navigate("/fr/error/migration-completed?rp_client_id=rp-123"),
    );
    const button = await screen.findByRole("button", {
      name: "Accéder à votre compte",
    });
    await act(async () =>
      resolveEnglish({
        rp_client_id: "rp-123",
        rp_redirect_url: "https://service.example/en",
      }),
    );
    fireEvent.click(button);
    expect(window.location.replace).toHaveBeenCalledWith(
      "https://service.example/fr",
    );
  });
});
