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

import { updateLinkStateAPI } from "../api/UpdateLinkState.jsx";
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
  GA_LABELS,
  GA_CATEGORIES,
  GA_EVENTS,
  GA_FORM_EVENTS,
  GA_STEPS,
  MIGRATION_ANALYTICS,
} from "../../../utils/constants.jsx";

export default function LinkPrompt() {
  const { language } = useParams();

  const trackEvent = useTrackEvent();

  const [serverErrorMessage] = useState("");

  const pageContentJson = getPageContent(language, PAGES.LinkPrompt);
  const errorPageJson = getPageContent(language, PAGES.error);

  useTrackPage("Migration - Legacy method prompt");

  const [links, setLinks] = useState({
    LinkingLink: "",
    SkipLink: "",
  });

  const [rpData, setRpData] = useState(null);

  useEffect(() => {
    async function getRPData() {
      try {
        const data = await updateLinkStateAPI.getRPAuthUrl();
        setRpData(data);
      } catch (e) {
        console.error("Failed loading RP data", e);
      }
    }

    try {
      const LinkingLink = MIGRATION_END_POINTS.login + "?lang=" + language;
      const SkipLink = MIGRATION_END_POINTS.skip;

      setLinks({ LinkingLink, SkipLink });
    } catch (e) {
      console.error("Failed building links", e);
    }

    getRPData();
  }, [language]);

  const errorMessage = errorPageJson[serverErrorMessage] || "";
  const isGcKeyOnly = Boolean(rpData?.is_gckey_only);
  const rpName = getLocalizedRpName(rpData, language);
  const rpAnalyticsParams = getRpAnalyticsParams(rpData);
  const linkButtonText = isGcKeyOnly
    ? pageContentJson["btn_1_gckey_only"] || pageContentJson["btn_1"]
    : pageContentJson["btn_1"];
  const skipHelpText = isGcKeyOnly
    ? pageContentJson["text_4_gckey_only"] || pageContentJson["text_4"]
    : pageContentJson["text_4"];

  return (
    <GcdsContainer>
      <MigrationStepper currentStep={2} />
      <GcdsHeading tag="h1" lang={language}>
        {pageContentJson["title"]}
      </GcdsHeading>

      {errorMessage ? <GcdsText>{errorMessage}</GcdsText> : null}

      {rpName ? (
        <GcdsText>
          {replaceRpName(pageContentJson["text_2"], rpData, language)}
        </GcdsText>
      ) : null}
      <GcdsText>{pageContentJson["text_3"]}</GcdsText>
      <GcdsButton
        type="link"
        href={links.LinkingLink}
        onGcdsClick={() => {
          trackEvent({
            category: GA_CATEGORIES.formSubmit,
            action: GA_EVENTS.click,
            label: `${GA_LABELS.button}_StartMigration`,
            form_id: MIGRATION_ANALYTICS.flowId,
            step: GA_STEPS.step1,
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
          <GcdsLink href={pageContentJson["link_1_url"]} external>
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
      <GcdsText>
        <GcdsLink
          href={links.SkipLink}
          onGcdsClick={() => {
            trackEvent({
              category: GA_CATEGORIES.formSubmit,
              action: GA_EVENTS.click,
              label: `${GA_LABELS.link}_SkipMigration`,
              form_id: MIGRATION_ANALYTICS.flowId,
              step: GA_STEPS.step1,
              ...rpAnalyticsParams,
            });
            trackEvent({
              category: GA_CATEGORIES.formSubmit,
              action: GA_FORM_EVENTS.formSubmitComplete,
              label: `${GA_LABELS.link}_MigrationComplete`,
              form_id: MIGRATION_ANALYTICS.flowId,
              step: MIGRATION_ANALYTICS.steps.complete,
              type: MIGRATION_ANALYTICS.completionTypes.skipped,
              status: "success",
              ...rpAnalyticsParams,
            });
          }}
        >
          {pageContentJson["link_2"]}
        </GcdsLink>
      </GcdsText>
    </GcdsContainer>
  );
}
