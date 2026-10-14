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

describe("updateLinkStateAPI.getMigrationStatus", () => {
  beforeEach(() => vi.clearAllMocks());

  it("shares an in-flight read but rechecks IBM on the next return", async () => {
    let resolveStatus;
    apiClient.get.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveStatus = resolve;
      }),
    );
    const first = updateLinkStateAPI.getMigrationStatus();
    const second = updateLinkStateAPI.getMigrationStatus();
    expect(first).toBe(second);
    expect(apiClient.get).toHaveBeenCalledOnce();
    expect(apiClient.get).toHaveBeenCalledWith(MIGRATION_END_POINTS.status);
    resolveStatus({ data: { rp_client_id: "rp-123", completed: false } });
    await expect(first).resolves.toEqual({
      rp_client_id: "rp-123",
      completed: false,
    });
    apiClient.get.mockResolvedValueOnce({
      data: { rp_client_id: "rp-123", completed: true },
    });
    await expect(updateLinkStateAPI.getMigrationStatus()).resolves.toEqual({
      rp_client_id: "rp-123",
      completed: true,
    });
    expect(apiClient.get).toHaveBeenCalledTimes(2);
  });

  it("starts a fresh visit read without letting the old request clear its pending slot", async () => {
    let resolveEarlier;
    let resolveReturned;
    apiClient.get
      .mockReturnValueOnce(
        new Promise((resolve) => {
          resolveEarlier = resolve;
        }),
      )
      .mockReturnValueOnce(
        new Promise((resolve) => {
          resolveReturned = resolve;
        }),
      );

    const earlier = updateLinkStateAPI.getMigrationStatus();
    const returned = updateLinkStateAPI.getMigrationStatus({
      forceFresh: true,
    });
    expect(returned).not.toBe(earlier);
    expect(apiClient.get).toHaveBeenCalledTimes(2);
    resolveEarlier({ data: { rp_client_id: "rp-123", completed: false } });
    await earlier;

    expect(updateLinkStateAPI.getMigrationStatus()).toBe(returned);
    expect(apiClient.get).toHaveBeenCalledTimes(2);
    resolveReturned({ data: { rp_client_id: "rp-123", completed: true } });
    await expect(returned).resolves.toMatchObject({ completed: true });
  });

  it.each([
    {},
    { rp_client_id: "rp-123" },
    { rp_client_id: "", completed: false },
    { rp_client_id: "rp-123", completed: "false" },
  ])(
    "rejects malformed status %j instead of allowing another action",
    async (data) => {
      apiClient.get.mockResolvedValue({ data });
      await expect(updateLinkStateAPI.getMigrationStatus()).rejects.toThrow(
        "migration status",
      );
    },
  );

  it("propagates failures without automatically starting login and permits a later read", async () => {
    const error = {
      response: { status: 401, data: { code: "authentication-required" } },
    };
    apiClient.get.mockRejectedValueOnce(error);
    await expect(updateLinkStateAPI.getMigrationStatus()).rejects.toBe(error);
    expect(handleApiError).not.toHaveBeenCalled();
    apiClient.get.mockResolvedValue({
      data: { rp_client_id: "rp-123", completed: false },
    });
    await expect(
      updateLinkStateAPI.getMigrationStatus(),
    ).resolves.toMatchObject({ completed: false });
  });
});

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
