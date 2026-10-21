import {
  useReducer,
  useEffect,
  ReactNode,
  useRef,
  useMemo,
  useState,
} from "react";
import {
  Navigate,
  useSearchParams,
  useParams,
  useLocation,
} from "react-router";
import {
  useEventSource,
  useEventSourceListener,
} from "@react-nano/use-event-source";
import config from "../../config";
import {
  SERVICES,
  CONTEXT_ACTIONS,
  SUBMIT_END_POINTS,
  RP_CLIENT_ID_KEY,
} from "../../utils/constants.jsx";
import UserContext from "./UserContext";
import { authService } from "../../services/authService.jsx";
import Loader from "../Layout/Loading.jsx";
import SessionTimeoutModal from "../Layout/SessionTimeoutModal.jsx";
import { getPageContent } from "../../utils/functions.jsx";
import { redirectToLogin } from "../../utils/apiErrorHandler.js";
import {
  getRecoveryPath,
  getRecoveryReason,
} from "../../utils/recoveryErrors.js";

interface Action {
  type: string;
  payload: any;
}

export interface UserProfile {
  id: string;
  active: boolean;
  details?: null | {
    emailVerified: boolean | null;
    lastLogin: string | null;
    lastMFA: string | null;
    twoFactorAuthentication: boolean;
    pwdChangedTime: string | null;
  };
  emails?: null | Array<{ value: string; type: string }>;
  phoneNumbers?: null | Array<{ value: string; type: string }>;
  meta?: {
    created: string;
    location: string;
    lastModified: string;
    resourceType: string;
  };
  userName: string;
  preferredLanguage?: string;
  name?: {
    givenName?: string;
    familyName?: string;
    formatted?: string;
  } | null;
}

export interface RelyingPartyInfo {
  icon: string;
  id: string;
  linkName: string;
  url: string;
}

export interface UserState {
  userProfile: UserProfile | null;
  userData: any;
  isLoading: boolean;
  loadingText: string | null;
  relyingPartyInfo: RelyingPartyInfo | null;
  authenticatedPages: string[];
}

export interface SessionTimeoutState {
  showModal: boolean;
  isLoading: boolean;
  expirationTime: number | null;
  newServerSideExpirationTime: number | null;
}

interface UserProviderProps {
  children: ReactNode;
  initial?: UserState;
  initialSessionTimeoutState?: SessionTimeoutState;
}

const initialState: UserState = {
  isLoading: true,
  loadingText: null,
  userData: {
    service: SERVICES[0].title, //to be set later when url referrer is given, also need to refactor other pages to use this value
    language: "en", //to be set later when refactoring possibly
    email: null,
    emailLanguage: null,
    emailValidated: false,
    trxnId: null,
    passwordSubmitted: false,
    phone: null,
    stepVerificationSent: false,
    stepVerified: false,
    viewPrivacy: false,
    id: null,
    otpType: null,
    passwordValidated: false,
  },
  userProfile: null,
  relyingPartyInfo: null,
  authenticatedPages: [],
};

const initialSessionState: SessionTimeoutState = {
  showModal: false,
  isLoading: false,
  expirationTime: null,
  newServerSideExpirationTime: null,
};

function userReducer(
  state: UserState = initialState,
  action: Action,
): UserState {
  switch (action.type) {
    case CONTEXT_ACTIONS.set_loading:
      if (typeof action.payload === "boolean") {
        return {
          ...state,
          isLoading: action.payload,
          loadingText: null,
        };
      }
      return {
        ...state,
        isLoading: action.payload.isLoading,
        loadingText: action.payload.text || null,
      };
    case CONTEXT_ACTIONS.updated_profile_success:
      return {
        ...state,
        userProfile: action.payload,
      };
    case CONTEXT_ACTIONS.set_relying_party_data:
      return {
        ...state,
        relyingPartyInfo: action.payload,
      };
    case CONTEXT_ACTIONS.set_authenticated_pages:
      return {
        ...state,
        authenticatedPages: [...state.authenticatedPages, action.payload],
      };
    case CONTEXT_ACTIONS.remove_authenticated_page:
      return {
        ...state,
        authenticatedPages: state.authenticatedPages.filter(
          (page) => page !== action.payload,
        ),
      };
    default:
      return state;
  }
}

function sessionTimeoutReducer(
  state: SessionTimeoutState = initialSessionState,
  action: Action,
): SessionTimeoutState {
  switch (action.type) {
    case CONTEXT_ACTIONS.show_session_timeout_modal:
      return {
        ...state,
        showModal: true,
        expirationTime: action.payload,
      };
    case CONTEXT_ACTIONS.hide_session_timeout_modal:
      return {
        ...state,
        showModal: false,
        expirationTime: null,
      };
    case CONTEXT_ACTIONS.reset_expire_time:
      // Avoid no-op updates that cause re-renders when the expire time didn't actually change
      if (state.newServerSideExpirationTime === action.payload) {
        return state;
      }
      return {
        ...state,
        newServerSideExpirationTime: action.payload,
      };
    default:
      return state;
  }
}

export function UserProvider({
  children,
  initial = initialState,
  initialSessionTimeoutState = initialSessionState,
}: UserProviderProps) {
  const [userState, userDispatch] = useReducer(userReducer, initial);
  const [recoveryReason, setRecoveryReason] = useState<string | null>(null);
  const [loginPending, setLoginPending] = useState(false);
  const recoveryStartedRef = useRef(false);
  const logoutStartedRef = useRef(false);
  const authenticatedRef = useRef(Boolean(initial.userProfile));
  const [sessionTimeoutState, sessionTimeoutDispatch] = useReducer(
    sessionTimeoutReducer,
    initialSessionTimeoutState,
  );
  const [searchParams] = useSearchParams();
  const { language } = useParams();
  const { pathname } = useLocation();
  const pageContentJson = getPageContent(language, "SessionManagement");
  const isLanguageSyncRoute = /^\/(en|fr)\/link\/lang-sync\/?$/.test(pathname);

  // keep latest expire in a ref so SSE handler can compare without capturing stale closure state
  const latestExpireRef = useRef<number | null>(
    sessionTimeoutState.newServerSideExpirationTime,
  );

  // Memoize provider value so consumers only re-render when userState or userDispatch change
  const contextValue = useMemo(
    () => ({ state: userState, dispatch: userDispatch }),
    [userState, userDispatch],
  );

  // Timer refs for session management
  const warningTimerRef = useRef<number | null>(null);
  const expireTimerRef = useRef<number | null>(null);

  // Session timeout configuration (in milliseconds)
  const WARNING_TIME = 5 * 60 * 1000; // 5 minutes before expiry

  // A new Verify entry authenticates through /me before it has an SSE session.
  const [eventSource] = useEventSource(
    userState.userProfile && !recoveryReason && !loginPending
      ? `${config.apiUrl}${SUBMIT_END_POINTS.sessionStatus}`
      : "",
    true,
  );

  // Clear existing timers
  const clearTimers = () => {
    if (warningTimerRef.current) {
      clearTimeout(warningTimerRef.current);
      warningTimerRef.current = null;
    }
    if (expireTimerRef.current) {
      clearTimeout(expireTimerRef.current);
      expireTimerRef.current = null;
    }
  };

  const showRecovery = (reason: string) => {
    if (recoveryStartedRef.current) return;
    recoveryStartedRef.current = true;
    clearTimers();
    if (eventSource) eventSource.close();
    setRecoveryReason(reason);
  };

  // Start session timers with specific expire time from SSE
  const resetSessionTimers = (expireTimestamp: number) => {
    clearTimers();
    if (!authenticatedRef.current || recoveryStartedRef.current) return;

    // Convert expire timestamp to milliseconds if it's in seconds
    const expireTimeMs = expireTimestamp * 1000;
    const currentTime = Date.now();
    const timeUntilExpire = expireTimeMs - currentTime;

    // Only set timers if expire time is in the future
    if (timeUntilExpire <= 0) {
      console.warn("Session already expired based on provided expire time");
      showRecovery("session-ended");
      return;
    }

    // Set warning timer (5 minutes before expire time, but not if less than 5 minutes remain)
    const timeUntilWarning =
      timeUntilExpire > WARNING_TIME ? timeUntilExpire - WARNING_TIME : 0;
    if (timeUntilWarning > 0) {
      warningTimerRef.current = setTimeout(() => {
        sessionTimeoutDispatch({
          type: CONTEXT_ACTIONS.show_session_timeout_modal,
          payload: expireTimeMs,
        });
      }, timeUntilWarning);
    } else {
      // If less than 5 minutes remain, show the modal immediately
      sessionTimeoutDispatch({
        type: CONTEXT_ACTIONS.show_session_timeout_modal,
        payload: expireTimeMs,
      });
    }

    // Set expire timer
    expireTimerRef.current = setTimeout(() => {
      showRecovery("session-ended");
    }, timeUntilExpire);

    console.log(
      `Session timers set: warning in ${timeUntilWarning}ms, expire in ${timeUntilExpire}ms`,
    );
  };

  // Handle keep session alive
  const handleKeepSession = async () => {
    try {
      const response = await authService.keepAlive();
      if (
        response?.success === false ||
        ["terminated", "expired"].includes(response?.data?.status)
      ) {
        showRecovery("session-ended");
        return;
      }
      if (!Number.isFinite(response?.data?.expire)) {
        showRecovery("service-unavailable");
        return;
      }
      sessionTimeoutDispatch({
        type: CONTEXT_ACTIONS.hide_session_timeout_modal,
        payload: null,
      });
      sessionTimeoutDispatch({
        type: CONTEXT_ACTIONS.reset_expire_time,
        payload: response.data.expire,
      });
    } catch (error) {
      console.error("Error keeping session alive:", error);
      showRecovery(getRecoveryReason(error) || "service-unavailable");
    }
  };
  // Handle logout
  const handleLogout = async () => {
    logoutStartedRef.current = true;
    clearTimers();
    if (eventSource) eventSource.close();
    try {
      const response = await authService.logout();
      // Check if response has redirect_url and redirect
      if (response && response.data && response.data.redirect_url) {
        window.location.href = response.data.redirect_url;
      } else {
        showRecovery("session-ended");
      }
    } catch (error) {
      console.error("Error during logout:", error);
      showRecovery(getRecoveryReason(error) || "service-unavailable");
    }
  };

  useEventSourceListener(
    eventSource,
    ["expired", "error", "notification", "terminated"],
    (event) => {
      if (
        !authenticatedRef.current ||
        recoveryStartedRef.current ||
        logoutStartedRef.current
      )
        return;
      if (event.type === "expired" || event.type === "terminated") {
        showRecovery("session-ended");
        return;
      }
      if (event.type === "error") {
        // Native connection errors have no payload and can reconnect. Only a
        // coded server event establishes that recovery is needed.
        if (!event.data) return;
        try {
          const eventData = JSON.parse(event.data);
          const reason = getRecoveryReason({ data: eventData });
          if (eventData.code && reason) showRecovery(reason);
        } catch (error) {
          console.error("Error parsing SSE error data:", error);
        }
        return;
      }
      if (event.type === "notification") {
        // Parse the event data and check status
        try {
          const eventData = JSON.parse(event.data);
          console.debug("SSE notification:", eventData);

          if (
            eventData.status === "active" &&
            Number.isFinite(eventData.expire)
          ) {
            // Only dispatch if expire changed to avoid unnecessary re-renders
            if (latestExpireRef.current !== eventData.expire) {
              console.debug(
                "SSE notification: resetting session timers based on new expire time",
                eventData.expire,
              );
              sessionTimeoutDispatch({
                type: CONTEXT_ACTIONS.reset_expire_time,
                payload: eventData.expire,
              });
            } else {
              console.debug(
                "SSE notification: expire time unchanged, no action taken",
                eventData.expire,
              );
            }
          } else {
            console.log(
              "SSE notification: status not active or missing expire time",
              eventData,
            );
          }
        } catch (error) {
          console.error(
            "Error parsing SSE notification data:",
            error,
            event.data,
          );
        }
      }
    },
    [sessionTimeoutDispatch], // Dependencies for the listener callback
  );

  useEffect(() => {
    const fetchProfileAndRelyingPartyInfo = async () => {
      try {
        // After an OIDC redirect, store any RP context from the redirect URL
        // through a CSRF-protected POST before reading the profile. Later reads
        // use the existing session context without changing it through GET.
        const rp_client_id = searchParams.get(RP_CLIENT_ID_KEY);

        const response = await authService.get_my_user_profile(rp_client_id);
        if (response && response.data) {
          // User is authenticated, set the profile
          authenticatedRef.current = true;
          userDispatch({
            type: CONTEXT_ACTIONS.updated_profile_success,
            payload: response.data,
          });
        } else {
          showRecovery("service-unavailable");
        }
      } catch (err) {
        const response = (err as any)?.response || err;
        const clientId = searchParams.get(RP_CLIENT_ID_KEY);
        if (
          response?.status === 401 &&
          response?.data?.code === "authentication-required" &&
          clientId
        ) {
          // Preserve the RP supplied by Verify when starting OIDC authentication.
          setLoginPending(true);
          redirectToLogin(clientId, language);
        } else {
          showRecovery(
            getRecoveryReason(err) ||
              (response?.data?.code === "authentication-required"
                ? "session-ended"
                : "service-unavailable"),
          );
        }
      } finally {
        // Recovery/login state takes precedence over rendering PrivateRoute.
        userDispatch({
          type: CONTEXT_ACTIONS.set_loading,
          payload: { isLoading: false, text: pageContentJson["9"] },
        });
      }
    };

    fetchProfileAndRelyingPartyInfo();
    return () => {
      // Cleanup on unmount
      clearTimers();
      if (eventSource) eventSource.close();
    };
  }, []);

  // Start timers when newServerSideExpirationTime is set/updated
  useEffect(() => {
    latestExpireRef.current = sessionTimeoutState.newServerSideExpirationTime;
    if (sessionTimeoutState.newServerSideExpirationTime) {
      resetSessionTimers(sessionTimeoutState.newServerSideExpirationTime);
    }

    return () => {};
  }, [sessionTimeoutState.newServerSideExpirationTime]);

  if (recoveryReason) {
    return <Navigate to={getRecoveryPath(recoveryReason, language)} replace />;
  }

  if (userState.isLoading || loginPending) {
    return (
      <Loader
        text={
          isLanguageSyncRoute
            ? "Loading / Chargement"
            : userState.loadingText || pageContentJson["9"]
        }
      />
    );
  }

  return (
    <UserContext.Provider value={contextValue}>
      {children}
      <SessionTimeoutModal
        isOpen={sessionTimeoutState.showModal}
        expirationTime={sessionTimeoutState.expirationTime}
        onKeepSession={handleKeepSession}
        onLogout={handleLogout}
        isLoading={sessionTimeoutState.isLoading}
        currentLang={language}
      />
    </UserContext.Provider>
  );
}
