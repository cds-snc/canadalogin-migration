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
} from "@gcds-core/components-react";
import { getPageContent } from "../../../utils/functions.jsx";

import { MIGRATION_END_POINTS, PAGES } from "../../../utils/constants.jsx";
import { useParams } from "react-router";
import { useSearchParams } from "react-router-dom";

export default function SkipLink() {
  const { language } = useParams();
  const [searchParams] = useSearchParams();
  const pageContentJson = getPageContent(language, PAGES.SkipLink);

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

        // Debug:
        console.log("LinkingLink:", LinkingLink);
        console.log("SkipLink   :", SkipLink);
      } catch (e) {
        console.error("Failed building links", e);
      }
    })();
    // include deps that change this computation
  }, [language, searchParams]);

  return (
    <GcdsContainer role="main">
      <GcdsHeading tag="h1" lang={language}>
        {pageContentJson["title"]}
      </GcdsHeading>
      <GcdsText>{pageContentJson["text_1"]}</GcdsText>
      <GcdsText>{pageContentJson["text_2"]}</GcdsText>
      <GcdsGrid columns="1" gap="300">
        <GcdsButton
          id="confirm-link-account-button"
          buttonId="confirm-link-account-button-control"
          type="link"
          href={links.LinkingLink}
          class="m-400"
        >
          {pageContentJson["btn_1"]}
        </GcdsButton>
        <GcdsButton
          id="confirm-skip-create-account-button"
          buttonId="confirm-skip-create-account-button-control"
          type="link"
          href={links.LinkingLink}
          buttonRole="secondary"
        >
          {pageContentJson["btn_2"]}
        </GcdsButton>
      </GcdsGrid>
    </GcdsContainer>
  );
}
