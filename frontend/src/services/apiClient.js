import axios from "axios";
import config from "../config";

const safeMethods = new Set(["get", "head", "options"]);

// Keep credentials and CSRF tokens on this app's backend client only.
export const apiClient = axios.create({
  withCredentials: true,
});

let pendingTokenRequest;

function getCsrfToken() {
  // Share concurrent requests, but fetch again for the next action so a login,
  // logout or session change in another tab cannot leave a cached token behind.
  if (!pendingTokenRequest) {
    pendingTokenRequest = apiClient
      .get(`${config.apiUrl}/v1/auth/csrf-token`)
      .then(({ data }) => {
        if (typeof data?.csrf_token !== "string" || !data.csrf_token) {
          throw new Error("The server did not return a CSRF token.");
        }
        return data.csrf_token;
      })
      .finally(() => {
        pendingTokenRequest = undefined;
      });
  }
  return pendingTokenRequest;
}

apiClient.interceptors.request.use(async (request) => {
  const backend = new URL(config.apiUrl, window.location.origin);
  const destination = new URL(
    apiClient.getUri(request),
    window.location.origin,
  );
  const backendPath = backend.pathname.replace(/\/$/, "");

  if (
    destination.origin !== backend.origin ||
    (destination.pathname !== backendPath &&
      !destination.pathname.startsWith(`${backendPath}/`))
  ) {
    throw new Error("The API client can only call the configured backend.");
  }

  if (!safeMethods.has(request.method?.toLowerCase() || "get")) {
    // A failed token request stops the action. Never automatically replay an
    // unsafe request: it may already have changed something on the server.
    request.headers.set("X-CSRF-Token", await getCsrfToken());
  }

  return request;
});
