from fastapi import APIRouter, HTTPException, Request
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/analyze")
async def analyze_database(connection_string: str, request: Request):
    """Analyze a database and return schema info"""
    schema_discovery = request.app.state.schema_discovery
    try:
        schema_info = schema_discovery.analyze_database(connection_string)
        return {"status": "success", "schema": schema_info}
    except Exception as e:
        logger.exception("Schema analysis failed")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/map")
async def map_query(query: str, connection_string: str, request: Request):
    """Map a natural language query to schema objects"""
    schema_discovery = request.app.state.schema_discovery
    try:
        if connection_string not in schema_discovery.schema_cache:
            # auto-analyze if not cached
            schema_discovery.analyze_database(connection_string)

        schema = schema_discovery.schema_cache[connection_string]
        mapping = schema_discovery.map_natural_language_to_schema(query, schema)
        return {"status": "success", "mapping": mapping}
    except Exception as e:
        logger.exception("Mapping failed")
        raise HTTPException(status_code=400, detail=str(e))
