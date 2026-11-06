# Biashara Hub

Kenya-focused local marketplace with a FastAPI backend and responsive React frontend. Customers and businesses use one registration page to choose their account type. Admins sign in separately to review business applications.

## Run locally

1. Copy `.env.example` to `.env` and set a random `JWT_SECRET_KEY` (at least 32 characters). To enable the local admin account, set both `INITIAL_ADMIN_EMAIL` and `INITIAL_ADMIN_PASSWORD`.
2. Start the API from `backend/`:

   ```sh
   python -m venv .venv
   . .venv/bin/activate
   pip install -e '.[dev]'
   set -a && . ../.env && set +a
   uvicorn app.main:app --reload
   ```

3. In another terminal, start the web app from `frontend/frontend/`:

   ```sh
   npm ci
   npm run dev
   ```

Open `http://localhost:5173`. The API documentation is at `http://localhost:8000/docs`.

## Hosting

The GitHub Actions workflow publishes the static frontend to GitHub Pages on pushes to `main`. Set the repository Actions variable `VITE_API_BASE_URL` to the HTTPS URL of a separately deployed backend. Configure backend `CORS_ORIGINS` to include the Pages origin. GitHub Pages cannot run the FastAPI backend. Use Safaricom's Daraja sandbox credentials only for development, and configure a reachable HTTPS callback URL before trying STK Push.

See [backend setup](backend/README.md) and [frontend setup](frontend/README.md) for details. Do not commit `.env` or real credentials.