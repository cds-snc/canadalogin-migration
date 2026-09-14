import { useEffect, useState } from "react";
import {
  GcdsContainer,
  GcdsText,
  GcdsButton,
  GcdsHeading,
} from "@gcds-core/components-react";
import { getPageContent } from "../../../utils/functions.jsx";
import {
  getRecoveryReason,
  redirectToRecovery,
} from "../../../utils/recoveryErrors.js";

import {
  PAGES,
  GA_CATEGORIES,
  GA_FORM_EVENTS,
  MIGRATION_ANALYTICS,
} from "../../../utils/constants.jsx";

import { useParams } from "react-router";

import { updateLinkStateAPI } from "../api/UpdateLinkState.jsx";
import {
  getLocalizedRpName,
  getRpAnalyticsParams,
  replaceRpName,
} from "../utils/relyingParty.js";
import { MigrationStepper } from "./MigrationStepper.jsx";
import { useTrackPage, useTrackEvent } from "../../../utils/gatag.jsx";

export default function LinkSuccess() {
  const { language } = useParams();

  const trackEvent = useTrackEvent();

  const [serverErrorMessage, setServerErrorMessage] = useState("");

  const pageContentJson = getPageContent(language, PAGES.LinkSuccess);
  const errorPageJson = getPageContent(language, PAGES.error);

  const [rpData, setRpData] = useState(null);

  useTrackPage("Migration - Confirmation");

  useEffect(() => {
    let isCurrent = true;
    setRpData(null);
    async function getRPData() {
      try {
        const data = await updateLinkStateAPI.getRPAuthUrl();
        if (!isCurrent) return;
        if (
          typeof data?.rp_redirect_url !== "string" ||
          !data.rp_redirect_url.trim()
        ) {
          redirectToRecovery("missing-rp-context", language);
          return;
        }
        setRpData(data);
      } catch (error) {
        if (isCurrent) {
          redirectToRecovery(
            getRecoveryReason(error) || "service-unavailable",
            language,
          );
        }
      }
    }

    getRPData();
    return () => {
      isCurrent = false;
    };
  }, [language]);

  const continueToRP = async () => {
    try {
      const redirectUrl = rpData?.rp_redirect_url;
      window.location.replace(redirectUrl);
    } catch (err) {
      if (err && err.data && err.data.message) {
        setServerErrorMessage(err.data.message);
      }
    }
  };

  const errorMessage = errorPageJson[serverErrorMessage] || "";
  const rpName = getLocalizedRpName(rpData, language);
  const rpAnalyticsParams = getRpAnalyticsParams(rpData);

  if (!rpData) return null;

  return (
    <GcdsContainer role="main">
      <MigrationStepper currentStep={3} />
      <GcdsHeading tag="h1" lang={language}>
        {pageContentJson["title"]}
      </GcdsHeading>

      {errorMessage ? <GcdsText>{errorMessage}</GcdsText> : null}
      {rpName ? (
        <GcdsText>
          {replaceRpName(pageContentJson["text_1"], rpData, language)}
        </GcdsText>
      ) : null}
      <GcdsText>{pageContentJson["text_2"]}</GcdsText>
      <ul className="list-disc mt-0">
        <li>{pageContentJson["list_text_1"]}</li>
        <li>{pageContentJson["list_text_2"]}</li>
      </ul>
      <div className="mt-500">
        <GcdsButton
          id="access-account-button"
          buttonId="access-account-button-control"
          onGcdsClick={(ev) => {
            ev.preventDefault();
            trackEvent({
              category: GA_CATEGORIES.formSubmit,
              action: GA_FORM_EVENTS.formSubmitComplete,
              label: MIGRATION_ANALYTICS.eventLabels.completedLinking,
              form_id: MIGRATION_ANALYTICS.flowId,
              type: MIGRATION_ANALYTICS.types.completedLinking,
              status: "success",
              ...rpAnalyticsParams,
            });
            continueToRP();
          }}
        >
          {pageContentJson["btn_1"]}
        </GcdsButton>
      </div>
    </GcdsContainer>
  );
}
