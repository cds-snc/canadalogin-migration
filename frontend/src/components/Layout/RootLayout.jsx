import { useEffect, useLayoutEffect } from "react";
import { Outlet, useLocation, useParams } from "react-router";
import { useLanguage } from "../Providers/LanguageProvider";
import { getLangValues } from "../../utils/functions";
import Header from "../Layout/Header";
import Footer from "../Layout/Footer";

import { GcdsContainer } from "@gcds-core/components-react";

export default function RootLayout() {
  const { pathname } = useLocation();
  const { language: urlLanguage } = useParams();
  const { state: languageState } = useLanguage();
  const { language } = languageState;
  const normalizedUrlLanguage =
    urlLanguage === "en" || urlLanguage === "fr" ? urlLanguage : undefined;
  const effectiveLanguage = normalizedUrlLanguage || language;
  const { langHref, currentLang } = getLangValues(effectiveLanguage, pathname);

  useLayoutEffect(() => {
    document.documentElement.lang = currentLang;
  }, [currentLang]);

  useEffect(() => {
    document.title = currentLang === "fr" ? "ConnexionCanada" : "CanadaLogin";
  }, [currentLang]);

  return (
    <div className="mainBody">
      <Header langHref={langHref} currentLang={currentLang} />
      <GcdsContainer className="gcds-page">
        <GcdsContainer size="sm" className="gcds-content">
          <Outlet />
        </GcdsContainer>
      </GcdsContainer>

      <Footer currentLang={currentLang} />
    </div>
  );
}
