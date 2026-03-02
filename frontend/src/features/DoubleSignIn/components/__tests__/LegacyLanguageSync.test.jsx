import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

import LegacyLanguageSync from "../LegacyLanguageSync.jsx";

const mockUseParams = vi.fn();

vi.mock("react-router", () => ({
  useParams: () => mockUseParams(),
}));

vi.mock("@cdssnc/gcds-components-react", () => ({
  GcdsContainer: ({ children }) => <div>{children}</div>,
  GcdsHeading: ({ children }) => <h1>{children}</h1>,
  GcdsText: ({ children }) => <p>{children}</p>,
}));

vi.mock("../../../../config.jsx", () => ({
  default: {
    legacyLanguageApiUrl: "https://lang-canada.fjgc-gccf.gc.ca/v1/lang",
    legacyLanguageTimeoutMs: 50,
  },
}));

describe("LegacyLanguageSync", () => {
  const originalLocation = window.location;
  const originalFetch = globalThis.fetch;
  let warnSpy;

  beforeEach(() => {
    vi.clearAllMocks();
    mockUseParams.mockReturnValue({ language: "en" });
    warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
    Object.defineProperty(window, "location", {
      value: { replace: vi.fn() },
      writable: true,
    });
  });

  afterEach(() => {
    warnSpy.mockRestore();
    globalThis.fetch = originalFetch;
    vi.useRealTimers();
    Object.defineProperty(window, "location", {
      value: originalLocation,
      writable: true,
    });
  });

  it("redirects to resolved language when API returns fr", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({ lang: "fr" }),
    });

    render(<LegacyLanguageSync />);

    await waitFor(() => {
      expect(window.location.replace).toHaveBeenCalledWith("/fr/link/success");
    });
  });

  it("falls back to URL language when API errors", async () => {
    mockUseParams.mockReturnValue({ language: "fr" });
    globalThis.fetch = vi.fn().mockRejectedValue(new Error("network failure"));

    render(<LegacyLanguageSync />);

    await waitFor(() => {
      expect(window.location.replace).toHaveBeenCalledWith("/fr/link/success");
    });
  });

  it("falls back to URL language when API language is invalid", async () => {
    mockUseParams.mockReturnValue({ language: "fr" });
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({ lang: "xx" }),
    });

    render(<LegacyLanguageSync />);

    await waitFor(() => {
      expect(window.location.replace).toHaveBeenCalledWith("/fr/link/success");
    });
  });

  it("falls back after timeout when request hangs", async () => {
    globalThis.fetch = vi.fn().mockImplementation((_url, options) => {
      const { signal } = options;
      return new Promise((_, reject) => {
        signal.addEventListener("abort", () => {
          reject(new Error("aborted"));
        });
      });
    });

    render(<LegacyLanguageSync />);

    await waitFor(() => {
      expect(window.location.replace).toHaveBeenCalledWith("/en/link/success");
    });
  });

  it("calls language API with credentials included", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({ lang: "en" }),
    });

    render(<LegacyLanguageSync />);

    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalled();
    });

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "https://lang-canada.fjgc-gccf.gc.ca/v1/lang",
      expect.objectContaining({
        method: "GET",
        credentials: "include",
        signal: expect.any(AbortSignal),
      }),
    );
  });
});
