# Potential Code Review Issues

This list tracks backend/frontend items to review or standardize later. It is intentionally scoped to avoid touching `auth_legacy` and other teams' areas for now.

## Backend
- `backend/app/auth/services/auth_user_session.py:111`–`118`: token refresh shadows the `refresh_token` function with a local variable, which will raise `TypeError` when refresh is needed.
- `backend/app/auth/services/auth.py:164`–`197`: `verify_audit_status` duplicates API calls and returns `None` instead of a boolean.
- `backend/app/auth/services/auth_user_session.py:200`–`225`: SSE responses set `Access-Control-Allow-Origin` to `config.CORS_ORIGINS` (no scheme), which browsers may reject.
- `backend/app/rp/v1_router.py:22`: assumes `SessionKeys.RP_CLIENT_ID_KEY` is always present in session.
- `backend/app/users/v1_router.py:57`, `backend/app/users/v1_router.py:71`, `backend/app/users/v1_router.py:92`: local-only endpoints return raw values instead of `ResponseModel` (left as-is for now).

## Frontend
- `frontend/src/components/Providers/UserProvider.tsx:282`–`306`: expects `response.data.expire`/`response.data.redirect_url`, but backend wraps these in `ResponseModel.data`.
- `frontend/src/utils/apiErrorHandler.js:8`–`11`: 401 redirects are global; confirm this is desired for all API calls.
