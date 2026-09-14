import { useEffect } from "react";
import { useLocation, useParams } from "react-router";
import {
  GcdsContainer,
  GcdsHeading,
  GcdsLink,
  GcdsText,
} from "@gcds-core/components-react";

import Header from "../../../components/Layout/Header.jsx";
import Footer from "../../../components/Layout/Footer.jsx";
import { getLangValues, getPageContent } from "../../../utils/functions.jsx";

// This page must render without a user profile, session, or backend request.
export default function RecoveryPage() {
  const { language, reason } = useParams();
  const { pathname } = useLocation();
  const { langHref, currentLang } = getLangValues(language, pathname);
  // TODO(content): Replace the provisional Recovery copy in both locale files
  // once the content/UI team provides the final wording and recovery links.
  const content = getPageContent(currentLang, "Recovery");
  const message = Object.hasOwn(content.reasons, reason)
    ? content.reasons[reason]
    : content.reasons["service-unavailable"];
  const productTitle = currentLang === "fr" ? "ConnexionCanada" : "CanadaLogin";

  useEffect(() => {
    document.documentElement.lang = currentLang;
    document.title = `${message.title} - ${productTitle}`;
  }, [currentLang, message.title, productTitle]);

  return (
    <div className="mainBody">
      <Header
        langHref={langHref}
        currentLang={currentLang}
        showBreadcrumbs={false}
      />
      <GcdsContainer className="gcds-page">
        <GcdsContainer size="sm" className="gcds-content">
          <main id="main-content">
            <GcdsHeading tag="h1" lang={currentLang}>
              {message.title}
            </GcdsHeading>
            <GcdsText>{message.description}</GcdsText>
            <GcdsText>{message.nextStep}</GcdsText>
            <GcdsLink href={content.helpUrl}>{content.helpLabel}</GcdsLink>
          </main>
        </GcdsContainer>
      </GcdsContainer>
      <Footer currentLang={currentLang} />
    </div>
  );
}
