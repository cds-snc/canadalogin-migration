import { useEffect } from "react";
import { useParams } from "react-router";

import config from "../../../config.jsx";
import Loader from "../../../components/Layout/Loading.jsx";

function toSupportedLanguage(language) {
  if (!language || typeof language !== "string") {
    return null;
  }

  const normalized = language.trim().toLowerCase().split(/[-_]/)[0];

  if (normalized === "fr" || normalized === "fra") {
    return "fr";
  }

  if (normalized === "en" || normalized === "eng") {
    return "en";
  }

  return null;
}

function normalizeLanguage(language) {
  return toSupportedLanguage(language) || "en";
}

function resolveLegacyLanguage(language) {
  return toSupportedLanguage(language);
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
        if (isActive) {
          redirectToSuccess(resolvedLanguage);
        }
      }
    };

    resolveLanguage();

    return () => {
      isActive = false;
      controller.abort();
    };
  }, [fallbackLanguage]);

  return <Loader text="Loading / Chargement" />;
}
