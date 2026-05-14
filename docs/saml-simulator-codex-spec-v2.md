# Local SAML Simulator Build Spec for GCCF / GCKey / Interac Migration

Version: 3  
Updated focus: closer public-profile match for legacy GCKey / Interac style SAML flows, informed by the public Sign In Canada Acceptance Platform repository.

## Purpose

This document defines a local SAML simulator harness for testing a migration solution involving:

- **GCCF consolidator** using OIDC
- **GCKey** using SAML
- **Interac sign-in style flow** using SAML-like legacy broker behaviour

The goal is to test migration logic before coordinated GCKey / Interac partner testing is available.

Use [`pfrest/mock-saml2-idp`](https://github.com/pfrest/mock-saml2-idp) as the local simulator.

Do **not** build a custom SAML IdP from scratch.  
Do **not** introduce Keycloak for the first version.  
Do **not** rely on hosted public SAML test services for the first version.

---

## Public research basis and constraints

Public documentation did **not** expose a complete partner-facing GCKey or Interac SAML integration guide with production/test metadata, signing certificates, attributes, onboarding steps, or official end-to-end test instructions.

The closest public material is the Sign In Canada / GC Federation documentation describing pairwise identifier auto-collection from legacy **GCKey** and **Credential Broker Service** systems. That documentation describes the migration/coexistence pattern: Sign In Canada sends SAML authentication requests to legacy credential service providers, receives SAML assertions, and collects pairwise identifier mappings so relying party enrolments are not broken during migration.

The public Sign In Canada Acceptance Platform repository is also useful as an implementation reference, even though it uses different technologies. It models the legacy first-factor providers as separate SAML providers with provider IDs `gckey` and `cbs`, persistent `NameID`, LOA2 `RequestedAuthnContext`, SHA-256 signing, SAML logout endpoints, and explicit provider certificates. This repo should use `interac-sim` as the local technical provider key because the migration team refers to this provider as Interac; keep Acceptance Platform's `cbs` naming as reference context only.

The public GC Federation SAML deployment profile also gives useful profile-close behaviour:

- SP deployments must include `RequestedAuthnContext` when using the profile.
- `RequestedAuthnContext` comparison should be `exact` when present.
- Requests should include a Level of Assurance value.
- SPs must support HTTP-POST for receiving SAML responses.
- SP response endpoints must be protected by TLS/SSL.
- SP deployments must support persistent `NameID` for subject identification.
- Assertions should contain an `AuthnContext` specifying the Level of Assurance.

Public Interac documentation does not provide a legacy Interac SAML integration guide. It does, however, describe the sign-in service as a broker between government services and sign-in partners, and says the only value supplied by a Sign-In Partner is a randomly generated number created on first use and returned on subsequent uses. For local simulation, model this as a **persistent pairwise identifier** exposed as the SAML persistent `NameID`.

Current Interac Hub public integration documentation is for OAuth 2.0 / OIDC Authorization Code Grant, so it should not be treated as the legacy Interac SAML integration guide.

### Terminology

In this repo, **legacy PAI** means the normalized old PAI value that the migration app saves and uses for account linking. It is not tied to one protocol field name or one SAML attribute name.

For SAML legacy providers, the source for that normalized legacy PAI should be the persistent SAML `NameID`, shaped as closely as the real legacy IdPs are expected to return it. For OIDC legacy providers, the source may be an OIDC subject value such as SIC's `sub`.

Use these terms consistently:

```text
legacy PAI = app/domain value saved by the migration flow
legacy_pai = internal migration field / IBM custom-attribute record value after normalization
```

Do not assume that a real SAML IdP returns a SAML attribute named `legacy_pai`. If a test fixture uses such an attribute, it should be isolated to parser fallback unit tests and not part of the default simulator contract.

### Implication for this simulator

The simulator should produce the app's normalized legacy PAI from the SAML subject:

```text
Required source:  SAML persistent NameID
Fallback source:  none in the default simulator path
```

The migration app should then save the extracted `NameID` value to IBM Verify using the same IBM custom-attribute patch path used by the SIC migration flow.

---

## Target SAML subject contract

For the default GCKey/Interac simulator path, model the legacy IdP assertion subject as the source of truth:

```xml
<saml:NameID
  Format="urn:oasis:names:tc:SAML:2.0:nameid-format:persistent"
  NameQualifier="<idp-entity-id>"
  SPNameQualifier="<sp-entity-id>">
  opaque-provider-pai-value
</saml:NameID>
```

Implementation requirements:

- Treat the `NameID` text value as the legacy PAI value returned by the SAML IdP.
- Save that value to IBM Verify through the existing migration API flow: fetch IBM custom attributes, call `patch_legacy_pai`, then patch audit status.
- Store the value in IBM Verify's `gcsattributeslegacypaidata` records as the `pai` field for the RP client ID and configured dependent client IDs.
- Validate/use `NameQualifier` and `SPNameQualifier` when the SAML library and simulator expose them, but do not merge qualifiers into the saved `pai` value unless partner documentation later requires that exact composite format.
- Keep `legacy_provider` as a provider-confirmation attribute only. It is not the identifier.

The `pfrest/mock-saml2-idp` image may not expose every qualifier exactly like a real GCKey/Interac IdP. Where the image cannot model a subject detail, cover that detail with unit tests at the parsed assertion seam and keep the end-to-end simulator focused on persistent `NameID` value extraction and IBM Verify patching.

---

## Recommended option

Use:

```text
ghcr.io/pfrest/mock-saml2-idp:latest
```

This remains the simplest useful option because it is:

- Docker-based
- local/private
- intended for SAML Service Provider testing
- configurable with custom user attributes
- configurable for persistent `NameID`
- suitable for running two separate simulated legacy IdPs: one for GCKey and one for Interac sign-in

---

## Default assumptions

Use these defaults unless the repo already has clearly established alternatives.

```text
Migration backend local base URL:
http://localhost:8000

Migration frontend local base URL:
http://localhost:3000

SAML SP entity ID:
http://localhost:8000/v1/auth/legacy/saml/metadata

SAML ACS endpoint:
http://localhost:8000/v1/auth/legacy/saml/acs

GCKey simulator HTTPS port:
9443

GCKey simulator HTTP port:
9080

Interac simulator HTTPS port:
9444

Interac simulator HTTP port:
9081

SAML NameID format:
urn:oasis:names:tc:SAML:2.0:nameid-format:persistent

Requested AuthnContext / LOA:
urn:gc-ca:cyber-auth:assurance:loa2
```

### HTTP vs HTTPS for local app endpoints

The simple local default keeps the migration backend at `http://localhost:8000`. The React frontend may still run at `http://localhost:3000`, but SAML metadata and ACS endpoints belong on the FastAPI backend.

For profile-close testing, prefer local HTTPS once the app supports it:

```text
https://localhost:8000/v1/auth/legacy/saml/metadata
https://localhost:8000/v1/auth/legacy/saml/acs
```

The GC Federation profile expects SAML response endpoints to be TLS/SSL-protected. Treat HTTP as a local convenience only.

---

## Dev Container note

If the migration app runs directly on the Mac host, use `localhost` for simulator metadata URLs.

If the migration app runs inside a Docker Dev Container, the app may need to reach services published on the host through:

```text
host.docker.internal
```

For example:

```text
https://host.docker.internal:9443/sso/saml2/idp/metadata.php
https://host.docker.internal:9444/sso/saml2/idp/metadata.php
```

From the Mac host, the metadata URLs should be:

```text
https://localhost:9443/sso/saml2/idp/metadata.php
https://localhost:9444/sso/saml2/idp/metadata.php
```

---

## Deliverables

Codex should create the following files:

```text
docker-compose.saml-sim.yml
.env.saml-sim.example
gckey-simulator/idp.env
gckey-simulator/README.md
interac-simulator/idp.env
interac-simulator/README.md
docs/saml-simulator.md
scripts/saml-sim-up.sh
scripts/saml-sim-down.sh
scripts/saml-sim-check.sh
```

Optional, depending on the repo structure:

```text
AGENTS.md update
README.md short link to docs/saml-simulator.md
application config for SAML IdP entries
unit tests for SAML migration parsing/config
integration tests for the migration ACS flow
scripts/saml-sim-e2e-check.sh
```

---

## Simulator services

Create two local SAML IdP simulators.

### GCKey simulator

```text
Service name:
saml-gckey-idp

Container name:
saml-gckey-idp

Image:
ghcr.io/pfrest/mock-saml2-idp:latest

Host HTTP port:
9080

Host HTTPS port:
9443

IdP entity ID:
local-gckey-saml-idp

Auth mode:
auto

NameID format:
urn:oasis:names:tc:SAML:2.0:nameid-format:persistent

NameID source:
uid

Test UID / persistent NameID value to save as legacy PAI:
gckey-pai-12345
```

GCKey custom attributes:

```json
{
  "legacy_provider": "GCKey",
  "credential_service_provider": "GCKey",
  "loa": "urn:gc-ca:cyber-auth:assurance:loa2",
  "credential_type": "GCKey"
}
```

### Interac simulator

```text
Service name:
saml-interac-idp

Container name:
saml-interac-idp

Image:
ghcr.io/pfrest/mock-saml2-idp:latest

Host HTTP port:
9081

Host HTTPS port:
9444

IdP entity ID:
local-interac-saml-idp

Auth mode:
auto

NameID format:
urn:oasis:names:tc:SAML:2.0:nameid-format:persistent

NameID source:
uid

Test UID / persistent NameID value to save as legacy PAI:
interac-pai-67890
```

Interac custom attributes:

```json
{
  "legacy_provider": "Interac",
  "credential_service_provider": "Interac",
  "loa": "urn:gc-ca:cyber-auth:assurance:loa2",
  "credential_type": "Interac"
}
```

---

## Target `docker-compose.saml-sim.yml`

```yaml
services:
  saml-gckey-idp:
    image: ghcr.io/pfrest/mock-saml2-idp:latest
    container_name: saml-gckey-idp
    ports:
      - "9080:8080"
      - "9443:8443"
    environment:
      SP_ENTITY_ID: "${SAML_SP_ENTITY_ID:-http://localhost:8000/v1/auth/legacy/saml/metadata}"
      SP_ACS_LOCATION: "${SAML_SP_ACS_URL:-http://localhost:8000/v1/auth/legacy/saml/acs}"
      SP_ACS_BINDING: "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
      IDP_ENTITY_ID: "local-gckey-saml-idp"
      IDP_AUTH_MODE: "auto"
      IDP_NAMEID_FORMAT: "urn:oasis:names:tc:SAML:2.0:nameid-format:persistent"
      IDP_NAMEID_ATTRIBUTE: "uid"
      IDP_USER_NAME: "gckey-user"
      IDP_USER_UID: "gckey-pai-12345"
      IDP_USER_EMAIL: "gckey.user@example.com"
      IDP_USER_CUSTOM_ATTRIBUTES: >-
        {"legacy_provider":"GCKey","credential_service_provider":"GCKey","loa":"urn:gc-ca:cyber-auth:assurance:loa2","credential_type":"GCKey"}

  saml-interac-idp:
    image: ghcr.io/pfrest/mock-saml2-idp:latest
    container_name: saml-interac-idp
    ports:
      - "9081:8080"
      - "9444:8443"
    environment:
      SP_ENTITY_ID: "${SAML_SP_ENTITY_ID:-http://localhost:8000/v1/auth/legacy/saml/metadata}"
      SP_ACS_LOCATION: "${SAML_SP_ACS_URL:-http://localhost:8000/v1/auth/legacy/saml/acs}"
      SP_ACS_BINDING: "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
      IDP_ENTITY_ID: "local-interac-saml-idp"
      IDP_AUTH_MODE: "auto"
      IDP_NAMEID_FORMAT: "urn:oasis:names:tc:SAML:2.0:nameid-format:persistent"
      IDP_NAMEID_ATTRIBUTE: "uid"
      IDP_USER_NAME: "interac-user"
      IDP_USER_UID: "interac-pai-67890"
      IDP_USER_EMAIL: "interac.user@example.com"
      IDP_USER_CUSTOM_ATTRIBUTES: >-
        {"legacy_provider":"Interac","credential_service_provider":"Interac","loa":"urn:gc-ca:cyber-auth:assurance:loa2","credential_type":"Interac"}
```

### Simulator limitations

`mock-saml2-idp` is good enough for this stage, but it will not perfectly emulate GCKey or Interac sign-in.

Known limitations to document:

- It supports a single configured user per container.
- On Apple Silicon / Colima, the upstream image may run as `linux/amd64` and require an Apache mutex compatibility override such as `Mutex posixsem`.
- It may not force the exact real `AuthnContextClassRef` in the SAML assertion.
- It may not emit encrypted assertions exactly as a production GC Federation deployment would.
- It does not emulate the real Interac financial institution picker.
- It does not provide real GCKey / Interac partner metadata, certificates, entity IDs, or endpoint behaviour.
- It may not emit `NameID` `NameQualifier` and `SPNameQualifier` exactly like the Acceptance Platform's Shibboleth-based flow. Cover qualifier handling with unit tests at the parsed assertion seam.
- It should be treated as a local migration-logic simulator, not a conformance test suite.

Because of those limitations, the app should also have unit tests at the SAML parsing/config seam for profile-specific behaviours.

---

## Acceptance Platform-informed choices

Use the public Sign In Canada Acceptance Platform repository to inform local naming and behaviour, while keeping this implementation native to this repo's FastAPI structure.

Important simulator choices:

- Use provider key `gckey-sim` for the local GCKey simulator.
- Use provider key `interac-sim` for the local Interac sign-in simulator.
- Use display text `Interac Simulator` where user-facing text is needed.
- Model the source for the normalized legacy PAI as SAML persistent `NameID`.
- Configure the simulator so the `NameID` itself carries the provider-shaped value that the app should save to IBM Verify.
- Parse and store SAML `SessionIndex` from the first assertion even if true two-step PAI collection is deferred.
- Include SAML logout endpoint config in provider data, but keep SLO implementation as a separate task unless required for the first local smoke test.
- Prefer deterministic local signing certificates mounted into the simulator containers over generated-at-startup certificates, so local metadata and tests remain stable.

Do not copy Acceptance Platform code directly. It is a reference for profile shape and flow semantics, not a drop-in implementation.

---

## Required metadata endpoints

When running the migration app directly on the Mac host:

```text
GCKey metadata:
https://localhost:9443/sso/saml2/idp/metadata.php

Interac metadata:
https://localhost:9444/sso/saml2/idp/metadata.php
```

When running the migration app inside a Dev Container:

```text
GCKey metadata:
https://host.docker.internal:9443/sso/saml2/idp/metadata.php

Interac metadata:
https://host.docker.internal:9444/sso/saml2/idp/metadata.php
```

---

## Example `.env.saml-sim.example`

```bash
# Local SAML simulator config for development only.
# Do not use these values in production.

# Easy local mode. OK for early local testing.
SAML_SP_ENTITY_ID=http://localhost:8000/v1/auth/legacy/saml/metadata
SAML_SP_ACS_URL=http://localhost:8000/v1/auth/legacy/saml/acs

# Profile-close mode. Prefer this once the local migration app supports HTTPS.
# SAML_SP_ENTITY_ID=https://localhost:8000/v1/auth/legacy/saml/metadata
# SAML_SP_ACS_URL=https://localhost:8000/v1/auth/legacy/saml/acs

# Use these when the migration app runs directly on the Mac host.
SAML_GCKEY_SIM_METADATA_URL=https://localhost:9443/sso/saml2/idp/metadata.php
SAML_INTERAC_SIM_METADATA_URL=https://localhost:9444/sso/saml2/idp/metadata.php

# Use these instead when the migration app runs inside a Docker Dev Container.
# SAML_GCKEY_SIM_METADATA_URL=https://host.docker.internal:9443/sso/saml2/idp/metadata.php
# SAML_INTERAC_SIM_METADATA_URL=https://host.docker.internal:9444/sso/saml2/idp/metadata.php

SAML_NAMEID_FORMAT=urn:oasis:names:tc:SAML:2.0:nameid-format:persistent
SAML_REQUESTED_AUTHN_CONTEXT=urn:gc-ca:cyber-auth:assurance:loa2
SAML_REQUESTED_AUTHN_CONTEXT_COMPARISON=exact

# For migration logic:
# Persistent NameID is the source for the normalized legacy PAI.
# SAML attribute fallback is disabled in the default simulator path.
SAML_PRIMARY_IDENTIFIER_SOURCE=nameid
SAML_ALLOW_LOCAL_FALLBACK_IDENTIFIER=false
# Only set a fallback attribute in isolated local/unit tests, not in the default simulator path.
# SAML_LOCAL_FALLBACK_IDENTIFIER_ATTRIBUTE=legacy_pai
```

---

## Required sanity checks

Codex should make the following commands work locally:

```bash
docker compose -f docker-compose.saml-sim.yml config
docker compose -f docker-compose.saml-sim.yml up -d
curl -k https://localhost:9443/api/settings.php
curl -k https://localhost:9444/api/settings.php
curl -k https://localhost:9443/sso/saml2/idp/metadata.php
curl -k https://localhost:9444/sso/saml2/idp/metadata.php
```

---

## Recommended script behaviour

### `scripts/saml-sim-up.sh`

Should:

- run from the repo root even if invoked elsewhere
- use `docker compose`, not legacy `docker-compose`
- start `docker-compose.saml-sim.yml` detached

Example behaviour:

```bash
scripts/saml-sim-up.sh
```

### `scripts/saml-sim-down.sh`

Should:

- run from the repo root even if invoked elsewhere
- stop and remove the simulator stack

Example behaviour:

```bash
scripts/saml-sim-down.sh
```

### `scripts/saml-sim-check.sh`

Should:

- run `docker compose -f docker-compose.saml-sim.yml config`
- check both `/api/settings.php` endpoints with `curl -k`
- check both metadata endpoints with `curl -k`
- print the two metadata URLs at the end

Example behaviour:

```bash
scripts/saml-sim-check.sh
```

---

## Migration-app provider config

The migration app should support two local-development SAML provider entries.

### GCKey simulator provider

```text
Provider key:
gckey-sim

Display name:
GCKey Simulator

IdP entity ID:
local-gckey-saml-idp

Metadata URL:
from SAML_GCKEY_SIM_METADATA_URL

Expected legacy_provider attribute:
GCKey

Primary source for normalized legacy PAI:
persistent SAML NameID

Local fallback source attribute:
disabled by default; do not configure for the main simulator path

Expected NameID format:
urn:oasis:names:tc:SAML:2.0:nameid-format:persistent

Requested AuthnContext:
urn:gc-ca:cyber-auth:assurance:loa2

Requested AuthnContext comparison:
exact
```

### Interac simulator provider

```text
Provider key:
interac-sim

Display name:
Interac Simulator

IdP entity ID:
local-interac-saml-idp

Metadata URL:
from SAML_INTERAC_SIM_METADATA_URL

Expected legacy_provider attribute:
Interac

Primary source for normalized legacy PAI:
persistent SAML NameID

Local fallback source attribute:
disabled by default; do not configure for the main simulator path

Expected NameID format:
urn:oasis:names:tc:SAML:2.0:nameid-format:persistent

Requested AuthnContext:
urn:gc-ca:cyber-auth:assurance:loa2

Requested AuthnContext comparison:
exact
```

---

## Production-safety requirements

The implementation must be production-safe.

Requirements:

- Local simulator config must not be enabled by default in production.
- Do not bypass existing SAML signature validation.
- Do not globally disable certificate validation.
- If self-signed metadata or certificates require a development-only exception, make that exception explicit and local-only.
- Do not modify production deployment files unless necessary.
- Real GCKey and Interac metadata should remain TODOs until partner-provided metadata is available.
- Do not emit `legacy_pai` or `pairwise_id` SAML attributes in the default simulator config; they are not real partner contract assumptions.
- Prefer SAML persistent `NameID` as the source for normalized legacy PAI unless partner documentation later says otherwise.

---

## Migration flow to test

Target flow:

```text
OIDC app starts migration
→ migration app creates migration transaction / RelayState
→ migration app redirects to simulated SAML IdP
→ fake GCKey or Interac assertion comes back by HTTP-POST to ACS
→ migration app validates signature and assertion conditions
→ migration app verifies RelayState / transaction state
→ migration app derives normalized legacy PAI from persistent NameID
→ migration app optionally checks legacy_provider for local-sim provider mismatch detection
→ migration app links or migrates the user
→ migration app marks the transaction consumed
→ migration app resumes the OIDC transaction
```

---

## Important test scenarios

Add focused tests around the migration logic.

### 1. Persistent NameID extraction — GCKey

Input:

```text
provider = gckey-sim
NameID format = urn:oasis:names:tc:SAML:2.0:nameid-format:persistent
NameID value = gckey-pai-12345
legacy_provider = GCKey
```

Expected result:

```text
migration logic extracts provider GCKey and derives normalized legacy PAI gckey-pai-12345 from NameID
```

### 2. Persistent NameID extraction — Interac

Input:

```text
provider = interac-sim
NameID format = urn:oasis:names:tc:SAML:2.0:nameid-format:persistent
NameID value = interac-pai-67890
legacy_provider = Interac
```

Expected result:

```text
migration logic extracts provider Interac and derives normalized legacy PAI interac-pai-67890 from NameID
```

### 3. Provider mismatch

Input:

```text
transaction expects GCKey
assertion says legacy_provider = Interac
```

Expected result:

```text
migration fails safely
```

### 4. Missing persistent identifier

Input:

```text
assertion has no NameID
```

Expected result:

```text
migration fails with a clear error
```

### 5. RelayState / transaction state

Expected behaviour:

```text
migration transaction ID or RelayState is created before SAML login
ACS handling requires it
missing or unknown RelayState fails safely
```

### 6. Replay / duplicate handling

If the app already has replay protection:

```text
same SAML response or same migration transaction cannot be consumed twice
```

### 7. RequestedAuthnContext generation

Expected AuthnRequest behaviour:

```text
RequestedAuthnContext is present
Comparison is exact
AuthnContextClassRef includes urn:gc-ca:cyber-auth:assurance:loa2
```

### 8. NameIDPolicy generation

Initial collection request:

```text
NameIDPolicy Format = urn:oasis:names:tc:SAML:2.0:nameid-format:persistent
AllowCreate = true
SPNameQualifier = migration platform / Sign In Canada style entity ID
```

RP pairwise identifier collection request, if the app supports the two-step collection pattern:

```text
NameIDPolicy Format = urn:oasis:names:tc:SAML:2.0:nameid-format:persistent
AllowCreate = false
SPNameQualifier = legacy relying party entity ID
```

### 9. SessionIndex preservation for two-step collection

If the app implements the two-step pairwise identifier collection pattern:

```text
first assertion SessionIndex == second assertion SessionIndex
mismatch fails safely
```

This protects against collecting an identifier for the wrong person when SSO/session timing changes between two back-to-back SAML requests.

### 10. ACS binding and endpoint matching

Expected behaviour:

```text
AuthnRequest ProtocolBinding expects HTTP-POST response
AssertionConsumerServiceURL matches the SP metadata exactly
local HTTPS is preferred once available
```

---

## Implementation plan

Implement this in small phases. This repo currently has an OIDC-oriented legacy IdP flow for SIC, so SAML support should be introduced as a separate protocol path and then joined back into the existing migration patch/audit logic after the legacy identity has been resolved.

### Phase 1 — local simulator harness

Goal: create a stable local test target without changing production runtime behaviour.

Tasks:

- Add `docker-compose.saml-sim.yml` with `saml-gckey-idp` and `saml-interac-idp`.
- Add deterministic local dev certificates for the simulator IdPs, or document why the first pass uses generated certs and cannot support stable metadata snapshots.
- Add `.env.saml-sim.example` using backend SP defaults:
  - `SAML_SP_ENTITY_ID=http://localhost:8000/v1/auth/legacy/saml/metadata`
  - `SAML_SP_ACS_URL=http://localhost:8000/v1/auth/legacy/saml/acs`
  - `SAML_GCKEY_SIM_METADATA_URL=https://localhost:9443/sso/saml2/idp/metadata.php`
  - `SAML_INTERAC_SIM_METADATA_URL=https://localhost:9444/sso/saml2/idp/metadata.php`
- Add `scripts/saml-sim-up.sh`, `scripts/saml-sim-down.sh`, and `scripts/saml-sim-check.sh`.
- Add `docs/saml-simulator.md` with exact start/check/stop commands and known limitations.

Validation:

```bash
docker compose -f docker-compose.saml-sim.yml config
scripts/saml-sim-up.sh
scripts/saml-sim-check.sh
```

### Phase 2 — backend SAML configuration model

Goal: let the migration backend load local SAML provider config without disturbing existing SIC OIDC config.

Tasks:

- Add a protocol discriminator to legacy IdP config, for example `protocol: "oidc" | "saml"`, while keeping current OIDC config backward-compatible.
- Add SAML provider config fields for provider key, display name, entity ID, metadata URL, expected `legacy_provider`, expected `NameID` format, requested authn context, ACS URL, SP entity ID, logout URL, and development-only metadata TLS behaviour.
- Add config tests for `gckey-sim` and `interac-sim`.
- Do not enable simulator providers by default in production.

Validation:

```bash
pytest backend/tests/test_rp_config.py backend/tests/test_constants_and_schemas.py
```

### Phase 3 — SAML login and ACS flow

Goal: support SP-initiated local SAML login through the FastAPI backend.

Tasks:

- Choose and pin a Python SAML SP library that supports signed response validation, condition validation, `RelayState`, persistent `NameID`, `SessionIndex`, `RequestedAuthnContext`, `NameIDPolicy`, and metadata generation.
- Add backend routes:
  - `GET /v1/auth/legacy/saml/metadata`
  - `GET /v1/auth/legacy/saml/login/{provider_key}`
  - `POST /v1/auth/legacy/saml/acs`
- Store transaction state in the existing session: provider key, RelayState, RP client ID, language, correlation ID, attempt ID, issued-at timestamp, and consumed flag.
- Validate assertion signature, audience, destination, recipient, `InResponseTo`, time conditions, expected provider, and persistent `NameID`.
- Normalize a successful SAML assertion into a small internal object such as `LegacyIdentity(provider_key, provider_name, legacy_pai, nameid_format, session_index)`, where `legacy_pai` is populated from the persistent `NameID` value.
- Do not read a `legacy_pai` SAML attribute in the default flow. If fallback parsing is ever added, keep it behind an explicit unit-test/local-only toggle and outside the normal simulator config.

Validation:

```bash
pytest backend/tests/test_auth_legacy.py
pytest backend/tests/test_saml_legacy.py
```

### Phase 4 — migration patch integration

Goal: reuse existing migration side effects after the legacy identity is resolved.

Tasks:

- Extract the common "resolved legacy identity" callback work from the current OIDC callback path: get IBM ID, fetch custom attributes, call `patch_legacy_pai` with the resolved legacy PAI, patch audit status, clear transaction state, and redirect to post-link flow.
- For SIC, the resolved legacy PAI remains the OIDC `sub`; for GCKey/Interac SAML, the resolved legacy PAI is the persistent `NameID` value.
- Route both OIDC/SIC and SAML/GCKey/Interac through that shared function.
- Preserve existing logging fields and add provider key / protocol fields where useful.
- Add regression tests to ensure existing OIDC/SIC behaviour is unchanged.

Validation:

```bash
pytest backend/tests/test_auth_legacy.py backend/tests/test_patch_services.py
```

### Phase 5 — provider choice and frontend integration

Goal: make local provider selection explicit and compatible with existing RP settings.

Tasks:

- Decide whether the first local UI uses a backend provider-selection page, a query param on the legacy login endpoint, or frontend buttons for `gckey-sim` and `interac-sim`.
- Keep production provider choice aligned with RP config and `acr_values`; do not expose simulator providers outside local/dev.
- Ensure GCKey-only RP config cannot accidentally start Interac.

Validation:

```bash
pytest backend/tests/test_auth_legacy.py
cd frontend && npm test -- --run src/features/DoubleSignIn/components/__tests__/LinkPrompt.test.jsx
```

### Phase 6 — two-step PAI collection

Goal: add Acceptance Platform-style RP PAI collection after the single-step simulator is stable.

Tasks:

- Add RP config for a legacy SAML RP entity ID / collection `SPNameQualifier`.
- On first SAML assertion, store `SessionIndex` and the Sign In Canada-style platform `NameID`.
- If RP PAI collection is required, issue a second AuthnRequest with:
  - persistent `NameIDPolicy`
  - `AllowCreate=false`
  - `SPNameQualifier=<legacy RP entity ID>`
- Reject the collected identifier if the second assertion's `SessionIndex` does not match the first assertion.
- If the IdP returns an equivalent of `InvalidNameIDPolicy`, fall back to creating a new local mapping only when that is an explicit product decision.

Validation:

```bash
pytest backend/tests/test_saml_legacy.py
```

### Phase 7 — optional SLO and browser smoke

Goal: cover session cleanup and manual end-to-end confidence without making Docker/browser checks part of normal CI.

Tasks:

- Add SAML SLO route support only after login/ACS is working.
- Add optional `scripts/saml-sim-e2e-check.sh`.
- Document manual browser steps from frontend link prompt to simulator ACS callback.

Validation:

```bash
scripts/saml-sim-e2e-check.sh
```

---

# Codex prompts

## Prompt 1 — add the profile-close local SAML simulator harness

```text
Add a local SAML simulator harness for this repo.

Context:
- This project is a migration solution for GCCF consolidator, GCKey, and Interac sign-in.
- GCCF is OIDC.
- GCKey and legacy Interac sign-in style login are SAML.
- We need a simple local SAML IdP simulator so we can test migration logic before real GCKey/Interac partner testing is available.
- The public Sign In Canada Acceptance Platform uses SAML provider IDs `gckey` and `cbs`; use `interac-sim` as the technical local provider key in this repo because the migration team refers to this provider as Interac.
- Use the Docker image ghcr.io/pfrest/mock-saml2-idp:latest.
- Do not build a custom SAML IdP from scratch.
- Do not introduce Keycloak.
- Do not modify production deployment files unless clearly necessary.

Important profile-close modelling requirements:
- Use persistent SAML NameID as the primary source for normalized legacy PAI.
- Use NameID format urn:oasis:names:tc:SAML:2.0:nameid-format:persistent.
- Use the user's uid as the NameID source.
- Do not emit legacy_pai or pairwise_id SAML attributes in the default simulator path.
- Ensure the migration app saves the NameID value to IBM Verify using the existing SIC-style `patch_legacy_pai` path.
- Use LOA URI urn:gc-ca:cyber-auth:assurance:loa2, not CAL2.
- Configure ACS binding as HTTP-POST.

Please inspect the repo structure first, then add these files:

1. docker-compose.saml-sim.yml
2. .env.saml-sim.example
3. docs/saml-simulator.md
4. scripts/saml-sim-up.sh
5. scripts/saml-sim-down.sh
6. scripts/saml-sim-check.sh

Use these defaults:

Migration backend local base URL:
http://localhost:8000

Migration frontend local base URL:
http://localhost:3000

SAML SP entity ID:
${SAML_SP_ENTITY_ID:-http://localhost:8000/v1/auth/legacy/saml/metadata}

SAML ACS endpoint:
${SAML_SP_ACS_URL:-http://localhost:8000/v1/auth/legacy/saml/acs}

Create two simulator services.

Service 1:
- service name: saml-gckey-idp
- container name: saml-gckey-idp
- image: ghcr.io/pfrest/mock-saml2-idp:latest
- ports:
  - 9080:8080
  - 9443:8443
- environment:
  - SP_ENTITY_ID=${SAML_SP_ENTITY_ID:-http://localhost:8000/v1/auth/legacy/saml/metadata}
  - SP_ACS_LOCATION=${SAML_SP_ACS_URL:-http://localhost:8000/v1/auth/legacy/saml/acs}
  - SP_ACS_BINDING=urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST
  - IDP_ENTITY_ID=local-gckey-saml-idp
  - IDP_AUTH_MODE=auto
  - IDP_NAMEID_FORMAT=urn:oasis:names:tc:SAML:2.0:nameid-format:persistent
  - IDP_NAMEID_ATTRIBUTE=uid
  - IDP_USER_NAME=gckey-user
  - IDP_USER_UID=gckey-pai-12345
  - IDP_USER_EMAIL=gckey.user@example.com
  - IDP_USER_CUSTOM_ATTRIBUTES={"legacy_provider":"GCKey","credential_service_provider":"GCKey","loa":"urn:gc-ca:cyber-auth:assurance:loa2","credential_type":"GCKey"}

Service 2:
- service name: saml-interac-idp
- container name: saml-interac-idp
- image: ghcr.io/pfrest/mock-saml2-idp:latest
- ports:
  - 9081:8080
  - 9444:8443
- environment:
  - SP_ENTITY_ID=${SAML_SP_ENTITY_ID:-http://localhost:8000/v1/auth/legacy/saml/metadata}
  - SP_ACS_LOCATION=${SAML_SP_ACS_URL:-http://localhost:8000/v1/auth/legacy/saml/acs}
  - SP_ACS_BINDING=urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST
  - IDP_ENTITY_ID=local-interac-saml-idp
  - IDP_AUTH_MODE=auto
  - IDP_NAMEID_FORMAT=urn:oasis:names:tc:SAML:2.0:nameid-format:persistent
  - IDP_NAMEID_ATTRIBUTE=uid
  - IDP_USER_NAME=interac-user
  - IDP_USER_UID=interac-pai-67890
  - IDP_USER_EMAIL=interac.user@example.com
  - IDP_USER_CUSTOM_ATTRIBUTES={"legacy_provider":"Interac","credential_service_provider":"Interac","loa":"urn:gc-ca:cyber-auth:assurance:loa2","credential_type":"Interac"}

The docs/saml-simulator.md file should explain:
- What the simulator is for
- How to start it
- How to stop it
- How to check it
- The GCKey and Interac metadata URLs
- The difference between using localhost from the Mac host and host.docker.internal from inside a Dev Container
- Which SAML NameID and attributes are emitted
- That persistent NameID is the primary source for normalized legacy PAI
- That the simulator does not emit legacy_pai or pairwise_id attributes in the default path
- That the migration app saves the persistent NameID value through the existing IBM Verify `patch_legacy_pai` path
- That this is for local development/testing only, not production
- That it does not perfectly emulate real GCKey or Interac sign-in
- That no complete public partner-facing GCKey/Interac SAML integration guide was found
- That local HTTPS should be used later for profile-close testing

The scripts should:
- be POSIX shell scripts, or use bash if set -euo pipefail is required
- use docker compose, not legacy docker-compose
- be executable
- fail fast with set -euo pipefail if compatible with the shell you choose
- run from the repo root even if invoked from another directory

saml-sim-up.sh:
- start the compose file detached

saml-sim-down.sh:
- stop and remove the simulator stack

saml-sim-check.sh:
- run docker compose config
- check both /api/settings.php endpoints with curl -k
- check both metadata endpoints with curl -k
- print the two metadata URLs at the end

Validation:
- Run docker compose -f docker-compose.saml-sim.yml config.
- If possible, run the check script.
- If Docker is not available in the Codex environment, still create the files and clearly report the exact validation commands I should run locally.

Please keep the implementation minimal and do not make unrelated changes.
```

---

## Prompt 2 — wire the migration app to the profile-close simulator

```text
Wire the migration app configuration to support the local SAML simulator added in docker-compose.saml-sim.yml.

Context:
- We now have two local SAML IdP simulators:
  - GCKey simulator: local-gckey-saml-idp
  - Interac simulator: local-interac-saml-idp
- When the app runs directly on the Mac, metadata URLs are:
  - https://localhost:9443/sso/saml2/idp/metadata.php
  - https://localhost:9444/sso/saml2/idp/metadata.php
- When the app runs inside a Dev Container, metadata URLs are:
  - https://host.docker.internal:9443/sso/saml2/idp/metadata.php
  - https://host.docker.internal:9444/sso/saml2/idp/metadata.php
- The app should remain production-safe. Local simulator config must not be enabled by default in production.

Please inspect the app config style and implement the smallest clean change that supports two local SAML IdP provider entries.

Requirements:
1. Add local-development config for:
   - provider key: gckey-sim
   - provider display name: GCKey Simulator
   - entity ID: local-gckey-saml-idp
   - metadata URL: configurable by environment variable SAML_GCKEY_SIM_METADATA_URL
   - expected legacy_provider attribute: GCKey
   - primary source for normalized legacy PAI: persistent NameID
   - expected NameID format: urn:oasis:names:tc:SAML:2.0:nameid-format:persistent
   - local fallback source attribute: disabled by default
   - requested AuthnContext: urn:gc-ca:cyber-auth:assurance:loa2
   - requested AuthnContext comparison: exact

2. Add local-development config for:
   - provider key: interac-sim
   - provider display name: Interac Simulator
   - entity ID: local-interac-saml-idp
   - metadata URL: configurable by environment variable SAML_INTERAC_SIM_METADATA_URL
   - expected legacy_provider attribute: Interac
   - primary source for normalized legacy PAI: persistent NameID
   - expected NameID format: urn:oasis:names:tc:SAML:2.0:nameid-format:persistent
   - local fallback source attribute: disabled by default
   - requested AuthnContext: urn:gc-ca:cyber-auth:assurance:loa2
   - requested AuthnContext comparison: exact

3. Add or update .env.saml-sim.example with variables such as:
   - SAML_GCKEY_SIM_METADATA_URL=https://localhost:9443/sso/saml2/idp/metadata.php
   - SAML_INTERAC_SIM_METADATA_URL=https://localhost:9444/sso/saml2/idp/metadata.php
   - SAML_SP_ENTITY_ID=http://localhost:8000/v1/auth/legacy/saml/metadata
   - SAML_SP_ACS_URL=http://localhost:8000/v1/auth/legacy/saml/acs
   - SAML_NAMEID_FORMAT=urn:oasis:names:tc:SAML:2.0:nameid-format:persistent
   - SAML_REQUESTED_AUTHN_CONTEXT=urn:gc-ca:cyber-auth:assurance:loa2
   - SAML_REQUESTED_AUTHN_CONTEXT_COMPARISON=exact
   - SAML_PRIMARY_IDENTIFIER_SOURCE=nameid
   - SAML_ALLOW_LOCAL_FALLBACK_IDENTIFIER=false

4. If the app already has SAML provider config:
   - integrate with the existing pattern
   - do not duplicate concepts
   - do not bypass existing signature validation
   - do not bypass assertion condition validation

5. If the app does not yet have SAML provider config:
   - add a clearly isolated local config module or config section
   - do not implement the whole SAML stack unless necessary
   - leave clear TODOs for real GCKey/Interac metadata

6. Ensure the migration logic distinguishes the two providers using:
   - provider key from the migration transaction, or
   - IdP entity ID, or
   - legacy_provider SAML attribute
   Prefer the existing project pattern if one exists.

7. Ensure the migration logic derives normalized legacy PAI from persistent SAML NameID, then saves that value through the existing IBM Verify custom-attribute API path used by SIC migration.

8. Add documentation to docs/saml-simulator.md showing the env vars and example values.

Validation:
- Run existing tests if available.
- Run typecheck/lint if available.
- If the repo has no tests for this area, add a small config unit test that verifies both provider entries load correctly from env vars.
- Do not disable certificate/signature validation globally.
- If local self-signed metadata requires a dev-only relaxation, make it explicit and local-only.

Keep changes minimal and production-safe.
```

---

## Prompt 3 — add migration-flow tests around persistent NameID and profile-close SAML behaviour

```text
Add focused tests for the SAML migration flow using the GCKey and Interac simulator assumptions.

Context:
- The local simulator emits persistent NameID as the primary source for normalized legacy PAI.
- The GCKey simulator uses NameID value gckey-pai-12345.
- The Interac simulator uses NameID value interac-pai-67890.
- The local simulator does not emit legacy_pai or pairwise_id SAML attributes in the default path.
- After resolving the SAML NameID, the app should save that value with the existing IBM Verify `patch_legacy_pai` flow used by SIC migration.
- RelayState or equivalent transaction state must be preserved across the SAML redirect/POST flow.
- AuthnRequest generation should request urn:gc-ca:cyber-auth:assurance:loa2 with comparison exact when supported by the SAML library.

Please inspect the current test framework and add the smallest useful tests.

Test scenarios:
1. GCKey successful migration from persistent NameID:
   - provider is gckey-sim
   - NameID format is urn:oasis:names:tc:SAML:2.0:nameid-format:persistent
   - NameID value is gckey-pai-12345
   - SAML attributes contain legacy_provider=GCKey
   - migration logic derives normalized legacy PAI from NameID
   - migration logic records or returns the correct provider and normalized legacy PAI

2. Interac successful migration from persistent NameID:
   - provider is interac-sim
   - NameID format is urn:oasis:names:tc:SAML:2.0:nameid-format:persistent
   - NameID value is interac-pai-67890
   - SAML attributes contain legacy_provider=Interac
   - migration logic derives normalized legacy PAI from NameID
   - migration logic records or returns the correct provider and normalized legacy PAI

3. IBM Verify patch integration:
   - ACS resolves the persistent NameID value
   - the shared migration completion path calls patch_legacy_pai with that value
   - the saved IBM Verify custom attribute record contains pai=<NameID value> for the RP client ID and configured dependent client IDs
   - audit data is patched as linked using the same post-resolution behaviour as SIC

4. Provider mismatch:
   - transaction expects GCKey
   - assertion says legacy_provider=Interac
   - migration should reject or fail safely

5. Missing identifier:
   - assertion has no NameID
   - migration should fail with a clear error

6. RelayState/transaction state:
   - migration transaction ID or RelayState is created before SAML login
   - the ACS handling step requires it
   - missing or unknown RelayState fails safely

7. Replay/duplicate handling if the app already has replay protection:
   - same SAML response or same transaction cannot be consumed twice

8. RequestedAuthnContext generation:
   - AuthnRequest includes RequestedAuthnContext
   - Comparison is exact
   - AuthnContextClassRef includes urn:gc-ca:cyber-auth:assurance:loa2

9. NameIDPolicy generation:
   - AuthnRequest includes NameIDPolicy Format urn:oasis:names:tc:SAML:2.0:nameid-format:persistent
   - initial collection request uses AllowCreate=true if the app supports that concept
   - RP PAI collection request uses AllowCreate=false if the app supports two-step collection
   - RP PAI collection request includes SPNameQualifier set to the legacy RP entity ID if the app supports two-step collection

10. SessionIndex preservation for two-step collection if implemented:
   - first assertion SessionIndex matches second assertion SessionIndex
   - mismatch fails safely

Important:
- Do not require the live Docker simulator for unit tests unless the repo already supports integration tests.
- Prefer unit tests around SAML result parsing / ACS handler / migration transaction handling.
- Use existing helper patterns.
- Do not weaken signature validation in production code.
- If generating a signed SAMLResponse is too heavy for the current tests, mock the already-validated SAML assertion object and test the migration logic at that seam.
- If AuthnRequest XML generation is library-owned and hard to inspect, test the config object passed to the library.

Validation:
- Run the relevant test command.
- Run lint/typecheck if configured.
- Report any tests that could not run and why.
```

---

## Prompt 4 — optional end-to-end local smoke test

```text
Add an optional local end-to-end smoke test for the SAML simulator integration.

Goal:
Verify that the local simulator stack is reachable and that the migration app can load both IdP metadata entries.

Requirements:
1. Add a script named scripts/saml-sim-e2e-check.sh.
2. It should:
   - start the simulator stack if it is not already running
   - call both simulator metadata endpoints
   - call both simulator settings endpoints
   - call a migration-app health/config endpoint if one exists
   - print clear next-step instructions for manually testing browser login if no automated browser flow exists
3. Do not add heavy browser automation unless the repo already uses Playwright, Cypress, or similar.
4. Do not make this part of normal CI by default.
5. Document it in docs/saml-simulator.md.
6. Mention that this smoke test does not prove real GCKey/Interac compatibility.

Validation:
- Run the script if Docker and the app are available.
- Otherwise report the local commands to run.
```

---

## Recommended execution order

Run the Codex prompts in this order. These map to the implementation plan above; do not ask Codex to implement all phases in a single change.

```text
1. Prompt 1 — profile-close simulator harness / Phase 1
2. Prompt 2 — app config / Phase 2
3. Add SAML login and ACS support / Phase 3
4. Integrate resolved SAML identity into migration patching / Phase 4
5. Add provider-choice wiring / Phase 5
6. Prompt 3 — migration-flow tests across Phases 2-5
7. Add two-step PAI collection / Phase 6
8. Prompt 4 — optional smoke test and SLO follow-up / Phase 7
```

Avoid asking Codex to do all of this in one large task. Smaller tasks are easier to review, test, and correct.

---

## Final local validation checklist

After Codex completes the work, run:

```bash
docker compose -f docker-compose.saml-sim.yml config
scripts/saml-sim-up.sh
scripts/saml-sim-check.sh
```

Expected metadata endpoints:

```text
https://localhost:9443/sso/saml2/idp/metadata.php
https://localhost:9444/sso/saml2/idp/metadata.php
```

Then configure the migration app to use:

```text
gckey-sim -> local-gckey-saml-idp
interac-sim   -> local-interac-saml-idp
```

The primary source for normalized legacy PAI should be:

```text
persistent SAML NameID
```

Use `legacy_provider` only to confirm that the assertion came from the expected simulated legacy provider.

Do not use a SAML attribute named `legacy_pai` in the normal simulator flow.

---

## Source notes for humans

These public sources informed the v2 spec:

- Sign In Canada, Pairwise Identifier Auto-Collection: https://connect.canada.ca/en/discover/auto-collection.html?wbdisable=true
- Sign In Canada, Session Management / transition and coexistence: https://connect.canada.ca/en/discover/session-management.html
- Cyber Authentication Technology Solutions, Deployment Profile of SAML 2.0: https://canada-ca.github.io/CATS-STAE/saml2-en.pdf
- pfrest/mock-saml2-idp README: https://github.com/pfrest/mock-saml2-idp
- Docker Desktop networking how-tos: https://docs.docker.com/desktop/features/networking/networking-how-tos/
- Interac sign into government services: https://www.interac.ca/en/verification/personal/sign-into-government-services/
- Interac sign-in service how-to: https://www.interac.ca/en/how-to-use/interac-verified/how-to-use-interac-sign-in-service/
- Interac Hub public integration guide: https://documents.hub-verify.innovation.interac.ca/docs/overview
- Sign In Canada Acceptance Platform provider config: https://github.com/sign-in-canada/Acceptance-Platform/blob/main/gluu-server/install/community-edition-setup/templates/passport/passport-central-config.json
- Sign In Canada Acceptance Platform PAI collection logic: https://github.com/sign-in-canada/Acceptance-Platform/blob/main/gluu-server/opt/gluu/jetty/oxauth/custom/scripts/person_authentication/SignInCanada.py
- Sign In Canada Acceptance Platform SAML NameID handling: https://github.com/sign-in-canada/Acceptance-Platform/blob/main/gluu-server/opt/dist/signincanada/shibboleth-idp/conf/nameIdAttributeDefn.js
