import { useEffect, useState } from "react";
import {
  GcdsContainer,
  GcdsText,
  GcdsButton,
  GcdsHeading,
} from "@gcds-core/components-react";
import { getPageContent } from "../../../utils/functions.jsx";

import {
  PAGES,
  GA_LABELS,
  GA_CATEGORIES,
  GA_EVENTS,
  GA_STEPS,
} from "../../../utils/constants.jsx";

import { useParams } from "react-router";

import { updateLinkStateAPI } from "../api/UpdateLinkState.jsx";
import { getLocalizedRpName, replaceRpName } from "../utils/relyingParty.js";
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
    async function getRPData() {
      const data = await updateLinkStateAPI.getRPAuthUrl();
      setRpData(data);
    }

    getRPData();
  }, []);

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

  return (
    <GcdsContainer>
      <MigrationStepper currentStep={3} />
      <GcdsHeading tag="h1" lang={language}>
        {pageContentJson["title"]}
      </GcdsHeading>

      {errorMessage ? <GcdsText>{errorMessage}</GcdsText> : null}
      {rpName ? (
        <GcdsText>{replaceRpName(pageContentJson["text_1"], rpData, language)}</GcdsText>
      ) : null}
      <GcdsText>{pageContentJson["text_2"]}</GcdsText>
      <ul className="list-disc mt-0">
        <li>{pageContentJson["list_text_1"]}</li>
        <li>{pageContentJson["list_text_2"]}</li>
      </ul>
      <div className="mt-500">
        <GcdsButton
          onGcdsClick={(ev) => {
            ev.preventDefault();
            trackEvent({
              category: GA_CATEGORIES.formSubmit,
              action: GA_EVENTS.click,
              label: `${GA_LABELS.button}_MigrationConfirmation`,
              step: GA_STEPS.step2,
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
