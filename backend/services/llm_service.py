import openai
import os
import logging
from typing import Dict, Any, Optional
import re

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if self.api_key:
            openai.api_key = self.api_key
        else:
            logger.warning("OPENAI_API_KEY not set. LLM queries will fail.")

    def generate_sql(self, natural_query: str, schema: Dict[str, Any], dialect: str = "sqlite") -> str:
        """
        Generate SQL from natural language query using OpenAI

        Args:
            natural_query: The natural language query
            schema: Database schema information
            dialect: SQL dialect (sqlite, postgresql, mysql, etc.)

        Returns:
            Generated SQL string
        """
        if not self.api_key:
            raise Exception("OpenAI API key not configured. Set OPENAI_API_KEY environment variable.")

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
- Make the query as efficient as possible
- If the query involves aggregation, use appropriate GROUP BY
- Return only the SQL query, no explanations

SQL Query:
"""

        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a SQL expert that generates safe SELECT queries."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.1  # Low temperature for consistent SQL generation
            )

            sql = response.choices[0].message.content.strip()

            # Clean up the response (remove markdown code blocks if present)
            sql = re.sub(r'```sql\s*', '', sql)
            sql = re.sub(r'```\s*$', '', sql)
            sql = sql.strip()

            # Safety check: ensure it's a SELECT query
            if not sql.upper().startswith("SELECT"):
                raise Exception("Generated query is not a SELECT statement")

            # Add LIMIT if not present
            if "LIMIT" not in sql.upper():
                sql += " LIMIT 100"

            return sql

        except Exception as e:
            logger.error(f"LLM SQL generation failed: {e}")
            raise Exception(f"Failed to generate SQL: {str(e)}")

    def _build_schema_description(self, schema: Dict[str, Any]) -> str:
        """Build a text description of the database schema"""
        description = ""

        if "tables" in schema:
            for table_name, table_info in schema["tables"].items():
                description += f"\nTable: {table_name}\n"
                if "columns" in table_info:
                    for col in table_info["columns"]:
                        description += f"  - {col['name']} ({col['type']})\n"

        if "relationships" in schema and schema["relationships"]:
            description += "\nRelationships:\n"
            for rel in schema["relationships"]:
                if rel.get("type") == "explicit_foreign_key":
                    description += f"  - {rel['from_table']}.{rel['from_column']} -> {rel['to_table']}.{rel['to_column']}\n"

        return description