const RECOVERY_REASONS = new Set([
  "missing-rp-context",
  "session-ended",
  "service-unavailable",
]);

export const getRecoveryReason = (error) => {
  const response = error?.response || error;
  const code = response?.data?.code;

  // A new entry from Verify still needs to start migration authentication.
  if (code === "authentication-required") return null;
  if (RECOVERY_REASONS.has(code)) return code;
  if (response?.status === 401) return "session-ended";
  if (response?.status >= 500) return "service-unavailable";
  if (error && !response?.status) return "service-unavailable";
  return null;
};

export const getRecoveryPath = (reason, language) => {
  const routeLanguage = window.location.pathname?.split("/")[1];
  const lang = (language || routeLanguage) === "fr" ? "fr" : "en";
  const safeReason = RECOVERY_REASONS.has(reason)
    ? reason
    : "service-unavailable";
  return `/${lang}/error/${safeReason}`;
};

export const redirectToRecovery = (reason, language) => {
  window.location.href = getRecoveryPath(reason, language);
};
