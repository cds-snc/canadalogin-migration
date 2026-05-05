import { useCallback, useEffect } from "react";
import { useLocation } from "react-router";
import ReactGA from "react-ga4";
import { GA_CATEGORIES } from "./constants.jsx";

function removeEmptyParams(params) {
  return Object.fromEntries(
    Object.entries(params).filter(
      ([, value]) => value !== undefined && value !== null && value !== "",
    ),
  );
}

export function trackPage(pagePath, pageTitle) {
  ReactGA.send({
    hitType: GA_CATEGORIES.pageView,
    page: pagePath,
    title: pageTitle,
  });
}

export function useTrackPage(pageTitle) {
  const { pathname } = useLocation();

  useEffect(() => {
    if (!pageTitle) return;
    trackPage(pathname, pageTitle);
  }, [pathname, pageTitle]);
}

export function useTrackEvent() {
  const { pathname } = useLocation();

  return useCallback(
    ({ category, action, label, ...params }) => {
      if (!category || !action) return;

      ReactGA.event(action, {
        event_category: category,
        transport_type: "beacon",
        ...removeEmptyParams({
          event_label: label,
          ...params,
          page: pathname,
        }),
      });
    },
    [pathname],
  );
}
