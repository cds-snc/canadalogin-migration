import { useRef, useState } from "react";
import { updateLinkStateAPI } from "../api/UpdateLinkState.jsx";

export function useSkipLink(language, onSuccess) {
  const inProgress = useRef(false);
  const [isSkipping, setIsSkipping] = useState(false);
  const [skipFailed, setSkipFailed] = useState(false);

  const skipLink = async () => {
    // Prevent repeated link activations from submitting duplicate requests.
    if (inProgress.current) return;
    inProgress.current = true;
    setIsSkipping(true);
    setSkipFailed(false);

    try {
      const { redirect_url } = await updateLinkStateAPI.skipLinking(language);
      onSuccess?.();
      window.location.assign(redirect_url);
    } catch {
      setSkipFailed(true);
      setIsSkipping(false);
      inProgress.current = false;
    }
  };

  return { skipLink, isSkipping, skipFailed };
}
