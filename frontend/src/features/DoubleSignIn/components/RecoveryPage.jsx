import { useEffect } from "react";
import { useLocation, useParams } from "react-router";
import {
  GcdsButton,
  GcdsContainer,
  GcdsHeading,
  GcdsIcon,
  GcdsLink,
  GcdsText,
} from "@gcds-core/components-react";

import Header from "../../../components/Layout/Header.jsx";
import Footer from "../../../components/Layout/Footer.jsx";
import { getLangValues, getPageContent } from "../../../utils/functions.jsx";
import "./RecoveryPage.css";

// This page must render without a user profile, session, or backend request.
export default function RecoveryPage() {
  const { language, reason } = useParams();
  const { pathname } = useLocation();
  const { langHref, currentLang } = getLangValues(language, pathname);
  // Session-ended and service-unavailable copy is still provisional.
  const content = getPageContent(currentLang, "Recovery");
  const message = Object.hasOwn(content.reasons, reason)
    ? content.reasons[reason]
    : content.reasons["service-unavailable"];
  const productTitle = currentLang === "fr" ? "ConnexionCanada" : "CanadaLogin";
  const isMissingService = reason === "missing-rp-context";

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
      <GcdsContainer
        className={`gcds-page${isMissingService ? " recovery-page" : ""}`}
      >
        <GcdsContainer
          size={isMissingService ? "md" : "sm"}
          className={`gcds-content${isMissingService ? " recovery-card" : ""}`}
        >
          <main id="main-content">
            {isMissingService && (
              <div className="recovery-icon" aria-hidden="true">
                <GcdsIcon name="exclamation-circle" size="h1" />
              </div>
            )}
            <GcdsHeading tag="h1" lang={currentLang}>
              {message.title}
            </GcdsHeading>
            <GcdsText>{message.description}</GcdsText>
            <GcdsText marginBottom={isMissingService ? "0" : undefined}>
              {message.nextStep}
            </GcdsText>
            {isMissingService && (
              <>
                <ul className="recovery-steps">
                  <li>{message.navigateStep}</li>
                  <li>
                    {message.signInStep} <strong>{message.signInLabel}</strong>
                  </li>
                </ul>
                <div className="recovery-action">
                  <GcdsButton
                    type="link"
                    href={message.servicesUrl}
                    lang={currentLang}
                  >
                    {message.servicesLabel}
                  </GcdsButton>
                </div>
              </>
            )}
            <GcdsLink href={content.helpUrl}>
              {message.helpLabel || content.helpLabel}
            </GcdsLink>
          </main>
        </GcdsContainer>
      </GcdsContainer>
      <Footer currentLang={currentLang} />
    </div>
  );
}
