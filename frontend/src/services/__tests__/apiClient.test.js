import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import axios from "axios";
import config from "../../config";
import { apiClient } from "../apiClient.js";

const tokenUrl = `${config.apiUrl}/v1/auth/csrf-token`;
const actionUrl = `${config.apiUrl}/v1/auth/keep-alive`;
const response = (request, data) => ({
  config: request,
  status: 200,
  statusText: "OK",
  headers: {},
  data,
});

describe("backend API client CSRF protection", () => {
  const originalAdapter = apiClient.defaults.adapter;
  const originalApiUrl = config.apiUrl;
  let adapter;

  beforeEach(() => {
    adapter = vi.fn(async (request) =>
      response(
        request,
        request.url === tokenUrl
          ? { csrf_token: "session-token" }
          : { success: true },
      ),
    );
    apiClient.defaults.adapter = adapter;
  });

  afterEach(() => {
    apiClient.defaults.adapter = originalAdapter;
    config.apiUrl = originalApiUrl;
  });

  it.each(["post", "put", "patch", "delete"])(
    "sends %s only after obtaining the token, with session credentials",
    async (method) => {
      await apiClient.request({
        method,
        url: actionUrl,
        data: { field: "value" },
      });
      expect(adapter).toHaveBeenCalledTimes(2);
      const [tokenRequest, action] = adapter.mock.calls.map(
        ([request]) => request,
      );
      expect(tokenRequest.url).toBe(tokenUrl);
      expect(tokenRequest.method).toBe("get");
      expect(tokenRequest.headers.has("X-CSRF-Token")).toBe(false);
      expect(tokenRequest.withCredentials).toBe(true);
      expect(action.headers.get("X-CSRF-Token")).toBe("session-token");
      expect(action.withCredentials).toBe(true);
      expect(JSON.parse(action.data)).toEqual({ field: "value" });
    },
  );

  it.each(["get", "head", "options"])(
    "does not obtain or attach a token for %s",
    async (method) => {
      await apiClient.request({ method, url: actionUrl });
      expect(adapter).toHaveBeenCalledTimes(1);
      expect(adapter.mock.calls[0][0].headers.has("X-CSRF-Token")).toBe(false);
    },
  );

  it("fetches the current token again for later actions after a session change", async () => {
    let token = "first-session";
    adapter.mockImplementation(async (request) =>
      response(request, request.url === tokenUrl ? { csrf_token: token } : {}),
    );
    await apiClient.post(actionUrl);
    token = "new-session";
    await apiClient.post(actionUrl);
    const actions = adapter.mock.calls
      .map(([request]) => request)
      .filter((request) => request.url === actionUrl);
    expect(
      actions.map((request) => request.headers.get("X-CSRF-Token")),
    ).toEqual(["first-session", "new-session"]);
  });

  it("shares token acquisition across concurrent actions", async () => {
    let resolveToken;
    adapter.mockImplementation((request) =>
      request.url === tokenUrl
        ? new Promise((resolve) => {
            resolveToken = () =>
              resolve(response(request, { csrf_token: "shared-token" }));
          })
        : Promise.resolve(response(request, {})),
    );
    const first = apiClient.post(actionUrl);
    const second = apiClient.post(actionUrl);
    await vi.waitFor(() => expect(resolveToken).toBeTypeOf("function"));
    expect(adapter).toHaveBeenCalledTimes(1);
    resolveToken();
    await Promise.all([first, second]);
    expect(adapter).toHaveBeenCalledTimes(3);
    expect(
      adapter.mock.calls
        .slice(1)
        .every(
          ([request]) => request.headers.get("X-CSRF-Token") === "shared-token",
        ),
    ).toBe(true);
  });

  it("stops the mutation when token acquisition fails and permits a later attempt", async () => {
    adapter.mockRejectedValueOnce(new Error("Token unavailable"));
    await expect(apiClient.post(actionUrl)).rejects.toThrow(
      "Token unavailable",
    );
    expect(adapter).toHaveBeenCalledTimes(1);
    expect(adapter.mock.calls[0][0].url).toBe(tokenUrl);
    await apiClient.post(actionUrl);
    expect(adapter).toHaveBeenCalledTimes(3);
  });

  it.each([{}, { csrf_token: "" }, { csrf_token: 1 }])(
    "stops the mutation when the token response is malformed: %j",
    async (data) => {
      adapter.mockImplementation(async (request) => response(request, data));
      await expect(apiClient.post(actionUrl)).rejects.toThrow(
        "did not return a CSRF token",
      );
      expect(adapter).toHaveBeenCalledTimes(1);
    },
  );

  it("does not replay a mutation rejected by the server", async () => {
    adapter.mockImplementation(async (request) => {
      if (request.url === tokenUrl)
        return response(request, { csrf_token: "session-token" });
      throw new Error("Forbidden");
    });
    await expect(apiClient.post(actionUrl)).rejects.toThrow("Forbidden");
    expect(adapter).toHaveBeenCalledTimes(2);
  });

  it.each([
    "https://lang-canada.fjgc-gccf.gc.ca/v1/lang",
    "https://rp.example/continue",
    "//external.example/action",
  ])(
    "never sends a token or credentials to another service: %s",
    async (url) => {
      await expect(apiClient.post(url)).rejects.toThrow("configured backend");
      expect(adapter).not.toHaveBeenCalled();
      expect(axios.defaults.withCredentials).not.toBe(true);
      expect(axios.defaults.headers.common["X-CSRF-Token"]).toBeUndefined();
    },
  );

  it.each(["https://backend.example/api", "/api"])(
    "keeps tokens inside the configured backend path: %s",
    async (backendUrl) => {
      config.apiUrl = backendUrl;
      adapter.mockImplementation(async (request) =>
        response(
          request,
          request.url === `${backendUrl}/v1/auth/csrf-token`
            ? { csrf_token: "path-token" }
            : {},
        ),
      );
      await apiClient.post(`${backendUrl}/v1/auth/keep-alive`);
      expect(adapter.mock.calls[1][0].url).toBe(
        `${backendUrl}/v1/auth/keep-alive`,
      );
      expect(adapter.mock.calls[1][0].headers.get("X-CSRF-Token")).toBe(
        "path-token",
      );
      await expect(
        apiClient.post(`${backendUrl}-other/action`),
      ).rejects.toThrow("configured backend");
      await expect(apiClient.post(`${backendUrl}/../action`)).rejects.toThrow(
        "configured backend",
      );
      expect(adapter).toHaveBeenCalledTimes(2);
    },
  );
});
