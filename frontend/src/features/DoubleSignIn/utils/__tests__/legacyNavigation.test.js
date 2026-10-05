import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  getPromptEntry,
  preparePromptEntry,
  rememberPromptRpId,
} from "../legacyNavigation.js";

describe("prompt return markers", () => {
  beforeEach(() => window.history.replaceState(null, ""));
  afterEach(() => vi.restoreAllMocks());

  it("preserves React Router state while recording the RP for a later return", () => {
    const routerState = { usr: { source: "rp" }, key: "en-prompt", idx: 3 };
    window.history.replaceState(routerState, "");
    expect(getPromptEntry()).toBeNull();
    expect(preparePromptEntry()).toBe(true);
    expect(rememberPromptRpId("rp-123")).toBe(true);
    expect(window.history.state).toMatchObject(routerState);
    expect(getPromptEntry()).toEqual({ visited: true, rpClientId: "rp-123" });
    const saved = window.history.state;
    expect(preparePromptEntry()).toBe(true);
    expect(window.history.state).toEqual(saved);
  });

  it("retains each language entry's RP across a cold reload without caching completion", async () => {
    rememberPromptRpId("rp-english");
    const englishEntry = window.history.state;
    window.history.replaceState(null, "");
    rememberPromptRpId("rp-french");
    window.history.replaceState(englishEntry, "");
    vi.resetModules();
    const reloaded = await import("../legacyNavigation.js");
    expect(reloaded.getPromptEntry()).toEqual({
      visited: true,
      rpClientId: "rp-english",
    });
  });

  it("leaves a fresh history entry unmarked until it is visited", () => {
    rememberPromptRpId("rp-123");
    window.history.replaceState({ key: "fresh-prompt", idx: 5 }, "");
    expect(getPromptEntry()).toBeNull();
  });

  it.each([null, undefined, "", "  ", 123])(
    "rejects an invalid RP id: %s",
    (rpId) => {
      expect(rememberPromptRpId(rpId)).toBe(false);
      expect(getPromptEntry()).toBeNull();
    },
  );

  it.each(["throws", "silently fails"])(
    "reports when recording the RP %s",
    (failure) => {
      vi.spyOn(window.history, "replaceState").mockImplementation(() => {
        if (failure === "throws")
          throw new DOMException("History unavailable", "SecurityError");
      });
      expect(rememberPromptRpId("rp-123")).toBe(false);
      expect(getPromptEntry()).toBeNull();
    },
  );
});
