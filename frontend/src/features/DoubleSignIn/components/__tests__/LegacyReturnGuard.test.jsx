import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { StrictMode, useContext, useEffect } from "react";
import { createBrowserRouter, Outlet, useParams } from "react-router";
import { RouterProvider } from "react-router/dom";
import { appRoutes } from "../../../../routes.jsx";
import { updateLinkStateAPI } from "../../api/UpdateLinkState.jsx";
import { MigrationReturnContext } from "../../utils/MigrationReturnContext.js";
import {
  getPromptEntry,
  preparePromptEntry,
  rememberPromptRpId,
} from "../../utils/legacyNavigation.js";

const loadSession = vi.hoisted(() => vi.fn());
const contextSnapshot = vi.hoisted(() => ({ current: null }));
vi.mock("../../../../components/Providers/UserProvider.tsx", () => ({
  UserProvider: function MockUserProvider() {
    useEffect(() => {
      loadSession();
    }, []);
    return <Outlet />;
  },
}));
vi.mock("../../../../components/Layout/RootLayout.jsx", () => ({
  default: () => <Outlet />,
}));
vi.mock("../../../../components/Layout/Loading.jsx", () => ({
  default: ({ text }) => <p role="status">{text}</p>,
}));
vi.mock("../../api/UpdateLinkState.jsx", () => ({
  updateLinkStateAPI: { getMigrationStatus: vi.fn() },
}));
vi.mock("../LinkPrompt.jsx", () => ({
  default: function MockPrompt() {
    const { language } = useParams();
    const context = useContext(MigrationReturnContext);
    contextSnapshot.current = context;
    useEffect(() => {
      rememberPromptRpId("rp-123");
    }, [language]);
    return <h1>Choices</h1>;
  },
}));
vi.mock("../LinkSuccess.jsx", () => ({ default: () => <h1>Success</h1> }));
vi.mock("../LegacyLanguageSync.jsx", () => ({
  default: () => <h1>Language sync</h1>,
}));
vi.mock("../RecoveryPage.jsx", () => ({
  default: function MockRecoveryPage() {
    const { language, reason } = useParams();
    return <h1>{`${language}: ${reason}`}</h1>;
  },
}));

const routers = [];
const originalNavigationEntries = window.performance.getEntriesByType;
function renderRoute(path, strict = false) {
  window.history.replaceState(window.history.state, "", path);
  const router = createBrowserRouter(appRoutes);
  routers.push(router);
  const element = <RouterProvider router={router} />;
  render(strict ? <StrictMode>{element}</StrictMode> : element);
  return router;
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
function restorePage() {
  fireEvent(window, new PageTransitionEvent("pageshow", { persisted: true }));
}

describe("checking a returned migration prompt", () => {
  beforeEach(() => {
    window.history.replaceState(null, "", "/");
    Object.defineProperty(window.performance, "getEntriesByType", {
      configurable: true,
      value: vi.fn(() => []),
    });
    vi.clearAllMocks();
    contextSnapshot.current = null;
    updateLinkStateAPI.getMigrationStatus
      .mockReset()
      .mockResolvedValue({ rp_client_id: "rp-123", completed: false });
  });
  afterEach(() => {
    cleanup();
    routers.splice(0).forEach((router) => router.dispose());
    Object.defineProperty(window.performance, "getEntriesByType", {
      configurable: true,
      value: originalNavigationEntries,
    });
  });

  it.each(["/", "/en", "/fr"])(
    "keeps one provider mount during the fresh redirect from %s",
    async (path) => {
      renderRoute(path);
      expect(
        await screen.findByRole("heading", { name: "Choices" }),
      ).toBeVisible();
      expect(loadSession).toHaveBeenCalledTimes(1);
      expect(updateLinkStateAPI.getMigrationStatus).not.toHaveBeenCalled();
    },
  );

  it.each(["en", "fr"])(
    "checks cached %s returns before restoring choices, without another profile load",
    async (language) => {
      const pending = deferred();
      updateLinkStateAPI.getMigrationStatus.mockReturnValueOnce(
        pending.promise,
      );
      const router = renderRoute(`/${language}/link`);
      const choices = await screen.findByRole("heading", { name: "Choices" });
      fireEvent(
        window,
        new PageTransitionEvent("pageshow", { persisted: false }),
      );
      expect(updateLinkStateAPI.getMigrationStatus).not.toHaveBeenCalled();
      act(() => {
        window.dispatchEvent(
          new PageTransitionEvent("pageshow", { persisted: true }),
        );
        expect(contextSnapshot.current.canActivate()).toBe(false);
      });
      expect(choices).not.toBeVisible();
      expect(choices.closest("[inert]")).not.toBeNull();
      expect(screen.getByRole("status")).toHaveTextContent(
        language === "fr" ? "Chargement..." : "Loading...",
      );
      restorePage();
      await waitFor(() =>
        expect(updateLinkStateAPI.getMigrationStatus).toHaveBeenCalledTimes(1),
      );
      expect(loadSession).toHaveBeenCalledTimes(1);

      await act(async () =>
        pending.resolve({ rp_client_id: "rp-123", completed: false }),
      );
      expect(choices).toBeVisible();
      expect(contextSnapshot.current.canActivate()).toBe(true);
      expect(contextSnapshot.current.resumeVersion).toBe(1);
      expect(loadSession).toHaveBeenCalledTimes(1);
      expect(getPromptEntry()).toEqual({ visited: true, rpClientId: "rp-123" });

      // An earlier incomplete result must never authorize a later return.
      updateLinkStateAPI.getMigrationStatus.mockResolvedValueOnce({
        rp_client_id: "rp-123",
        completed: true,
      });
      restorePage();
      expect(
        await screen.findByRole("heading", {
          name: `${language}: migration-completed`,
        }),
      ).toBeVisible();
      expect(router.state.historyAction).toBe("REPLACE");
      expect(router.state.location.search).toBe("?rp_client_id=rp-123");
      expect(updateLinkStateAPI.getMigrationStatus).toHaveBeenCalledTimes(2);
      expect(loadSession).toHaveBeenCalledTimes(1);
    },
  );

  it.each(["/en/link", "/fr/link", "/en", "/"])(
    "checks a cold marked return at %s before mounting UserProvider",
    async (path) => {
      rememberPromptRpId("rp-123");
      const pending = deferred();
      updateLinkStateAPI.getMigrationStatus.mockReturnValueOnce(
        pending.promise,
      );
      renderRoute(path);
      expect(screen.getByRole("status")).toBeVisible();
      expect(loadSession).not.toHaveBeenCalled();
      expect(screen.queryByText("Choices")).not.toBeInTheDocument();
      await act(async () =>
        pending.resolve({ rp_client_id: "rp-123", completed: false }),
      );
      expect(
        await screen.findByRole("heading", { name: "Choices" }),
      ).toBeVisible();
      expect(loadSession).toHaveBeenCalledTimes(1);
      expect(updateLinkStateAPI.getMigrationStatus).toHaveBeenCalledTimes(1);
    },
  );

  it.each(["en", "fr"])(
    "blocks a completed cold %s return without loading the session",
    async (language) => {
      rememberPromptRpId("rp-123");
      updateLinkStateAPI.getMigrationStatus.mockResolvedValue({
        rp_client_id: "rp-123",
        completed: true,
      });
      renderRoute(`/${language}/link`);
      expect(
        await screen.findByRole("heading", {
          name: `${language}: migration-completed`,
        }),
      ).toBeVisible();
      expect(loadSession).not.toHaveBeenCalled();
    },
  );

  it("checks an older language entry and still permits a genuinely fresh service entry", async () => {
    rememberPromptRpId("rp-123");
    const englishEntry = window.history.state;
    window.history.replaceState(null, "");
    rememberPromptRpId("rp-123");
    window.history.replaceState(englishEntry, "");
    updateLinkStateAPI.getMigrationStatus.mockResolvedValue({
      rp_client_id: "rp-123",
      completed: true,
    });
    renderRoute("/en/link");
    expect(
      await screen.findByRole("heading", { name: "en: migration-completed" }),
    ).toBeVisible();
    expect(loadSession).not.toHaveBeenCalled();
    cleanup();
    routers.splice(0).forEach((router) => router.dispose());

    window.history.replaceState(null, "");
    renderRoute("/en/link");
    expect(
      await screen.findByRole("heading", { name: "Choices" }),
    ).toBeVisible();
    expect(updateLinkStateAPI.getMigrationStatus).toHaveBeenCalledTimes(1);
    expect(loadSession).toHaveBeenCalledTimes(1);
  });

  it("starts a fresh read after leaving during a pending check and ignores the earlier result", async () => {
    const earlier = deferred();
    const returned = deferred();
    updateLinkStateAPI.getMigrationStatus
      .mockReturnValueOnce(earlier.promise)
      .mockReturnValueOnce(returned.promise);
    renderRoute("/en/link");
    const choices = await screen.findByRole("heading", { name: "Choices" });
    restorePage();
    await waitFor(() =>
      expect(updateLinkStateAPI.getMigrationStatus).toHaveBeenCalledTimes(1),
    );

    fireEvent(window, new PageTransitionEvent("pagehide", { persisted: true }));
    restorePage();
    await waitFor(() =>
      expect(updateLinkStateAPI.getMigrationStatus).toHaveBeenCalledTimes(2),
    );
    expect(updateLinkStateAPI.getMigrationStatus).toHaveBeenLastCalledWith({
      forceFresh: true,
    });
    await act(async () =>
      earlier.resolve({ rp_client_id: "rp-123", completed: false }),
    );
    expect(choices).not.toBeVisible();
    expect(contextSnapshot.current.canActivate()).toBe(false);
    expect(contextSnapshot.current.resumeVersion).toBe(0);
    restorePage();
    expect(updateLinkStateAPI.getMigrationStatus).toHaveBeenCalledTimes(2);

    await act(async () =>
      returned.resolve({ rp_client_id: "rp-123", completed: true }),
    );
    expect(
      await screen.findByRole("heading", { name: "en: migration-completed" }),
    ).toBeVisible();
    expect(loadSession).toHaveBeenCalledTimes(1);
  });

  it("ignores an old response after navigating to a fresh entry", async () => {
    const pending = deferred();
    updateLinkStateAPI.getMigrationStatus.mockReturnValueOnce(pending.promise);
    const router = renderRoute("/en/link");
    await screen.findByRole("heading", { name: "Choices" });
    restorePage();
    await waitFor(() =>
      expect(updateLinkStateAPI.getMigrationStatus).toHaveBeenCalledTimes(1),
    );
    await act(() => router.navigate("/fr/link"));
    expect(screen.getByRole("heading", { name: "Choices" })).toBeVisible();
    await act(async () =>
      pending.resolve({ rp_client_id: "rp-123", completed: true }),
    );
    expect(screen.getByRole("heading", { name: "Choices" })).toBeVisible();
    expect(contextSnapshot.current.canActivate()).toBe(true);
    expect(loadSession).toHaveBeenCalledTimes(1);
  });

  it("shares the cold status check across StrictMode effect replay", async () => {
    rememberPromptRpId("rp-123");
    renderRoute("/en/link", true);
    expect(
      await screen.findByRole("heading", { name: "Choices" }),
    ).toBeVisible();
    expect(updateLinkStateAPI.getMigrationStatus).toHaveBeenCalledTimes(1);
  });

  it.each([
    [{ rp_client_id: "different-rp", completed: false }, "missing-rp-context"],
    [{ rp_client_id: "rp-123" }, "service-unavailable"],
  ])(
    "does not reopen choices for invalid or mismatched status",
    async (status, reason) => {
      rememberPromptRpId("rp-123");
      updateLinkStateAPI.getMigrationStatus.mockResolvedValue(status);
      renderRoute("/en/link");
      expect(
        await screen.findByRole("heading", { name: `en: ${reason}` }),
      ).toBeVisible();
      expect(loadSession).not.toHaveBeenCalled();
    },
  );

  it.each([
    [
      { status: 401, data: { code: "authentication-required" } },
      "session-ended",
    ],
    [{ response: { status: 401 } }, "session-ended"],
    [
      { status: 503, data: { code: "service-unavailable" } },
      "service-unavailable",
    ],
    [new Error("Network unavailable"), "service-unavailable"],
  ])(
    "shows recovery when the return status cannot be read",
    async (error, reason) => {
      rememberPromptRpId("rp-123");
      updateLinkStateAPI.getMigrationStatus.mockRejectedValue(error);
      renderRoute("/en/link");
      expect(
        await screen.findByRole("heading", { name: `en: ${reason}` }),
      ).toBeVisible();
      expect(loadSession).not.toHaveBeenCalled();
      expect(updateLinkStateAPI.getMigrationStatus).toHaveBeenCalledTimes(1);
    },
  );

  it("does not query another RP when a returned marker has no RP id", async () => {
    preparePromptEntry();
    renderRoute("/en/link");
    expect(
      await screen.findByRole("heading", { name: "en: missing-rp-context" }),
    ).toBeVisible();
    expect(updateLinkStateAPI.getMigrationStatus).not.toHaveBeenCalled();
    expect(loadSession).not.toHaveBeenCalled();
  });

  it.each(["back_forward", "reload"])(
    "fails closed when a cold %s document has lost its prompt marker",
    async (type) => {
      window.performance.getEntriesByType.mockReturnValue([{ type }]);
      renderRoute("/en/link");
      expect(
        await screen.findByRole("heading", {
          name: "en: missing-rp-context",
        }),
      ).toBeVisible();
      expect(updateLinkStateAPI.getMigrationStatus).not.toHaveBeenCalled();
      expect(loadSession).not.toHaveBeenCalled();
    },
  );

  it("does not reuse document navigation timing for later in-app redirects", async () => {
    window.performance.getEntriesByType.mockReturnValue([{ type: "reload" }]);
    const router = renderRoute("/en/link/success");
    expect(
      await screen.findByRole("heading", { name: "Success" }),
    ).toBeVisible();
    await act(() => router.navigate("/fr"));
    expect(
      await screen.findByRole("heading", { name: "Choices" }),
    ).toBeVisible();
    expect(loadSession).toHaveBeenCalledTimes(1);
    expect(updateLinkStateAPI.getMigrationStatus).not.toHaveBeenCalled();
  });

  it.each([
    ["/en/link/success", "Success"],
    ["/fr/link/lang-sync", "Language sync"],
  ])("leaves normal completion route %s unaffected", async (path, heading) => {
    rememberPromptRpId("rp-123");
    renderRoute(path);
    expect(await screen.findByRole("heading", { name: heading })).toBeVisible();
    expect(updateLinkStateAPI.getMigrationStatus).not.toHaveBeenCalled();
    expect(loadSession).toHaveBeenCalledTimes(1);
  });
});
