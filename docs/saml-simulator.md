# Local SAML Simulators

This harness runs two local SAML IdP simulators for migration development:

- GCKey simulator, configured from `gckey-simulator/idp.env`
- Interac simulator, configured from `interac-simulator/idp.env`

Both simulators use `ghcr.io/pfrest/mock-saml2-idp:latest` and are intended for local development only.

On Apple Silicon with Colima, the upstream image currently runs as `linux/amd64`. The compose file applies an Apache `Mutex posixsem` compatibility setting before the image's normal entrypoint to avoid the `mpm-accept mutex` startup failure seen under emulation.

## Start

```bash
scripts/saml-sim-up.sh
```

The first run may need to pull the image from GitHub Container Registry.

## Check

```bash
scripts/saml-sim-check.sh
```

The check script validates the compose file and fetches each simulator's settings and metadata endpoints.

## Stop

```bash
scripts/saml-sim-down.sh
```

## Endpoints

From the Mac host:

```text
GCKey metadata:
http://localhost:9080/sso/saml2/idp/metadata.php

Interac metadata:
http://localhost:9081/sso/saml2/idp/metadata.php
```

From a backend container attached to the simulator Docker network:

```text
GCKey metadata:
http://saml-gckey-idp:8080/sso/saml2/idp/metadata.php

Interac metadata:
http://saml-interac-idp:8080/sso/saml2/idp/metadata.php
```

When the backend is running in Docker, prefer the simulator service hostnames above and attach the backend container to `gc-sign-in-saml-sim_default`. The browser still uses the published localhost ports.

The simulators also expose local interstitial screens that can be used as the SAML login target:

```text
GCKey simulator screen:
http://localhost:9080/sim/index.php

Interac simulator screen:
http://localhost:9081/sim/index.php
```

These pages display the fake user, fake password, persistent `NameID`, provider metadata, and decoded SAML AuthnRequest details. They forward the original `SAMLRequest` and `RelayState` unchanged into SimpleSAMLphp, so the backend still validates a signed SAML response.

## SP Defaults

The compose file defaults to the local FastAPI backend SAML endpoints:

```text
SAML_SP_ENTITY_ID=http://localhost:8000/v1/auth/legacy/saml/metadata
SAML_SP_ACS_URL=http://localhost:8000/v1/auth/legacy/saml/acs
```

To override them, copy `.env.saml-sim.example` to `.env.saml-sim` and edit the values. The scripts automatically load `.env.saml-sim` when it exists.

## Backend Routes

The migration backend exposes these SAML endpoints:

```text
GET  /v1/auth/legacy/saml/metadata
GET  /v1/auth/legacy/saml/login/{provider_key}
POST /v1/auth/legacy/saml/acs
```

The regular legacy login endpoint also accepts `provider`, so local flows can use either:

```text
/v1/auth/legacy/login?provider=gckey-sim
/v1/auth/legacy/login?provider=interac-sim
```

For local simulator config, prefer the HTTP metadata URLs above. This avoids local TLS certificate friction while keeping SAML response signing and validation in place. If you intentionally use the HTTPS simulator ports, set `metadata_tls_verify` to `false` on the SAML provider entries because the simulator publishes HTTPS metadata with a local/self-signed certificate. The backend only allows that setting for local simulator hosts in `ENVIRONMENT=local`.

Example local SAML IdP config values:

```json
{
  "provider_key": "gckey-sim",
  "metadata_url": "http://saml-gckey-idp:8080/sso/saml2/idp/metadata.php",
  "simulator_login_url": "http://localhost:9080/sim/index.php"
}
```

The backend uses `python3-saml` for SAML response validation. The backend Docker image installs the required XMLSec libraries; a direct local virtualenv may need equivalent system packages before installing `backend/requirements.txt`.

## Identity Values

The simulator returns the legacy PAI source as persistent SAML `NameID`.

```text
GCKey NameID:
gckey-pai-12345
GCKey fake username/password:
gckey-user / gckey-password

Interac NameID:
interac-pai-67890
Interac fake username/password:
interac-user / interac-password
```

The normal simulator path does not emit `legacy_pai` or `pairwise_id` SAML attributes. The migration app should save the persistent `NameID` value through the existing IBM Verify `patch_legacy_pai` flow used by SIC migration.

The simulators do emit provider-confirmation attributes:

```text
GCKey:
legacy_provider=GCKey
credential_service_provider=GCKey
loa=urn:gc-ca:cyber-auth:assurance:loa2
credential_type=GCKey

Interac:
legacy_provider=Interac
credential_service_provider=Interac
loa=urn:gc-ca:cyber-auth:assurance:loa2
credential_type=Interac
```

## Limits

This harness does not perfectly emulate real GCKey or Interac. In particular, `mock-saml2-idp` may not expose `NameQualifier`, `SPNameQualifier`, SAML logout, or partner-specific error behaviour exactly like production providers.

Keep partner-specific parsing and validation covered with backend unit tests at the parsed assertion seam. Treat real GCKey/Interac metadata, certificates, and final attribute contracts as TODOs until partner-provided metadata is available.
