# Interac / CBS SAML Simulator

This folder contains provider-specific configuration for the local Interac / Credential Broker Service SAML IdP simulator.

The technical provider key should be `cbs-sim`, matching the public Acceptance Platform provider naming. Use Interac wording only where the user-facing product flow needs it.

The simulator uses `ghcr.io/pfrest/mock-saml2-idp:latest` through the root `docker-compose.saml-sim.yml` file.

## Local Contract

- Provider key in the migration app: `cbs-sim`
- IdP entity ID: `local-cbs-saml-idp`
- Metadata URL from the Mac host: `https://localhost:9444/sso/saml2/idp/metadata.php`
- Metadata URL from a Dev Container: `https://host.docker.internal:9444/sso/saml2/idp/metadata.php`
- Persistent NameID value: `cbs-pai-67890`

The persistent SAML `NameID` is the simulated legacy PAI value. The normal simulator path does not emit `legacy_pai` or `pairwise_id` SAML attributes.

Start both local simulators from the repo root:

```bash
scripts/saml-sim-up.sh
```
