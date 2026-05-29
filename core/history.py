from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from . import db
from . import history_repository
from .settings import ANALISES_DIR
from .insights import build_executive_summary


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _format_date(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if "/" in text:
        return text
    try:
        return datetime.fromisoformat(text).strftime("%d/%m/%Y %H:%M")
    except Exception:
        return text


def _analysis_path(analysis_id: str) -> Path:
    return ANALISES_DIR / f"{analysis_id}.json"


def ensure_history_dir() -> None:
    if db.is_vercel_runtime() and not db.database_configured():
        raise db.PersistenceNotConfigured("DATABASE_URL nao configurado; historico persistente indisponivel.")
    ANALISES_DIR.mkdir(parents=True, exist_ok=True)


def _build_record(analysis: dict[str, Any], source_id: str | None = None) -> dict[str, Any]:
    parent = load_analysis(source_id) if source_id else None
    version = int(parent.get("version", 0)) + 1 if parent else 1
    analysis_id = uuid4().hex[:12]
    created_at = _now_iso()
    record = {
        **analysis,
        "id": analysis_id,
        "createdAt": created_at,
        "updatedAt": created_at,
        "archived": False,
        "version": version,
        "parentId": source_id,
    }
    record["analysisDate"] = record.get("analysisDate") or _format_date(created_at)
    record["analysisName"] = record.get("analysisName") or record.get("title") or "Analise sem titulo"
    record["responsible"] = record.get("responsible") or ""
    return record


def save_analysis(analysis: dict[str, Any], source_id: str | None = None) -> dict[str, Any]:
    record = _build_record(analysis, source_id)
    if db.database_configured():
        return history_repository.save_analysis(record)

    ensure_history_dir()
    _analysis_path(str(record["id"])).write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return record


def load_analysis(analysis_id: str | None) -> dict[str, Any] | None:
    if not analysis_id:
        return None
    if db.database_configured():
        return history_repository.load_analysis(analysis_id)
    if db.is_vercel_runtime():
        return None
    path = _analysis_path(analysis_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def list_analyses(archived: bool | None = None) -> list[dict[str, Any]]:
    if db.database_configured():
        source_records = history_repository.list_analysis_records(archived=archived)
        return [_summary_record(record) for record in source_records]
    if db.is_vercel_runtime():
        return []
    ensure_history_dir()
    records: list[dict[str, Any]] = []
    for path in sorted(ANALISES_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if archived is not None and bool(record.get("archived")) != archived:
            continue
        records.append(_summary_record(record))
    return records


def _summary_record(record: dict[str, Any]) -> dict[str, Any]:
    summary = record.get("summary", {})
    rows = record.get("rows") or []
    main_carrier = summary.get("mainCarrier") or next((row.get("key") or row.get("label") for row in rows if row.get("role") == "main"), "")
    secondary_carriers = summary.get("secondaryCarriers") or [
        row.get("key") or row.get("label") for row in rows if row.get("role") == "secondary"
    ]
    analysis_date = record.get("analysisDate") or record.get("createdAt")
    analysis_name = record.get("analysisName") or record.get("title") or "Analise sem titulo"
    executive = record.get("executive") or build_executive_summary(record)
    best_cost = executive.get("bestCostCarrier") or {}
    fastest = executive.get("fastestCarrier") or {}
    balance = executive.get("bestBalanceCarrier") or {}
    saving = executive.get("potentialSaving") or {}
    return {
        "id": record.get("id"),
        "title": record.get("title"),
        "analysisName": analysis_name,
        "analysisDate": analysis_date,
        "analysisDateDisplay": _format_date(analysis_date),
        "responsible": record.get("responsible") or "",
        "createdAt": record.get("createdAt"),
        "createdAtDisplay": _format_date(record.get("createdAt")),
        "updatedAt": record.get("updatedAt"),
        "archived": bool(record.get("archived")),
        "version": record.get("version"),
        "parentId": record.get("parentId"),
        "cep": record.get("cep", {}).get("cep"),
        "city": record.get("location", {}).get("municipio") or record.get("cep", {}).get("city"),
        "uf": record.get("location", {}).get("uf") or record.get("cep", {}).get("uf"),
        "estb": record.get("location", {}).get("estb"),
        "mainCarrier": main_carrier,
        "secondaryCarriers": secondary_carriers,
        "bestCostCarrier": best_cost.get("label") or best_cost.get("key") or "",
        "fastestCarrier": fastest.get("label") or fastest.get("key") or "",
        "bestBalanceCarrier": balance.get("label") or balance.get("key") or "",
        "averageCost": executive.get("averageCost"),
        "potentialSavingAmount": saving.get("amount"),
        "potentialSavingPct": saving.get("percent"),
        "statusTags": executive.get("statusTags") or [],
        "executive": executive,
        "summary": summary,
    }


def delete_analysis(analysis_id: str) -> dict[str, Any]:
    if db.database_configured():
        return history_repository.soft_delete(analysis_id)
    if db.is_vercel_runtime():
        raise db.PersistenceNotConfigured("DATABASE_URL nao configurado; historico persistente indisponivel.")
    path = _analysis_path(analysis_id)
    if not path.exists():
        raise FileNotFoundError("Analise nao encontrada.")
    path.unlink()
    return {"id": analysis_id, "deleted": True}


def set_archived(analysis_id: str, archived: bool = True) -> dict[str, Any]:
    if db.database_configured():
        return history_repository.update_archived(analysis_id, archived, _now_iso())
    if db.is_vercel_runtime():
        raise db.PersistenceNotConfigured("DATABASE_URL nao configurado; historico persistente indisponivel.")
    record = load_analysis(analysis_id)
    if not record:
        raise FileNotFoundError("Analise nao encontrada.")
    record["archived"] = archived
    record["updatedAt"] = _now_iso()
    _analysis_path(analysis_id).write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return record
