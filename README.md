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

### Running the Application Locally
#### 1. Run the backend
- See the [backend README](backend/README.md)
#### 2. Run frontend
- See the [frontend README](frontend/README.md)

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
