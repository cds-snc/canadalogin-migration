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
