from fastapi import APIRouter, Request, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import logging
import time
from backend.services.history_service import HistoryService
from backend.services.llm_service import LLMService
from backend.services.schema_discovery import SchemaDiscovery
from backend.services.query_engine import QueryEngine
from backend.api.routes.auth import get_current_user, get_db

router = APIRouter()
logger = logging.getLogger(__name__)

# Lazy initialization of services
_history_service = None
_llm_service = None
_schema_discovery = None
_query_engine = None

def get_history_service():
    global _history_service
    if _history_service is None:
        _history_service = HistoryService()
    return _history_service

def get_llm_service():
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service

def get_schema_discovery():
    global _schema_discovery
    if _schema_discovery is None:
        _schema_discovery = SchemaDiscovery()
    return _schema_discovery

def get_query_engine():
    global _query_engine
    if _query_engine is None:
        _query_engine = QueryEngine()
    return _query_engine

class QueryRequest(BaseModel):
    query: str
    connection_string: str
    mode: Optional[str] = "llm"  # "llm" or "sql"

@router.post("/", dependencies=[Depends(get_current_user)])
async def run_query(
    request: QueryRequest,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Execute a query in LLM or SQL mode"""
    start_time = time.time()

    if not request.query:
        raise HTTPException(status_code=400, detail="Missing query")

    if not request.connection_string:
        raise HTTPException(status_code=400, detail="Missing connection_string")

    try:
        # Set connection for query engine
        query_engine = get_query_engine()
        query_engine.set_connection(request.connection_string)

        result = None
        generated_sql = None

        if request.mode == "sql":
            # Raw SQL mode - validate it's SELECT only
            if not request.query.strip().upper().startswith("SELECT"):
                raise HTTPException(status_code=400, detail="Only SELECT statements allowed in SQL mode")

            result = query_engine.execute_sql(request.query)
            generated_sql = request.query

        elif request.mode == "llm":
            # LLM mode - generate SQL from natural language
            schema_discovery = get_schema_discovery()
            schema = schema_discovery.analyze_database(request.connection_string)
            llm_service = get_llm_service()
            generated_sql = llm_service.generate_sql(request.query, schema)

            # Execute the generated SQL
            result = query_engine.execute_sql(generated_sql)

        else:
            raise HTTPException(status_code=400, detail="Invalid mode. Use 'llm' or 'sql'")

        # Store in history
        response_time_ms = int((time.time() - start_time) * 1000)
        history_service = get_history_service()
        history_service.store_history(
            user_id=current_user.id,
            query_text=request.query,
            mode=request.mode,
            connection_string=request.connection_string,
            generated_sql=generated_sql,
            status="success",
            response_time=response_time_ms
        )

        return {
            "status": "success",
            "result": result,
            "mode": request.mode,
            "generated_sql": generated_sql
        }

    except Exception as e:
        logger.error(f"Query failed: {e}")

        # Store failed query in history
        response_time_ms = int((time.time() - start_time) * 1000)
        try:
            history_service = get_history_service()
            history_service.store_history(
                user_id=current_user.id,
                query_text=request.query,
                mode=request.mode,
                connection_string=request.connection_string,
                status="error",
                error_message=str(e),
                response_time=response_time_ms
            )
        except Exception as history_error:
            logger.error(f"Failed to store query history: {history_error}")

        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history", dependencies=[Depends(get_current_user)])
async def get_query_history(
    current_user = Depends(get_current_user),
    limit: int = 50
):
    """Get user's query history"""
    try:
        history_service = get_history_service()
        history = history_service.get_user_history(current_user.id, limit)
        return {
            "status": "success",
            "history": history
        }
    except Exception as e:
        logger.error(f"Failed to get query history: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve history")
