import { GcdsContainer, GcdsHeader } from "@cdssnc/gcds-components-react";
import Breadcrumbs from "./Breadcrumbs";
import TopNav from "./TopNav";

export default function Header({ langHref, currentLang }) {
  return (
    <GcdsContainer className="gcds-header">
      <GcdsHeader
        langHref={langHref}
        skipToHref="#"
        signature-variant={"colour"}
        lang={currentLang}
      >
        <TopNav currentLang={currentLang} />
        <Breadcrumbs />
      </GcdsHeader>
    </GcdsContainer>
  );
}
