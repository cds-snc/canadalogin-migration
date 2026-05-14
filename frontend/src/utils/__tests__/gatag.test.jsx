import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

import ReactGA from "react-ga4";
import { useTrackEvent } from "../gatag.jsx";

vi.mock("react-ga4", () => ({
  default: {
    event: vi.fn(),
  },
}));

vi.mock("react-router", () => ({
  useLocation: () => ({ pathname: "/test-path" }),
}));

describe("useTrackEvent", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("sends GA4 event parameters, including RP analytics params", () => {
    const { result } = renderHook(() => useTrackEvent());

    act(() => {
      result.current({
        category: "form_submit",
        action: "form_submit_complete",
        label: "Completed linking from confirmation",
        form_id: "migration",
        type: "completed linking",
        status: "success",
        rp_client_id: "rp-123",
        rp_name: "Example RP",
      });
    });

    expect(ReactGA.event).toHaveBeenCalledWith("form_submit_complete", {
      event_category: "form_submit",
      transport_type: "beacon",
      event_label: "Completed linking from confirmation",
      form_id: "migration",
      type: "completed linking",
      status: "success",
      rp_client_id: "rp-123",
      rp_name: "Example RP",
      page: "/test-path",
    });
  });
});
