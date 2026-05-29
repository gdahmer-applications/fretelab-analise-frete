from __future__ import annotations

from typing import Any

import pandas as pd

from .calculator import (
    best_by_carrier_and_weight,
    build_weights,
    calc_rows,
    carrier_key,
    make_label,
    merge_config,
    row_for_output,
    top_carriers,
)
from .coverage import CepInfo, coverage_by_carrier, fallback_cep_from_contracts
from .history import save_analysis
from .insights import build_executive_summary
from .logistics import logistics_metadata, logistics_options, resolve_cep_in_logistics
from .normalization import get_cell, norm_key, parse_cep, parse_ibge, safe_json_value, to_number
from .repository import load_dataset
from .validation import resolve_contract_columns, resolve_pedido_columns, validate_contracts, validate_pedidos


def _filter_stocks(df: pd.DataFrame, stocks: list[str], config: dict[str, Any]) -> pd.DataFrame:
    if not stocks or df.empty:
        return df
    columns = resolve_contract_columns(df, config)
    stock_col = columns.get("estoque")
    if not stock_col:
        return df
    wanted = {str(item).strip() for item in stocks if str(item).strip()}
    return df[df[stock_col].astype(str).str.strip().isin(wanted)]


def _filter_by_coverage(df: pd.DataFrame, coverage: dict[str, Any], stocks: list[str], config: dict[str, Any]) -> pd.DataFrame:
    valid_indexes = coverage.get("validIndexes") or []
    if not valid_indexes:
        return df.iloc[0:0].copy()
    scoped = df.loc[valid_indexes].copy()
    return _filter_stocks(scoped, stocks, config)


def _stock_is_all(estb: str | None) -> bool:
    return norm_key(estb) in {"__ALL__", "TODOS", "TODO", "ALL"}


def _normalize_estbs(values: Any) -> list[str]:
    if values is None:
        return ["__ALL__"]
    if isinstance(values, str):
        items = [values]
    else:
        items = [str(item) for item in values if str(item).strip()]
    cleaned = [item.strip() for item in items if item.strip()]
    if not cleaned or any(_stock_is_all(item) for item in cleaned):
        return ["__ALL__"]
    return cleaned


def _estbs_are_all(estbs: list[str]) -> bool:
    return not estbs or any(_stock_is_all(item) for item in estbs)


def _estb_label(estbs: list[str]) -> str:
    return "Todos" if _estbs_are_all(estbs) else ", ".join(estbs)


def _carrier_display(key: str) -> str:
    pieces = [piece.strip() for piece in str(key).split("|") if piece.strip()]
    if not pieces:
        return "Transportadora sem nome"
    name = pieces[0]
    extras: list[str] = []
    for piece in pieces[1:]:
        if norm_key(piece).startswith("EST "):
            extras.append(piece.split(" ", 1)[1].strip())
        else:
            extras.append(piece)
    return " - ".join([name, *extras]) if extras else name


def _format_cep(value: int | None) -> str:
    if value is None:
        return ""
    return str(value).zfill(8)


def _select_contract_dataset(config: dict[str, Any], use_negociacoes: bool = True) -> tuple[pd.DataFrame, str]:
    vigentes, _files, _errors = load_dataset("contratos_vigentes")
    negociacoes, _nfiles, _nerrors = load_dataset("contratos_negociacoes")
    if use_negociacoes and not negociacoes.empty:
        return negociacoes, "CONTRATOS NEGOCIACOES"
    return vigentes, "CONTRATOS VIGENTES"


def _row_matches_location(row: pd.Series, columns: dict[str, str | None], uf: str, municipio: str, estbs: list[str]) -> bool:
    row_uf = norm_key(get_cell(row, columns.get("uf")))
    row_city = norm_key(get_cell(row, columns.get("cidade")))
    if row_uf != norm_key(uf) or row_city != norm_key(municipio):
        return False
    if _estbs_are_all(estbs):
        return True
    row_stock = str(get_cell(row, columns.get("estoque")) or "").strip()
    return row_stock in {str(item).strip() for item in estbs}


def _row_matches_estb(row: pd.Series, columns: dict[str, str | None], estbs: list[str]) -> bool:
    if _estbs_are_all(estbs):
        return True
    row_stock = str(get_cell(row, columns.get("estoque")) or "").strip()
    return row_stock in {str(item).strip() for item in estbs}


def _cep_info_for_contracts(cep_value: Any, contracts: pd.DataFrame, config: dict[str, Any]) -> CepInfo:
    logistics_hit = resolve_cep_in_logistics(cep_value)
    if logistics_hit:
        return CepInfo(
            cep=str(logistics_hit.get("cep") or ""),
            city=str(logistics_hit.get("city") or ""),
            uf=str(logistics_hit.get("uf") or ""),
            ibge=None,
            source=str(logistics_hit.get("source") or "regioes_logisticas"),
            error=None,
        )
    return fallback_cep_from_contracts(cep_value, contracts, config)


def _cep_coverage(df: pd.DataFrame, cep_info: CepInfo, estbs: list[str], config: dict[str, Any]) -> dict[str, Any]:
    cep_int = parse_cep(cep_info.cep)
    if cep_int is None:
        raise ValueError("Informe um CEP valido para consultar transportadoras.")

    columns = resolve_contract_columns(df, config)
    valid: dict[str, dict[str, Any]] = {}
    invalid: dict[str, dict[str, Any]] = {}
    valid_indexes: list[int] = []
    all_carriers: set[str] = set()
    cep_ranges: list[dict[str, Any]] = []

    for index, row in df.iterrows():
        key = carrier_key(row, config, columns)
        all_carriers.add(key)
        if not _row_matches_estb(row, columns, estbs):
            continue

        cep_ini = parse_cep(get_cell(row, columns.get("cepInicial")))
        cep_fim = parse_cep(get_cell(row, columns.get("cepFinal")))
        if cep_ini is None or cep_fim is None:
            continue

        low, high = sorted((cep_ini, cep_fim))
        if not (low <= cep_int <= high):
            continue

        valid_indexes.append(index)
        range_item = {
            "cepInicial": _format_cep(low),
            "cepFinal": _format_cep(high),
            "estb": str(get_cell(row, columns.get("estoque")) or ""),
        }
        cep_ranges.append({"carrier": key, **range_item})
        reason = f"CEP {_format_cep(cep_int)} dentro da faixa {range_item['cepInicial']}-{range_item['cepFinal']} do contrato."
        valid.setdefault(key, {"key": key, "validRows": 0, "reasons": [], "ranges": []})
        valid[key]["validRows"] += 1
        valid[key]["ranges"].append(range_item)
        if reason not in valid[key]["reasons"]:
            valid[key]["reasons"].append(reason)

    for key in all_carriers:
        if key not in valid:
            invalid[key] = {
                "key": key,
                "invalidRows": 1,
                "reasons": [f"Nenhuma faixa de CEP do contrato atende o CEP {_format_cep(cep_int)} para o ESTB selecionado."],
            }

    cep_ranges.sort(key=lambda item: (item.get("cepInicial") or "", item.get("carrier") or ""))
    return {
        "cep": cep_info.as_dict(),
        "location": {
            "uf": cep_info.uf,
            "municipio": cep_info.city,
            "estb": _estb_label(estbs),
            "estbs": estbs,
        },
        "cepRanges": cep_ranges,
        "validCarriers": sorted(valid.values(), key=lambda item: item["key"]),
        "invalidCarriers": sorted(invalid.values(), key=lambda item: item["key"]),
        "validIndexes": valid_indexes,
    }


def _location_coverage(df: pd.DataFrame, uf: str, municipio: str, estbs: list[str], config: dict[str, Any]) -> dict[str, Any]:
    if not uf or not municipio or not estbs:
        raise ValueError("Selecione UF, Municipio e ESTB.")

    columns = resolve_contract_columns(df, config)
    valid: dict[str, dict[str, Any]] = {}
    invalid: dict[str, dict[str, Any]] = {}
    valid_indexes: list[int] = []
    all_carriers: set[str] = set()
    cep_ranges: list[dict[str, Any]] = []

    for index, row in df.iterrows():
        key = carrier_key(row, config, columns)
        all_carriers.add(key)
        if not _row_matches_location(row, columns, uf, municipio, estbs):
            continue

        valid_indexes.append(index)
        cep_ini = parse_cep(get_cell(row, columns.get("cepInicial")))
        cep_fim = parse_cep(get_cell(row, columns.get("cepFinal")))
        ibge = parse_ibge(get_cell(row, columns.get("ibge")))
        ibge_ini = parse_ibge(get_cell(row, columns.get("ibgeInicial"))) or ibge
        ibge_fim = parse_ibge(get_cell(row, columns.get("ibgeFinal"))) or ibge
        range_item = {
            "cepInicial": _format_cep(cep_ini),
            "cepFinal": _format_cep(cep_fim),
            "ibgeInicial": ibge_ini,
            "ibgeFinal": ibge_fim,
            "estb": str(get_cell(row, columns.get("estoque")) or ""),
        }
        cep_ranges.append({"carrier": key, **range_item})
        if ibge_ini is not None or ibge_fim is not None:
            reason = "UF/Municipio/ESTB validos. Abrangencia com referencia IBGE do contrato."
        else:
            reason = "UF/Municipio/ESTB validos. Abrangencia por range de CEP do contrato."
        valid.setdefault(key, {"key": key, "validRows": 0, "reasons": [], "ranges": []})
        valid[key]["validRows"] += 1
        valid[key]["ranges"].append(range_item)
        if reason not in valid[key]["reasons"]:
            valid[key]["reasons"].append(reason)

    for key in all_carriers:
        if key not in valid:
            invalid[key] = {
                "key": key,
                "invalidRows": 1,
                "reasons": ["Sem linha valida para UF/Municipio/ESTB selecionados."],
            }

    cep_ranges.sort(key=lambda item: (item.get("cepInicial") or "", item.get("carrier") or ""))
    return {
        "location": {
            "uf": uf,
            "municipio": municipio,
            "estb": _estb_label(estbs),
            "estbs": estbs,
        },
        "cepRanges": cep_ranges,
        "validCarriers": sorted(valid.values(), key=lambda item: item["key"]),
        "invalidCarriers": sorted(invalid.values(), key=lambda item: item["key"]),
        "validIndexes": valid_indexes,
    }


def location_options(
    config: dict[str, Any] | None = None,
    uf: str | None = None,
    municipio: str | None = None,
    logistics_region: str | None = None,
) -> dict[str, Any]:
    cfg = merge_config(config)
    df, dataset = _select_contract_dataset(cfg)
    if df.empty:
        return {"dataset": dataset, "logisticsRegions": [], "ufs": [], "municipios": [], "estbs": []}

    columns = resolve_contract_columns(df, cfg)
    uf_col = columns.get("uf")
    city_col = columns.get("cidade")
    stock_col = columns.get("estoque")

    logistics = logistics_options(logistics_region, uf)
    logistics_meta = logistics_metadata()
    ufs = logistics["ufs"] if logistics["ufs"] else (sorted({str(value).strip() for value in df[uf_col].dropna() if str(value).strip()}) if uf_col else [])
    scoped = df
    if uf and uf_col:
        scoped = scoped[scoped[uf_col].apply(lambda value: norm_key(value) == norm_key(uf))]
    municipios = logistics["municipios"] if logistics["municipios"] else (sorted({str(value).strip() for value in scoped[city_col].dropna() if str(value).strip()}) if city_col else [])
    if municipio and city_col:
        scoped = scoped[scoped[city_col].apply(lambda value: norm_key(value) == norm_key(municipio))]

    stocks = sorted({str(value).strip() for value in scoped[stock_col].dropna() if str(value).strip()}) if stock_col else []
    estbs = [{"value": "__ALL__", "label": "Todos"}] + [{"value": item, "label": item} for item in stocks]
    return {
        "dataset": dataset,
        "logisticsRegions": logistics_meta.get("regions", []),
        "ufs": ufs,
        "municipios": municipios,
        "estbs": estbs,
    }


def available_carriers_by_location(params: dict[str, Any]) -> dict[str, Any]:
    cfg = merge_config(params.get("config"))
    df, _dataset = _select_contract_dataset(cfg)
    if df.empty:
        raise ValueError("Nenhum arquivo de contrato encontrado.")
    estbs = _normalize_estbs(params.get("estbs") if "estbs" in params else params.get("estb"))
    if parse_cep(params.get("cep")) is not None:
        cep_info = _cep_info_for_contracts(params.get("cep"), df, cfg)
        return {k: v for k, v in _cep_coverage(df, cep_info, estbs, cfg).items() if k != "validIndexes"}
    return {k: v for k, v in _location_coverage(
        df,
        str(params.get("uf") or ""),
        str(params.get("municipio") or ""),
        estbs,
        cfg,
    ).items() if k != "validIndexes"}


def resolve_location_from_cep(cep_value: Any, config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = merge_config(config)
    df, _dataset = _select_contract_dataset(cfg)
    if df.empty:
        raise ValueError("Nenhum arquivo de contrato encontrado.")
    logistics_hit = resolve_cep_in_logistics(cep_value)
    if logistics_hit:
        return logistics_hit
    cep_info = fallback_cep_from_contracts(cep_value, df, cfg)
    if not cep_info.cep:
        raise ValueError(cep_info.error or "CEP invalido.")
    return cep_info.as_dict()


def _variation(main: list[float | None], other: list[float | None]) -> list[float | None]:
    out: list[float | None] = []
    for a, b in zip(main, other):
        if a is None or b in (None, 0):
            out.append(None)
        else:
            out.append((a / b) - 1)
    return out


def _representativity_by_weights(pedidos: pd.DataFrame, cep: str, stocks: list[str], weights: list[int], config: dict[str, Any]) -> list[float | None]:
    if pedidos.empty or not weights:
        return [None for _ in weights]

    validation = validate_pedidos(pedidos, config)
    if not validation["ok"]:
        return [None for _ in weights]

    columns = validation["columns"]
    scoped = pedidos.copy()
    cep_int = parse_cep(cep)
    if cep_int is not None and columns.get("cep"):
        cep_str = str(cep_int).zfill(8)
        scoped = scoped[scoped[columns["cep"]].apply(lambda value: str(parse_cep(value) or "").zfill(8) == cep_str)]
    if stocks and columns.get("estoque"):
        wanted = {str(item).strip() for item in stocks}
        scoped = scoped[scoped[columns["estoque"]].astype(str).str.strip().isin(wanted)]

    counts = {weight: 0 for weight in weights}
    weight_col = columns.get("peso")
    if not weight_col or scoped.empty:
        return [0 for _ in weights]

    for value in scoped[weight_col]:
        peso = to_number(value)
        if peso is None:
            continue
        bucket = next((weight for weight in weights if peso <= weight), weights[-1])
        counts[bucket] += 1

    total = sum(counts.values())
    if total <= 0:
        return [0 for _ in weights]
    return [counts[weight] / total for weight in weights]


def _pedido_summary(pedidos: pd.DataFrame, cep: str, stocks: list[str], config: dict[str, Any]) -> dict[str, Any]:
    if pedidos.empty:
        return {"available": False, "warnings": ["Nenhum arquivo de pedidos carregado."]}

    validation = validate_pedidos(pedidos, config)
    if not validation["ok"]:
        return {"available": False, "warnings": [f"Pedidos sem campos obrigatorios: {', '.join(validation['missing'])}."]}

    columns = validation["columns"]
    cep_int = parse_cep(cep)
    scoped = pedidos.copy()
    if cep_int is not None and columns.get("cep"):
        cep_str = str(cep_int).zfill(8)
        scoped = scoped[scoped[columns["cep"]].apply(lambda value: str(parse_cep(value) or "").zfill(8) == cep_str)]
    if stocks and columns.get("estoque"):
        wanted = {str(item).strip() for item in stocks}
        scoped = scoped[scoped[columns["estoque"]].astype(str).str.strip().isin(wanted)]

    frete_pago = 0.0
    extra = 0.0
    for key in ("fretePago", "extra", "adicional", "avaria"):
        col = columns.get(key)
        if not col:
            continue
        total = sum((to_number(value) or 0.0) for value in scoped[col])
        if key == "fretePago":
            frete_pago += total
        else:
            extra += total

    return {
        "available": True,
        "orders": int(len(scoped)),
        "fretePago": frete_pago,
        "custosAdicionais": extra,
        "ticketMedioFrete": (frete_pago / len(scoped)) if len(scoped) else None,
        "warnings": [],
    }


def _pedido_summary_by_ranges(
    pedidos: pd.DataFrame,
    cep_ranges: list[dict[str, Any]],
    estbs: list[str],
    config: dict[str, Any],
) -> dict[str, Any]:
    if pedidos.empty:
        return {"available": False, "warnings": ["Nenhum arquivo de pedidos carregado."]}

    validation = validate_pedidos(pedidos, config)
    if not validation["ok"]:
        return {"available": False, "warnings": [f"Pedidos sem campos obrigatorios: {', '.join(validation['missing'])}."]}

    columns = validation["columns"]
    ranges: list[tuple[int, int]] = []
    for item in cep_ranges:
        ini = parse_cep(item.get("cepInicial"))
        fim = parse_cep(item.get("cepFinal"))
        if ini is not None and fim is not None:
            ranges.append(tuple(sorted((ini, fim))))

    scoped = pedidos.copy()
    if ranges and columns.get("cep"):
        def in_any_range(value: Any) -> bool:
            cep = parse_cep(value)
            return cep is not None and any(ini <= cep <= fim for ini, fim in ranges)
        scoped = scoped[scoped[columns["cep"]].apply(in_any_range)]

    if not _estbs_are_all(estbs) and columns.get("estoque"):
        wanted = {str(item).strip() for item in estbs}
        scoped = scoped[scoped[columns["estoque"]].astype(str).str.strip().isin(wanted)]

    frete_pago = 0.0
    extra = 0.0
    for key in ("fretePago", "extra", "adicional", "avaria"):
        col = columns.get(key)
        if not col:
            continue
        total = sum((to_number(value) or 0.0) for value in scoped[col])
        if key == "fretePago":
            frete_pago += total
        else:
            extra += total

    return {
        "available": True,
        "orders": int(len(scoped)),
        "fretePago": frete_pago,
        "custosAdicionais": extra,
        "ticketMedioFrete": (frete_pago / len(scoped)) if len(scoped) else None,
        "warnings": [],
    }


def _dataset_preview(df: pd.DataFrame, limit: int = 5) -> list[dict[str, Any]]:
    return [
        {str(key): safe_json_value(value) for key, value in row.items()}
        for row in df.head(limit).to_dict(orient="records")
    ]


def generate_analysis(params: dict[str, Any]) -> dict[str, Any]:
    config = merge_config(params.get("config"))
    cep_value = params.get("cep") or ""
    uf = str(params.get("uf") or "").strip()
    municipio = str(params.get("municipio") or "").strip()
    estbs = _normalize_estbs(params.get("estbs") if "estbs" in params else params.get("estb"))
    logistics_region = str(params.get("logisticsRegion") or "").strip()
    cep_mode = parse_cep(cep_value) is not None
    location_mode = bool(not cep_mode and uf and municipio and estbs)
    stocks = [str(item).strip() for item in params.get("estoques") or [] if str(item).strip()]
    if cep_mode or location_mode:
        stocks = [] if _estbs_are_all(estbs) else estbs
    source_id = params.get("sourceAnalysisId")

    vigentes, vigentes_files, vigentes_errors = load_dataset("contratos_vigentes")
    negociacoes, negociacoes_files, negociacoes_errors = load_dataset("contratos_negociacoes")
    pedidos, pedidos_files, pedidos_errors = load_dataset("pedidos")

    if vigentes.empty:
        raise ValueError("Nenhum contrato vigente encontrado em input/contratos_vigentes ou data/.")

    candidate = negociacoes if not negociacoes.empty else vigentes
    candidate_label = "CONTRATOS NEGOCIACOES" if not negociacoes.empty else "CONTRATOS VIGENTES"

    validations = {
        "contratos_vigentes": validate_contracts(vigentes, config),
        "contratos_negociacoes": validate_contracts(candidate, config),
    }
    if not validations["contratos_vigentes"]["ok"]:
        raise ValueError("Contratos vigentes com campos faltantes: " + ", ".join(validations["contratos_vigentes"]["missing"]))
    if not validations["contratos_negociacoes"]["ok"]:
        raise ValueError("Contratos negociacoes com campos faltantes: " + ", ".join(validations["contratos_negociacoes"]["missing"]))

    if cep_mode:
        contracts_for_cep = pd.concat([vigentes, candidate], ignore_index=True, sort=False)
        cep_info = _cep_info_for_contracts(cep_value, contracts_for_cep, config)
        coverage_candidate = _cep_coverage(candidate, cep_info, estbs, config)
        coverage_vigentes = _cep_coverage(vigentes, cep_info, estbs, config)
        candidate_scoped = candidate.loc[coverage_candidate.get("validIndexes") or []].copy()
        vigentes_scoped = vigentes.loc[coverage_vigentes.get("validIndexes") or []].copy()
        location_info = {**coverage_candidate["location"], "logisticsRegion": logistics_region}
        cep_ranges = coverage_candidate.get("cepRanges") or []
        if candidate_scoped.empty:
            raise ValueError("Nenhuma transportadora candidata valida para o CEP/ESTB selecionado.")
        if vigentes_scoped.empty:
            raise ValueError("Nenhum contrato vigente valido para o CEP/ESTB selecionado.")
    elif location_mode:
        coverage_candidate = _location_coverage(candidate, uf, municipio, estbs, config)
        coverage_vigentes = _location_coverage(vigentes, uf, municipio, estbs, config)
        candidate_scoped = candidate.loc[coverage_candidate.get("validIndexes") or []].copy()
        vigentes_scoped = vigentes.loc[coverage_vigentes.get("validIndexes") or []].copy()
        location_info = {**coverage_candidate["location"], "logisticsRegion": logistics_region}
        cep_info = None
        cep_ranges = coverage_candidate.get("cepRanges") or []
        if candidate_scoped.empty:
            raise ValueError("Nenhuma transportadora candidata valida para UF/Municipio/ESTB selecionados.")
        if vigentes_scoped.empty:
            raise ValueError("Nenhum contrato vigente valido para UF/Municipio/ESTB selecionados.")
    else:
        contracts_for_cep = pd.concat([vigentes, candidate], ignore_index=True, sort=False)
        cep_info = fallback_cep_from_contracts(cep_value, contracts_for_cep, config)
        if not cep_info.cep:
            raise ValueError(cep_info.error or "CEP invalido.")

        coverage_candidate = coverage_by_carrier(candidate, cep_info, config)
        coverage_vigentes = coverage_by_carrier(vigentes, cep_info, config)
        candidate_scoped = _filter_by_coverage(candidate, coverage_candidate, stocks, config)
        vigentes_scoped = _filter_by_coverage(vigentes, coverage_vigentes, stocks, config)
        location_info = {
            "uf": cep_info.uf,
            "municipio": cep_info.city,
            "estb": "Todos" if not stocks else ", ".join(stocks),
            "logisticsRegion": logistics_region,
        }
        cep_ranges = []
        if candidate_scoped.empty:
            raise ValueError("Nenhuma transportadora candidata valida para o CEP/estoque selecionado.")
        if vigentes_scoped.empty:
            raise ValueError("Nenhum contrato vigente valido para o CEP/estoque selecionado.")

    weights = build_weights(config)
    best_candidate = best_by_carrier_and_weight(candidate_scoped, weights, config)
    best_vigentes = best_by_carrier_and_weight(vigentes_scoped, weights, config)

    main_key = params.get("mainCarrier")
    if not main_key or main_key not in best_candidate:
        main_key = top_carriers(best_candidate, weights, 1)[0]

    secondary_keys = [key for key in params.get("secondaryCarriers") or [] if key in best_candidate and key != main_key]
    if not secondary_keys:
        raise ValueError("Selecione ao menos uma transportadora secundaria.")

    rows = [
        {**row_for_output(_carrier_display(main_key), main_key, candidate_label, best_candidate[main_key], weights), "role": "main"},
    ]
    for key in secondary_keys:
        rows.append({**row_for_output(_carrier_display(key), key, candidate_label, best_candidate[key], weights), "role": "secondary"})

    variations = [
        {"label": f"VARIACAO {rows[0]['label']} X {row['label']}", "targetKey": row["key"], "values": _variation(rows[0]["totals"], row["totals"])}
        for row in rows[1:]
    ]

    calc = []
    calc.extend(calc_rows(rows[0]["label"], main_key, candidate_label, best_candidate[main_key], weights))
    for row, key in zip(rows[1:], secondary_keys):
        calc.extend(calc_rows(row["label"], key, candidate_label, best_candidate[key], weights))

    if cep_mode and cep_info:
        pedido_summary = _pedido_summary(pedidos, cep_info.cep, stocks, config)
        representativity = _representativity_by_weights(pedidos, cep_info.cep, stocks, weights, config)
    elif location_mode:
        pedido_summary = _pedido_summary_by_ranges(pedidos, cep_ranges, estbs, config)
        representativity = [None for _ in weights]
    else:
        pedido_summary = _pedido_summary(pedidos, cep_info.cep, stocks, config)
        representativity = _representativity_by_weights(pedidos, cep_info.cep, stocks, weights, config)
    warnings = []
    warnings.extend(vigentes_errors)
    warnings.extend(negociacoes_errors)
    warnings.extend(pedidos_errors)
    warnings.extend(pedido_summary.get("warnings") or [])
    if cep_info and cep_info.error:
        warnings.append(cep_info.error)

    title_city = location_info.get("municipio") or "Cidade nao identificada"
    title_uf = location_info.get("uf") or "--"
    region_title = f" - {location_info.get('logisticsRegion')}" if location_info.get("logisticsRegion") else ""
    title = f"Analise de frete - {title_city}/{title_uf}{region_title} - ESTB {location_info.get('estb') or '--'}"
    analysis_date = str(params.get("analysisDate") or "").strip()
    analysis_name = str(params.get("analysisName") or "").strip() or title
    responsible = str(params.get("responsible") or "").strip()

    summary = {
        "mainCarrier": main_key,
        "secondaryCarriers": secondary_keys,
        "carrierCount": len(best_candidate),
        "validCarrierCount": len(coverage_candidate.get("validCarriers", [])),
        "invalidCarrierCount": len(coverage_candidate.get("invalidCarriers", [])),
        "weights": len(weights),
        "orders": pedido_summary.get("orders"),
    }

    analysis = {
        "title": title,
        "analysisDate": analysis_date,
        "analysisName": analysis_name,
        "responsible": responsible,
        "cep": cep_info.as_dict() if cep_info else {"cep": "", "city": title_city, "uf": title_uf, "ibge": None, "source": "location", "error": None},
        "location": location_info,
        "cepRanges": cep_ranges,
        "filters": {"estoques": stocks, "estb": location_info.get("estb"), "estbs": estbs, "logisticsRegion": logistics_region},
        "config": config,
        "source": {
            "candidateDataset": candidate_label,
            "contratosVigentesFiles": vigentes_files,
            "contratosNegociacoesFiles": negociacoes_files,
            "pedidosFiles": pedidos_files,
        },
        "validations": validations,
        "coverage": {
            "candidate": {k: v for k, v in coverage_candidate.items() if k != "validIndexes"},
            "vigentes": {k: v for k, v in coverage_vigentes.items() if k != "validIndexes"},
        },
        "weights": weights,
        "rows": rows,
        "variations": variations,
        "representativity": {"label": "REPRESENTATIVIDADE", "values": representativity},
        "calc": calc,
        "pedidoSummary": pedido_summary,
        "warnings": warnings,
        "summary": summary,
        "previews": {
            "contratosVigentes": _dataset_preview(vigentes),
            "contratosNegociacoes": _dataset_preview(negociacoes),
            "pedidos": _dataset_preview(pedidos),
        },
    }
    analysis["executive"] = build_executive_summary(analysis)

    return save_analysis(analysis, source_id=source_id)


def available_carriers(cep_value: Any, config: dict[str, Any] | None = None, use_negociacoes: bool = True) -> dict[str, Any]:
    cfg = merge_config(config)
    vigentes, _files, _errors = load_dataset("contratos_vigentes")
    negociacoes, _nfiles, _nerrors = load_dataset("contratos_negociacoes")
    df = negociacoes if use_negociacoes and not negociacoes.empty else vigentes
    if df.empty:
        raise ValueError("Nenhum arquivo de contrato encontrado.")
    cep_info = fallback_cep_from_contracts(cep_value, df, cfg)
    coverage = coverage_by_carrier(df, cep_info, cfg)
    return {k: v for k, v in coverage.items() if k != "validIndexes"}
