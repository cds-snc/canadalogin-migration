import { useContext, useEffect, useRef, useState } from "react";
import { updateLinkStateAPI } from "../api/UpdateLinkState.jsx";
import { MigrationReturnContext } from "../utils/MigrationReturnContext.js";

export function useSkipLink(language, onSuccess) {
  const { checking, resumeVersion, canActivate } = useContext(
    MigrationReturnContext,
  );
  const inProgress = useRef(null);
  const lastResumeVersion = useRef(resumeVersion);
  const completedSkip = useRef(null);
  const [isSkipping, setIsSkipping] = useState(false);
  const [isLinking, setIsLinking] = useState(false);
  const [skipFailed, setSkipFailed] = useState(false);

  useEffect(() => {
    if (lastResumeVersion.current === resumeVersion) return;
    lastResumeVersion.current = resumeVersion;
    // Only the guard's confirmed incomplete result can reopen a legacy choice.
    // A status read must never release a pending Skip POST.
    if (inProgress.current === "link") {
      inProgress.current = null;
      setIsLinking(false);
      setSkipFailed(false);
    }
  }, [resumeVersion]);

  const startLinking = () => {
    if (inProgress.current || checking || !canActivate()) return false;
    inProgress.current = "link";
    // Discard any earlier Skip destination when making a new choice.
    completedSkip.current = null;
    setIsLinking(true);
    setSkipFailed(false);
    return true;
  };

  const skipLink = async () => {
    // Both choices share a synchronous guard against competing requests.
    if (inProgress.current || checking || !canActivate()) return;
    inProgress.current = "skip";
    setIsSkipping(true);
    setSkipFailed(false);

    try {
      if (completedSkip.current?.language !== language) {
        completedSkip.current = null;
        const { redirect_url } = await updateLinkStateAPI.skipLinking(language);
        // Reuse confirmed work only if navigation itself fails. Back is checked
        // against IBM by LegacyReturnGuard before choices can be used again.
        completedSkip.current = { language, redirectUrl: redirect_url };
        onSuccess?.();
      }
      window.location.assign(completedSkip.current.redirectUrl);
    } catch {
      setSkipFailed(true);
      setIsSkipping(false);
      inProgress.current = null;
    }
  };

  return {
    skipLink,
    startLinking,
    isSkipping,
    isLinking,
    isChecking: checking,
    skipFailed,
  };
}
