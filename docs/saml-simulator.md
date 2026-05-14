# Local SAML Simulators

This harness runs two local SAML IdP simulators for migration development:

- GCKey simulator, configured from `gckey-simulator/idp.env`
- Interac / Credential Broker Service simulator, configured from `interac-simulator/idp.env`

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
https://localhost:9443/sso/saml2/idp/metadata.php

Interac / CBS metadata:
https://localhost:9444/sso/saml2/idp/metadata.php
```

From a Docker Dev Container:

```text
GCKey metadata:
https://host.docker.internal:9443/sso/saml2/idp/metadata.php

Interac / CBS metadata:
https://host.docker.internal:9444/sso/saml2/idp/metadata.php
```

## SP Defaults

The compose file defaults to the local FastAPI backend SAML endpoints:

```text
SAML_SP_ENTITY_ID=http://localhost:8000/v1/auth/legacy/saml/metadata
SAML_SP_ACS_URL=http://localhost:8000/v1/auth/legacy/saml/acs
```

To override them, copy `.env.saml-sim.example` to `.env.saml-sim` and edit the values. The scripts automatically load `.env.saml-sim` when it exists.

## Identity Values

The simulator returns the legacy PAI source as persistent SAML `NameID`.

```text
GCKey NameID:
gckey-pai-12345

Interac / CBS NameID:
cbs-pai-67890
```

The normal simulator path does not emit `legacy_pai` or `pairwise_id` SAML attributes. The migration app should save the persistent `NameID` value through the existing IBM Verify `patch_legacy_pai` flow used by SIC migration.

The simulators do emit provider-confirmation attributes:

```text
GCKey:
legacy_provider=GCKey
credential_service_provider=GCKey
loa=urn:gc-ca:cyber-auth:assurance:loa2
credential_type=GCKey

Interac / CBS:
legacy_provider=CBS
credential_service_provider=CBS
loa=urn:gc-ca:cyber-auth:assurance:loa2
credential_type=CBS
```

## Limits

This harness does not perfectly emulate real GCKey or Interac/CBS. In particular, `mock-saml2-idp` may not expose `NameQualifier`, `SPNameQualifier`, SAML logout, or partner-specific error behaviour exactly like production providers.

Keep partner-specific parsing and validation covered with backend unit tests at the parsed assertion seam. Treat real GCKey/CBS metadata, certificates, and final attribute contracts as TODOs until partner-provided metadata is available.
