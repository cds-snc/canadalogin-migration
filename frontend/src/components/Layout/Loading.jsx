import { GcdsContainer, GcdsHeading } from "@gcds-core/components-react";

export default function Loader({ text }) {
  return (
    <>
      <GcdsContainer className="page-loader">
        <div className="loader-fixed-position">
          <GcdsHeading tag="h1">{text}</GcdsHeading>
        </div>
      </GcdsContainer>
    </>
  );
}
