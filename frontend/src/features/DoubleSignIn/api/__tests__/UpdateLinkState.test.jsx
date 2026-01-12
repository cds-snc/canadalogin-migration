import { describe, it, expect, vi, beforeEach } from "vitest";

import { updateLinkStateAPI } from "../UpdateLinkState.jsx";
import { MIGRATION_END_POINTS } from "../../../../utils/constants.jsx";

vi.mock("axios", () => ({
  default: {
    get: vi.fn(),
    defaults: {
      withCredentials: false,
    },
  },
}));

vi.mock("../../../../utils/apiErrorHandler.js", () => ({
  handleApiError: vi.fn(),
}));

import axios from "axios";
import { handleApiError } from "../../../../utils/apiErrorHandler.js";

describe("updateLinkStateAPI.getRPAuthUrl", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns RP data on success", async () => {
    axios.get.mockResolvedValue({ data: { rp_client_name_en: "RP" } });
    const result = await updateLinkStateAPI.getRPAuthUrl();
    expect(axios.get).toHaveBeenCalledWith(MIGRATION_END_POINTS.rpcallback);
    expect(result).toEqual({ rp_client_name_en: "RP" });
  });

  it("calls handleApiError on failure", async () => {
    const error = new Error("boom");
    axios.get.mockRejectedValue(error);
    await updateLinkStateAPI.getRPAuthUrl();
    expect(handleApiError).toHaveBeenCalledWith(error);
  });
});
