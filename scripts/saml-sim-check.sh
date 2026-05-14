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

check_url() {
  local label="$1"
  local url="$2"
  local attempt

  printf 'Checking %s: %s\n' "${label}" "${url}"
  for attempt in {1..30}; do
    if curl -fsSk --max-time 10 "${url}" >/dev/null; then
      return 0
    fi
    sleep 1
  done

  printf 'Timed out waiting for %s: %s\n' "${label}" "${url}" >&2
  return 1
}

docker compose "${COMPOSE_ARGS[@]}" config >/dev/null

check_url "GCKey settings" "https://localhost:9443/api/settings.php"
check_url "GCKey metadata" "https://localhost:9443/sso/saml2/idp/metadata.php"
check_url "Interac settings" "https://localhost:9444/api/settings.php"
check_url "Interac metadata" "https://localhost:9444/sso/saml2/idp/metadata.php"

docker compose "${COMPOSE_ARGS[@]}" ps

cat <<'EOF'
Local SAML simulators are reachable.
EOF
