import { useEffect, useRef, useState } from "react";
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
import { updateLinkStateAPI } from "../api/UpdateLinkState.jsx";
import "./RecoveryPage.css";

// Recovery always renders without a user profile or working backend. Completed
// migrations may also offer the configured RP destination when context matches.
export default function RecoveryPage() {
  const { language, reason } = useParams();
  const { pathname, search } = useLocation();
  const { langHref, currentLang } = getLangValues(language, pathname);
  // Session-ended and service-unavailable copy is still provisional.
  const content = getPageContent(currentLang, "Recovery");
  const message = Object.hasOwn(content.reasons, reason)
    ? content.reasons[reason]
    : content.reasons["service-unavailable"];
  const productTitle = currentLang === "fr" ? "ConnexionCanada" : "CanadaLogin";
  const isMissingService = reason === "missing-rp-context";
  const expectedRpId = new URLSearchParams(search).get("rp_client_id");
  const [destination, setDestination] = useState(null);
  const navigationStarted = useRef(false);
  const canContinue =
    reason === "migration-completed" &&
    destination?.language === currentLang &&
    destination?.rpClientId === expectedRpId;

  useEffect(() => {
    let current = true;
    setDestination(null);
    navigationStarted.current = false;
    if (reason !== "migration-completed" || !expectedRpId) return;

    updateLinkStateAPI
      .getRecoveryRPDetails(currentLang)
      .then((data) => {
        if (!current || data?.rp_client_id !== expectedRpId) return;
        const url = new URL(data.rp_redirect_url);
        if (
          !["https:", "http:"].includes(url.protocol) ||
          url.username ||
          url.password
        )
          return;
        setDestination({
          language: currentLang,
          rpClientId: expectedRpId,
          url: url.href,
        });
      })
      .catch(() => {
        // Keep the restart instructions when configuration/session is unavailable.
      });

    return () => {
      current = false;
    };
  }, [reason, currentLang, expectedRpId]);

  useEffect(() => {
    document.documentElement.lang = currentLang;
    document.title = `${message.title} - ${productTitle}`;
  }, [currentLang, message.title, productTitle]);

  return (
    <div className="mainBody">
      <Header
        langHref={`${langHref}${reason === "migration-completed" && expectedRpId ? `?rp_client_id=${encodeURIComponent(expectedRpId)}` : ""}`}
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
              {canContinue ? message.continueStep : message.nextStep}
            </GcdsText>
            {canContinue && (
              <div className="recovery-action">
                <GcdsButton
                  id="recovery-access-account-button"
                  buttonId="recovery-access-account-button-control"
                  onGcdsClick={(event) => {
                    event.preventDefault();
                    if (navigationStarted.current) return;
                    navigationStarted.current = true;
                    window.location.replace(destination.url);
                  }}
                >
                  {getPageContent(currentLang, "LinkSuccess")["btn_1"]}
                </GcdsButton>
              </div>
            )}
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
