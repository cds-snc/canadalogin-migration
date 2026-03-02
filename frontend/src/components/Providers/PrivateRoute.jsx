import { useEffect } from "react";
import { Outlet, useParams } from "react-router";
import { useUser } from "./useUser.tsx";
import Loader from "../../components/Layout/Loading.jsx";

import { getPageContent } from "../../utils/functions.jsx";
import { OIDC_REDIRECT, PAGES } from "../../utils/constants.jsx";

function PrivateRoute() {
  const { state } = useUser();
  const { language } = useParams();
  const pageContentJson = getPageContent(language, PAGES.otpSelection);

  useEffect(() => {
    if (!state.isLoading && !state.userProfile) {
      window.location.href = OIDC_REDIRECT.login;
    }
  }, [state.isLoading, state.userProfile]);
  if (state.isLoading)
    return <Loader text={state.loadingText || pageContentJson["11"]} />;
  if (!state.userProfile) return null;

  return <Outlet />;
}

export { PrivateRoute };
