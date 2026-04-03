from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
import logging
import re
import hashlib
import time
from typing import Dict, Any, List
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class QueryCache:
    def __init__(self, ttl_seconds: int = 300, max_size: int = 1000):
        self.cache = {}
        self.ttl = ttl_seconds
        self.max_size = max_size
        self.access_times = {}

    def get(self, key: str) -> Any:
        if key in self.cache:
            if time.time() - self.access_times[key] < self.ttl:
                self.access_times[key] = time.time()
                return self.cache[key]
            else:
                # Expired
                del self.cache[key]
                del self.access_times[key]
        return None

    def set(self, key: str, value: Any):
        if len(self.cache) >= self.max_size:
            # Remove oldest
            oldest_key = min(self.access_times.items(), key=lambda x: x[1])[0]
            del self.cache[oldest_key]
            del self.access_times[oldest_key]

        self.cache[key] = value
        self.access_times[key] = time.time()

class QueryEngine:
    def __init__(self, connection_string: str = None):
        self.connection_string = connection_string
        self.engine = None
        self.cache = QueryCache()

        if connection_string:
            self.engine = create_engine(connection_string)

    def set_connection(self, connection_string: str):
        """Set database connection after initialization"""
        self.connection_string = connection_string
        self.engine = create_engine(connection_string)

    def execute_sql(self, sql: str) -> Dict[str, Any]:
        """Execute SQL query and return results"""
        start_time = time.time()

        # Generate cache key
        cache_key = hashlib.md5(sql.encode()).hexdigest()

        # Check cache
        cached_result = self.cache.get(cache_key)
        if cached_result:
            cached_result["cache_hit"] = True
            cached_result["response_time"] = time.time() - start_time
            return cached_result

        if not self.engine:
            raise Exception("Database connection not established")

        try:
            with self.engine.connect() as conn:
                # Safety check: only allow SELECT queries
                if not sql.strip().upper().startswith("SELECT"):
                    raise Exception("Only SELECT queries are allowed")

                # Execute query
                result = conn.execute(text(sql))
                rows = [dict(row._mapping) for row in result]

                result_data = {
                    "results": rows,
                    "result_count": len(rows),
                    "sql_executed": sql,
                    "cache_hit": False,
                    "response_time": time.time() - start_time,
                    "timestamp": datetime.utcnow().isoformat()
                }

                # Cache the result
                self.cache.set(cache_key, result_data)

                return result_data

        except SQLAlchemyError as e:
            logger.error(f"SQL execution failed: {e}")
            raise Exception(f"Query execution failed: {str(e)}")

    def get_query_history(self) -> List[Dict]:
        """Get recent query history (deprecated - use history_service instead)"""
        return []