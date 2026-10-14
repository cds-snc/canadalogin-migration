import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { createElement } from "react";
import { createMemoryRouter } from "react-router";
import { RouterProvider } from "react-router/dom";

import RootLayout from "../../../../components/Layout/RootLayout.jsx";
import { LanguageProvider } from "../../../../components/Providers/LanguageProvider.tsx";
import en from "../../../../locales/en/en.json";
import fr from "../../../../locales/fr/fr.json";
import { MIGRATION_END_POINTS } from "../../../../utils/constants.jsx";
import { redirectToRecovery } from "../../../../utils/recoveryErrors.js";
import { updateLinkStateAPI } from "../../api/UpdateLinkState.jsx";
import LinkPrompt from "../LinkPrompt.jsx";

vi.mock("@gcds-core/components-react", () => ({
  GcdsContainer: ({ children, id, role }) => (
    <div id={id} role={role}>
      {children}
    </div>
  ),
  GcdsText: ({ children }) => <p>{children}</p>,
  GcdsHeading: ({ children, tag }) => createElement(tag, {}, children),
  GcdsLink: ({ children, href }) => <a href={href}>{children}</a>,
  GcdsButton: ({ children, href }) => <a href={href}>{children}</a>,
  GcdsNotice: ({ children }) => <aside>{children}</aside>,
  GcdsHeader: ({ children, langHref, lang }) => (
    <header>
      <a href={langHref}>{lang === "fr" ? "English" : "Français"}</a>
      {children}
    </header>
  ),
}));

vi.mock("../../../../components/Layout/TopNav.jsx", () => ({
  default: () => null,
}));
vi.mock("../../../../components/Layout/Breadcrumbs.jsx", () => ({
  default: () => null,
}));
vi.mock("../../../../components/Layout/Footer.jsx", () => ({
  default: () => null,
}));
vi.mock("../../../../utils/gatag.jsx", () => ({
  useTrackPage: vi.fn(),
  useTrackEvent: () => vi.fn(),
}));
vi.mock("../../api/UpdateLinkState.jsx", () => ({
  updateLinkStateAPI: { getRPAuthUrl: vi.fn(), skipLinking: vi.fn() },
}));
vi.mock("../../../../utils/recoveryErrors.js", async (importOriginal) => ({
  ...(await importOriginal()),
  redirectToRecovery: vi.fn(),
}));

const content = { en: en.LinkPrompt, fr: fr.LinkPrompt };
const rp = {
  rp_client_id: "flow-b-rp",
  rp_client_name_en: "Example service",
  rp_client_name_fr: "Service exemple",
  acr_values: "gckey",
  is_gckey_only: true,
};

function renderPrompt(language) {
  const router = createMemoryRouter(
    [
      {
        path: "/:language/link",
        element: (
          <LanguageProvider>
            <RootLayout />
          </LanguageProvider>
        ),
        children: [{ index: true, element: <LinkPrompt /> }],
      },
    ],
    { initialEntries: [`/${language}/link`] },
  );
  render(<RouterProvider router={router} />);
  return router;
}

async function switchLanguage(router, from, to) {
  const toggle = screen.getByRole("link", {
    name: from === "fr" ? "English" : "Français",
  });
  expect(toggle).toHaveAttribute("href", `/${to}/link`);
  // jsdom cannot follow the header's full-document navigation. Follow the
  // actual href through the router so route parameters and effects update.
  await act(() => router.navigate(toggle.getAttribute("href")));
}

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

describe("LinkPrompt language changes", () => {
  beforeEach(() => vi.resetAllMocks());
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it.each([
    ["fr", "en", true],
    ["en", "fr", true],
    ["fr", "en", false],
    ["en", "fr", false],
  ])(
    "preserves provider selection from %s to %s (GCKey only: %s) while configuration reloads",
    async (from, to, isGcKeyOnly) => {
      const config = {
        ...rp,
        acr_values: isGcKeyOnly ? "gckey" : "",
        is_gckey_only: isGcKeyOnly,
      };
      const nextConfig = deferred();
      updateLinkStateAPI.getRPAuthUrl
        .mockResolvedValueOnce(config)
        .mockReturnValueOnce(nextConfig.promise);
      const router = renderPrompt(from);
      const buttonKey = isGcKeyOnly ? "btn_1_gckey_only" : "btn_1";
      const helpKey = isGcKeyOnly ? "text_4_gckey_only" : "text_4";

      expect(
        await screen.findByRole("link", { name: content[from][buttonKey] }),
      ).toHaveAttribute("href", `${MIGRATION_END_POINTS.login}?lang=${from}`);

      await switchLanguage(router, from, to);

      expect(screen.queryByRole("main")).not.toBeInTheDocument();
      expect(document.body).not.toHaveTextContent(content[to].btn_1);
      await act(async () => nextConfig.resolve(config));

      expect(
        await screen.findByRole("link", { name: content[to][buttonKey] }),
      ).toHaveAttribute("href", `${MIGRATION_END_POINTS.login}?lang=${to}`);
      expect(screen.getByText(content[to][helpKey])).toBeInTheDocument();
      expect(
        screen.getByRole("heading", { level: 1, name: content[to].title }),
      ).toBeInTheDocument();
      expect(document.documentElement.lang).toBe(to);
      expect(screen.getByRole("main")).toHaveTextContent(
        config[`rp_client_name_${to}`],
      );
      if (isGcKeyOnly) {
        expect(screen.getByRole("main")).not.toHaveTextContent("Interac");
      }
      expect(updateLinkStateAPI.getRPAuthUrl).toHaveBeenCalledTimes(2);
      expect(redirectToRecovery).not.toHaveBeenCalled();
    },
  );

  it.each([
    ["fr", "en", "rejected"],
    ["en", "fr", "rejected"],
    ["fr", "en", "empty"],
    ["en", "fr", "empty"],
  ])(
    "never offers Interac when switching %s to %s with a %s configuration response",
    async (from, to, response) => {
      vi.spyOn(console, "error").mockImplementation(() => {});
      const nextConfig = deferred();
      updateLinkStateAPI.getRPAuthUrl
        .mockResolvedValueOnce(rp)
        .mockReturnValueOnce(nextConfig.promise);
      const router = renderPrompt(from);
      await screen.findByRole("link", {
        name: content[from].btn_1_gckey_only,
      });

      await switchLanguage(router, from, to);
      await act(async () => {
        if (response === "empty") nextConfig.resolve({});
        else nextConfig.reject({ status: 503 });
      });

      await waitFor(() =>
        expect(redirectToRecovery).toHaveBeenCalledWith(
          response === "empty" ? "missing-rp-context" : "service-unavailable",
          to,
        ),
      );
      expect(screen.queryByRole("main")).not.toBeInTheDocument();
      expect(document.body).not.toHaveTextContent("Interac");
      expect(
        screen.queryByRole("link", { name: content[to].link_2 }),
      ).not.toBeInTheDocument();
    },
  );
});
