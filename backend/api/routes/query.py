from fastapi import APIRouter, Request, HTTPException
from fastapi import APIRouter
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/")
async def run_query(request: Request):
    """Accept a query in either NLP or SQL mode."""
    body = await request.json()
    user_query = body.get("query")
    mode = body.get("mode", "nlp")  # default NLP
    db_path = body.get("db_path", "data/sqldb.db")
    
    if not user_query:
        raise HTTPException(status_code=400, detail="Missing query")

    connection_string = f"sqlite:///{db_path}"

    # Use app-level singletons
    schema_discovery = request.app.state.schema_discovery
    query_engine = request.app.state.query_engine

    try:
        if mode == "sql":
            # Raw SQL mode (be careful!)
            if not user_query.strip().lower().startswith("select"):
                raise HTTPException(status_code=400, detail="Only SELECT statements allowed")
            
            result = query_engine.execute_sql(user_query)
            return {"mode": "sql", "results": result}

        else:
            # NLP mode
            schema = schema_discovery.analyze_database(connection_string)
            result = query_engine.process_query(user_query, schema)
            return {"mode": "nlp", "results": result}

    except Exception as e:
        logger.error(f"Query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_query_history(request: Request):
    query_engine = request.app.state.query_engine
    return query_engine.get_query_history()
