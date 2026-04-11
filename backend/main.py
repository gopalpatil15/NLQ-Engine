from dotenv import load_dotenv
load_dotenv()  # Load .env file before anything else reads env vars

from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import sqlite3
import logging
import uuid
import tempfile
import os
import json
from backend.services.schema_discovery import SchemaDiscovery
from backend.services.document_processor import DocumentProcessor
from backend.services.query_engine import QueryEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Startup validation
if not os.getenv('OPENAI_API_KEY'):
    logger.warning(
        "WARNING: OPENAI_API_KEY is not set. LLM queries will fail. "
        "Set it with: export OPENAI_API_KEY=sk-... (Linux/Mac) or "
        "$env:OPENAI_API_KEY='sk-...' (Windows PowerShell)"
    )

# Create FastAPI app
app = FastAPI(
    title="LLM Query Engine",
    description="LLM-powered Query Engine for Database Access with User Authentication",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for demo
schemas = {}
query_history = []
processing_status = {}

class QueryRequest(BaseModel):
    query: str
    connection_string: Optional[str] = None

# Absolute paths
base_dir = os.path.dirname(os.path.dirname(__file__))   # E:/NLQ-Engine
frontend_dir = os.path.join(base_dir, "frontend")
static_dir = os.path.join(frontend_dir, "static")

# Mount /static → frontend/static
app.mount("/static", StaticFiles(directory=static_dir), name="static")

schema_discovery = SchemaDiscovery()
document_processor = DocumentProcessor()
query_engine = QueryEngine()
app.state.schema_discovery = schema_discovery
app.state.document_processor = document_processor
app.state.query_engine = query_engine
app.state.processing_status = processing_status

from backend.api.routes import ingestion as ingestion_router_mod
from backend.api.routes import query as query_router_mod
from backend.api.routes import schema as schema_router_mod
from backend.api.routes import auth as auth_router_mod

app.include_router(auth_router_mod.router, prefix="/api/auth", tags=["auth"])
app.include_router(ingestion_router_mod.router, prefix="/api/ingest", tags=["ingest"])
app.include_router(query_router_mod.router, prefix="/api/query", tags=["query"])
app.include_router(schema_router_mod.router, prefix="/api/schema", tags=["schema"])

# Serve index.html at root
@app.get("/")
async def serve_index():
    return FileResponse(os.path.join(frontend_dir, "index.html"))


@app.get("/favicon.ico")
async def favicon():
        """Return a simple SVG favicon so browsers don't 404 when requesting /favicon.ico."""
        svg = '''
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
            <rect width="64" height="64" rx="12" fill="#667eea"/>
            <text x="50%" y="55%" font-size="36" text-anchor="middle" fill="#fff" font-family="Arial" font-weight="700">N</text>
        </svg>
        '''
        return Response(content=svg, media_type='image/svg+xml')

# Catch-all for client-side routing
@app.get("/{full_path:path}")
async def catch_all(full_path: str):
    """Serve index.html for any unmatched route (SPA support)."""
    index = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index):
        return FileResponse(index)
    raise HTTPException(status_code=404, detail="Not found")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
@app.get("/api/metrics")
async def get_metrics():
    """Get system metrics"""
    avg_response_time = 0.0
    if query_history:
        avg_response_time = sum([q.get("response_time", 0) for q in query_history]) / len(query_history)
    
    return {
        "status": "success",
        "metrics": {
            "query_count": len(query_history),
            "average_response_time": round(avg_response_time, 2),
            "cache_hit_rate": 65,  # simulated
            "documents_processed": 0,
            "active_connections": 1
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)