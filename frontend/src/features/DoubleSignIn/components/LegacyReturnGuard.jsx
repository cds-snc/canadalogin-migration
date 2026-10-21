import { useCallback, useLayoutEffect, useRef, useState } from "react";
import { Navigate, useLocation } from "react-router";
import Loader from "../../../components/Layout/Loading.jsx";
import { getPageContent } from "../../../utils/functions.jsx";
import {
  getRecoveryPath,
  getRecoveryReason,
} from "../../../utils/recoveryErrors.js";
import { updateLinkStateAPI } from "../api/UpdateLinkState.jsx";
import {
  getPromptEntry,
  preparePromptEntry,
} from "../utils/legacyNavigation.js";
import { MigrationReturnContext } from "../utils/MigrationReturnContext.js";

function isReturnedDocument() {
  const type = window.performance.getEntriesByType?.("navigation")?.[0]?.type;
  return type === "back_forward" || type === "reload";
}

// Cold returns are checked before UserProvider loads. Cached returns retain
// that provider while its choices are hidden, avoiding another profile load.
export default function LegacyReturnGuard({ children }) {
  const { key, pathname } = useLocation();
  const entryId = `${key}:${pathname}`;
  const language = pathname.split("/")[1] === "fr" ? "fr" : "en";
  const isPrompt = /^\/(en|fr)(\/link)?\/?$/.test(pathname) || pathname === "/";
  const initialDocument = useRef({ entryId, returned: isReturnedDocument() });
  const [view, setView] = useState(() => {
    const checking =
      isPrompt &&
      (Boolean(getPromptEntry()) || initialDocument.current.returned);
    return {
      entryId,
      checking,
      recoveryReason: null,
      recoveryRpId: null,
      hasAllowed: !checking,
      resumeVersion: 0,
    };
  });
  const currentEntry = useRef(null);
  const activationAllowed = useRef(!view.checking);
  const canActivate = useCallback(() => activationAllowed.current, []);

  useLayoutEffect(() => {
    let entry = currentEntry.current;
    if (entry?.id !== entryId) {
      if (entry) entry.active = false;
      entry = {
        id: entryId,
        active: true,
        initialized: false,
        promise: null,
        visit: 0,
        forceFresh: false,
      };
      currentEntry.current = entry;
    }
    entry.active = true;

    const isCurrent = () => entry.active && currentEntry.current === entry;
    const recover = (reason, rpClientId = null) => {
      if (!isCurrent()) return;
      activationAllowed.current = false;
      setView((previous) => ({
        ...previous,
        entryId,
        checking: false,
        recoveryReason: reason,
        recoveryRpId: reason === "migration-completed" ? rpClientId : null,
      }));
    };
    const checkReturn = () => {
      if (!isCurrent() || entry.promise) return;
      // Block actions immediately, before React renders the loading state.
      activationAllowed.current = false;
      setView((previous) => ({
        ...previous,
        entryId,
        checking: true,
        recoveryReason: null,
        recoveryRpId: null,
      }));
      const expectedRpId = getPromptEntry()?.rpClientId;
      if (typeof expectedRpId !== "string" || !expectedRpId.trim()) {
        recover("missing-rp-context");
        return;
      }

      const visit = entry.visit;
      const forceFresh = entry.forceFresh;
      entry.forceFresh = false;
      const isCurrentRequest = () => isCurrent() && entry.visit === visit;
      const request = Promise.resolve()
        .then(() => {
          if (!isCurrentRequest()) return null;
          return forceFresh
            ? updateLinkStateAPI.getMigrationStatus({ forceFresh: true })
            : updateLinkStateAPI.getMigrationStatus();
        })
        .then((status) => {
          if (!isCurrentRequest()) return;
          if (status?.rp_client_id !== expectedRpId) {
            recover("missing-rp-context");
            return;
          }
          if (typeof status.completed !== "boolean") {
            recover("service-unavailable");
            return;
          }
          if (status.completed) {
            recover("migration-completed", status.rp_client_id);
            return;
          }
          activationAllowed.current = true;
          setView((previous) => ({
            ...previous,
            entryId,
            checking: false,
            recoveryReason: null,
            recoveryRpId: null,
            hasAllowed: true,
            resumeVersion: previous.resumeVersion + 1,
          }));
        })
        .catch((error) => {
          if (!isCurrentRequest()) return;
          const response = error?.response || error;
          const reason =
            response?.status === 401 ||
            response?.data?.code === "authentication-required"
              ? "session-ended"
              : getRecoveryReason(error) || "service-unavailable";
          recover(reason);
        })
        .finally(() => {
          if (entry.promise === request) entry.promise = null;
        });
      entry.promise = request;
    };

    if (!entry.initialized) {
      entry.initialized = true;
      if (
        isPrompt &&
        (getPromptEntry() ||
          (initialDocument.current.entryId === entryId &&
            initialDocument.current.returned))
      ) {
        checkReturn();
      } else {
        if (isPrompt) preparePromptEntry();
        activationAllowed.current = true;
        setView((previous) => ({
          ...previous,
          entryId,
          checking: false,
          recoveryReason: null,
          recoveryRpId: null,
          hasAllowed: true,
        }));
      }
    }

    const handlePageShow = (event) => {
      if (isPrompt && event.persisted) checkReturn();
    };
    const handlePageHide = () => {
      if (!isPrompt) return;
      // A result requested before leaving cannot authorize a later visit.
      activationAllowed.current = false;
      entry.visit += 1;
      entry.promise = null;
      entry.forceFresh = true;
    };
    window.addEventListener("pageshow", handlePageShow);
    window.addEventListener("pagehide", handlePageHide);
    return () => {
      entry.active = false;
      window.removeEventListener("pageshow", handlePageShow);
      window.removeEventListener("pagehide", handlePageHide);
    };
  }, [entryId, isPrompt]);

  // A route change can precede the layout effect. Read its marker before
  // mounting a provider, but preserve providers across ordinary redirects.
  const sameEntry = view.entryId === entryId;
  const checking = sameEntry
    ? view.checking
    : isPrompt && Boolean(getPromptEntry());
  const recoveryReason = sameEntry ? view.recoveryReason : null;
  if (recoveryReason) {
    return (
      <Navigate
        to={getRecoveryPath(recoveryReason, language, view.recoveryRpId)}
        replace
      />
    );
  }

  return (
    <MigrationReturnContext.Provider
      value={{ checking, resumeVersion: view.resumeVersion, canActivate }}
    >
      {checking && (
        <Loader text={getPageContent(language, "SessionManagement")["9"]} />
      )}
      <div hidden={checking} inert={checking}>
        {(view.hasAllowed || !checking) && children}
      </div>
    </MigrationReturnContext.Provider>
  );
}
