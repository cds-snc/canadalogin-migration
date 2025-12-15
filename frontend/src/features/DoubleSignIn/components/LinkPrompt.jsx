import { useState, useEffect, useRef } from "react";
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
  GcdsIcon,
  GcdsNotice,
} from "@cdssnc/gcds-components-react";
import { getPageContent } from "../../../utils/functions.jsx";
import { MIGRATION_END_POINTS, PAGES } from "../../../utils/constants.jsx";
import { useParams } from "react-router";
import { useSearchParams } from "react-router-dom";
import { MigrationStepper } from "./MigrationStepper.jsx";

export default function LinkPrompt() {
  const { language } = useParams();

  const [serverErrorMessage] = useState("");
  const [searchParams] = useSearchParams();

  const pageContentJson = getPageContent(language, PAGES.LinkPrompt);
  const errorPageJson = getPageContent(language, PAGES.error);

  const configRef = useRef({}); // <-- never null
  const [links, setLinks] = useState({
    LinkingLink: "",
    SkipLink: "",
  });

  useEffect(() => {
    (async () => {
      try {
        // 1) Fetch/build values
        const LinkingLink = MIGRATION_END_POINTS.login;
        const SkipLink = MIGRATION_END_POINTS.skip;

        // 2) Write to ref (safe)
        configRef.current = {
          ...configRef.current,
          LinkingLink,
          SkipLink,
        };

        // 3) Mirror to state so UI updates
        setLinks(configRef.current);

        // Debug
        console.log("linkSuccess:", LinkingLink);
        console.log("skipLink   :", SkipLink);
      } catch (e) {
        console.error("Failed building links", e);
      }
    })();
    // include deps that change this computation
  }, [language, searchParams]);

  const skipHref = links.toSkipLinkPage?.startsWith("http")
    ? links.toSkipLinkPage
    : `${window.location.origin}${links.toSkipLinkPage || ""}`;

  const errorMessage = errorPageJson[serverErrorMessage] || "";

  const steps = [
    { description: "Create a GC Sign in or sign in" },
    { description: "Link your old sign-in method" },
    { description: "Access your existing account" },
  ];

  return (
    <GcdsContainer>
      <MigrationStepper steps={steps} currentStep={2} />
      <GcdsHeading tag="h1" lang={language}>
        {pageContentJson["title"]}
      </GcdsHeading>

      <GcdsText>{errorMessage}</GcdsText>

      <GcdsText>{pageContentJson["text_2"]}</GcdsText>
      <GcdsText>{pageContentJson["text_3"]}</GcdsText>
      <GcdsButton type="link" href={links.LinkingLink}>
        {pageContentJson["btn_1"]}
      </GcdsButton>

      <div className="mt-500 mb-700">
        <GcdsNotice
          type="info"
          noticeTitle="For more information"
          noticeTitleTag="h2"
          lang={language}
        >
          <GcdsLink href="#" external>
            {pageContentJson["link_1"]}
          </GcdsLink>
        </GcdsNotice>
      </div>

      <GcdsHeading tag="h2">{pageContentJson["subtitle"]}</GcdsHeading>
      <GcdsText>{pageContentJson["text_4"]}</GcdsText>
      <GcdsText>
        <GcdsLink key={skipHref} href={links.SkipLink}>
          {pageContentJson["link_2"]}
        </GcdsLink>
      </GcdsText>
    </GcdsContainer>
  );
}
