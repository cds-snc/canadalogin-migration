function parseTimeoutMs(value, fallback) {
  const parsed = Number.parseInt(value, 10);
  if (Number.isNaN(parsed) || parsed <= 0) {
    return fallback;
  }

  return parsed;
}

const config = {
  apiUrl: import.meta.env.VITE_BACKEND_API_URL || "http://localhost:8000",
  gatag: import.meta.env.VITE_GOOGLE_ANALYTICS_ID || "G-0Z1YGGZH02",
  legacyLanguageApiUrl:
    import.meta.env.VITE_LEGACY_LANGUAGE_API_URL ||
    "https://lang-canada.fjgc-gccf.gc.ca/v1/lang",
  legacyLanguageTimeoutMs: parseTimeoutMs(
    import.meta.env.VITE_LEGACY_LANGUAGE_TIMEOUT_MS,
    1500,
  ),
};

export default config;
