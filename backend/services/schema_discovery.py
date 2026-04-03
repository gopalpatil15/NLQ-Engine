from sqlalchemy import create_engine, MetaData, inspect, text
from sqlalchemy.exc import SQLAlchemyError
import logging
from typing import Dict, List, Any
import re
from fastapi import HTTPException

logger = logging.getLogger(__name__)

class SchemaDiscovery:
    def __init__(self):
        self.engine = None
        self.inspector = None
        self.schema_cache = {}
        
        # Common naming patterns for employee databases
        self.table_patterns = {
            'employee': ['employee', 'employees', 'emp', 'staff', 'personnel', 'worker', 'workers'],
            'department': ['department', 'departments', 'dept', 'division', 'team', 'group'],
            'salary': ['salary', 'salaries', 'compensation', 'pay', 'wage', 'income'],
            'manager': ['manager', 'managers', 'supervisor', 'lead', 'head'],
            'hire_date': ['hire_date', 'start_date', 'joining_date', 'employed_since', 'hired_on']
        }
    
    def analyze_database(self, connection_string: str) -> Dict[str, Any]:
        """Connect to database and automatically discover schema"""
        try:
            self.engine = create_engine(connection_string)
            self.inspector = inspect(self.engine)
            metadata = MetaData()
            metadata.reflect(bind=self.engine)
            
            schema_info = {
                "tables": {},
                "relationships": [],
                "sample_data": {},
                "table_purposes": {}
            }
            
            # Discover tables and columns
            for table_name in self.inspector.get_table_names():
                columns = self.inspector.get_columns(table_name)
                primary_keys = self.inspector.get_pk_constraint(table_name)
                foreign_keys = self.inspector.get_foreign_keys(table_name)
                
                schema_info["tables"][table_name] = {
                    "columns": [
                        {
                            "name": col["name"],
                            "type": str(col["type"]),
                            "nullable": col["nullable"],
                            "default": col.get("default")
                        } for col in columns
                    ],
                    "primary_key": primary_keys.get("constrained_columns", []),
                    "foreign_keys": foreign_keys
                }
                
                # Infer table purpose based on column names and patterns
                schema_info["table_purposes"][table_name] = self._infer_table_purpose(table_name, columns)
                
                # Get sample data (limited to 3 rows for context)
                try:
                    with self.engine.connect() as conn:
                        result = conn.execute(text(f"SELECT * FROM {table_name} LIMIT 3"))
                        sample_rows = [dict(row._mapping) for row in result]
                        schema_info["sample_data"][table_name] = sample_rows
                except Exception as e:
                    logger.warning(f"Could not fetch sample data for {table_name}: {e}")
                    schema_info["sample_data"][table_name] = []
            
            # Extract relationships
            schema_info["relationships"] = self._discover_relationships(schema_info["tables"])
            
            # Cache the schema
            self.schema_cache[connection_string] = schema_info
            
            return schema_info
            
        except SQLAlchemyError as e:
            logger.error(f"Database connection failed: {e}")
            raise HTTPException(status_code=400, detail=f"Database connection failed: {str(e)}")
    
    def _infer_table_purpose(self, table_name: str, columns: List[Dict]) -> str:
        """Infer the purpose of a table based on its name and columns"""
        table_name_lower = table_name.lower()
        column_names = [col["name"].lower() for col in columns]
        
        # Check table name patterns
        for purpose, patterns in self.table_patterns.items():
            if any(pattern in table_name_lower for pattern in patterns):
                return purpose
        
        # Check column patterns for inference
        if any(name in ['emp_id', 'employee_id', 'staff_id'] for name in column_names):
            return 'employee'
        elif any(name in ['dept_id', 'department_id', 'division_id'] for name in column_names):
            return 'department'
        elif any(name in ['salary', 'compensation', 'pay_rate'] for name in column_names):
            return 'salary'
        
        return 'unknown'
    
    def _discover_relationships(self, tables: Dict) -> List[Dict]:
        """Discover relationships between tables"""
        relationships = []
        
        for table_name, table_info in tables.items():
            for fk in table_info["foreign_keys"]:
                relationships.append({
                    "from_table": table_name,
                    "from_column": fk["constrained_columns"],
                    "to_table": fk["referred_table"],
                    "to_column": fk["referred_columns"],
                    "type": "explicit_foreign_key"
                })
        
        # Try to discover implicit relationships based on naming patterns
        for table_name, table_info in tables.items():
            for column in table_info["columns"]:
                col_name = column["name"].lower()
                # Look for ID columns that might reference other tables
                if col_name.endswith('_id') and col_name != 'id':
                    potential_target = col_name[:-3]  # Remove '_id'
                    for other_table in tables.keys():
                        if potential_target in other_table.lower():
                            relationships.append({
                                "from_table": table_name,
                                "from_column": [column["name"]],
                                "to_table": other_table,
                                "to_column": ["id"],  # Assume primary key is 'id'
                                "type": "implicit_relationship"
                            })
        
        return relationships
    
    def map_natural_language_to_schema(self, query: str, schema: Dict) -> Dict[str, Any]:
        """Map user's natural language to actual database structure"""
        query_lower = query.lower()
        mapping = {
            "table_mappings": {},
            "column_mappings": {},
            "detected_entities": []
        }
        
        # Map table names
        for table_name, table_info in schema["tables"].items():
            table_purpose = schema["table_purposes"].get(table_name, "unknown")
            
            for purpose, patterns in self.table_patterns.items():
                if table_purpose == purpose:
                    for pattern in patterns:
                        if pattern in query_lower:
                            mapping["table_mappings"][pattern] = table_name
                            mapping["detected_entities"].append({
                                "type": "table",
                                "natural_language": pattern,
                                "database_object": table_name,
                                "confidence": 0.9
                            })
        
        # Map column names
        for table_name, table_info in schema["tables"].items():
            for column in table_info["columns"]:
                col_name = column["name"].lower()
                
                # Simple string matching for common patterns
                if any(term in query_lower for term in ['name', 'full name', 'employee name']):
                    if any(pattern in col_name for pattern in ['name', 'full_name', 'employee_name']):
                        mapping["column_mappings"][col_name] = column["name"]
                
                if any(term in query_lower for term in ['salary', 'pay', 'compensation']):
                    if any(pattern in col_name for pattern in ['salary', 'compensation', 'pay']):
                        mapping["column_mappings"][col_name] = column["name"]
                
                if any(term in query_lower for term in ['department', 'dept', 'division']):
                    if any(pattern in col_name for pattern in ['department', 'dept', 'division']):
                        mapping["column_mappings"][col_name] = column["name"]
        
        return mapping