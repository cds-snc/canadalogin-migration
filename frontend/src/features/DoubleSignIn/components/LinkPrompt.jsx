import { useState, useEffect } from "react";
import {
  GcdsContainer,
  GcdsText,
  GcdsLink,
  GcdsButton,
  GcdsHeading,
  GcdsNotice,
} from "@cdssnc/gcds-components-react";
import { getPageContent } from "../../../utils/functions.jsx";

import { updateLinkStateAPI } from "../api/UpdateLinkState.jsx";
import { MIGRATION_END_POINTS, PAGES } from "../../../utils/constants.jsx";
import { useParams } from "react-router";
import { MigrationStepper } from "./MigrationStepper.jsx";

export default function LinkPrompt() {
  const { language } = useParams();

  const [serverErrorMessage] = useState("");

  const pageContentJson = getPageContent(language, PAGES.LinkPrompt);
  const errorPageJson = getPageContent(language, PAGES.error);

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

  return (
    <GcdsContainer>
      <MigrationStepper currentStep={2} />
      <GcdsHeading tag="h1" lang={language}>
        {pageContentJson["title"]}
      </GcdsHeading>

      {errorMessage ? <GcdsText>{errorMessage}</GcdsText> : null}

      <GcdsText>
        {pageContentJson["text_2"].replace(
          "{RP_Name}",
          language != "en"
            ? rpData?.rp_client_name_fr
            : rpData?.rp_client_name_en,
        )}
      </GcdsText>
      <GcdsText>{pageContentJson["text_3"]}</GcdsText>
      <GcdsButton type="link" href={links.LinkingLink}>
        {pageContentJson["btn_1"]}
      </GcdsButton>

      <div className="mt-500 mb-700">
        <GcdsNotice
          type="info"
          noticeTitle={pageContentJson["notice_title"]}
          noticeTitleTag="h2"
          lang={language}
        >
          <GcdsLink href="#" external>
            {pageContentJson["link_1"]}
          </GcdsLink>
        </GcdsNotice>
      </div>
      <GcdsHeading tag="h2" lang={language}>
        {pageContentJson["subtitle"].replace(
          "{RP_Name}",
          language != "en"
            ? rpData?.rp_client_name_fr
            : rpData?.rp_client_name_en,
        )}
      </GcdsHeading>
      <GcdsText>{pageContentJson["text_4"]}</GcdsText>
      <GcdsText>
        <GcdsLink href={links.SkipLink}>{pageContentJson["link_2"]}</GcdsLink>
      </GcdsText>
    </GcdsContainer>
  );
}
