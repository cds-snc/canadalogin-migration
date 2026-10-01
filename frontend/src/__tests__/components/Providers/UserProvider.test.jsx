import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { createMemoryRouter } from "react-router";
import { RouterProvider } from "react-router/dom";
import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";
import { UserProvider } from "../../../components/Providers/UserProvider.tsx";
import { PrivateRoute } from "../../../components/Providers/PrivateRoute.jsx";
import { authService } from "../../../services/authService.jsx";
import { handleApiError } from "../../../utils/apiErrorHandler.js";

const sse = vi.hoisted(() => ({
  listener: null,
  source: { close: vi.fn() },
  connect: vi.fn(),
}));

vi.mock("@react-nano/use-event-source", () => ({
  useEventSource: (url) => {
    sse.connect(url);
    return [url ? sse.source : null, url ? "open" : "closed"];
  },
  useEventSourceListener: (_source, _types, listener) => {
    sse.listener = listener;
  },
}));

vi.mock("../../../components/Layout/Loading.jsx", () => ({
  default: () => <p>Loading</p>,
}));

vi.mock("../../../components/Layout/SessionTimeoutModal.jsx", () => ({
  default: ({ isOpen, onKeepSession, onLogout }) =>
    isOpen ? (
      <div>
        <button onClick={onKeepSession}>Keep session</button>
        <button onClick={onLogout}>Log out</button>
      </div>
    ) : null,
}));

const profile = { id: "user123", userName: "test", active: true };
const originalLocation = window.location;

function renderFlow(entry = "/fr/link", sessionState) {
  const url = new URL(entry, "http://localhost:3000");
  Object.assign(window.location, {
    pathname: url.pathname,
    search: url.search,
  });
  const router = createMemoryRouter(
    [
      { path: "/:language/error/:reason", element: <p>Recovery page</p> },
      {
        path: "/:language",
        element: (
          <UserProvider initialSessionTimeoutState={sessionState}>
            <PrivateRoute />
          </UserProvider>
        ),
        children: [{ path: "link", element: <p>Migration page</p> }],
      },
    ],
    { initialEntries: [entry] },
  );
  render(<RouterProvider router={router} />);
  return router;
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.spyOn(authService, "get_my_user_profile").mockResolvedValue({
    data: profile,
  });
  vi.spyOn(authService, "keepAlive").mockResolvedValue({
    data: { expire: Date.now() / 1000 + 600 },
  });
  vi.spyOn(authService, "logout").mockResolvedValue({
    data: { redirect_url: "https://logout.example.test/" },
  });
  Object.defineProperty(window, "location", {
    value: { href: "original", pathname: "/fr/link", search: "" },
    writable: true,
  });
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.restoreAllMocks();
  Object.defineProperty(window, "location", {
    value: originalLocation,
    writable: true,
  });
});

describe("profile and session recovery", () => {
  it.each([
    [400, "missing-rp-context"],
    [401, "session-ended"],
    [503, "service-unavailable"],
  ])("shows the %s recovery without starting OIDC", async (status, code) => {
    authService.get_my_user_profile.mockRejectedValue({
      status,
      data: { code },
    });
    const router = renderFlow();
    await waitFor(() =>
      expect(router.state.location.pathname).toBe(`/fr/error/${code}`),
    );
    expect(window.location.href).toBe("original");
    expect(screen.queryByText("Migration page")).toBeNull();
    expect(sse.connect.mock.calls.every(([url]) => !url)).toBe(true);
  });

  it("does not let PrivateRoute overwrite an API503 recovery with login", async () => {
    authService.get_my_user_profile.mockImplementation(async () => {
      handleApiError({
        response: { status: 503, data: { code: "service-unavailable" } },
      });
    });
    const router = renderFlow("/fr/link?rp_client_id=rp123");
    await waitFor(() =>
      expect(router.state.location.pathname).toBe(
        "/fr/error/service-unavailable",
      ),
    );
    expect(window.location.href).toBe("/fr/error/service-unavailable");
  });

  it("treats a failed network request as service unavailable", async () => {
    authService.get_my_user_profile.mockRejectedValue(
      new Error("Network Error"),
    );
    const router = renderFlow();
    await waitFor(() =>
      expect(router.state.location.pathname).toBe(
        "/fr/error/service-unavailable",
      ),
    );
  });

  it("preserves a legitimate Verify entry and ignores an early session event", async () => {
    let rejectProfile;
    authService.get_my_user_profile.mockReturnValue(
      new Promise((_resolve, reject) => {
        rejectProfile = reject;
      }),
    );
    const router = renderFlow("/fr/link?rp_client_id=rp%2Bspecial%26");
    expect(authService.get_my_user_profile).toHaveBeenCalledWith("rp+special&");
    expect(sse.connect).toHaveBeenLastCalledWith("");
    act(() =>
      sse.listener({
        type: "error",
        data: JSON.stringify({ code: "session-ended" }),
      }),
    );
    expect(router.state.location.pathname).toBe("/fr/link");
    await act(async () =>
      rejectProfile({ status: 401, data: { code: "authentication-required" } }),
    );
    const login = new URL(window.location.href);
    expect(login.pathname).toBe("/v1/auth/login");
    expect(login.searchParams.get("clientId")).toBe("rp+special&");
    expect(login.searchParams.get("lang")).toBe("fr");
    expect(screen.queryByText("Migration page")).toBeNull();
    expect(router.state.location.pathname).toBe("/fr/link");
    expect(sse.connect.mock.calls.every(([url]) => !url)).toBe(true);
  });

  it("starts session monitoring after an authenticated profile loads", async () => {
    renderFlow("/en/link?rp_client_id=rp123");
    await screen.findByText("Migration page");
    expect(sse.connect.mock.calls[0][0]).toBe("");
    expect(sse.connect.mock.calls.at(-1)[0]).toContain("/session-status");
  });

  it.each(["expired", "terminated"])(
    "shows session ended for an authenticated %s event",
    async (type) => {
      const router = renderFlow();
      await screen.findByText("Migration page");
      act(() => sse.listener({ type, data: "{}" }));
      await waitFor(() =>
        expect(router.state.location.pathname).toBe("/fr/error/session-ended"),
      );
      expect(authService.logout).not.toHaveBeenCalled();
      expect(window.location.href).toBe("original");
      expect(sse.source.close).toHaveBeenCalled();
    },
  );

  it("shows service unavailable for a coded Redis/SSE failure", async () => {
    const router = renderFlow();
    await screen.findByText("Migration page");
    act(() =>
      sse.listener({
        type: "error",
        data: JSON.stringify({ code: "service-unavailable" }),
      }),
    );
    await waitFor(() =>
      expect(router.state.location.pathname).toBe(
        "/fr/error/service-unavailable",
      ),
    );
  });

  it("allows a native SSE connection error to reconnect", async () => {
    const router = renderFlow();
    await screen.findByText("Migration page");
    act(() => sse.listener({ type: "error" }));
    expect(router.state.location.pathname).toBe("/fr/link");
    expect(sse.source.close).not.toHaveBeenCalled();
  });

  it("shows session ended on the expiry timer without a root/login bounce", async () => {
    const router = renderFlow();
    await screen.findByText("Migration page");
    vi.useFakeTimers();
    act(() =>
      sse.listener({
        type: "notification",
        data: JSON.stringify({
          status: "active",
          expire: Date.now() / 1000 + 2,
        }),
      }),
    );
    await act(async () => vi.advanceTimersByTime(2001));
    expect(router.state.location.pathname).toBe("/fr/error/session-ended");
    expect(authService.logout).not.toHaveBeenCalled();
    expect(window.location.href).toBe("original");
  });

  it("shows service unavailable when keepalive fails instead of trying logout", async () => {
    authService.keepAlive.mockRejectedValue({
      status: 503,
      data: { code: "service-unavailable" },
    });
    const router = renderFlow("/fr/link", {
      showModal: true,
      isLoading: false,
      expirationTime: Date.now() + 10000,
      newServerSideExpirationTime: null,
    });
    await screen.findByText("Migration page");
    fireEvent.click(screen.getByText("Keep session"));
    await waitFor(() =>
      expect(router.state.location.pathname).toBe(
        "/fr/error/service-unavailable",
      ),
    );
    expect(authService.logout).not.toHaveBeenCalled();
  });

  it("retains the server redirect for an explicit successful logout", async () => {
    let resolveLogout;
    authService.logout.mockReturnValue(
      new Promise((resolve) => {
        resolveLogout = resolve;
      }),
    );
    const router = renderFlow("/fr/link", {
      showModal: true,
      isLoading: false,
      expirationTime: Date.now() + 10000,
      newServerSideExpirationTime: null,
    });
    await screen.findByText("Migration page");
    fireEvent.click(screen.getByText("Log out"));
    act(() => sse.listener({ type: "terminated", data: "{}" }));
    await act(async () =>
      resolveLogout({ data: { redirect_url: "https://logout.example.test/" } }),
    );
    await waitFor(() =>
      expect(window.location.href).toBe("https://logout.example.test/"),
    );
    expect(router.state.location.pathname).toBe("/fr/link");
  });
});
