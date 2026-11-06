# Biashara Hub delivery plan

Work only in the folder assigned to your role. Tick items only after implementation and record verification evidence. Contract changes require an integrator decision first.

## Backend — Codex (`backend/`)

- [ ] Create FastAPI/SQLModel application and SQLite development setup with PostgreSQL-compatible types.
- [ ] Implement vendor/customer registration, login, JWT auth, and role/ownership checks.
- [ ] Implement vendor onboarding and admin vendor approval.
- [ ] Implement product CRUD/search, cart/order creation, delivery status, and health endpoint.
- [ ] Implement Daraja sandbox OAuth, STK Push, status query fallback, and idempotent callback result processing.
- [ ] Match all response/error shapes in `contract/openapi.yaml`; configure CORS from environment.
- [ ] Run and record backend checks; commit to `agent/backend`.

## Frontend — Qwen via Ollama (`frontend/`)

- [ ] Create React + TypeScript + Vite app and typed API client generated from/consistent with the contract.
- [ ] Build marketplace search, product detail, cart, and checkout with Kenyan phone validation and M-Pesa pending/polling states.
- [ ] Build vendor onboarding/dashboard, product/order screens, delivery tracking, and admin vendor approval.
- [ ] Make screens mobile-first, accessible, resilient to slow connections, and explicit about loading/errors.
- [ ] Use env-configured API base URL; include contract-based mocks until backend is ready.
- [ ] Run and record frontend checks; commit to `agent/frontend`.

## QA — Hermes (`tests/`)

- [ ] Add pytest/httpx contract tests for endpoint success and failure cases.
- [ ] Cover STK success, cancellation, timeout, duplicate callback idempotency, and tampered callback.
- [ ] Add full-flow smoke test: vendor registration → product → order → sandbox payment → delivery.
- [ ] Report defects here under Bugs with endpoint, reproduction steps, expected and actual results; do not fix app code.
- [ ] Run and record checks; commit to `agent/tests`.

## Ops — OpenClaw (`deploy/`)

- [ ] Add backend Dockerfile and frontend production build configuration.
- [ ] Add local docker-compose and one staging deployment config (Render or Railway).
- [ ] Document every `.env.example` variable and non-expert deployment steps in `DEPLOY.md`.
- [ ] Document HTTPS callback setup (ngrok for development, owned domain for production), database backup, and health checks.
- [ ] Use placeholders only; no real secrets. Run and record config checks; commit to `agent/deploy`.

## Integrator / merge order

- [x] Establish the API and folder ownership contract before feature work.
- [ ] Review each branch against contract, ownership rules, and security; rebase before merge.
- [ ] Merge backend, tests, frontend, then deploy, one branch at a time; run relevant checks after each.
- [ ] Send test findings to the owning agent and repeat until smoke tests pass.
- [ ] Deploy to staging with Daraja sandbox only after review.

## Contract questions

None recorded.

## Bugs

None recorded.

## Local agent connectivity notes

- Codex desktop is authenticated and is the current integrator.
- Ollama's local API responds at `http://127.0.0.1:11434`; `qwen2.5:7b` and `llama3.2:3b` are installed. Both returned live smoke-test responses.
- Hermes Agent is installed. Its global default points to Ollama Cloud, which currently returns HTTP 429. Local project runs work with `hermes -m llama3.2:3b --provider ollama`; Hermes rejects `qwen2.5:7b` because its advertised 32K context is below Hermes's 64K minimum.
- OpenClaw 2026.9.8 is installed and configured to use local `ollama/qwen2.5:7b` as its default. Its direct inference smoke test returned successfully. A previous `openclaw status` call timed out, but the CLI model inference path is operational.
- The `qwen` executable is absent; Qwen is the local Ollama model and is callable through Ollama/OpenClaw.
