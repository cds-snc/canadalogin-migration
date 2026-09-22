import { describe, it, expect, vi, beforeEach } from "vitest";

import { isMobileMediaQuery } from "../authService.jsx";

const createMatchMedia = (matches) =>
  vi.fn().mockImplementation(() => ({
    matches,
    media: "(max-width: 767px)",
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  }));

describe("authService helpers", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("isMobileMediaQuery returns true when matchMedia matches", () => {
    window.matchMedia = createMatchMedia(true);
    expect(isMobileMediaQuery()).toBe(true);
  });

  it("isMobileMediaQuery returns false when matchMedia does not match", () => {
    window.matchMedia = createMatchMedia(false);
    expect(isMobileMediaQuery()).toBe(false);
  });

  it("isMobileMediaQuery returns false when matchMedia throws", () => {
    window.matchMedia = vi.fn(() => {
      throw new Error("boom");
    });
    expect(isMobileMediaQuery()).toBe(false);
  });
});

vi.mock("../apiClient.js", () => ({
  apiClient: { get: vi.fn(), post: vi.fn() },
}));

import { apiClient } from "../apiClient.js";
import { authService } from "../authService.jsx";
import config from "../../config";

describe("profile RP context", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiClient.get.mockResolvedValue({ data: { id: "user-1" } });
    apiClient.post.mockResolvedValue({ data: { success: true } });
  });

  it("stores RP context with a protected POST before reading the profile", async () => {
    expect(await authService.get_my_user_profile("rp-123")).toEqual({
      id: "user-1",
    });
    expect(apiClient.post).toHaveBeenCalledWith(
      `${config.apiUrl}/v1/auth/rp-context`,
      { rp_client_id: "rp-123" },
    );
    expect(apiClient.get).toHaveBeenCalledWith(`${config.apiUrl}/v1/auth/me`);
    expect(apiClient.post.mock.invocationCallOrder[0]).toBeLessThan(
      apiClient.get.mock.invocationCallOrder[0],
    );
  });

  it("only reads the profile when no RP context is supplied", async () => {
    await authService.get_my_user_profile();
    expect(apiClient.post).not.toHaveBeenCalled();
    expect(apiClient.get).toHaveBeenCalledWith(`${config.apiUrl}/v1/auth/me`);
  });

  it("does not continue after a failed context change", async () => {
    apiClient.post.mockRejectedValueOnce(new Error("Forbidden"));
    await expect(authService.get_my_user_profile("rp-123")).rejects.toThrow(
      "Forbidden",
    );
    expect(apiClient.get).not.toHaveBeenCalled();
  });
});
