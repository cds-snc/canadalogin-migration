import { useEffect } from "react";
import { useParams } from "react-router";

import config from "../../../config.jsx";
import Loader from "../../../components/Layout/Loading.jsx";

function normalizeLanguage(language) {
  if (!language || typeof language !== "string") {
    return "en";
  }

  const normalized = language.includes("-")
    ? language.split("-")[0].toLowerCase()
    : language.toLowerCase();

  return normalized === "fr" ? "fr" : "en";
}

function resolveLegacyLanguage(language) {
  if (!language || typeof language !== "string") {
    return null;
  }

  const normalized = language.includes("-")
    ? language.split("-")[0].toLowerCase()
    : language.toLowerCase();

  if (normalized === "en" || normalized === "fr") {
    return normalized;
  }

  return null;
}

async function getLegacyLanguage(signal) {
  const response = await fetch(config.legacyLanguageApiUrl, {
    method: "GET",
    credentials: "include",
    signal,
  });

  if (!response.ok) {
    throw new Error(`Language service returned status ${response.status}`);
  }

  const data = await response.json();
  return resolveLegacyLanguage(data?.lang);
}

export default function LegacyLanguageSync() {
  const { language } = useParams();
  const fallbackLanguage = normalizeLanguage(language);

  useEffect(() => {
    let isActive = true;
    const controller = new AbortController();
    const timeoutId = window.setTimeout(
      () => controller.abort(),
      config.legacyLanguageTimeoutMs,
    );

    const redirectToSuccess = (resolvedLanguage) => {
      window.location.replace(`/${resolvedLanguage}/link/success`);
    };

    const resolveLanguage = async () => {
      let resolvedLanguage = fallbackLanguage;

      try {
        const detectedLanguage = await getLegacyLanguage(controller.signal);
        if (detectedLanguage) {
          resolvedLanguage = detectedLanguage;
        }
      } catch (error) {
        console.warn(
          "Legacy language sync failed; using fallback language.",
          error,
        );
      } finally {
        window.clearTimeout(timeoutId);
        if (isActive) {
          redirectToSuccess(resolvedLanguage);
        }
      }
    };

    resolveLanguage();

    return () => {
      isActive = false;
      window.clearTimeout(timeoutId);
      controller.abort();
    };
  }, [fallbackLanguage]);

  return <Loader text="Loading / Chargement" />;
}
