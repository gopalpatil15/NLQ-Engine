# LLM Query Engine

LLM Query Engine — a FastAPI backend with authentication and a static frontend for AI-powered database queries. Connect to any database, run natural language queries converted to SQL by OpenAI's GPT models, or execute raw SQL directly.

This repository includes:

- `backend/` — FastAPI application with LLM-powered SQL generation, user authentication (JWT), persistent query history, schema discovery, and modular routers.
- `frontend/` — Single-page static UI with login/register, database connection, and query interface.
- `data/` — Example SQLite database for testing.

## Quick overview

- Start the backend (FastAPI + Uvicorn). Serves frontend at `/` and API endpoints under `/api/...`.
- Frontend is static files served by backend; open `http://127.0.0.1:8000` in browser.
- Requires OpenAI API key for LLM queries; falls back gracefully if unavailable.

## Prerequisites

- Python 3.10+ installed on the machine.
- OpenAI API key (for LLM SQL generation).
- Recommended: Create a virtual environment.

On Windows PowerShell (example):

```powershell
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt
```

Set environment variable for OpenAI:

**Windows (PowerShell):**
```powershell
$env:OPENAI_API_KEY = "your-openai-api-key-here"
```

**Linux / macOS (bash/zsh):**
```bash
export OPENAI_API_KEY="your-openai-api-key-here"
```

Alternatively, copy `.env.example` to `.env` and fill in your key — the app loads it automatically if `python-dotenv` is installed.

Note: If OpenAI API key is not set, LLM queries will fail but raw SQL queries will still work.

## Running the app (development)

Start the backend (do this from the workspace root):

```powershell
# from the repo root (e:\NLQ-Engine)
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Notes:
- On Windows, the `--reload` auto-reloader may be flaky; if you see repeated restarts, run without `--reload` as above.
- The server serves the frontend at `http://127.0.0.1:8000`.

## Frontend

Open your browser at:

```
http://127.0.0.1:8000
```

UI features:
- User Authentication: Register/login with JWT tokens for secure access.
- Connect Database: Enter any SQLAlchemy-supported connection string and analyze schema.
- Query Data: Choose between LLM-powered natural language queries or raw SQL execution.
- Query History: View your personal query history with performance metrics.

## Important backend API endpoints

- GET `/health`
  - Health check: returns `{"status":"healthy"}`.

- POST `/api/auth/register`
  - Register new user. Body: `{ "username": "user", "password": "pass" }`.
  - Response: `{ "access_token": "...", "token_type": "bearer", "username": "user" }`.

- POST `/api/auth/login`
  - Login user. Body: `{ "username": "user", "password": "pass" }`.
  - Response: `{ "access_token": "...", "token_type": "bearer", "username": "user" }`.

- POST `/api/ingest/database`
  - Discover schema for a database. Requires auth header.
  - Body: `{ "connection_string": "sqlite:///path/to/db" }`.
  - Response: `{ "status": "success", "schema": { ... } }`.

- POST `/api/query`
  - Execute query in LLM or SQL mode. Requires auth header.
  - Body: `{ "query": "How many employees?", "connection_string": "...", "mode": "llm" }`.
  - Response: `{ "status": "success", "result": { ... }, "generated_sql": "..." }`.

- GET `/api/query/history`
  - Get user's query history. Requires auth header.
  - Response: `{ "status": "success", "history": [...] }`.

- GET `/favicon.ico`
  - Serves a small SVG so browsers don't 404 on favicon requests.

## Example PowerShell API calls

Register user:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/auth/register `
  -Body (@{username='testuser'; password='testpass'} | ConvertTo-Json) `
  -ContentType 'application/json'
```

Login (save token for other requests):

```powershell
$loginResponse = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/auth/login `
  -Body (@{username='testuser'; password='testpass'} | ConvertTo-Json) `
  -ContentType 'application/json'
$token = $loginResponse.access_token
```

Discover schema (with auth):

```powershell
$headers = @{Authorization="Bearer $token"}
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/ingest/database `
  -Headers $headers `
  -Body (@{connection_string='sqlite:///./data/Chinook_Sqlite.db'} | ConvertTo-Json) `
  -ContentType 'application/json'
```

Run LLM query:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/query `
  -Headers $headers `
  -Body (@{query='How many employees do we have?'; connection_string='sqlite:///./data/Chinook_Sqlite.db'; mode='llm'} | ConvertTo-Json) `
  -ContentType 'application/json'
```

Run SQL query:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/query `
  -Headers $headers `
  -Body (@{query='SELECT COUNT(*) FROM employees'; connection_string='sqlite:///./data/Chinook_Sqlite.db'; mode='sql'} | ConvertTo-Json) `
  -ContentType 'application/json'
```

## Troubleshooting

- If the frontend shows the backend as unreachable:
  - Confirm the uvicorn server is running in a terminal and listening (see server logs in the terminal).
  - Check for errors printed in the server terminal (model-loading errors, syntax errors). The repo has been adjusted to lazy-load heavy models to reduce startup issues.
  - On Windows, prefer running uvicorn without `--reload` to avoid the reloader interfering with long-running background work.

- If schema discovery fails for SQLite:
  - Ensure the path is correct and accessible from the process (Windows absolute paths require proper URI: `sqlite:///E:/path/to/db` or `sqlite:///e:/...`).

- If you see JS errors in the browser UI:
  - Open DevTools (F12) → Console and paste any error here; the UI has been updated to avoid common missing-function problems.

## Notes and next steps

- The services are currently instantiated on app startup and exposed on `app.state`. For production-grade usage, consider creating them in a startup event with controlled lifecycle and persistence for embeddings (e.g., a vector DB).
- The NL-to-SQL mapping and query engine are intentionally simple (rule-based) in this demo. Replace with a proper parser or LLM mapping for production.
- Document processing uses `sentence-transformers` for embeddings; consider swapping to a vector database and persistent index if you need large-scale document search.

## Contributing

PRs welcome. If you add heavy dependencies or model changes, update `backend/requirements.txt` and document the hardware requirements.

## License

This project is a demo. No license file is included; add MIT License via GitHub UI: **Add file → Create new file → type `LICENSE` → GitHub offers a template picker**.

---
## Docker

Run with a single command (no Python install needed):

```bash
docker build -t nlq-engine .
docker run -p 8000:8000 -e OPENAI_API_KEY=sk-... nlq-engine
```

Then open http://localhost:8000 in your browser.

---
If you want, I can also:

- Add a one-command `Makefile` / `tasks.json` for running the app and tests.
- Add an automated integration test that verifies health, schema discovery against the sample DB, and a sample query.
- Move service instantiation into FastAPI startup/shutdown lifecycle for cleaner resource management.

Tell me which of the above you'd like next and I'll implement it.