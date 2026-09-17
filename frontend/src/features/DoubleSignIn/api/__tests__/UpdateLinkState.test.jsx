import { describe, it, expect, vi, beforeEach } from "vitest";

import { updateLinkStateAPI } from "../UpdateLinkState.jsx";
import { MIGRATION_END_POINTS } from "../../../../utils/constants.jsx";

vi.mock("../../../../services/apiClient.js", () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

vi.mock("../../../../utils/apiErrorHandler.js", () => ({
  handleApiError: vi.fn(),
}));

import { apiClient } from "../../../../services/apiClient.js";
import { handleApiError } from "../../../../utils/apiErrorHandler.js";

describe("updateLinkStateAPI.getRPAuthUrl", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns RP data on success", async () => {
    apiClient.get.mockResolvedValue({ data: { rp_client_name_en: "RP" } });
    const result = await updateLinkStateAPI.getRPAuthUrl();
    expect(apiClient.get).toHaveBeenCalledWith(MIGRATION_END_POINTS.rpcallback);
    expect(result).toEqual({ rp_client_name_en: "RP" });
  });

  it("calls handleApiError on failure", async () => {
    const error = new Error("boom");
    apiClient.get.mockRejectedValue(error);
    await updateLinkStateAPI.getRPAuthUrl();
    expect(handleApiError).toHaveBeenCalledWith(error);
  });
});

describe("updateLinkStateAPI.skipLinking", () => {
  beforeEach(() => vi.clearAllMocks());

  it.each(["en", "fr"])(
    "posts the action with language %s",
    async (language) => {
      apiClient.post.mockResolvedValue({
        data: { redirect_url: "https://rp.example/" },
      });
      expect(await updateLinkStateAPI.skipLinking(language)).toEqual({
        redirect_url: "https://rp.example/",
      });
      expect(apiClient.post).toHaveBeenCalledWith(
        `${MIGRATION_END_POINTS.skip}?lang=${language}`,
      );
    },
  );

  it("handles a rejected action", async () => {
    const error = new Error("Request rejected");
    apiClient.post.mockRejectedValue(error);
    await updateLinkStateAPI.skipLinking("en");
    expect(handleApiError).toHaveBeenCalledWith(error);
  });

  it("rejects a response without a destination", async () => {
    apiClient.post.mockResolvedValue({ data: {} });
    await updateLinkStateAPI.skipLinking("en");
    expect(handleApiError).toHaveBeenCalledWith(expect.any(Error));
  });
});
