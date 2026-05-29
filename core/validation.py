from __future__ import annotations

from typing import Any

import pandas as pd

from .normalization import first_existing_column
from .settings import CONTRACT_COLUMN_ALIASES, DEFAULT_CONFIG, PEDIDO_REQUIRED_ALIASES


def resolve_contract_columns(df: pd.DataFrame, config: dict[str, Any] | None = None) -> dict[str, str | None]:
    cfg_columns = (config or DEFAULT_CONFIG).get("columns", {})
    resolved: dict[str, str | None] = {}
    for key, aliases in CONTRACT_COLUMN_ALIASES.items():
        configured = cfg_columns.get(key)
        candidates = [configured] if configured else []
        candidates.extend(aliases)
        resolved[key] = first_existing_column(df.columns, [c for c in candidates if c])
    return resolved


def resolve_pedido_columns(df: pd.DataFrame, config: dict[str, Any] | None = None) -> dict[str, str | None]:
    cfg_columns = (config or DEFAULT_CONFIG).get("pedidoColumns", {})
    resolved: dict[str, str | None] = {}
    for key, configured in cfg_columns.items():
        candidates = [configured]
        candidates.extend(PEDIDO_REQUIRED_ALIASES.get(key, []))
        resolved[key] = first_existing_column(df.columns, [c for c in candidates if c])
    return resolved


def detect_weight_columns(df: pd.DataFrame) -> list[int]:
    weights: list[int] = []
    for col in df.columns:
        text = str(col).strip()
        if text.isdigit():
            weights.append(int(text))
    return sorted(set(weights))


def validate_contracts(df: pd.DataFrame, config: dict[str, Any] | None = None) -> dict[str, Any]:
    columns = resolve_contract_columns(df, config)
    missing: list[str] = []
    for required in ("nome", "cidade", "uf"):
        if not columns.get(required):
            missing.append(required)

    has_cep_range = bool(columns.get("cepInicial") and columns.get("cepFinal"))
    has_ibge_range = bool(columns.get("ibge") or (columns.get("ibgeInicial") and columns.get("ibgeFinal")))
    if not has_cep_range and not has_ibge_range:
        missing.append("cepInicial/cepFinal ou ibge/ibgeInicial/ibgeFinal")

    weights = detect_weight_columns(df)
    if not weights:
        missing.append("faixas de peso numericas")

    return {
        "ok": not missing,
        "missing": missing,
        "columns": columns,
        "weightColumns": weights,
        "rowCount": len(df),
    }


def validate_pedidos(df: pd.DataFrame, config: dict[str, Any] | None = None) -> dict[str, Any]:
    columns = resolve_pedido_columns(df, config)
    missing = [key for key in ("cep", "peso", "nota") if not columns.get(key)]
    return {
        "ok": not missing,
        "missing": missing,
        "columns": columns,
        "rowCount": len(df),
    }

