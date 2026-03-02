import { useEffect } from "react";
import { Outlet, useParams, useLocation } from "react-router";
import { useUser } from "./useUser.tsx";
import Loader from "../../components/Layout/Loading.jsx";

import { getPageContent } from "../../utils/functions.jsx";
import { OIDC_REDIRECT, PAGES } from "../../utils/constants.jsx";

function PrivateRoute() {
  const { state } = useUser();
  const { language } = useParams();
  const { pathname } = useLocation();
  const pageContentJson = getPageContent(language, PAGES.otpSelection);
  const isLanguageSyncRoute = /^\/(en|fr)\/link\/lang-sync\/?$/.test(pathname);

  useEffect(() => {
    if (!state.isLoading && !state.userProfile) {
      window.location.href = OIDC_REDIRECT.login;
    }
  }, [state.isLoading, state.userProfile]);
  if (state.isLoading)
    return (
      <Loader
        text={
          isLanguageSyncRoute
            ? "Loading / Chargement"
            : state.loadingText || pageContentJson["11"]
        }
      />
    );
  if (!state.userProfile) return null;

  return <Outlet />;
}

export { PrivateRoute };
