# Backend Application

This is the FastAPI application for the GC Sign in back-end API.

## Running with Docker

### Prerequisites

- Docker installed on your machine (use Colima if on a CDS MacBook)
- Python 3.12 (if running locally without Docker)
- Redis server running locally (required for session management)
- `.env` file with required environment variables

#### Setting up Redis

The application requires Redis for session management. Install and start Redis:

```bash
# Install Redis using Homebrew (macOS)
brew install redis

# Start Redis as a background service
brew services start redis

# Verify Redis is running
redis-cli ping
# Should return: PONG
```

For other operating systems:

- **Ubuntu/Debian**: `sudo apt-get install redis-server`
- **CentOS/RHEL**: `sudo yum install redis` or `sudo dnf install redis`
- **Windows**: Use Redis for Windows or run via Docker

#### Docker Networking for Redis

Since the application runs in a Docker container and Redis runs on your host machine, we need to configure Docker networking to allow the container to access the host's Redis instance:

- `--add-host host.docker.internal:host-gateway`: Creates a network route from the container to the host
- `SESSION_REDIS_URL=redis://host.docker.internal:6379/0`: Overrides the default Redis URL to use the Docker host gateway

This approach works across different Docker platforms (Docker Desktop, Colima, etc.) and is more reliable than using `--network host`.

### Environment Variables

Create a `.env` file with the following variables (or copy from `.env.example`):

```env
IBM_VERIFY_TENANT_URL=https://cds-gcsignin-dev.verify.ibm.com/
IBM_VERIFY_MIGRATION_API_CLIENT_ID=
IBM_VERIFY_MIGRATION_CLIENT_ID=
IBM_VERIFY_MIGRATION_SECRET=
IBM_VERIFY_MIGRATION_API_SECRET=
LEGACY_IDP_LOGOUT_ENABLED=true
RP_MIGRATION_CONFIG=[{"rp_client_id":"your-rp-client-id","rp_client_name":"Example RP","rp_client_name_en":"Example RP","rp_client_name_fr":"Exemple RP","rp_redirect_uri":"http://localhost:8080/auth/callback/client1","rp_redirect_uri_en":"http://localhost:8080/auth/callback/client1?lang=en","rp_redirect_uri_fr":"http://localhost:8080/auth/callback/client1?lang=fr","acr_values":"","IDP":[{"client_id":"your-legacy-idp-client-id","client_name":"SIC","openid_configuration":"https://te-auth.id.tbs-sct.gc.ca/oxauth/.well-known/openid-configuration","redirect_uris":["http://localhost:8000/v1/auth/legacy/callback"],"scope":"openid profile email","max_age":3600,"code_challenge_method":"S256","token_endpoint_auth_method":"client_secret_basic"}]}]
RP_MIGRATION_CONFIG_SECRETS=[{"client_id":"your-legacy-idp-client-id","client_secret":"your-legacy-idp-client-secret"}]
```

`LEGACY_IDP_LOGOUT_ENABLED` defaults to `false`. Set to `true` to enable the configured legacy OIDC IdP's logout redirect.

When legacy logout is enabled, the migration flow now redirects users to `/{lang}/link/lang-sync` before `/{lang}/link/success`.
That sync step is handled in the frontend and calls `https://lang-canada.fjgc-gccf.gc.ca/v1/lang` from the browser with credentials.
If the language API is unavailable or blocked (CORS/cookie policy/network), the app falls back to the language stored in backend session (`en` by default).

`RP_MIGRATION_CONFIG` supports per-RP `acr_values`:
- `""` (blank): no forced MFA; legacy provider choice unchanged (e.g., GCKey + Interac)
- `"gckey"`: GCKey only
- `"MFA"`: force MFA prompt
- `"gckeymfa"`: GCKey only + force MFA prompt

`RP_MIGRATION_CONFIG` also supports per-language RP return URLs:
- `rp_redirect_uri_en`: used when the migration session language is English
- `rp_redirect_uri_fr`: used when the migration session language is French
- `rp_redirect_uri`: optional fallback used when a language-specific URL is not configured

At least one of `rp_redirect_uri`, `rp_redirect_uri_en`, or `rp_redirect_uri_fr` must be present for each RP.

A formatted non-secret sample file is available at `backend/docs/rp_migration_config.sample.json`.
A sample secrets payload is available at `backend/docs/rp_migration_config_secrets.sample.json`.

`RP_MIGRATION_CONFIG_SECRETS` is keyed by legacy IdP `client_id`.
The loader merges matching `client_secret` values at startup before runtime validation.
If a legacy IdP secret is missing, the config still loads and a warning is logged.
Those IdPs may still require a configured `client_secret` at runtime if they use confidential client authentication.
Inline `client_secret` inside `RP_MIGRATION_CONFIG` is still accepted for backward compatibility.

To convert a formatted JSON file into a one-line env var value:

```bash
python3 backend/scripts/rp_migration_config_to_env.py
```

This prints:

```bash
RP_MIGRATION_CONFIG='[...]'
```

Useful options:

```bash
# Output raw compact JSON only (no RP_MIGRATION_CONFIG= prefix)
python3 backend/scripts/rp_migration_config_to_env.py --format value

# Use a custom input file and write to output file
python3 backend/scripts/rp_migration_config_to_env.py \
  --input /path/to/rp_migration_config.json \
  --output /tmp/rp_migration_config.env
```

#### GCCF migration configuration in TEST

GCCF uses the existing OIDC configuration with `IDP[].client_name` set to `"GCCF"`.
Each migration RP is configured through `RP_MIGRATION_CONFIG`; adding an RP does not require a code change.
Use one legacy `IDP` entry per RP. No `protocol` or `provider_key` field is required.

The [GCCF sample](docs/rp_migration_config.gccf.sample.json) contains two RP entries for the simulator's `client7` and `client8` flows.
Append these entries to the existing `RP_MIGRATION_CONFIG` array in Terraform after replacing the placeholders:

- Outer `rp_client_id`: the corresponding RP's client ID from IBM Verify TEST. Use a distinct `rp_client_name` for each RP.
- Inner `IDP[].client_id`: the GCCF client ID used by migration. Both entries can share it when they use the same GCCF registration.
- `openid_configuration`: the full discovery URL supplied for GCCF TEST, including its discovery path. The sample URL is a placeholder.
- `token_endpoint_auth_method`: the method registered for that GCCF client. The sample's `client_secret_basic` is illustrative; replace it with the registered shared-secret method, such as `client_secret_post` if applicable.
- `scope`: scopes allowed by the GCCF registration. The sample requests `openid`; add `profile` or `email` only if required and allowed.

Register this migration callback on the GCCF client:

```text
https://api.migration.test.login-connexion.alpha.canada.ca/v1/auth/legacy/callback
```

If `LEGACY_IDP_LOGOUT_ENABLED=true` and GCCF advertises an end-session endpoint, also register `https://api.migration.test.login-connexion.alpha.canada.ca/v1/auth/legacy/post_logout` as the migration post-logout redirect URI. This is separate from the simulator's logout callback. If the provider has no end-session endpoint, migration continues to its completion flow without a provider logout redirect.

The sample's `rp_redirect_uri_en` and `rp_redirect_uri_fr` return the user to the simulator's `/auth/client7/{lang}` or `/auth/client8/{lang}` route after migration.
These are RP return URLs, separate from the OIDC callback registered on the GCCF client.
The simulator's direct GCCF `client6` flow does not need an entry in migration configuration.

The first entry uses `acr_values: ""` to leave provider selection to GCCF; the second sends `acr_values: "gckey"` for GCKey only.
Confirm in TEST that GCCF accepts `gckey` and applies the expected provider restriction.

Supply the GCCF secret separately through `RP_MIGRATION_CONFIG_SECRETS`, using the same inner GCCF client ID:

```json
[
  {
    "client_id": "your-gccf-test-client-id",
    "client_secret": "your-gccf-test-client-secret"
  }
]
```

One matching secret entry is merged into both RP configurations at startup.
The Verify RP secrets used by the simulator are not the legacy IdP secret in this payload.
Keep existing secret entries when adding the GCCF entry, and supply the real secret through the deployment secret process.

The sample can be validated and compacted without contacting GCCF:

```bash
python3 backend/scripts/rp_migration_config_to_env.py \
  --input backend/docs/rp_migration_config.gccf.sample.json
```

Automated OIDC tests use mocks. The real GCCF flow must be validated in TEST: discovery and authentication, callback and account linking, return to each RP, GCKey-only selection, and logout if enabled.
Local GCCF credentials or connectivity are not required for the mock tests.

#### IBM_VERIFY_MIGRATION_CLIENT_ID and IBM_VERIFY_MIGRATION_SECRET

Head to https://cds-gcsignin-dev.verify.ibm.com/ui/admin/application/9053160440215070489?tab=sso, open the "Sign-on" tab, and copy the Client ID and Client secret.

#### IBM_VERIFY_MIGRATION_API_CLIENT_ID and IBM_VERIFY_MIGRATION_API_SECRET

Head to https://cds-gcsignin-dev.verify.ibm.com/ui/admin/application/9053160440215070489?tab=API%20access, open the "API access" tab. Select the DEV API Client key. Copy the Client ID and Client secret on the right side of the screen.

### Quick Start

1. Build the Docker image:

```bash
docker build -t gc-signin-backend .
```

2. Run the container:

```bash
docker run -p 8000:8000 \
  --add-host host.docker.internal:host-gateway \
  --env-file ./.env \
  -e SESSION_REDIS_URL=redis://host.docker.internal:6379/0 \
  gc-signin-backend
```

3. You can also run the fastapi server locally from the root folder:
   Start the server from the root directory with the [FastAPI CLI](https://fastapi.tiangolo.com/#run-it) command or Uvicorn

```
make install-dev-python
fastapi run backend/app/main.py or uvicorn app.main:app --reload --app-dir backend
```

The API will be available at `http://localhost:8000`

### Verification

After starting the container, verify the application is working:

```bash
# Test the health endpoint
curl http://localhost:8000/health/health

# Should return: {"status":"healthy","timestamp":"...","service":"gc-signin-backend"}
```

If you see a Redis connection error, ensure Redis is running and the Docker networking is configured correctly (see Troubleshooting section).

### API Documentation

Once running, you can access:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI Spec: `http://localhost:8000/openapi.json`

Generate and store the OpenAPI spec in the repository:

```bash
make generate-openapi
```

The checked-in file is written to `backend/openapi/openapi.json`.

### Development Mode

For development with hot-reload:

```bash
docker run -p 8000:8000 \
  --add-host host.docker.internal:host-gateway \
  --env-file .env \
  -e SESSION_REDIS_URL=redis://host.docker.internal:6379/0 \
  -v $(pwd):/app \
  gc-signin-backend \
  uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Note**: The `--add-host host.docker.internal:host-gateway` flag allows the Docker container to access Redis running on your host machine. The environment variable `SESSION_REDIS_URL` overrides the default localhost Redis URL to use `host.docker.internal`.

**Background Mode**: To run the container in the background (detached mode), add the `-d` flag:

```bash
docker run -d -p 8000:8000 \
  --add-host host.docker.internal:host-gateway \
  --env-file .env \
  -e SESSION_REDIS_URL=redis://host.docker.internal:6379/0 \
  -v $(pwd):/app \
  gc-signin-backend \
  uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Troubleshooting

1. **Redis Connection Error** (`ConnectionError: Error connecting to localhost:6379`):

   This error occurs because Docker containers can't access `localhost` on the host machine by default.

   **Solution - Use host gateway** (recommended):

   ```bash
   docker run -p 8000:8000 \
     --add-host host.docker.internal:host-gateway \
     --env-file .env \
     -e SESSION_REDIS_URL=redis://host.docker.internal:6379/0 \
     -v $(pwd):/app \
     gc-signin-backend \
     uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

   **Check Redis status**:

   ```bash
   # Verify Redis is running
   redis-cli ping

   # If not running, start Redis
   brew services start redis

   # Check Redis status
   brew services list | grep redis
   ```

2. If you encounter permission issues:

   ```bash
   docker run -p 8000:8000 \
     --env-file ./.env \
     -u $(id -u):$(id -g) \
     gc-signin-backend
   ```

3. To view logs:

   ```bash
   docker logs <container_id>
   ```

4. To access the container shell:
   ```bash
   docker exec -it <container_id> /bin/bash
   ```

### Health Check

Monitor the application health:

```bash
curl http://localhost:8000/health/health
```

Expected response:

```json
{
  "status": "healthy",
  "timestamp": "2025-09-23 15:32:33",
  "service": "gc-signin-backend"
}
```

## Running Tests

To run the unit tests, follow these steps:

1. Install the development dependencies (run this from root of the repo):

   ```bash
   make install-dev-python
   ```

2. Set environment variables (they can be dummy values for mock tests)

   ```bash
   export IBM_VERIFY_TENANT_URL=abc123
   export IBM_VERIFY_API_CLIENT_ID=abc123
   export IBM_VERIFY_API_CLIENT_SECRET=abc123
   export IBM_VERIFY_MIGRATION_API_CLIENT_ID=abc123
   export IBM_VERIFY_MIGRATION_API_SECRET=abc123
   export IBM_VERIFY_MIGRATION_CLIENT_ID=abc123
   export IBM_VERIFY_MIGRATION_SECRET=abc123
   ```

3. Run all the tests (run this from root of the repo):

   ```bash
   make run-pytest
   ```

4. Run tests and generate a coverage report:

   ```bash
   pytest --cov=app --cov-report=term-missing
   ```

5. Run a specific test:
   ```bash
   pytest tests/test_hello.py::test_hello_world -v
   ```

## Other commands

- Format python (from root folder)

  ```bash
  make fmt-python
  ```

- Run Lint (from root folder)
  ```bash
  make lint-python
  ```
- Building a Dockerimage from your macbook M1 to AWS
  ```bash
  docker buildx  build --platform linux/amd64 -t [NAME] .
  ```
