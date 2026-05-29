from __future__ import annotations

from datetime import datetime
from typing import Any

from . import db


def _row_to_record(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None
    payload = row.get("payload_json") or {}
    if not isinstance(payload, dict):
        payload = {}
    record = dict(payload)
    record.setdefault("id", row.get("id"))
    record["archived"] = bool(row.get("archived"))
    if row.get("deleted_at"):
        record["deletedAt"] = row["deleted_at"].isoformat() if hasattr(row["deleted_at"], "isoformat") else row["deleted_at"]
    return record


def load_analysis(analysis_id: str) -> dict[str, Any] | None:
    with db.connection(row_factory=db.dict_row_factory()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "select * from analyses where id = %s and deleted_at is null",
                (analysis_id,),
            )
            return _row_to_record(cur.fetchone())


def list_analysis_records(archived: bool | None = None) -> list[dict[str, Any]]:
    where = "deleted_at is null"
    params: list[Any] = []
    if archived is not None:
        where += " and archived = %s"
        params.append(archived)
    with db.connection(row_factory=db.dict_row_factory()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"select * from analyses where {where} order by created_at desc",
                params,
            )
            return [record for row in cur.fetchall() if (record := _row_to_record(row))]


def save_analysis(record: dict[str, Any]) -> dict[str, Any]:
    cep = record.get("cep") or {}
    location = record.get("location") or {}
    summary = record.get("summary") or {}
    rows = record.get("rows") or []
    executive = record.get("executive") or {}
    best_cost = executive.get("bestCostCarrier") or {}
    main_carrier = summary.get("mainCarrier") or next(
        (row.get("key") or row.get("label") for row in rows if row.get("role") == "main"),
        "",
    )

    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into analyses (
                    id, parent_id, version, analysis_name, analysis_date, responsible,
                    archived, created_at, updated_at, cep, city, uf, main_carrier,
                    best_cost_carrier, payload_json
                )
                values (
                    %(id)s, %(parent_id)s, %(version)s, %(analysis_name)s,
                    %(analysis_date)s, %(responsible)s, %(archived)s,
                    %(created_at)s, %(updated_at)s, %(cep)s, %(city)s, %(uf)s,
                    %(main_carrier)s, %(best_cost_carrier)s, %(payload_json)s
                )
                """,
                {
                    "id": record.get("id"),
                    "parent_id": record.get("parentId"),
                    "version": int(record.get("version") or 1),
                    "analysis_name": record.get("analysisName") or record.get("title") or "Analise sem titulo",
                    "analysis_date": record.get("analysisDate"),
                    "responsible": record.get("responsible") or "",
                    "archived": bool(record.get("archived")),
                    "created_at": record.get("createdAt"),
                    "updated_at": record.get("updatedAt"),
                    "cep": cep.get("cep"),
                    "city": location.get("municipio") or cep.get("city"),
                    "uf": location.get("uf") or cep.get("uf"),
                    "main_carrier": main_carrier,
                    "best_cost_carrier": best_cost.get("label") or best_cost.get("key") or "",
                    "payload_json": db.jsonb(record),
                },
            )
    return record


def update_archived(analysis_id: str, archived: bool, updated_at: str) -> dict[str, Any]:
    current = load_analysis(analysis_id)
    if not current:
        raise FileNotFoundError("Analise nao encontrada.")
    current["archived"] = archived
    current["updatedAt"] = updated_at
    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                update analyses
                set archived = %s, updated_at = %s, payload_json = %s
                where id = %s and deleted_at is null
                """,
                (archived, updated_at, db.jsonb(current), analysis_id),
            )
            if cur.rowcount == 0:
                raise FileNotFoundError("Analise nao encontrada.")
    return current


def soft_delete(analysis_id: str) -> dict[str, Any]:
    now = datetime.now().isoformat(timespec="seconds")
    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "update analyses set deleted_at = %s, updated_at = %s where id = %s and deleted_at is null",
                (now, now, analysis_id),
            )
            if cur.rowcount == 0:
                raise FileNotFoundError("Analise nao encontrada.")
    return {"id": analysis_id, "deleted": True}
