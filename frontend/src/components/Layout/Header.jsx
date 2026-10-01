import { GcdsContainer, GcdsHeader } from "@gcds-core/components-react";
import Breadcrumbs from "./Breadcrumbs";
import TopNav from "./TopNav";

export default function Header({
  langHref,
  currentLang,
  showBreadcrumbs = true,
}) {
  return (
    <GcdsContainer className="gcds-header">
      <GcdsHeader
        langHref={langHref}
        skipToHref="#main-content"
        signature-variant={"colour"}
        lang={currentLang}
      >
        <TopNav currentLang={currentLang} />
        {showBreadcrumbs ? <Breadcrumbs /> : null}
      </GcdsHeader>
    </GcdsContainer>
  );
}
