from __future__ import annotations

from copy import deepcopy
from typing import Any

import pandas as pd

from .normalization import first_existing_column, get_cell, norm_key, safe_json_value, to_number
from .settings import DEFAULT_CONFIG
from .validation import detect_weight_columns, resolve_contract_columns


def merge_config(config: dict[str, Any] | None = None) -> dict[str, Any]:
    merged = deepcopy(DEFAULT_CONFIG)
    if not config:
        return merged
    for key, value in config.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key].update(value)
        else:
            merged[key] = value
    return merged


def build_weights(config: dict[str, Any]) -> list[int]:
    weight_cfg = config.get("weights", {})
    start = int(weight_cfg.get("start") or 20)
    end = int(weight_cfg.get("end") or 200)
    step = int(weight_cfg.get("step") or 20)
    if start <= 0 or end < start or step <= 0:
        raise ValueError("Configuracao de pesos invalida.")
    weights = list(range(start, end + 1, step))
    if 999 not in weights:
        weights.append(999)
    if not weights or len(weights) > 200:
        raise ValueError("Quantidade de pesos invalida.")
    return weights


def carrier_key(row: pd.Series | dict[str, Any], config: dict[str, Any], resolved_columns: dict[str, str | None] | None = None) -> str:
    configured = config.get("columns", {})
    if resolved_columns:
        name_col = resolved_columns.get("nome")
        id_col = resolved_columns.get("id")
        stock_col = resolved_columns.get("estoque")
    else:
        row_columns = row.index if isinstance(row, pd.Series) else row.keys()
        name_col = first_existing_column(row_columns, [configured.get("nome"), "NOME", "TRANSPORTADORA"])
        id_col = first_existing_column(row_columns, [configured.get("id"), "ID INTELIPOST", "ID"])
        stock_col = first_existing_column(row_columns, [configured.get("estoque"), "ESTOQUE", "CD"])

    pieces = [str(get_cell(row, name_col) or "").strip()]
    if id_col:
        value = str(get_cell(row, id_col) or "").strip()
        if value:
            pieces.append(f"ID {value}")
    if stock_col:
        value = str(get_cell(row, stock_col) or "").strip()
        if value:
            pieces.append(f"Est {value}")
    return " | ".join(piece for piece in pieces if piece) or "Transportadora sem nome"


def make_label(key: str, suffix: str = "") -> str:
    short = str(key).split("|")[0].strip()
    return f"{short} {suffix}".strip()


def _build_fixed_fraction_map(columns: list[str], fixed_fields: list[str]) -> dict[str, str | None]:
    mapping: dict[str, str | None] = {}
    for field in fixed_fields:
        base = str(field).replace("VALOR FIXO", "").strip()
        candidates = [
            f"{base} FRACAO A CADA x KG",
            f"{base} FRAÇÃO A CADA x KG",
            f"{base} FRACAO A CADA X KG",
            f"{base} FRAÇÃO A CADA X KG",
            f"{base} FRACAO A CADA KG",
            f"{base} FRAÇÃO A CADA KG",
        ]
        found = first_existing_column(columns, candidates)
        if not found:
            base_norm = norm_key(base)
            for col in columns:
                col_norm = norm_key(col)
                if base_norm and base_norm in col_norm and "KG" in col_norm and "FRAC" in col_norm:
                    found = str(col)
                    break
        mapping[field] = found
    return mapping


def sum_fixed(row: pd.Series, config: dict[str, Any], weight_for_fraction: float, fixed_fraction_map: dict[str, str | None]) -> float:
    if not config.get("flags", {}).get("addFixed", True):
        return 0.0
    total = 0.0
    for field in config.get("fixedFields", []):
        value = to_number(get_cell(row, field))
        if value is None or value <= 0:
            continue
        fraction_field = fixed_fraction_map.get(field)
        if fraction_field:
            fraction_kg = to_number(get_cell(row, fraction_field))
            if fraction_kg is None or fraction_kg <= 0 or weight_for_fraction <= 0:
                continue
            total += value * int(-(-weight_for_fraction // fraction_kg))
        else:
            total += value
    return total


def percent_costs(row: pd.Series, config: dict[str, Any], nota_override: float | None = None) -> float:
    if not config.get("flags", {}).get("addPerc", False):
        return 0.0
    nota = float(nota_override if nota_override is not None else config.get("nota") or 0)
    rules = {
        "SEGURO(%)": {"min": "SEGURO MINIMO"},
        "GRIS(%)": {"min": "GRIS MINIMO", "max": "GRIS MAXIMO"},
        "FRETE VALOR SOBRE A NOTA(%)": {},
    }
    total = 0.0
    for field in config.get("percentFields", []):
        pct = to_number(get_cell(row, field))
        if pct is None:
            continue
        value = nota * (pct / 100)
        rule = rules.get(norm_key(field), rules.get(field, {}))
        min_value = to_number(get_cell(row, rule.get("min"))) if rule.get("min") else None
        max_value = to_number(get_cell(row, rule.get("max"))) if rule.get("max") else None
        if min_value is not None:
            value = max(value, min_value)
        if max_value is not None:
            value = min(value, max_value)
        total += value
    return total


def apply_minimum(total: float, row: pd.Series, config: dict[str, Any]) -> tuple[float, float]:
    if not config.get("flags", {}).get("applyMinFrete", False):
        return total, 0.0
    minimum = to_number(get_cell(row, "FRETE TOTAL MINIMO")) or to_number(get_cell(row, "FRETE TOTAL MÍNIMO"))
    if minimum is None:
        return total, 0.0
    applied = max(total, minimum)
    return applied, applied - total


def excedente_per_kg(row: pd.Series) -> float | None:
    candidates = [
        "VALOR EXCEDENTE",
        "EXCEDENTE",
        "VALOR EXCEDENTE (R$/KG)",
        "VALOR EXCEDENTE R$/KG",
        "EXCEDENTE R$/KG",
        "R$/KG EXCEDENTE",
    ]
    for candidate in candidates:
        value = to_number(get_cell(row, candidate))
        if value is not None and value > 0:
            return value
    return None


def deadline_days(row: pd.Series) -> float | None:
    candidates = [
        "PRAZO(DIAS ÚTEIS)",
        "PRAZO(DIAS UTEIS)",
        "PRAZO DIAS UTEIS",
        "PRAZO",
        "PRAZO ENTREGA",
        "PRAZO DE ENTREGA",
        "SLA",
    ]
    for candidate in candidates:
        value = to_number(get_cell(row, candidate))
        if value is not None and value >= 0:
            return value
    return None


def pick_base_by_weight(row: pd.Series, weight_columns: list[int], desired_weight: int) -> dict[str, float] | None:
    valid: list[tuple[int, float]] = []
    for weight in weight_columns:
        value = to_number(get_cell(row, str(weight)))
        if value is not None and value > 0:
            valid.append((weight, value))
    if not valid:
        return None

    chosen_weight, base = next(((w, v) for w, v in valid if w >= desired_weight), valid[-1])
    excedente = 0.0
    if desired_weight > chosen_weight:
        excedente_value = excedente_per_kg(row)
        if excedente_value is not None:
            excedente = excedente_value * (desired_weight - chosen_weight)
            base += excedente

    return {"chosenKg": chosen_weight, "base": base, "excedApplied": excedente}


def compute_row_total(
    row: pd.Series,
    desired_weight: int,
    weight_columns: list[int],
    config: dict[str, Any],
    fixed_fraction_map: dict[str, str | None],
    weight_for_fraction: float | None = None,
    nota_override: float | None = None,
) -> dict[str, Any] | None:
    picked = pick_base_by_weight(row, weight_columns, desired_weight)
    if not picked:
        return None
    fixed = sum_fixed(row, config, weight_for_fraction or desired_weight, fixed_fraction_map)
    percent = percent_costs(row, config, nota_override)
    before_min = picked["base"] + fixed + percent
    total, min_applied = apply_minimum(before_min, row, config)
    return {
        "chosenKg": picked["chosenKg"],
        "base": picked["base"],
        "excedApplied": picked["excedApplied"],
        "fixed": fixed,
        "perc": percent,
        "minApplied": min_applied,
        "total": total,
        "deadlineDays": deadline_days(row),
        "rowIndex": int(row.name) if row.name is not None else None,
    }


def best_by_carrier_and_weight(df: pd.DataFrame, weights: list[int], config: dict[str, Any]) -> dict[str, dict[int, dict[str, Any] | None]]:
    weight_columns = detect_weight_columns(df)
    if not weight_columns:
        raise ValueError("Nao encontrei colunas numericas de peso no contrato.")
    fixed_map = _build_fixed_fraction_map([str(c) for c in df.columns], config.get("fixedFields", []))
    resolved_columns = resolve_contract_columns(df, config)

    grouped: dict[str, list[pd.Series]] = {}
    for _, row in df.iterrows():
        grouped.setdefault(carrier_key(row, config, resolved_columns), []).append(row)

    result: dict[str, dict[int, dict[str, Any] | None]] = {}
    for carrier, rows in grouped.items():
        by_weight: dict[int, dict[str, Any] | None] = {}
        for weight in weights:
            best = None
            for row in rows:
                current = compute_row_total(row, weight, weight_columns, config, fixed_map)
                if current and (best is None or current["total"] < best["total"]):
                    best = current
            by_weight[weight] = best
        result[carrier] = by_weight
    return result


def top_carriers(best: dict[str, dict[int, dict[str, Any] | None]], weights: list[int], limit: int = 5) -> list[str]:
    scored: list[tuple[str, float]] = []
    for carrier, by_weight in best.items():
        values = [by_weight[w]["total"] for w in weights if by_weight.get(w)]
        if values:
            scored.append((carrier, sum(values) / len(values)))
    scored.sort(key=lambda item: item[1])
    return [carrier for carrier, _score in scored[:limit]]


def row_for_output(label: str, key: str, dataset: str, best: dict[int, dict[str, Any] | None], weights: list[int]) -> dict[str, Any]:
    return {
        "label": label,
        "key": key,
        "dataset": dataset,
        "totals": [best[w]["total"] if best.get(w) else None for w in weights],
        "deadlines": [best[w].get("deadlineDays") if best.get(w) else None for w in weights],
    }


def calc_rows(label: str, key: str, dataset: str, best: dict[int, dict[str, Any] | None], weights: list[int]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for weight in weights:
        item = best.get(weight)
        if not item:
            continue
        out.append({
            "dataset": dataset,
            "label": label,
            "carrier": key,
            "weight": weight,
            "chosenKg": item["chosenKg"],
            "base": item["base"],
            "fixed": item["fixed"],
            "perc": item["perc"],
            "minApplied": item["minApplied"],
            "total": item["total"],
            "deadlineDays": item.get("deadlineDays"),
            "rowIndex": item.get("rowIndex"),
        })
    return out


def compact_row(row: pd.Series, max_columns: int = 120) -> dict[str, Any]:
    return {
        str(key): safe_json_value(value)
        for key, value in list(row.items())[:max_columns]
    }
