import { GcdsNavLink, GcdsTopNav } from "@cdssnc/gcds-components-react";
import { getPageContent } from "../../utils/functions.jsx";
import { useBreakpoints } from "../../hooks/useBreakpoints.ts";

export default function TopNav({ currentLang }) {
  const { mobile, tablet } = useBreakpoints();
  const pageContentJson = getPageContent(currentLang, "TopNavBar");
  const homeLink = ""; //path(PAGES.manageDashboard, { language: currentLang });

  if (mobile || tablet) {
    return (
      <div slot="menu" className="gcds-top-nav-mobile-label">
        {pageContentJson["1"]}
      </div>
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
