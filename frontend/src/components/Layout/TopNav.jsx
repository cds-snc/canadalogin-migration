import {
  GcdsContainer,
  GcdsNavLink,
  GcdsText,
  GcdsTopNav,
} from "@cdssnc/gcds-components-react";
import { getPageContent } from "../../utils/functions.jsx";
import { useBreakpoints } from "../../hooks/useBreakpoints.ts";

export default function TopNav({ currentLang }) {
  const { mobile, tablet } = useBreakpoints();
  const pageContentJson = getPageContent(currentLang, "TopNavBar");
  const homeLink = ""; //path(PAGES.manageDashboard, { language: currentLang });

  if (mobile || tablet) {
    return (
      <GcdsContainer slot="menu" mainContainer padding="100 0">
        <GcdsText size="small" marginBottom="0">
          {pageContentJson["1"]}
        </GcdsText>
      </GcdsContainer>
    );
  }

  return (
    <GcdsTopNav
      slot="menu"
      label="Top navigation"
      alignment="right"
      lang={currentLang}
      className="gcds-top-nav"
    >
      <GcdsNavLink href={homeLink} slot="home">
        {pageContentJson["1"]}
      </GcdsNavLink>
    </GcdsTopNav>
  );
}
