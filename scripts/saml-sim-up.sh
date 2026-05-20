#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/docker-compose.saml-sim.yml"
LOCAL_ENV_FILE="${REPO_ROOT}/.env.saml-sim"

COMPOSE_ARGS=()
if [[ -f "${LOCAL_ENV_FILE}" ]]; then
  COMPOSE_ARGS+=(--env-file "${LOCAL_ENV_FILE}")
fi
COMPOSE_ARGS+=(-f "${COMPOSE_FILE}")

docker compose "${COMPOSE_ARGS[@]}" up -d --remove-orphans

cat <<'EOF'
Local SAML simulators are starting.

GCKey metadata:
  http://localhost:9080/sso/saml2/idp/metadata.php

GCKey simulator screen:
  http://localhost:9080/sim/index.php

Interac metadata:
  http://localhost:9081/sso/saml2/idp/metadata.php

Interac simulator screen:
  http://localhost:9081/sim/index.php

Run scripts/saml-sim-check.sh to verify readiness.
EOF
