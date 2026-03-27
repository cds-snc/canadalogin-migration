# GC Sign in - Migration web application

A modern and accessible web application that allows users to link legacy pai to their GC Sign in account.  Built with a React front-end using the [GC Design System](https://github.com/cds-snc/gcds-components), and a supporting FastAPI back-end API that integrates with the IBM Verify SaaS (IdP) to handle login, logout and profile updates. Nice!

## Architecture
This solution follows a BFF (backend for frontend) architectural pattern:
- Frontend: React-based SPA
- Backend: FastAPI Python service
- Authentication and Identity Store: IBM Security Verify CIAM SaaS
- Infrastructure (AWS): ECS, ECR, ALB, Secrets Manager, CloudFront, Route 53, WAF, CloudWatch

### Local Development Setup

1. Clone the repository:
```bash
git clone https://github.com/cds-snc/gc-sign-in-migration.git
```

### Running the application locally (quick start)

These condensed steps give a fast path to run both the backend and frontend for local development. For more details and configuration options, see the [backend README](backend/README.md) and [frontend README](frontend/README.md).

1. Install backend development dependencies (from repo root):

```bash
make install-dev-python
```

2. Ensure Redis is running locally (required by the backend for sessions):

macOS (Homebrew):

```bash
brew install redis
brew services start redis
redis-cli ping # should return PONG
```

3. Create a `.env` file in the repo root or backend folder and populate required environment variables. You can copy values from `backend/docs/rp_migration_config.sample.json` for non-secret config, and use dummy values for tests.

4. Run the backend locally (hot-reload):

```bash
# from the repo root
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --app-dir backend
```

Alternatively build and run the backend in Docker:

```bash
docker build -t gc-signin-backend ./backend
docker run -p 8000:8000 \
	--add-host host.docker.internal:host-gateway \
	--env-file ./.env \
	-e SESSION_REDIS_URL=redis://host.docker.internal:6379/0 \
	gc-signin-backend
```

5. Run the frontend (separate terminal):

```bash
cd frontend
npm install
npm run dev
# frontend available at http://localhost:3000
```

6. Verify the backend is healthy:

```bash
curl http://localhost:8000/health/health
# expected: {"status":"healthy",...}
```

### Legacy Language Sync
- After legacy IDP callback, users are redirected to `/{lang}/link/lang-sync`.
- The frontend page calls `https://lang-canada.fjgc-gccf.gc.ca/v1/lang` in the browser with credentials to resolve language.
- If the language service call fails, the app falls back to session/URL language (`en` default).

### OpenAPI Spec

Generate and update the checked-in backend OpenAPI spec:

```bash
make generate-openapi
```

This writes `backend/openapi/openapi.json`.

It is important to keep this up to date.

### Additional Documentation
- [IBM Verify Documentation](https://docs.verify.ibm.com/verify/reference/overview)

### Other GC Sign in Repos
- [GC Sign in Terraform Repo (AWS Deployment)](https://github.com/cds-snc/gc-signin-terraform)
- [IBM Tenant Configuration Repo](https://github.com/cds-snc/gc-signin-ibm-configuration)
- [GC Sign in Static website](https://github.com/cds-snc/gc-signin-static-website)

### AWS Deployment
See [AWS Architecture](docs/architecture/gc-signin-pilot-architecture.png) for infrastructure details and visit the [gc-signin-terraform repo](https://github.com/cds-snc/gc-signin-terraform).

### Running tests (backend)

Run tests from the repo root after installing dev dependencies:

```bash
make install-dev-python
make run-pytest
# or run a single test with pytest
pytest tests/test_auth_user_session.py -q
```
