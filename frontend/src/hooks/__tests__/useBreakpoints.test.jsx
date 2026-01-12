import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";

import { useBreakpoints } from "../useBreakpoints.ts";

const createMatchMedia = (matchesMap) => {
  return vi.fn().mockImplementation((query) => {
    return {
      matches: Boolean(matchesMap[query]),
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    };
  });
};

describe("useBreakpoints", () => {
  const mobileQuery = "(max-width: 47.999em)";
  const tabletQuery = "(min-width: 48em) and (max-width: 63.999em)";

  beforeEach(() => {
    window.matchMedia = createMatchMedia({
      [mobileQuery]: true,
      [tabletQuery]: false,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns initial match state", () => {
    const { result } = renderHook(() => useBreakpoints());
    expect(result.current.mobile).toBe(true);
    expect(result.current.tablet).toBe(false);
  });

  it("updates when matchMedia values change", () => {
    const listeners = [];
    window.matchMedia = vi.fn().mockImplementation((query) => {
      const entry = {
        matches: query === mobileQuery,
        media: query,
        addEventListener: vi.fn((_, cb) => listeners.push(cb)),
        removeEventListener: vi.fn(),
      };
      return entry;
    });

    const { result } = renderHook(() => useBreakpoints());
    expect(result.current.mobile).toBe(true);
    expect(result.current.tablet).toBe(false);

    window.matchMedia = createMatchMedia({
      [mobileQuery]: false,
      [tabletQuery]: true,
    });

    act(() => {
      listeners.forEach((cb) => cb());
    });

    expect(result.current.mobile).toBe(false);
    expect(result.current.tablet).toBe(true);
  });
});
