from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

import pandas as pd

from . import db
from .normalization import clean_dataframe, safe_json_value


def _json_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    cleaned = clean_dataframe(df)
    return [
        {str(key): safe_json_value(value) for key, value in row.items()}
        for row in cleaned.to_dict(orient="records")
    ]


def dataframe_to_version_payload(df: pd.DataFrame) -> tuple[list[str], list[dict[str, Any]]]:
    cleaned = clean_dataframe(df)
    return [str(col) for col in cleaned.columns], _json_records(cleaned)


def active_dataset(kind: str) -> tuple[pd.DataFrame, list[dict[str, Any]], list[str]]:
    with db.connection(row_factory=db.dict_row_factory()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select dv.*, uf.original_filename, uf.size_bytes, uf.blob_pathname, uf.blob_url
                from dataset_active_versions av
                join dataset_versions dv on dv.id = av.dataset_version_id
                left join uploaded_files uf on uf.id = dv.source_file_id
                where av.kind = %s and dv.status = 'active'
                """,
                (kind,),
            )
            row = cur.fetchone()
    if not row:
        return pd.DataFrame(), [], []

    rows = row.get("rows_json") or []
    df = clean_dataframe(pd.DataFrame(rows))
    columns = row.get("columns_json") or list(df.columns)
    if columns and not df.empty:
        ordered = [col for col in columns if col in df.columns]
        df = df[ordered + [col for col in df.columns if col not in ordered]]
    file_info = {
        "kind": kind,
        "name": row.get("version_label") or row.get("original_filename") or kind,
        "path": row.get("blob_pathname") or "",
        "source": "supabase",
        "size": row.get("size_bytes") or 0,
        "modified": row["created_at"].timestamp() if hasattr(row.get("created_at"), "timestamp") else None,
        "sheets": [kind],
        "activeSheet": kind,
        "rows": int(row.get("row_count") or len(df)),
        "columns": list(df.columns),
        "error": None,
        "format": "postgres_jsonb",
        "blobUrl": row.get("blob_url") or "",
        "versionId": row.get("id"),
    }
    return df, [file_info], []


def datasets_status(kinds: list[str]) -> dict[str, Any]:
    status: dict[str, Any] = {kind: [] for kind in kinds}
    with db.connection(row_factory=db.dict_row_factory()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select av.kind, dv.*, uf.original_filename, uf.size_bytes, uf.blob_pathname, uf.blob_url
                from dataset_active_versions av
                join dataset_versions dv on dv.id = av.dataset_version_id
                left join uploaded_files uf on uf.id = dv.source_file_id
                where av.kind = any(%s)
                order by av.kind
                """,
                (kinds,),
            )
            rows = cur.fetchall()
    for row in rows:
        status[row["kind"]] = [{
            "kind": row["kind"],
            "name": row.get("version_label") or row.get("original_filename") or row["kind"],
            "path": row.get("blob_pathname") or "",
            "source": "supabase",
            "size": row.get("size_bytes") or 0,
            "modified": row["created_at"].timestamp() if hasattr(row.get("created_at"), "timestamp") else None,
            "sheets": [row["kind"]],
            "activeSheet": row["kind"],
            "rows": int(row.get("row_count") or 0),
            "columns": row.get("columns_json") or [],
            "error": None,
            "format": "postgres_jsonb",
            "blobUrl": row.get("blob_url") or "",
            "versionId": row.get("id"),
        }]
    return status


def register_uploaded_file(
    *,
    purpose: str,
    dataset_kind: str | None,
    original_filename: str,
    content_type: str,
    size_bytes: int,
    blob_info: dict[str, Any],
    created_by: str = "admin_env",
) -> str:
    file_id = uuid4().hex
    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into uploaded_files (
                    id, purpose, dataset_kind, original_filename, content_type, size_bytes,
                    blob_pathname, blob_url, blob_download_url, etag, created_by
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    file_id,
                    purpose,
                    dataset_kind,
                    original_filename,
                    content_type,
                    size_bytes,
                    blob_info.get("pathname"),
                    blob_info.get("url"),
                    blob_info.get("downloadUrl") or blob_info.get("download_url"),
                    blob_info.get("etag"),
                    created_by,
                ),
            )
    return file_id


def create_dataset_version(
    *,
    kind: str,
    df: pd.DataFrame,
    source_file_id: str | None,
    sqlite_file_id: str | None = None,
    version_label: str | None = None,
    metadata: dict[str, Any] | None = None,
    created_by: str = "admin_env",
) -> str:
    version_id = uuid4().hex
    columns, rows = dataframe_to_version_payload(df)
    now_label = version_label or f"{kind}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("update dataset_versions set status = 'replaced' where kind = %s and status = 'active'", (kind,))
            cur.execute(
                """
                insert into dataset_versions (
                    id, kind, version_label, source_file_id, sqlite_file_id, row_count,
                    columns_json, rows_json, metadata_json, status, created_by
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'active', %s)
                """,
                (
                    version_id,
                    kind,
                    now_label,
                    source_file_id,
                    sqlite_file_id,
                    int(len(df)),
                    db.jsonb(columns),
                    db.jsonb(rows),
                    db.jsonb(metadata or {}),
                    created_by,
                ),
            )
            cur.execute(
                """
                insert into dataset_active_versions (kind, dataset_version_id, updated_by)
                values (%s, %s, %s)
                on conflict (kind)
                do update set dataset_version_id = excluded.dataset_version_id,
                              updated_at = now(),
                              updated_by = excluded.updated_by
                """,
                (kind, version_id, created_by),
            )
    return version_id


def audit(action: str, entity_type: str, entity_id: str | None, details: dict[str, Any], ip_address: str | None = None) -> None:
    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into admin_audit_logs (action, entity_type, entity_id, details_json, created_by, ip_address)
                values (%s, %s, %s, %s, %s, %s)
                """,
                (action, entity_type, entity_id, db.jsonb(details), "admin_env", ip_address),
            )


def delete_active_dataset(kind: str, ip_address: str | None = None) -> dict[str, Any]:
    with db.connection(row_factory=db.dict_row_factory()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "select dataset_version_id from dataset_active_versions where kind = %s",
                (kind,),
            )
            row = cur.fetchone()
            if not row:
                raise FileNotFoundError("Base ativa nao encontrada.")
            version_id = row["dataset_version_id"]
            cur.execute("update dataset_versions set status = 'deleted' where id = %s", (version_id,))
            cur.execute("delete from dataset_active_versions where kind = %s", (kind,))
            cur.execute(
                """
                insert into admin_audit_logs (action, entity_type, entity_id, details_json, created_by, ip_address)
                values (%s, %s, %s, %s, %s, %s)
                """,
                ("dataset.delete_active", "dataset_version", version_id, db.jsonb({"kind": kind}), "admin_env", ip_address),
            )
    return {"ok": True, "deleted": kind, "versionId": version_id}
