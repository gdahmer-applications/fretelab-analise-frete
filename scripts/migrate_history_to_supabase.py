from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

from core import db


def _load_env() -> None:
    if load_dotenv:
        load_dotenv(ROOT / ".env")
    env_path = ROOT / ".env"
    if env_path.exists():
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _record_params(record: dict[str, Any]) -> dict[str, Any]:
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
    return {
        "id": record.get("id"),
        "parent_id": record.get("parentId"),
        "version": int(record.get("version") or 1),
        "analysis_name": record.get("analysisName") or record.get("title") or "Analise sem titulo",
        "analysis_date": record.get("analysisDate"),
        "responsible": record.get("responsible") or "",
        "archived": bool(record.get("archived")),
        "created_at": record.get("createdAt"),
        "updated_at": record.get("updatedAt") or record.get("createdAt"),
        "cep": cep.get("cep"),
        "city": location.get("municipio") or cep.get("city"),
        "uf": location.get("uf") or cep.get("uf"),
        "main_carrier": main_carrier,
        "best_cost_carrier": best_cost.get("label") or best_cost.get("key") or "",
        "payload_json": db.jsonb(record),
    }


def migrate(history_dir: Path) -> int:
    files = sorted(history_dir.glob("*.json"))
    count = 0
    with db.connection() as conn:
        with conn.cursor() as cur:
            for path in files:
                record = json.loads(path.read_text(encoding="utf-8"))
                if not record.get("id"):
                    record["id"] = path.stem
                params = _record_params(record)
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
                    on conflict (id) do update set
                        parent_id = excluded.parent_id,
                        version = excluded.version,
                        analysis_name = excluded.analysis_name,
                        analysis_date = excluded.analysis_date,
                        responsible = excluded.responsible,
                        archived = excluded.archived,
                        updated_at = excluded.updated_at,
                        cep = excluded.cep,
                        city = excluded.city,
                        uf = excluded.uf,
                        main_carrier = excluded.main_carrier,
                        best_cost_carrier = excluded.best_cost_carrier,
                        payload_json = excluded.payload_json
                    """,
                    params,
                )
                count += 1
    return count


def main() -> None:
    _load_env()
    if not db.database_configured():
        raise SystemExit("DATABASE_URL nao configurado.")
    history_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "storage" / "analises"
    if not history_dir.exists():
        raise SystemExit(f"Diretorio de historico nao encontrado: {history_dir}")
    count = migrate(history_dir)
    print(f"{count} analise(s) migrada(s) para Supabase.")


if __name__ == "__main__":
    main()
