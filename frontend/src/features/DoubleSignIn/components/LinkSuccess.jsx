import { useEffect, useState } from "react";
import {
  GcdsContainer,
  GcdsText,
  GcdsButton,
  GcdsHeading,
} from "@cdssnc/gcds-components-react";
import { getPageContent } from "../../../utils/functions.jsx";

import { PAGES } from "../../../utils/constants.jsx";
import { useParams } from "react-router";

import { updateLinkStateAPI } from "../api/UpdateLinkState.jsx";
import { MigrationStepper } from "./MigrationStepper.jsx";

export default function LinkSuccess() {
  const { language } = useParams();

  const [serverErrorMessage, setServerErrorMessage] = useState("");

  const pageContentJson = getPageContent(language, PAGES.LinkSuccess);
  const errorPageJson = getPageContent(language, PAGES.error);

  const [rpData, setRpData] = useState(null);

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

  return (
    <GcdsContainer>
      <MigrationStepper currentStep={3} />
      <GcdsHeading tag="h1" lang={language}>
        {pageContentJson["title"]}
      </GcdsHeading>

      {errorMessage ? <GcdsText>{errorMessage}</GcdsText> : null}
      <GcdsText>
        {pageContentJson["text_1"].replace(
          "{RP_Name}",
          language != "en"
            ? rpData?.rp_client_name_fr
            : rpData?.rp_client_name_en,
        )}
      </GcdsText>
      <GcdsText>{pageContentJson["text_2"]}</GcdsText>
      <ul className="list-disc mt-0">
        <li>{pageContentJson["list_text_1"]}</li>
        <li>{pageContentJson["list_text_2"]}</li>
      </ul>
      <div className="mt-500">
        <GcdsButton
          onGcdsClick={(ev) => {
            ev.preventDefault();
            continueToRP();
          }}
        >
          {pageContentJson["btn_1"]}
        </GcdsButton>
      </div>
    </GcdsContainer>
  );
}
