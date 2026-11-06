# Biashara Hub agent contract

## Product and stack

Biashara Hub is a Kenyan SME marketplace. Backend: Python 3.12+, FastAPI, SQLModel, SQLite for local development with PostgreSQL-compatible models, and JWT authentication. Frontend: React, TypeScript, and Vite. Payments: Safaricom Daraja STK Push in sandbox mode only until an explicit production release decision. The API source of truth is `contract/openapi.yaml`.

## Ownership

- Backend agent owns `backend/` only.
- Frontend agent owns `frontend/` only.
- QA agent owns `tests/` only.
- Ops agent owns `deploy/` only.
- Integrator owns root documentation and `contract/`. `TASKS.md` is a shared status board: each agent may check only its own acceptance boxes and append relevant entries under `Bugs` or `Contract questions`. Agents must not change the API contract. If a required change is discovered, describe it in `TASKS.md` under `Contract questions`; wait for the integrator to update the contract and tasks.
- Everyone may read the full repository. Do not overwrite another owner's files. Report cross-folder needs rather than implementing them.

## Agent/model assignments on this PC

- Integrator: this Codex task (authenticated OpenAI Codex session).
- Backend: Codex CLI in the backend worktree.
- Frontend: Qwen 2.5 7B served locally by Ollama. The `qwen` executable is not installed; call it with `ollama run qwen2.5:7b` or through OpenClaw's coding agent runtime.
- QA: Hermes Agent with the local Ollama provider and `llama3.2:3b`. Hermes rejects Qwen 2.5 7B because the available model window is below Hermes's 64K minimum. A one-shot Hermes response using local Llama 3.2 was verified.
- Ops: OpenClaw with default model `ollama/qwen2.5:7b`. A direct local model response through OpenClaw was verified. For isolated coding runs, set `--cwd` to the role worktree and use `--local`.

Verified local routes: Ollama serves Qwen 2.5 7B and Llama 3.2 3B at `http://127.0.0.1:11434`; OpenClaw's default model is set to local Qwen; Hermes can call local Ollama using `--provider ollama -m llama3.2:3b`; Codex desktop is authenticated. The Hermes global default remains Ollama Cloud, so always pass the local provider/model flags for this project.

No agent may paste, commit, or log secrets. Never use production payment credentials. Do not silently substitute a model/provider: record actual model/provider and failures in `TASKS.md`.

## Setup and run commands

- Backend: `cd backend && python -m venv .venv && . .venv/bin/activate && pip install -e '.[dev]' && uvicorn app.main:app --reload`
- Frontend: `cd frontend && npm install && npm run dev`
- Tests: `cd tests && python -m venv .venv && . .venv/bin/activate && pip install -e '.[dev]' && pytest`
- Local services: `cd deploy && docker compose up --build`

Keep commands and dependency manifests aligned with the actual implementation. Never claim a command passes unless it was run.

## Coding and security rules

- Match `contract/openapi.yaml`; validate inputs and return the documented error shape.
- Read configuration only from environment variables. `.env` is local-only and must remain ignored.
- Keep M-Pesa sandbox endpoints/configuration; never add real Daraja credentials.
- Verify callback origin/signature where supported, correlate checkout requests, and make callback processing idempotent. Do not trust a client-supplied payment success state.
- Use password hashing, JWT expiry and role checks; authorize vendor resources by owner.
- Add CORS origins through configuration, not `*` in production.
- Avoid storing unnecessary personal data. Never log passwords, tokens, phone numbers in full, or payment secrets.
- Make accessibility, mobile layout, and slow-network states part of frontend acceptance.

## Definition of done

1. Acceptance criteria for the owned tasks are met and checked in `TASKS.md`.
2. Contract compatibility and relevant automated checks are run; exact commands and results are recorded.
3. No secrets, unrelated files, or unrequested contract edits are included.
4. Changes are committed on the assigned `agent/<owner>` branch with a clear message.
5. Any blocker, security concern, contract ambiguity, or unrun check is recorded in `TASKS.md`.
