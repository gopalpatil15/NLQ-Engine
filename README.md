# NLQ-Engine

Natural Language Query Engine (NLQ-Engine) — a small demo that exposes a FastAPI backend and a minimal static frontend which lets you connect to a database, discover schema, upload documents for processing, and run natural-language-style queries against employee data.

This repository is intended as a developer demo / prototype. It includes:

- `backend/` — FastAPI application with a small rule-based NL-to-SQL layer, schema discovery helpers, document processing service (with sentence-transformers support), and modular routers.
- `frontend/` — A single-page static UI (`index.html`) with `static/script.js` and `static/style.css` to interact with the backend.
- `data/` — Example SQLite database (`sqldb.db`) used for quick testing (Chinook-style sample DB included).

## Quick overview

- Start the backend (FastAPI + Uvicorn). The backend serves the frontend at `/` and exposes API endpoints under `/api/...`.
- The frontend is static files served by the backend; open `http://127.0.0.1:8000` in a browser to use the UI.
- The document processor uses a sentence-transformers model for embeddings; the model is loaded lazily (on first use) to keep startup fast.

## Prerequisites

- Python 3.10+ installed on the machine.
- Recommended: Create a virtual environment.

On Windows PowerShell (example):

```powershell
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt
```

Note: `sentence-transformers` downloads model weights the first time a model is created. The code defers loading until the first document processing request, but ensure you have a working internet connection and sufficient disk/memory if you use the document search features.

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
- Connect Database: Enter a connection string (SQLite example: `sqlite:///e:/NLQ-Engine/data/sqldb.db`) and click *Connect & Analyze Schema*.
- Upload Documents: Upload PDFs/DOCX/TXT/CSV for indexing (background job).
- Query Data: Ask natural-language-style questions; the backend returns structured results (simulated / rule-based for the demo).

## Important backend API endpoints

- GET `/health`
  - Health check: returns `{"status":"healthy"}`.

- POST `/api/ingest/database`
  - Discover schema for a database. Accepts either:
    - JSON body: `{ "connection_string": "sqlite:///path/to/db" }` (recommended), or
    - Query parameter: `?connection_string=...` (legacy support).
  - Response: `{ "status": "success", "schema": { ... } }` or HTTP 400/422 with details.

- POST `/api/ingest/documents`
  - Upload files (multipart form). Returns a `job_id` and processes in background. Poll `/api/ingest/status/{job_id}` for progress.

- GET `/api/ingest/status/{job_id}`
  - Check ingestion / processing progress.

- POST `/api/query`
  - Run a natural-language query. Body: `{ "query": "How many employees do we have?", "connection_string": "..." }`.
  - Response: `{ "status": "success", "result": { ... } }`.

- GET `/api/query/history`
  - Returns last queries processed by the query engine instance.

- GET `/favicon.ico`
  - Serves a small SVG so browsers don't 404 on favicon requests.

## Example PowerShell API calls

Health check:

```powershell
Invoke-RestMethod -Method GET -Uri http://127.0.0.1:8000/health | ConvertTo-Json
```

Discover schema (JSON body):

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/ingest/database `
  -Body (@{connection_string='sqlite:///e:/NLQ-Engine/data/sqldb.db'} | ConvertTo-Json) `
  -ContentType 'application/json' | ConvertTo-Json
```

Run a query:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/query `
  -Body (@{query='How many employees do we have?'} | ConvertTo-Json) -ContentType 'application/json' | ConvertTo-Json
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

This project is a demo. No license file is included; add one if you plan to publish or share this repository publicly.

---
If you want, I can also:

- Add a one-command `Makefile` / `tasks.json` for running the app and tests.
- Add an automated integration test that verifies health, schema discovery against the sample DB, and a sample query.
- Move service instantiation into FastAPI startup/shutdown lifecycle for cleaner resource management.

Tell me which of the above you'd like next and I'll implement it.