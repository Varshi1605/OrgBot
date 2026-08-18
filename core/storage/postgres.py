from __future__ import annotations

import json
from datetime import datetime, timezone


class PostgresStore:
    def __init__(self, dsn: str):
        self.dsn = dsn

    def _connect(self):
        import psycopg2

        return psycopg2.connect(self.dsn)

    def init_schema(self) -> None:
        statements = [
            "CREATE TABLE IF NOT EXISTS cursors ("
            " source TEXT PRIMARY KEY,"
            " cursor_value TEXT NOT NULL,"
            " updated_at TIMESTAMPTZ NOT NULL DEFAULT now())",
            "CREATE TABLE IF NOT EXISTS feedback ("
            " id SERIAL PRIMARY KEY,"
            " query TEXT NOT NULL,"
            " original_answer TEXT,"
            " sme_answer TEXT,"
            " feedback_type TEXT NOT NULL,"
            " sme_id TEXT NOT NULL,"
            " created_at TIMESTAMPTZ NOT NULL DEFAULT now())",
            "CREATE TABLE IF NOT EXISTS feedback_boosts ("
            " query_key TEXT PRIMARY KEY,"
            " boost_factor DOUBLE PRECISION NOT NULL,"
            " approved_sources TEXT NOT NULL DEFAULT '[]',"
            " created_at TIMESTAMPTZ NOT NULL DEFAULT now())",
        ]
        with self._connect() as conn:
            with conn.cursor() as cursor:
                for statement in statements:
                    cursor.execute(statement)
            conn.commit()

    def get_cursor(self, source: str) -> str | None:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT cursor_value FROM cursors WHERE source = %s", (source,))
                row = cursor.fetchone()
        return row[0] if row else None

    def set_cursor(self, source: str, cursor_value: str) -> None:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO cursors (source, cursor_value, updated_at) "
                    "VALUES (%s, %s, now()) "
                    "ON CONFLICT (source) DO UPDATE SET cursor_value = EXCLUDED.cursor_value, "
                    "updated_at = now()",
                    (source, cursor_value),
                )
            conn.commit()

    def add_feedback(
        self,
        query: str,
        original_answer: str,
        sme_answer: str,
        feedback_type: str,
        sme_id: str,
    ) -> dict:
        created_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO feedback (query, original_answer, sme_answer, feedback_type, sme_id) "
                    "VALUES (%s, %s, %s, %s, %s) RETURNING id, created_at",
                    (query, original_answer, sme_answer, feedback_type, sme_id),
                )
                row = cursor.fetchone()
            conn.commit()
        return {
            "id": row[0],
            "query": query,
            "original_answer": original_answer,
            "sme_answer": sme_answer,
            "feedback_type": feedback_type,
            "sme_id": sme_id,
            "created_at": created_at,
        }

    def list_feedback(self, limit: int = 100) -> list[dict]:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT id, query, original_answer, sme_answer, feedback_type, sme_id, created_at "
                    "FROM feedback ORDER BY id DESC LIMIT %s",
                    (limit,),
                )
                rows = cursor.fetchall()
        return [
            {
                "id": r[0],
                "query": r[1],
                "original_answer": r[2],
                "sme_answer": r[3],
                "feedback_type": r[4],
                "sme_id": r[5],
                "created_at": r[6].isoformat() if r[6] else None,
            }
            for r in rows
        ]

    def add_boost(
        self,
        query_key: str,
        boost_factor: float,
        approved_sources: list[str] | None = None,
    ) -> dict:
        sources_json = json.dumps(approved_sources or [])
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO feedback_boosts (query_key, boost_factor, approved_sources, created_at) "
                    "VALUES (%s, %s, %s, now()) "
                    "ON CONFLICT (query_key) DO UPDATE SET "
                    "boost_factor = EXCLUDED.boost_factor, "
                    "approved_sources = EXCLUDED.approved_sources, "
                    "created_at = now() "
                    "RETURNING query_key, boost_factor, approved_sources, created_at",
                    (query_key, float(boost_factor), sources_json),
                )
                row = cursor.fetchone()
            conn.commit()
        return {
            "query_key": row[0],
            "boost_factor": row[1],
            "approved_sources": json.loads(row[2] or "[]"),
            "created_at": row[3].isoformat() if row[3] else None,
        }

    def get_boost_for_query(self, query_key: str) -> dict | None:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT query_key, boost_factor, approved_sources, created_at "
                    "FROM feedback_boosts WHERE query_key = %s",
                    (query_key,),
                )
                row = cursor.fetchone()
        if row is None:
            return None
        return {
            "query_key": row[0],
            "boost_factor": row[1],
            "approved_sources": json.loads(row[2] or "[]"),
            "created_at": row[3].isoformat() if row[3] else None,
        }

    def list_boosts(self, limit: int = 100) -> list[dict]:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT query_key, boost_factor, approved_sources, created_at "
                    "FROM feedback_boosts ORDER BY created_at DESC LIMIT %s",
                    (limit,),
                )
                rows = cursor.fetchall()
        return [
            {
                "query_key": r[0],
                "boost_factor": r[1],
                "approved_sources": json.loads(r[2] or "[]"),
                "created_at": r[3].isoformat() if r[3] else None,
            }
            for r in rows
        ]

    def is_healthy(self) -> bool:
        try:
            with self._connect() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    cursor.fetchone()
            return True
        except Exception:
            return False
