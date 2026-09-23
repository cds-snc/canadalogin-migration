import { useState, useEffect } from "react";
import {
  GcdsContainer,
  GcdsText,
  GcdsLink,
  GcdsButton,
  GcdsHeading,
  GcdsNotice,
} from "@gcds-core/components-react";
import { getPageContent } from "../../../utils/functions.jsx";
import {
  getRecoveryReason,
  redirectToRecovery,
} from "../../../utils/recoveryErrors.js";

import { updateLinkStateAPI } from "../api/UpdateLinkState.jsx";
import { useSkipLink } from "../hooks/useSkipLink.js";
import {
  getLocalizedRpName,
  getRpAnalyticsParams,
  replaceRpName,
} from "../utils/relyingParty.js";
import { useParams } from "react-router";
import { MigrationStepper } from "./MigrationStepper.jsx";
import { useTrackPage, useTrackEvent } from "../../../utils/gatag.jsx";

import {
  PAGES,
  MIGRATION_END_POINTS,
  GA_CATEGORIES,
  GA_FORM_EVENTS,
  MIGRATION_ANALYTICS,
} from "../../../utils/constants.jsx";

export default function LinkPrompt() {
  const { language } = useParams();

  const trackEvent = useTrackEvent();

  const [rpLoadState, setRpLoadState] = useState({
    language,
    isLoading: true,
    data: null,
    error: null,
  });

  const pageContentJson = getPageContent(language, PAGES.LinkPrompt);
  const errorPageJson = getPageContent(language, PAGES.error);
  const pageTitle = pageContentJson["title"];
  const productTitle = language === "fr" ? "ConnexionCanada" : "CanadaLogin";

  useTrackPage("Migration - Legacy method prompt");

  const linkingLink = `${MIGRATION_END_POINTS.login}?lang=${language}`;

  useEffect(() => {
    let isCurrent = true;

    async function getRPData() {
      setRpLoadState({
        language,
        isLoading: true,
        data: null,
        error: null,
      });

      try {
        const data = await updateLinkStateAPI.getRPAuthUrl();
        if (isCurrent) {
          if (
            typeof data?.rp_client_id !== "string" ||
            !data.rp_client_id.trim()
          ) {
            setRpLoadState({
              language,
              isLoading: false,
              data: null,
              error: "missing-rp-context",
            });
            redirectToRecovery("missing-rp-context", language);
            return;
          }
          setRpLoadState({
            language,
            isLoading: false,
            data,
            error: null,
          });
        }
      } catch (e) {
        console.error("Failed loading RP data", e);
        if (isCurrent) {
          const reason = getRecoveryReason(e) || "service-unavailable";
          setRpLoadState({
            language,
            isLoading: false,
            data: null,
            error: reason,
          });
          redirectToRecovery(reason, language);
        }
      }
    }

    getRPData();

    return () => {
      isCurrent = false;
    };
  }, [language]);

  const isPageReady =
    !rpLoadState.isLoading &&
    !rpLoadState.error &&
    rpLoadState.language === language;
  const rpData = isPageReady ? rpLoadState.data : null;

  useEffect(() => {
    if (!isPageReady) {
      return;
    }

    document.title = pageTitle
      ? `${pageTitle} - ${productTitle}`
      : productTitle;

    return () => {
      document.title = productTitle;
    };
  }, [isPageReady, pageTitle, productTitle]);

  const isGcKeyOnly = Boolean(rpData?.is_gckey_only);
  const rpName = getLocalizedRpName(rpData, language);
  const rpAnalyticsParams = getRpAnalyticsParams(rpData);
  const { skipLink, isSkipping, skipFailed } = useSkipLink(language, () => {
    trackEvent({
      category: GA_CATEGORIES.formSubmit,
      action: GA_FORM_EVENTS.formSubmitComplete,
      label: MIGRATION_ANALYTICS.eventLabels.skippedLinking,
      form_id: MIGRATION_ANALYTICS.flowId,
      type: MIGRATION_ANALYTICS.types.skippedLinking,
      status: "success",
      ...rpAnalyticsParams,
    });
  });
  const linkButtonText = isGcKeyOnly
    ? pageContentJson["btn_1_gckey_only"] || pageContentJson["btn_1"]
    : pageContentJson["btn_1"];
  const skipHelpText = isGcKeyOnly
    ? pageContentJson["text_4_gckey_only"] || pageContentJson["text_4"]
    : pageContentJson["text_4"];

  if (!isPageReady) {
    return null;
  }

  return (
    <GcdsContainer role="main">
      <MigrationStepper currentStep={2} />
      <GcdsHeading tag="h1" lang={language}>
        {pageContentJson["title"]}
      </GcdsHeading>

      {skipFailed ? (
        <div role="alert">
          <GcdsText>{errorPageJson["skip_failed"]}</GcdsText>
        </div>
      ) : null}

      {rpName ? (
        <GcdsText>
          {replaceRpName(pageContentJson["text_2"], rpData, language)}
        </GcdsText>
      ) : null}
      <GcdsText>{pageContentJson["text_3"]}</GcdsText>
      <GcdsButton
        id="sign-in-old-method-button"
        buttonId="sign-in-old-method-button-control"
        type="link"
        href={linkingLink}
        disabled={isSkipping}
        onGcdsClick={() => {
          trackEvent({
            category: GA_CATEGORIES.formSubmit,
            action: GA_FORM_EVENTS.formSubmitComplete,
            label: MIGRATION_ANALYTICS.eventLabels.startedLinking,
            form_id: MIGRATION_ANALYTICS.flowId,
            type: MIGRATION_ANALYTICS.types.startedLinking,
            status: "success",
            ...rpAnalyticsParams,
          });
        }}
      >
        {linkButtonText}
      </GcdsButton>

      <div className="mt-500 mb-700">
        <GcdsNotice
          noticeRole="info"
          noticeTitle={pageContentJson["notice_title"]}
          noticeTitleTag="h2"
          lang={language}
        >
          <GcdsLink
            id="sign-in-method-help-link"
            href={pageContentJson["link_1_url"]}
            external
          >
            {pageContentJson["link_1"]}
          </GcdsLink>
        </GcdsNotice>
      </div>
      {rpName ? (
        <GcdsHeading tag="h2" lang={language}>
          {replaceRpName(pageContentJson["subtitle"], rpData, language)}
        </GcdsHeading>
      ) : null}
      <GcdsText>{skipHelpText}</GcdsText>
      <GcdsText aria-busy={isSkipping}>
        <GcdsLink
          id="skip-create-new-account-link"
          href="#skip-create-new-account-link"
          onGcdsClick={(event) => {
            // Keep the link appearance while submitting the protected action.
            event.preventDefault();
            skipLink();
          }}
        >
          {pageContentJson["link_2"]}
        </GcdsLink>
      </GcdsText>
    </GcdsContainer>
  );
}
