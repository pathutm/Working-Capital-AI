import psycopg2
from psycopg2.extras import RealDictCursor
from app.core.config import settings
from typing import List, Dict, Any

class DBService:
    def __init__(self):
        self.db_url = settings.DATABASE_URL
        self._conn = None

    def execute_query(self, sql: str, params: Any = None) -> List[Dict[str, Any]]:
        """
        Execute a read-only SQL query and return results as a list of dictionaries.
        """
        conn = psycopg2.connect(self.db_url, cursor_factory=RealDictCursor)
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                if cursor.description:
                    return cursor.fetchall()
                return []
        except Exception as e:
            conn.rollback()
            print(f"Database Query Error: {e}")
            raise e
        finally:
            conn.close()

    def get_table_sample(self, table_name: str, limit: int = 3) -> List[Dict[str, Any]]:
        """
        Fetch a few rows from a table to help the LLM understand the data format.
        """
        # Safety check: table_name should be from our allowlist/metadata
        sql = f'SELECT * FROM "{table_name}" LIMIT %s'
        return self.execute_query(sql, (limit,))

db_service = DBService()
