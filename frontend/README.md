# Frontend

Owned by the frontend agent. Implement the mobile-first React + TypeScript + Vite experience to match `../contract/openapi.yaml`. Configure the API base URL through environment variables.
# Biashara Hub web app

Mobile-first React + TypeScript + Vite interface for the local marketplace.

## Run locally

From this directory:

```bash
npm install
npm run dev
```

Vite reads `VITE_API_BASE_URL` from the repository root `.env` (copy the root `.env.example` to `.env` first). The default is `http://localhost:8000`. Start the FastAPI backend separately, then open the Vite URL, usually `http://localhost:5173`.

## Included screens

- Public marketplace landing page with a shared customer/business account choice and registration/sign-in.
- Customer marketplace view with product search and order list.
- Business profile submission and business workspace.
- Separate admin sign-in entry point and vendor application review dashboard.

Admin accounts are provisioned by the backend using `INITIAL_ADMIN_EMAIL` and `INITIAL_ADMIN_PASSWORD`; there is no public admin registration.

## GitHub Pages

The repository includes a workflow that builds and publishes this frontend on pushes to `main`. Enable GitHub Pages with **GitHub Actions** as the build source in the repository settings. Set the repository Actions variable `VITE_API_BASE_URL` to the HTTPS URL of a separately deployed FastAPI backend; GitHub Pages only serves the frontend and cannot run this project's Python API. The backend must allow the Pages origin in `CORS_ORIGINS`.
