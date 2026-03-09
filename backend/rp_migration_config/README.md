# RP Migration Config Tooling

This folder centralizes RP migration config assets:

- `scripts/rp_migration_config_to_env.py`: converter script for `RP_MIGRATION_CONFIG`.
- `config/env/<env>/rp_migration_config.json`: full per-environment non-sensitive RP config (primary source for merge mode).
- `config/base/rp_migration_config.json`: shared base template (optional/backward-compatible path).
- `samples/rp_overrides.sample.json`: single-object override sample.
- `samples/rp_overrides.full.sample.json`: full override sample (all current RPs).
- `samples/rp_migration_config.sample.json`: legacy complete sample (single-file mode).

## Structure

```text
backend/rp_migration_config/
├── config/
│   ├── base/
│   │   └── rp_migration_config.json
│   └── env/
│       ├── dev/
│       │   └── rp_migration_config.json
│       ├── test/
│       │   └── rp_migration_config.json
│       ├── staging/
│       │   └── rp_migration_config.json
│       └── prod/
│           └── rp_migration_config.json
├── samples/
│   ├── rp_migration_config.sample.json
│   ├── rp_overrides.sample.json
│   └── rp_overrides.full.sample.json
└── scripts/
    └── rp_migration_config_to_env.py
```

## Inputs

- Env RP config (non-sensitive): `config/env/<env>/rp_migration_config.json`
- RP overrides (usually sensitive): pass one-time via `stdin` (`--rp-overrides-stdin`)

Expected fields:

- Each env RP entry should contain `rp_config_id` (recommended required), RP values, and SIC `openid_configuration`/`redirect_uris`.
- Override entry must include `rp_config_id` (preferred) or `rp_client_name`.
- Override can be full (client IDs + secret) or partial (for example, only `idp.client_secret`).
- Final merged RP still must satisfy schema requirements (`rp_client_id`, `rp_redirect_uri`, `idp.client_id`, `idp.client_secret`, etc.).

## Converter Modes

### 1. Legacy mode (single full JSON)

```bash
python3 backend/rp_migration_config/scripts/rp_migration_config_to_env.py \
  --input backend/rp_migration_config/samples/rp_migration_config.sample.json
```

### 2. Merge mode (env config + overrides)

```bash
cat backend/rp_migration_config/samples/rp_overrides.sample.json | \
python3 backend/rp_migration_config/scripts/rp_migration_config_to_env.py \
  --env dev \
  --rp-overrides-stdin \
  --rp-config-id atip \
  --format single-value
```

Default merge mode behavior:

- Loads env RP config from `config/env/<env>/rp_migration_config.json`.
- `--env` is required.

Backward compatibility:

- You can still pass `--env-input` with a legacy env-values file (`sic.openid_configuration.<env>`, `sic.redirect_uris.<env>`), and the script will merge that with `config/base/rp_migration_config.json`.

## CLI Parameters

| Parameter | Required | Default | Description |
|---|---|---|---|
| `-h`, `--help` | No | N/A | Show help and exit. |
| `--input <path>` | No | `backend/rp_migration_config/samples/rp_migration_config.sample.json` | Legacy mode full input JSON. |
| `--env <name>` | Yes (merge mode) | N/A | Environment selector. |
| `--env-input <path>` | No | `backend/rp_migration_config/config/env/<env>/rp_migration_config.json` | Override the default merge input path. |
| `--rp-overrides-input <path>` | No | N/A | RP overrides from JSON file. |
| `--rp-overrides-json '<json>'` | No | N/A | RP overrides as inline JSON string. |
| `--rp-overrides-stdin` | No | N/A | RP overrides from stdin (recommended for secrets). |
| `--rp-config-id <id>` | No | N/A | Filter output to one RP. |
| `--run-id <text>` | No | N/A | Optional trace label to stderr only. |
| `--format dotenv\|value\|single-value` | No | `dotenv` | `dotenv`: `RP_MIGRATION_CONFIG='...'`; `value`: raw array JSON; `single-value`: raw object JSON (one RP only). |
| `--output <path>` | No | stdout | Write output to file. |

Rules:

- Merge mode is activated by any merge flags (`--env`, `--env-input`, `--rp-overrides-*`).
- Do not combine `--input` with merge-mode flags.
- Use only one override source at a time (`--rp-overrides-input` or `--rp-overrides-json` or `--rp-overrides-stdin`).
- `--format single-value` requires exactly one RP in result.

## Examples

### Single RP from one JSON object (your onboarding case)

```bash
python3 backend/rp_migration_config/scripts/rp_migration_config_to_env.py \
  --env dev \
  --rp-overrides-stdin \
  --rp-config-id atip \
  --format single-value <<'JSON'
{
  "rp_config_id": "atip",
  "rp_client_id": "33333333-3333-3333-3333-333333333333",
  "rp_redirect_uri": "https://atip.example.ca/auth/callback/client1",
  "dependentClientIds": [
    "44444444-4444-4444-4444-444444444444",
    "55555555-5555-5555-5555-555555555555"
  ],
  "idp": {
    "client_id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
    "client_secret": "replace-with-real-secret"
  }
}
JSON
```

### Single RP secret-only override (env file carries non-sensitive values)

```bash
python3 backend/rp_migration_config/scripts/rp_migration_config_to_env.py \
  --env dev \
  --rp-config-id atip \
  --rp-overrides-stdin \
  --format single-value <<'JSON'
{
  "rp_config_id": "atip",
  "idp": {
    "client_secret": "replace-with-real-secret"
  }
}
JSON
```

### Full array output for all RPs

```bash
cat backend/rp_migration_config/samples/rp_overrides.full.sample.json | \
python3 backend/rp_migration_config/scripts/rp_migration_config_to_env.py \
  --env dev \
  --rp-overrides-stdin \
  --format value
```

Security note: prefer `--rp-overrides-stdin` for secrets. Command-line JSON (`--rp-overrides-json`) can be exposed via shell history/process lists.
