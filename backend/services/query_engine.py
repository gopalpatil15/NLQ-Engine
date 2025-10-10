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
        self.query_history = []
        
        if connection_string:
            self.engine = create_engine(connection_string)
    
    def set_connection(self, connection_string: str):
        """Set database connection after initialization"""
        self.connection_string = connection_string
        self.engine = create_engine(connection_string)
    
    def process_query(self, user_query: str, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Process natural language query"""
        start_time = time.time()
        
        # Generate cache key
        cache_key = self._generate_cache_key(user_query, schema)
        
        # Check cache
        cached_result = self.cache.get(cache_key)
        if cached_result:
            cached_result["cache_hit"] = True
            cached_result["response_time"] = time.time() - start_time
            return cached_result
        
        try:
            # Classify query type
            query_type = self._classify_query(user_query)
            
            # Process based on type
            if query_type == "sql":
                result = self._process_sql_query(user_query, schema)
            elif query_type == "document":
                result = self._process_document_query(user_query)
            else:  # hybrid
                result = self._process_hybrid_query(user_query, schema)
            
            # Add metadata
            result["query_type"] = query_type
            result["cache_hit"] = False
            result["response_time"] = time.time() - start_time
            result["timestamp"] = datetime.utcnow().isoformat()
            
            # Cache the result
            self.cache.set(cache_key, result)
            
            # Add to history
            self.query_history.append({
                "query": user_query,
                "type": query_type,
                "timestamp": result["timestamp"],
                "response_time": result["response_time"]
            })
            
            return result
            
        except Exception as e:
            logger.error(f"Query processing failed: {e}")
            return {
                "error": str(e),
                "query_type": "error",
                "cache_hit": False,
                "response_time": time.time() - start_time,
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def _generate_cache_key(self, query: str, schema: Dict) -> str:
        """Generate unique cache key for query and schema"""
        key_data = query + json.dumps(schema, sort_keys=True)
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _classify_query(self, query: str) -> str:
        """Classify query as SQL, document, or hybrid"""
        query_lower = query.lower()
        
        document_keywords = ['resume', 'cv', 'document', 'file', 'pdf', 'docx', 'skill', 'experience']
        sql_keywords = ['count', 'average', 'sum', 'max', 'min', 'department', 'salary', 'hire']
        
        has_document_terms = any(term in query_lower for term in document_keywords)
        has_sql_terms = any(term in query_lower for term in sql_keywords)
        
        if has_document_terms and has_sql_terms:
            return "hybrid"
        elif has_document_terms:
            return "document"
        else:
            return "sql"
    
    def _process_sql_query(self, query: str, schema: Dict) -> Dict[str, Any]:
        """Process SQL-oriented natural language query"""
        # Simple rule-based NL to SQL conversion
        sql = self._natural_language_to_sql(query, schema)
        
        if not self.engine:
            raise Exception("Database connection not established")
        
        try:
            with self.engine.connect() as conn:
                # Execute with safety limits
                if "LIMIT" not in sql.upper():
                    sql += " LIMIT 100"
                
                result = conn.execute(text(sql))
                rows = [dict(row._mapping) for row in result]
                
                return {
                    "results": rows,
                    "sql_generated": sql,
                    "result_count": len(rows),
                    "sources": ["database"]
                }
                
        except SQLAlchemyError as e:
            logger.error(f"SQL execution failed: {e}")
            raise Exception(f"Query execution failed: {str(e)}")
    
    def _natural_language_to_sql(self, query: str, schema: Dict) -> str:
        """Convert natural language to SQL (simplified version)"""
        query_lower = query.lower()
        
        # Basic pattern matching for common queries
        if "how many" in query_lower and "employee" in query_lower:
            employee_table = self._find_employee_table(schema)
            return f"SELECT COUNT(*) as count FROM {employee_table}"
        
        elif "average salary" in query_lower:
            employee_table = self._find_employee_table(schema)
            salary_column = self._find_salary_column(schema, employee_table)
            return f"SELECT AVG({salary_column}) as average_salary FROM {employee_table}"
        
        elif "list" in query_lower and "employee" in query_lower:
            employee_table = self._find_employee_table(schema)
            return f"SELECT * FROM {employee_table}"
        
        elif "department" in query_lower and "employee" in query_lower:
            employee_table = self._find_employee_table(schema)
            dept_column = self._find_department_column(schema, employee_table)
            return f"SELECT {dept_column}, COUNT(*) as count FROM {employee_table} GROUP BY {dept_column}"
        
        else:
            # Fallback - return limited query from first employee-like table
            employee_table = self._find_employee_table(schema)
            return f"SELECT * FROM {employee_table} LIMIT 10"
    
    def _find_employee_table(self, schema: Dict) -> str:
        """Find the most likely employee table"""
        for table_name, purpose in schema.get("table_purposes", {}).items():
            if purpose == "employee":
                return table_name
        
        # Fallback to first table
        return list(schema.get("tables", {}).keys())[0]
    
    def _find_salary_column(self, schema: Dict, table_name: str) -> str:
        """Find salary column in table"""
        columns = schema["tables"][table_name]["columns"]
        for col in columns:
            if any(term in col["name"].lower() for term in ['salary', 'compensation', 'pay']):
                return col["name"]
        return columns[0]["name"]  # Fallback
    
    def _find_department_column(self, schema: Dict, table_name: str) -> str:
        """Find department column in table"""
        columns = schema["tables"][table_name]["columns"]
        for col in columns:
            if any(term in col["name"].lower() for term in ['department', 'dept', 'division']):
                return col["name"]
        return columns[0]["name"]  # Fallback
    
    def _process_document_query(self, query: str) -> Dict[str, Any]:
        """Process document-oriented query (placeholder)"""
        return {
            "results": [
                {"document": "resume_1.pdf", "content": "Python developer with 5 years experience...", "relevance": 0.85},
                {"document": "resume_2.pdf", "content": "Senior engineer with ML background...", "relevance": 0.72}
            ],
            "result_count": 2,
            "sources": ["documents"]
        }
    
    def _process_hybrid_query(self, query: str, schema: Dict) -> Dict[str, Any]:
        """Process hybrid query (both SQL and document)"""
        sql_result = self._process_sql_query(query, schema)
        doc_result = self._process_document_query(query)
        
        return {
            "sql_results": sql_result.get("results", []),
            "document_results": doc_result.get("results", []),
            "sql_count": sql_result.get("result_count", 0),
            "document_count": doc_result.get("result_count", 0),
            "sources": ["database", "documents"]
        }
    
    def optimize_sql_query(self, sql: str) -> str:
        """Optimize generated SQL query"""
        # Simple optimizations
        optimized = sql
        
        # Ensure LIMIT is present for large queries
        if "COUNT(" not in sql.upper() and "LIMIT" not in sql.upper():
            optimized += " LIMIT 100"
        
        return optimized
    
    def get_query_history(self) -> List[Dict]:
        """Get recent query history"""
        return self.query_history[-10:]  # Last 10 queries