from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from .normalization import get_cell, parse_cep, parse_ibge, safe_json_value, to_number
from .repository import load_dataset
from .settings import ANALISES_DIR
from .validation import resolve_contract_columns

CACHE_PATH = ANALISES_DIR.parent / "cep_cache.json"


@dataclass(frozen=True)
class CepInfo:
    cep: str
    city: str = ""
    uf: str = ""
    ibge: int | None = None
    source: str = "not_found"
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "cep": self.cep,
            "city": self.city,
            "uf": self.uf,
            "ibge": self.ibge,
            "source": self.source,
            "error": self.error,
        }


def _load_cache() -> dict[str, Any]:
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_cache(cache: dict[str, Any]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def _cache_get(cep: str) -> CepInfo | None:
    cached = _load_cache().get(cep)
    if not cached:
        return None
    if cached.get("error") and time.time() - float(cached.get("cachedAt", 0)) > 3600:
        return None
    return CepInfo(**{k: v for k, v in cached.items() if k != "cachedAt"})


def _cache_set(info: CepInfo) -> None:
    cache = _load_cache()
    data = info.as_dict()
    data["cachedAt"] = time.time()
    cache[info.cep] = data
    _save_cache(cache)


def _resolve_cep_from_local_table(cep: str) -> CepInfo | None:
    df, _files, _errors = load_dataset("cep_ibge")
    if df.empty:
        return None

    cep_int = int(cep)
    cols = {str(c).strip().upper(): str(c) for c in df.columns}
    cep_col = cols.get("CEP")
    cep_ini = cols.get("CEP INICIAL") or cols.get("CEPI")
    cep_fim = cols.get("CEP FINAL") or cols.get("CEPF")
    city_col = cols.get("CIDADE") or cols.get("MUNICIPIO") or cols.get("MUNICÍPIO")
    uf_col = cols.get("UF")
    ibge_col = cols.get("IBGE") or cols.get("CODIGO IBGE") or cols.get("CÓDIGO IBGE")

    for _, row in df.iterrows():
        match = False
        if cep_col and parse_cep(row.get(cep_col)) == cep_int:
            match = True
        elif cep_ini and cep_fim:
            ini = parse_cep(row.get(cep_ini))
            fim = parse_cep(row.get(cep_fim))
            match = ini is not None and fim is not None and ini <= cep_int <= fim
        if not match:
            continue
        return CepInfo(
            cep=cep,
            city=str(row.get(city_col) or "") if city_col else "",
            uf=str(row.get(uf_col) or "") if uf_col else "",
            ibge=parse_ibge(row.get(ibge_col)) if ibge_col else None,
            source="local_table",
        )
    return None


def resolve_cep(cep_value: Any) -> CepInfo:
    cep_int = parse_cep(cep_value)
    if cep_int is None:
        return CepInfo(cep="", error="CEP invalido. Informe 8 digitos.")

    cep = str(cep_int).zfill(8)
    cached = _cache_get(cep)
    if cached:
        return cached

    local = _resolve_cep_from_local_table(cep)
    if local and local.ibge:
        _cache_set(local)
        return local

    if os.getenv("ENABLE_CEP_API", "1").strip().lower() not in {"1", "true", "yes"}:
        info = local or CepInfo(cep=cep, error="Consulta externa de CEP desabilitada.")
        _cache_set(info)
        return info

    request = urllib.request.Request(
        f"https://viacep.com.br/ws/{cep}/json/",
        headers={"User-Agent": "FreteLab/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            data = json.loads(response.read().decode("utf-8"))
        if data.get("erro"):
            raise ValueError("CEP nao encontrado no ViaCEP.")
        info = CepInfo(
            cep=cep,
            city=str(data.get("localidade") or ""),
            uf=str(data.get("uf") or ""),
            ibge=parse_ibge(data.get("ibge")),
            source="viacep",
        )
        _cache_set(info)
        return info
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        if local:
            return local
        info = CepInfo(cep=cep, error=f"CEP nao encontrado ou servico indisponivel: {exc}")
        _cache_set(info)
        return info


def fallback_cep_from_contracts(cep_value: Any, contracts: pd.DataFrame, config: dict[str, Any]) -> CepInfo:
    cep_int = parse_cep(cep_value)
    if cep_int is None or contracts.empty:
        return resolve_cep(cep_value)

    columns = resolve_contract_columns(contracts, config)
    cep_ini = columns.get("cepInicial")
    cep_fim = columns.get("cepFinal")
    if not cep_ini or not cep_fim:
        return resolve_cep(cep_value)

    for _, row in contracts.iterrows():
        ini = parse_cep(get_cell(row, cep_ini))
        fim = parse_cep(get_cell(row, cep_fim))
        if ini is None or fim is None:
            continue
        if ini <= cep_int <= fim:
            return CepInfo(
                cep=str(cep_int).zfill(8),
                city=str(get_cell(row, columns.get("cidade")) or ""),
                uf=str(get_cell(row, columns.get("uf")) or ""),
                ibge=parse_ibge(get_cell(row, columns.get("ibge"))),
                source="contract_fallback",
                error=None,
            )
    return resolve_cep(cep_value)


def evaluate_row_coverage(
    row: pd.Series,
    cep_info: CepInfo,
    config: dict[str, Any],
    columns: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    columns = columns or resolve_contract_columns(pd.DataFrame([row]), config)
    cep_int = parse_cep(cep_info.cep)
    ibge = cep_info.ibge

    row_ibge = parse_ibge(get_cell(row, columns.get("ibge")))
    ibge_ini = parse_ibge(get_cell(row, columns.get("ibgeInicial"))) or row_ibge
    ibge_fim = parse_ibge(get_cell(row, columns.get("ibgeFinal"))) or row_ibge
    cep_ini = parse_cep(get_cell(row, columns.get("cepInicial")))
    cep_fim = parse_cep(get_cell(row, columns.get("cepFinal")))

    details = {
        "carrier": str(get_cell(row, columns.get("nome")) or ""),
        "city": str(get_cell(row, columns.get("cidade")) or ""),
        "uf": str(get_cell(row, columns.get("uf")) or ""),
        "cepInicial": cep_ini,
        "cepFinal": cep_fim,
        "ibgeInicial": ibge_ini,
        "ibgeFinal": ibge_fim,
    }

    if cep_int is None:
        return {"valid": False, "reason": "CEP invalido.", **details}

    if ibge is not None and ibge_ini is not None and ibge_fim is not None:
        low, high = sorted((ibge_ini, ibge_fim))
        valid = low <= ibge <= high
        return {
            "valid": valid,
            "reason": "IBGE dentro da faixa de abrangencia." if valid else "IBGE fora da faixa de abrangencia.",
            "method": "ibge",
            **details,
        }

    if ibge is None:
        ibge_reason = "Codigo IBGE do CEP ausente."
    else:
        ibge_reason = "Contrato sem campos de IBGE."

    if cep_ini is not None and cep_fim is not None:
        low, high = sorted((cep_ini, cep_fim))
        valid = low <= cep_int <= high
        return {
            "valid": valid,
            "reason": (
                f"{ibge_reason} Validado por faixa de CEP." if valid else f"{ibge_reason} CEP fora da faixa do contrato."
            ),
            "method": "cep_fallback",
            **details,
        }

    return {
        "valid": False,
        "reason": f"{ibge_reason} Contrato sem faixa de CEP valida.",
        "method": "missing_range",
        **details,
    }


def coverage_by_carrier(df: pd.DataFrame, cep_info: CepInfo, config: dict[str, Any]) -> dict[str, Any]:
    from .calculator import carrier_key

    valid: dict[str, dict[str, Any]] = {}
    invalid: dict[str, dict[str, Any]] = {}
    valid_indexes: list[int] = []
    columns = resolve_contract_columns(df, config)

    for index, row in df.iterrows():
        key = carrier_key(row, config, columns)
        result = evaluate_row_coverage(row, cep_info, config, columns)
        row_info = {
            "index": int(index),
            "key": key,
            "reason": result["reason"],
            "method": result.get("method"),
            "details": {k: safe_json_value(v) for k, v in result.items() if k not in {"valid", "reason", "method"}},
        }
        if result["valid"]:
            valid_indexes.append(index)
            valid.setdefault(key, {"key": key, "validRows": 0, "reasons": []})
            valid[key]["validRows"] += 1
            if row_info["reason"] not in valid[key]["reasons"]:
                valid[key]["reasons"].append(row_info["reason"])
            invalid.pop(key, None)
        elif key not in valid:
            invalid.setdefault(key, {"key": key, "invalidRows": 0, "reasons": []})
            invalid[key]["invalidRows"] += 1
            if row_info["reason"] not in invalid[key]["reasons"]:
                invalid[key]["reasons"].append(row_info["reason"])

    return {
        "cep": cep_info.as_dict(),
        "validCarriers": sorted(valid.values(), key=lambda item: item["key"]),
        "invalidCarriers": sorted(invalid.values(), key=lambda item: item["key"]),
        "validIndexes": valid_indexes,
    }
