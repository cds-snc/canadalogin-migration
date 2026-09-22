# CSRF protection

The browser sends the migration session cookie automatically. A CSRF token adds
a value that the frontend must explicitly send before the backend accepts an
action. A different website cannot normally read this value because the browser's
same-origin policy and the backend's CORS allowlist prevent it.

This application uses a **synchronizer token**: the backend stores a random token
in the existing Redis session and compares it with the `X-CSRF-Token` request
header. Authentication and authorization still apply after that check.

## Follow one request

For example, when a user chooses to skip linking:

```mermaid
sequenceDiagram
    participant UI as React
    participant API as FastAPI
    participant Session as Redis session
    UI->>API: GET /v1/auth/csrf-token + session cookie
    API->>Session: Read or create this session's CSRF token
    API-->>UI: JSON csrf_token (Cache-Control: no-store)
    UI->>API: POST /v1/auth/legacy/skip?lang=en + cookie + X-CSRF-Token
    API->>Session: Read expected CSRF token
    alt Missing or incorrect token
        API-->>UI: 403; skip action does not run
    else Matching token
        API->>API: Authenticate user and update skip status
        API-->>UI: JSON redirect_url
        UI->>UI: Navigate to the configured return URL
    end
```

The token is separate from the session cookie and the identity provider's access
token. The frontend never needs to read the session cookie or the access token.

## Where the implementation lives

- Backend token creation and comparison: `backend/app/auth/services/csrf.py`.
- Application-wide enforcement: the global dependency in `backend/app/main.py`.
- Token and RP-context endpoints: `backend/app/auth/v1_router.py`.
- Token rotation after successful sign-in: `backend/app/auth/services/auth.py`.
- Browser request handling: `frontend/src/services/apiClient.js`.
- Skip-linking action: the migration API helper, `useSkipLink` hook, and
  `LinkPrompt` component in `frontend/src/features/DoubleSignIn/`.

The backend check runs before route authentication dependencies and business
actions. Missing, malformed, incorrect, or another session's token is rejected.
Ordinary token refresh keeps the CSRF token; successful sign-in rotates it.
Clearing or expiring the session invalidates the token stored in that session.

The client acquires the current token before an unsafe request and shares an
in-flight acquisition across concurrent requests. It does not persist tokens in
browser storage or automatically replay rejected actions. The dedicated client
only sends the token to the configured migration backend; the external language
service continues using its own transport.

## Which requests are protected?

The global check protects registered routes using methods other than `GET`,
`HEAD`, `OPTIONS`, and `TRACE`. New state-changing routes inherit the check when
registered on the application. Use `POST`, `PUT`, `PATCH`, or `DELETE` for actions;
keep ordinary `GET` endpoints read-only.

The browser actions include logout, keep-alive, skipping linking, and setting the
relying-party context. The latter two previously changed state through `GET`:

- `POST /v1/auth/legacy/skip?lang=en` returns `{ "redirect_url": "..." }`.
  The frontend navigates after success so an API request does not follow a
  redirect to another service.
- `POST /v1/auth/rp-context` accepts `{ "rp_client_id": "..." }` before the
  frontend reads the profile. `GET /v1/auth/me` no longer changes this context
  from its query string.

OIDC redirects and callbacks keep their protocol-specific state validation.
They cannot supply the React client's custom header. The exact
`POST /v1/auth/backchannel-logout` endpoint is exempt because it is called by the
identity provider, not the browser; its logout-token validation remains required.
Do not extend this exemption to other authentication routes.

## Errors and rollout

A CSRF failure returns HTTP `403` before the action runs. Authentication failures
remain separate. The UI shows a localized error for a failed skip action and
allows a deliberate retry. Never automatically replay a mutation after an error:
the outcome of a network failure may be unknown.

Deploy the frontend and backend changes together. An older frontend cannot send
the required header and still uses the old skip request. Other browser/API
clients must fetch a CSRF token with the same cookie session and attach it to
their action requests. Keep credentialed CORS restricted to trusted frontends.
Never put the token in a URL, analytics event, or log.

## Verification

Backend tests exercise the actual session middleware with an in-memory test
store: valid tokens, missing and incorrect tokens, different sessions, sign-in
rotation, protected actions, read-only profile loading, and the protocol
exception. Production still uses Redis.

Frontend tests cover token acquisition and headers, concurrent requests, blocked
actions when token acquisition fails, external destinations, and the skip UI's
success and error paths. Existing authentication tests cover callback and logout
behavior.

For background, see the [OWASP synchronizer-token guidance](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html#synchronizer-token-pattern)
and [MDN's CSRF explanation](https://developer.mozilla.org/en-US/docs/Web/Security/Attacks/CSRF).
