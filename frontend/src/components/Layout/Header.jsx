import { GcdsContainer, GcdsHeader } from "@cdssnc/gcds-components-react";
import Breadcrumbs from "./Breadcrumbs";

export default function Header({ langHref, currentLang }) {
  return (
    <GcdsContainer className="gcds-header">
      <GcdsHeader
        langHref={langHref}
        skipToHref="#"
        signature-variant={"colour"}
        lang={currentLang}
      >
        <Breadcrumbs />
      </GcdsHeader>
    </GcdsContainer>
  );
}
