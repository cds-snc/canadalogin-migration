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

  useEffect(() => {
    async function getRPAuthUrl() {
      configRef.rpAuthUrl = await updateLinkStateAPI.getRPAuthUrl();
    }

    getRPAuthUrl();
  }, []);

  const continueToRP = async () => {
    try {
      console.log("info", "clicked start linking and continue back to rp");

      window.location.replace(configRef.rpAuthUrl);
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
      <gcds-text>{pageContentJson["text_1"]}</gcds-text>
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
