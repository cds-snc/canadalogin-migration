# GCKey SAML Simulator

This folder contains provider-specific configuration for the local GCKey SAML IdP simulator.

The simulator uses `ghcr.io/pfrest/mock-saml2-idp:latest` through the root `docker-compose.saml-sim.yml` file.

## Local Contract

- Provider key in the migration app: `gckey-sim`
- IdP entity ID: `local-gckey-saml-idp`
- Metadata URL from the Mac host: `https://localhost:9443/sso/saml2/idp/metadata.php`
- Metadata URL from a Dev Container: `https://host.docker.internal:9443/sso/saml2/idp/metadata.php`
- Persistent NameID value: `gckey-pai-12345`

The persistent SAML `NameID` is the simulated legacy PAI value. The normal simulator path does not emit `legacy_pai` or `pairwise_id` SAML attributes.

Start both local simulators from the repo root:

```bash
scripts/saml-sim-up.sh
```
