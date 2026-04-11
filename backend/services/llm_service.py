import os
import logging
import re
from typing import Dict, Any
from openai import OpenAI  # New Import
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if self.api_key:
            # Initialize the client once during setup
            self.client = OpenAI(api_key=self.api_key)
        else:
            self.client = None
            logger.warning("OPENAI_API_KEY not set. LLM queries will fail.")

    def generate_sql(self, natural_query: str, schema: Dict[str, Any], dialect: str = "sqlite") -> str:
        if not self.client:
            raise Exception("OpenAI API key not configured. Set OPENAI_API_KEY in .env")

        # Build schema description
        schema_description = self._build_schema_description(schema)

        # Create prompt
        prompt = f"""
You are an expert SQL query generator. Given a database schema and a natural language question,
generate a valid SQL SELECT query that answers the question.

Database Schema:
{schema_description}

SQL Dialect: {dialect}

Natural Language Query: {natural_query}

Instructions:
- Generate ONLY a SELECT query (no INSERT, UPDATE, DELETE, DROP, etc.)
- Use proper table and column names from the schema
- Use appropriate JOINs if needed
- Include LIMIT 100 to prevent large result sets
- Return only the SQL query, no markdown, no explanations

SQL Query:
"""

        try:
            # Use the initialized client with the actual dynamic prompt
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that generates SQL."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0  # Keep it deterministic for SQL
            )

            sql = response.choices[0].message.content.strip()

            # Clean up response (remove markdown blocks)
            sql = re.sub(r'```sql\s*', '', sql, flags=re.IGNORECASE)
            sql = re.sub(r'```', '', sql)
            sql = sql.strip()

            # Safety check
            if not sql.upper().startswith("SELECT"):
                raise Exception(f"Generated query is not a SELECT statement: {sql}")

            if "LIMIT" not in sql.upper() and dialect == "sqlite":
                sql += " LIMIT 100"

            return sql

        except Exception as e:
            logger.error(f"LLM SQL generation failed: {e}")
            raise Exception(f"Failed to generate SQL: {str(e)}")

    def _build_schema_description(self, schema: Dict[str, Any]) -> str:
        description = ""
        if "tables" in schema:
            for table_name, table_info in schema["tables"].items():
                cols = [f"{c['name']} ({c['type']})" for c in table_info.get("columns", [])]
                description += f"Table {table_name}: {', '.join(cols)}\n"

        if "relationships" in schema and schema["relationships"]:
            description += "\nRelationships:\n"
            for rel in schema["relationships"]:
                if rel.get("type") == "explicit_foreign_key":
                    description += f"- {rel['from_table']} links to {rel['to_table']} on {rel['from_column']}\n"
        return description