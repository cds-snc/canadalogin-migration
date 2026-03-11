import { useCallback, useEffect } from "react";
import { useLocation } from "react-router";
import ReactGA from "react-ga4";
import { GA_CATEGORIES } from "./constants.jsx";

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
    ({ category, action, label, step }) => {
      if (!category || !action) return;

      ReactGA.event({
        category,
        action,
        label,
        step,
        page: pathname,
      });
    },
    [pathname],
  );
}
