"""Thin Postgres client wrapping psycopg with connection pooling.

Used by:
  * retrieval-mcp (ioc_lookup tool)
  * api/ (feedback + agent_runs persistence)
"""
from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

log = logging.getLogger(__name__)


class PGClient:
    def __init__(self, dsn: str, *, min_size: int = 1, max_size: int = 10):
        self.pool = ConnectionPool(
            conninfo=dsn,
            min_size=min_size,
            max_size=max_size,
            kwargs={"row_factory": dict_row},
            open=True,
        )

    @contextmanager
    def conn(self):
        with self.pool.connection() as c:
            yield c

    # ------------------------------------------------------------------
    # IOC lookup
    # ------------------------------------------------------------------
    def lookup_ioc(self, value: str, ioc_type: Optional[str] = None) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM iocs WHERE ioc_value = %s"
        params: List[Any] = [value]
        if ioc_type:
            sql += " AND ioc_type = %s"
            params.append(ioc_type)
        sql += " LIMIT 25"
        with self.conn() as c:
            with c.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchall()

    def search_iocs_by_tag(self, tag: str, *, limit: int = 50) -> List[Dict[str, Any]]:
        with self.conn() as c:
            with c.cursor() as cur:
                cur.execute(
                    "SELECT * FROM iocs WHERE %s = ANY(tags) ORDER BY first_seen DESC LIMIT %s",
                    [tag, limit],
                )
                return cur.fetchall()

    def insert_ioc(self, **fields) -> str:
        cols = ", ".join(fields.keys())
        placeholders = ", ".join(["%s"] * len(fields))
        sql = (
            f"INSERT INTO iocs ({cols}) VALUES ({placeholders}) "
            "ON CONFLICT (ioc_value, ioc_type) DO UPDATE "
            "SET last_seen = NOW(), confidence = EXCLUDED.confidence "
            "RETURNING id"
        )
        with self.conn() as c:
            with c.cursor() as cur:
                cur.execute(sql, list(fields.values()))
                return str(cur.fetchone()["id"])

    # ------------------------------------------------------------------
    # Agent runs
    # ------------------------------------------------------------------
    def create_run(self, user_query: str, selected_tools: List[str]) -> str:
        with self.conn() as c:
            with c.cursor() as cur:
                cur.execute(
                    "INSERT INTO agent_runs (user_query, selected_tools) "
                    "VALUES (%s, %s) RETURNING id",
                    [user_query, selected_tools],
                )
                return str(cur.fetchone()["id"])

    def append_step(self, run_id: str, step: Dict[str, Any]):
        with self.conn() as c:
            with c.cursor() as cur:
                cur.execute(
                    "UPDATE agent_runs SET steps = steps || %s::jsonb WHERE id = %s",
                    [json.dumps([step]), run_id],
                )

    def complete_run(self, run_id: str, final_answer: str, duration_ms: int, status: str = "completed"):
        with self.conn() as c:
            with c.cursor() as cur:
                cur.execute(
                    "UPDATE agent_runs SET final_answer = %s, completed_at = NOW(), "
                    "duration_ms = %s, status = %s WHERE id = %s",
                    [final_answer, duration_ms, status, run_id],
                )

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        with self.conn() as c:
            with c.cursor() as cur:
                cur.execute("SELECT * FROM agent_runs WHERE id = %s", [run_id])
                return cur.fetchone()

    # ------------------------------------------------------------------
    # Feedback
    # ------------------------------------------------------------------
    def record_feedback(self, run_id: str, rating: int, comment: str = "", user_email: str = "") -> str:
        with self.conn() as c:
            with c.cursor() as cur:
                cur.execute(
                    "INSERT INTO feedback (run_id, rating, comment, user_email) "
                    "VALUES (%s, %s, %s, %s) RETURNING id",
                    [run_id, rating, comment, user_email],
                )
                return str(cur.fetchone()["id"])

    def feedback_stats(self) -> Dict[str, int]:
        with self.conn() as c:
            with c.cursor() as cur:
                cur.execute(
                    "SELECT "
                    "  SUM(CASE WHEN rating = 1 THEN 1 ELSE 0 END) AS thumbs_up, "
                    "  SUM(CASE WHEN rating = -1 THEN 1 ELSE 0 END) AS thumbs_down, "
                    "  COUNT(*) AS total "
                    "FROM feedback"
                )
                row = cur.fetchone() or {}
                return {
                    "thumbs_up": int(row.get("thumbs_up") or 0),
                    "thumbs_down": int(row.get("thumbs_down") or 0),
                    "total": int(row.get("total") or 0),
                }
