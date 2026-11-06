# Biashara Hub backend

FastAPI + SQLModel API matching `../contract/openapi.yaml`. For local development:

```sh
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
uvicorn app.main:app --reload
```

Configuration is read from environment variables: `DATABASE_URL` (defaults to `sqlite:///./biashara.db`), `JWT_SECRET_KEY` (required, at least 32 characters), `JWT_EXPIRES_MINUTES`, `CORS_ORIGINS` (comma-separated), `INITIAL_ADMIN_EMAIL` and `INITIAL_ADMIN_PASSWORD` (set both only to bootstrap the initial admin; an existing account is never promoted), `DARAJA_BASE_URL` (must remain the Safaricom sandbox URL), `DARAJA_CONSUMER_KEY`, `DARAJA_CONSUMER_SECRET`, `DARAJA_SHORTCODE`, `DARAJA_PASSKEY`, `DARAJA_CALLBACK_URL` (public HTTPS callback), `DARAJA_TIMEOUT_SECONDS`, and optional `DARAJA_TRANSACTION_TYPE`. Use sandbox credentials only. Do not commit credentials.

Copy the root `.env.example` to a private `.env`, fill the required local values, then start with the root env loaded, for example: `set -a && . ../.env && set +a && uvicorn app.main:app --reload` from this directory. The `.env` file is ignored by Git.
