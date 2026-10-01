import { OIDC_REDIRECT, RP_CLIENT_ID_KEY } from "./constants.jsx";
import { getRecoveryReason, redirectToRecovery } from "./recoveryErrors.js";

export const redirectToLogin = (
  clientId = new URLSearchParams(window.location.search).get(RP_CLIENT_ID_KEY),
  language = window.location.pathname?.split("/")[1],
) => {
  const params = new URLSearchParams({ lang: language === "fr" ? "fr" : "en" });
  if (clientId) params.set("clientId", clientId);
  window.location.href = `${OIDC_REDIRECT.login}?${params}`;
};

export const handleApiError = (error) => {
  const response = error.response || error;
  if (
    response.status === 401 &&
    response.data?.code === "authentication-required"
  ) {
    const clientId = new URLSearchParams(window.location.search).get(
      RP_CLIENT_ID_KEY,
    );
    if (clientId) redirectToLogin(clientId);
    else redirectToRecovery("session-ended");
  } else {
    const reason = getRecoveryReason(error);
    if (reason) redirectToRecovery(reason);
  }
  throw response;
};
