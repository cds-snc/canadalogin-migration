# GC Sign in - User self-service Frontend Application

This is the frontend application built with React and GC Design System for the Government of Canada GC Sign in user self-service application.

## Running the Application

### Prerequisites

- node/npm should be installed on your machine or you can run this repository in a devcontainer to have them automatically available
- the back-end API should be running on port 8000 (see backend folder for instructions)

### Run the application locally

1. Install dependencies locally:

   ```bash
   npm install
   ```

2. Run the development server:

   ```bash
   npm run dev
   ```

   The application will be available at `http://localhost:3000`

### Optional environment variables

You can override the legacy language sync endpoint and timeout:

```env
VITE_LEGACY_LANGUAGE_API_URL=https://lang-canada.fjgc-gccf.gc.ca/v1/lang
VITE_LEGACY_LANGUAGE_TIMEOUT_MS=1500
```

Notes:

- The language sync call is browser-side and uses `credentials: include`.
- Language API values beginning with `en` or `fr` (such as `eng`, `fra`, `en-CA`, or `fr-CA`) are normalized to the app's `en` and `fr` routes.
- If the external language API fails, the app falls back to the language in the callback URL (`/en` or `/fr`).

3. Run tests:

   ```bash
   npm run test
   ```

See package.json scripts for additional commands.

4. Run Storybook:
   ```bash
   npm run storybook
   ```

### Running Vitest

To execute a specific unit test file, specify your file path:

```bash
npx vitest src/features/ProfileName/__tests__/ProfileUpdateName.test.jsx
```

To update snapshots for a specific test:

```bash
npx vitest src/features/ProfileName/__tests__/ProfileUpdateName.test.jsx -u
```

vitest docs:

- [Vitest CLI Documentation](https://vitest.dev/guide/cli.html)
