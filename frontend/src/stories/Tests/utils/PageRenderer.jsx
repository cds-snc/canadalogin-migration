import React from "react";
import { PAGES } from "../../../utils/constants.jsx";

import DeleteMFAPage from "../../../features/MFAPhoneNumber/DeleteMFAPhoneNumber/component/DeleteMFAPage.jsx";
import DeleteMFAPhoneNumberConfirm from "../../../features/MFAPhoneNumber/DeleteMFAPhoneNumber/component/DeleteMFAPhoneNumberConfirm.jsx";

const PageRenderer = ({ page, ...props }) => {
  switch (page) {
    case PAGES.deleteMFAPage:
      return <DeleteMFAPage />;
    case PAGES.deleteMFAPhoneNumberConfirm:
      return <DeleteMFAPhoneNumberConfirm {...props} />;
    default:
      return null;
  }
};

export default PageRenderer;
