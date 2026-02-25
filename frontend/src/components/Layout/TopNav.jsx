import {
  GcdsNavLink,
  GcdsTopNav,
} from "@cdssnc/gcds-components-react";
import { getPageContent } from "../../utils/functions.jsx";

export default function TopNav({ currentLang }) {
  const pageContentJson = getPageContent(currentLang, "TopNavBar");
  const homeLink = ""; //path(PAGES.manageDashboard, { language: currentLang });

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
