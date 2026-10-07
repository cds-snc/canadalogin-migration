import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { createMemoryRouter } from "react-router";
import { RouterProvider } from "react-router/dom";
import { appRoutes } from "../routes.jsx";
import { apiClient } from "../services/apiClient.js";

vi.mock("../services/apiClient.js", () => ({
  apiClient: { get: vi.fn(), post: vi.fn() },
}));

vi.mock("@react-nano/use-event-source", () => ({
  useEventSource: () => [null, "closed"],
  useEventSourceListener: () => {},
}));

vi.mock("../components/Layout/Header.jsx", () => ({
  default: () => <header />,
}));

vi.mock("../components/Layout/Footer.jsx", () => ({
  default: () => <footer />,
}));

vi.mock("@gcds-core/components-react", () => ({
  GcdsContainer: ({ children }) => <div>{children}</div>,
  GcdsHeading: ({ children }) => <h1>{children}</h1>,
  GcdsText: ({ children }) => <p>{children}</p>,
  GcdsLink: ({ children, href }) => <a href={href}>{children}</a>,
  GcdsButton: ({ children, href }) => <a href={href}>{children}</a>,
  GcdsIcon: () => <span />,
}));

const originalLocation = window.location;

function visit(entry) {
  const url = new URL(entry, "http://localhost:3000");
  Object.assign(window.location, {
    pathname: url.pathname,
    search: url.search,
  });
  const router = createMemoryRouter(appRoutes, { initialEntries: [entry] });
  render(<RouterProvider router={router} />);
  return router;
}

beforeEach(() => {
  vi.resetAllMocks();
  Object.defineProperty(window, "location", {
    value: { href: "original", pathname: "/", search: "" },
    writable: true,
  });
});

afterEach(() => {
  cleanup();
  Object.defineProperty(window, "location", {
    value: originalLocation,
    writable: true,
  });
});

describe("migration entry recovery", () => {
  it.each([
    ["/", "en", "Service not found"],
    ["/en", "en", "Service not found"],
    ["/fr", "fr", "Service introuvable"],
    ["/fr/link", "fr", "Service introuvable"],
    ["/?rp_client_id=", "en", "Service not found"],
    ["/fr?rp_client_id=%20%20", "fr", "Service introuvable"],
  ])(
    "shows missing-service recovery from %s",
    async (entry, language, title) => {
      apiClient.get.mockRejectedValue({
        response: { status: 400, data: { code: "missing-rp-context" } },
      });
      const router = visit(entry);

      expect(
        await screen.findByRole("heading", { name: title }),
      ).toBeInTheDocument();
      expect(router.state.location.pathname).toBe(
        `/${language}/error/missing-rp-context`,
      );
      expect(window.location.href).toBe(
        `/${language}/error/missing-rp-context`,
      );
      expect(apiClient.post).not.toHaveBeenCalled();
      expect(apiClient.get).toHaveBeenCalledTimes(1);
    },
  );

  it("preserves session-ended recovery when the server identifies an expired session", async () => {
    apiClient.get.mockRejectedValue({
      response: { status: 401, data: { code: "session-ended" } },
    });
    const router = visit("/");

    expect(
      await screen.findByRole("heading", { name: "Your session has ended" }),
    ).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/en/error/session-ended");
    expect(apiClient.post).not.toHaveBeenCalled();
  });

  it("still starts authentication from the root when a service ID is supplied", async () => {
    apiClient.post.mockRejectedValue({
      response: { status: 401, data: { code: "authentication-required" } },
    });
    visit("/?rp_client_id=rp%2Bspecial%26");

    await waitFor(() => expect(window.location.href).not.toBe("original"));
    const login = new URL(window.location.href);
    expect(login.pathname).toBe("/v1/auth/login");
    expect(login.searchParams.get("clientId")).toBe("rp+special&");
    expect(login.searchParams.get("lang")).toBe("en");
    expect(apiClient.get).not.toHaveBeenCalled();
  });
});
