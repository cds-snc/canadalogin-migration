import { describe, it, expect, vi, afterEach } from "vitest";

import { handleApiError, redirectToLogin } from "../../utils/apiErrorHandler.js";

vi.mock("../../utils/constants.jsx", () => ({
  OIDC_REDIRECT: {
    login: "https://login.example.test",
    reauth: "https://reauth.example.test",
  },
}));

const setLocationHref = (value) => {
  Object.defineProperty(window, "location", {
    value: { href: value },
    writable: true,
  });
};

describe("apiErrorHandler", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("redirects to login on 401", () => {
    setLocationHref("about:blank");
    const error = { response: { status: 401 } };
    expect.assertions(2);
    try {
      handleApiError(error);
    } catch (thrown) {
      expect(thrown).toBe(error.response);
    }
    expect(window.location.href).toBe("https://login.example.test");
  });

  it("throws response for non-401 errors", () => {
    const error = { response: { status: 500, data: { message: "boom" } } };
    expect.assertions(1);
    try {
      handleApiError(error);
    } catch (thrown) {
      expect(thrown).toBe(error.response);
    }
  });

  it("redirectToLogin updates location", () => {
    setLocationHref("about:blank");
    redirectToLogin();
    expect(window.location.href).toBe("https://login.example.test");
  });
});
