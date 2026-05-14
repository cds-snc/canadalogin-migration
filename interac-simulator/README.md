# Interac SAML Simulator

This folder contains provider-specific configuration for the local Interac SAML IdP simulator.

The technical provider key should be `interac-sim`, matching the name used internally by the migration team. Public Acceptance Platform material uses `cbs` for the same legacy broker area; keep that as background context, not as the default app-facing name.

The simulator uses `ghcr.io/pfrest/mock-saml2-idp:latest` through the root `docker-compose.saml-sim.yml` file.

## Local Contract

- Provider key in the migration app: `interac-sim`
- IdP entity ID: `local-interac-saml-idp`
- Metadata URL from the Mac host: `https://localhost:9444/sso/saml2/idp/metadata.php`
- Metadata URL from a Dev Container: `https://host.docker.internal:9444/sso/saml2/idp/metadata.php`
- Persistent NameID value: `interac-pai-67890`

The persistent SAML `NameID` is the simulated legacy PAI value. The normal simulator path does not emit `legacy_pai` or `pairwise_id` SAML attributes.

Start both local simulators from the repo root:

```bash
scripts/saml-sim-up.sh
```
