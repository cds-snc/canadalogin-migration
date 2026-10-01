import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  handleApiError,
  redirectToLogin,
} from "../../utils/apiErrorHandler.js";
import {
  getRecoveryReason,
  getRecoveryPath,
  redirectToRecovery,
} from "../../utils/recoveryErrors.js";

vi.mock("../../utils/constants.jsx", () => ({
  OIDC_REDIRECT: { login: "https://login.example.test/v1/auth/login" },
  RP_CLIENT_ID_KEY: "rp_client_id",
}));

describe("API recovery", () => {
  const originalLocation = window.location;

  beforeEach(() => {
    Object.defineProperty(window, "location", {
      value: { href: "original", pathname: "/fr/link", search: "" },
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
    [400, "missing-rp-context", "missing-rp-context"],
    [401, "session-ended", "session-ended"],
    [503, "service-unavailable", "service-unavailable"],
    [401, undefined, "session-ended"],
    [500, undefined, "service-unavailable"],
    [502, "unknown-code", "service-unavailable"],
  ])(
    "routes %s %s to %s without losing the thrown response",
    (status, code, reason) => {
      const response = { status, data: { code } };
      expect(() => handleApiError({ response })).toThrow();
      try {
        handleApiError({ response });
      } catch (thrown) {
        expect(thrown).toBe(response);
      }
      expect(window.location.href).toBe(`/fr/error/${reason}`);
      expect(getRecoveryReason(response)).toBe(reason);
      expect(getRecoveryReason({ response })).toBe(reason);
    },
  );

  it.each([
    new Error("Network Error"),
    { code: "ECONNABORTED", request: {} },
    { code: "ERR_NETWORK", request: {} },
  ])("handles network or timeout errors without a response", (error) => {
    expect(() => handleApiError(error)).toThrow();
    expect(window.location.href).toBe("/fr/error/service-unavailable");
  });

  it("leaves ordinary validation failures to the caller", () => {
    const response = { status: 400, data: { message: "Invalid entry" } };
    expect(() => handleApiError({ response })).toThrow();
    expect(getRecoveryReason(response)).toBeNull();
    expect(window.location.href).toBe("original");
  });

  it("preserves the Verify client ID and language during initial authentication", () => {
    window.location.search = "?rp_client_id=rp%2Bwith%26special";
    const response = { status: 401, data: { code: "authentication-required" } };
    expect(() => handleApiError({ response })).toThrow();
    const login = new URL(window.location.href);
    expect(login.origin + login.pathname).toBe(
      "https://login.example.test/v1/auth/login",
    );
    expect(login.searchParams.get("clientId")).toBe("rp+with&special");
    expect(login.searchParams.get("lang")).toBe("fr");
    expect(getRecoveryReason(response)).toBeNull();
  });

  it("does not restart authentication without an RP ID", () => {
    expect(() =>
      handleApiError({
        status: 401,
        data: { code: "authentication-required" },
      }),
    ).toThrow();
    expect(window.location.href).toBe("/fr/error/session-ended");
  });

  it("does not treat an expired authenticated session as a new entry, even with an RP query", () => {
    window.location.search = "?rp_client_id=rp123";
    expect(() =>
      handleApiError({ status: 401, data: { code: "session-ended" } }),
    ).toThrow();
    expect(window.location.href).toBe("/fr/error/session-ended");
  });

  it("supports an explicit router client ID and language for login", () => {
    redirectToLogin("rp123", "en");
    const login = new URL(window.location.href);
    expect(login.searchParams.get("clientId")).toBe("rp123");
    expect(login.searchParams.get("lang")).toBe("en");
  });

  it("only builds supported local error routes", () => {
    expect(getRecoveryPath("session-ended", "en")).toBe(
      "/en/error/session-ended",
    );
    expect(getRecoveryPath("https://untrusted.test", "../../")).toBe(
      "/en/error/service-unavailable",
    );
    redirectToRecovery("missing-rp-context", "fr");
    expect(window.location.href).toBe("/fr/error/missing-rp-context");
  });
});
