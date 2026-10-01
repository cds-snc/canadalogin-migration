import { useEffect } from "react";
import { Navigate, Outlet, useParams, useLocation } from "react-router";
import { useUser } from "./useUser.tsx";
import Loader from "../../components/Layout/Loading.jsx";

import { getPageContent } from "../../utils/functions.jsx";
import { PAGES, RP_CLIENT_ID_KEY } from "../../utils/constants.jsx";
import { redirectToLogin } from "../../utils/apiErrorHandler.js";
import { getRecoveryPath } from "../../utils/recoveryErrors.js";

function PrivateRoute() {
  const { state } = useUser();
  const { language } = useParams();
  const { pathname, search } = useLocation();
  const clientId = new URLSearchParams(search).get(RP_CLIENT_ID_KEY);
  const pageContentJson = getPageContent(language, PAGES.otpSelection);
  const isLanguageSyncRoute = /^\/(en|fr)\/link\/lang-sync\/?$/.test(pathname);

  useEffect(() => {
    if (!state.isLoading && !state.userProfile && clientId) {
      redirectToLogin(clientId, language);
    }
  }, [state.isLoading, state.userProfile, clientId, language]);
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
  if (!state.userProfile) {
    return clientId ? null : (
      <Navigate to={getRecoveryPath("session-ended", language)} replace />
    );
  }

  return <Outlet />;
}

export { PrivateRoute };
