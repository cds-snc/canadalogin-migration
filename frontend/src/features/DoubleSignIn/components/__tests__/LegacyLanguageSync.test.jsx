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

  it("maps legacy fra code to fr", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({ lang: "fra" }),
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

  it("waits for the language response instead of auto-falling back", async () => {
    globalThis.fetch = vi.fn().mockImplementation(() => new Promise(() => {}));

    render(<LegacyLanguageSync />);

    await new Promise((resolve) => {
      setTimeout(resolve, 25);
    });

    expect(window.location.replace).not.toHaveBeenCalled();
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
