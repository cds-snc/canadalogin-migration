import { useEffect, useState, useRef } from "react";
import {
  GcdsContainer,
  GcdsText,
  GcdsDetails,
  GcdsInput,
  GcdsStepper,
  GcdsLink,
  GcdsCheckboxes,
  GcdsGrid,
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

  const configRef = useRef(null);

  const [rpData, setRpData] = useState(null);

  useEffect(() => {
    async function getRPData() {
      const data = await updateLinkStateAPI.getRPAuthUrl();
      console.log("data", data);
      setRpData(data);

      // optional: keep ref if other non-UI logic uses it
      configRef.current = {
        ...configRef.current,
        rpData: data,
      };
    }

    getRPData();
  }, []);

  const continueToRP = async () => {
    try {
      console.log("info", "clicked start linking and continue back to rp");
      const redirectUrl =
        language != "en" ? rpData?.rp_redirect_url : rpData?.rp_redirect_url;
      window.location.replace(redirectUrl);
    } catch (err) {
      if (err && err.data && err.data.message) {
        setServerErrorMessage(err.data.message);
      }
      console.log("err", err);
    }
  };

  const errorMessage = errorPageJson[serverErrorMessage] || "";

  const steps = [
    { description: "Create a GC Sign in or sign in" },
    { description: "Link your old sign-in method" },
    { description: "Access your existing account" },
  ];

  return (
    <GcdsContainer>
      <MigrationStepper steps={steps} currentStep={3} />
      <GcdsHeading tag="h1" lang={language}>
        {pageContentJson["title"]}
      </GcdsHeading>

      <GcdsText>{errorMessage}</GcdsText>
      <gcds-text>
        {pageContentJson["text_1"].replace(
          "{RP_Name}",
          language != "en"
            ? rpData?.rp_client_name_fr
            : rpData?.rp_client_name_en,
        )}
      </gcds-text>
      <gcds-text>
        {pageContentJson["text_2"]}
        <ul class="list-disc">
          <li>{pageContentJson["list_text_1"]}</li>
          <li>{pageContentJson["list_text_2"]}</li>
        </ul>
      </gcds-text>
      <GcdsButton
        onGcdsClick={(ev) => {
          ev.preventDefault();
          continueToRP();
        }}
      >
        {pageContentJson["btn_1"]}
      </GcdsButton>
    </GcdsContainer>
  );
}
