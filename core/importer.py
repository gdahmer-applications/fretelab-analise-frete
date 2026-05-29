from __future__ import annotations

from bisect import bisect_right
import re
from pathlib import Path
from typing import Any

import pandas as pd

from .logistics import load_logistics_table
from .normalization import clean_dataframe, first_existing_column, norm_key, parse_cep


CONTRACT_KINDS = {"contratos_vigentes", "contratos_negociacoes"}


RENAME_COLUMNS = {
    "FRETE TOTAL MINIMO": "FRETE TOTAL MINIMO",
    "FRETE TOTAL MINIMO R$": "FRETE TOTAL MINIMO",
    "FRETE TOTAL MÍNIMO": "FRETE TOTAL MINIMO",
    "PEDAGIO VALOR FIXO": "PEDAGIO VALOR FIXO",
    "PEDÁGIO VALOR FIXO": "PEDAGIO VALOR FIXO",
    "PEDAGIO FRACAO A CADA X KG": "PEDAGIO FRACAO A CADA x KG",
    "PEDÁGIO FRAÇÃO A CADA X KG": "PEDAGIO FRACAO A CADA x KG",
}


def load_xlsx_dataset(path: Path, kind: str) -> pd.DataFrame:
    if kind in CONTRACT_KINDS:
        return load_contract_xlsx(path)
    return clean_dataframe(pd.read_excel(path, sheet_name=0, dtype=object))


def load_contract_xlsx(path: Path) -> pd.DataFrame:
    raw = pd.read_excel(path, sheet_name=0, header=None, dtype=object)
    header_row = _find_contract_header(raw)
    if header_row is None:
        return clean_dataframe(pd.read_excel(path, sheet_name=0, dtype=object))

    df = _dataframe_from_header(raw, header_row)
    df = _normalize_contract_columns(df)
    if "CEPI" in df.columns and "CEPF" in df.columns:
        df = df[df["CEPI"].apply(parse_cep).notna() & df["CEPF"].apply(parse_cep).notna()].copy()
    if _looks_like_intelipost(df):
        df = _enrich_intelipost_contract(df, path)
    else:
        df = enrich_contract_location(df)
    return clean_dataframe(df)


def _find_contract_header(raw: pd.DataFrame) -> int | None:
    for idx in range(min(len(raw), 40)):
        values = [norm_key(value) for value in raw.iloc[idx].tolist()]
        if "CEPI" in values and "CEPF" in values:
            return idx
    return None


def _dataframe_from_header(raw: pd.DataFrame, header_row: int) -> pd.DataFrame:
    headers = [_normalize_header(value, pos) for pos, value in enumerate(raw.iloc[header_row].tolist())]
    data = raw.iloc[header_row + 1 :].copy()
    data.columns = headers
    keep_cols = [col for col in data.columns if col]
    data = data[keep_cols]
    data = data.dropna(how="all")
    return data


def _normalize_header(value: Any, pos: int) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip()
    if not text:
        return ""
    number = _weight_from_header(text)
    if number is not None:
        return str(number)
    normalized = norm_key(text)
    return RENAME_COLUMNS.get(normalized, text.strip())


def _weight_from_header(text: str) -> int | None:
    stripped = text.strip()
    if re.fullmatch(r"\d+\.0{3}", stripped):
        return int(stripped.split(".", 1)[0])
    cleaned = stripped.replace(",", ".")
    if not re.fullmatch(r"\d+(\.\d+)?", cleaned):
        return None
    value = float(cleaned)
    if value <= 0 or value > 100000:
        return None
    if abs(value - round(value)) < 0.0001:
        return int(round(value))
    return None


def _normalize_contract_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    renamed: dict[str, str] = {}
    for col in out.columns:
        text = str(col).strip()
        number = _weight_from_header(text)
        if number is not None:
            renamed[col] = str(number)
            continue
        renamed[col] = RENAME_COLUMNS.get(norm_key(text), text)
    out = out.rename(columns=renamed)
    return out.loc[:, [str(col).strip() != "" for col in out.columns]]


def _looks_like_intelipost(df: pd.DataFrame) -> bool:
    columns = {norm_key(col) for col in df.columns}
    return {"CEPI", "CEPF"}.issubset(columns) and "NOME" not in columns


def _enrich_intelipost_contract(df: pd.DataFrame, path: Path) -> pd.DataFrame:
    out = df.copy()
    meta = _metadata_from_filename(path)
    out.insert(0, "ID INTELIPOST", meta["id"])
    out.insert(1, "NOME", meta["name"])
    out.insert(2, "CNPJ", meta["cnpj"])
    if "ESTOQUE" not in out.columns:
        out.insert(3, "ESTOQUE", "")
    out = _expand_by_logistics(out)
    out["_FORMATO_ORIGEM"] = "intelipost_peso"
    return out


def enrich_contract_location(df: pd.DataFrame) -> pd.DataFrame:
    has_city = first_existing_column(df.columns, ["CIDADE", "MUNICIPIO", "MUNICÍPIO"])
    has_uf = first_existing_column(df.columns, ["UF"])
    if has_city and has_uf:
        missing_mask = (
            df[has_city].astype(str).str.strip().isin(["", "nan", "None"])
            | df[has_uf].astype(str).str.strip().isin(["", "nan", "None"])
        )
        if not bool(missing_mask.any()):
            return df
    return _expand_by_logistics(df)


def _metadata_from_filename(path: Path) -> dict[str, str]:
    stem = path.stem
    match = re.search(r"\bID\s*(\d+)\s*-\s*(.+?)(?:\s*-\s*(\d{14}))?(?:\s*-\s*\d+)?$", stem, flags=re.I)
    if not match:
        return {"id": "", "name": stem, "cnpj": ""}
    return {
        "id": match.group(1) or "",
        "name": (match.group(2) or stem).strip(),
        "cnpj": match.group(3) or "",
    }


def _expand_by_logistics(df: pd.DataFrame) -> pd.DataFrame:
    cep_ini_col = first_existing_column(df.columns, ["CEPI", "CEP INICIAL", "CEP_INICIAL", "CEP INI"])
    cep_fim_col = first_existing_column(df.columns, ["CEPF", "CEP FINAL", "CEP_FINAL", "CEP FIM"])
    if not cep_ini_col or not cep_fim_col:
        return df
    logistics = _logistics_ranges()
    if not logistics:
        out = df.copy()
        out["UF"] = ""
        out["CIDADE"] = ""
        return out
    starts = [item["ini"] for item in logistics]

    rows: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        ini = parse_cep(row.get(cep_ini_col))
        fim = parse_cep(row.get(cep_fim_col))
        if ini is None or fim is None:
            rows.append({**row.to_dict(), "UF": "", "CIDADE": ""})
            continue
        low, high = sorted((ini, fim))
        candidates = logistics[:bisect_right(starts, high)]
        hits = [item for item in candidates if item["fim"] >= low]
        if not hits:
            rows.append({**row.to_dict(), "UF": "", "CIDADE": ""})
            continue
        for hit in hits:
            rows.append({**row.to_dict(), "UF": hit["uf"], "CIDADE": hit["cidade"], "REGIAO LOGISTICA": hit["regiao"]})
    return pd.DataFrame(rows)


def _logistics_ranges() -> list[dict[str, Any]]:
    df = load_logistics_table()
    if df.empty:
        return []
    cep_ini = first_existing_column(df.columns, ["CEP INI", "CEP INICIAL", "CEPI"])
    cep_fim = first_existing_column(df.columns, ["CEP FIM", "CEP FINAL", "CEPF"])
    uf_col = first_existing_column(df.columns, ["UF"])
    city_col = first_existing_column(df.columns, ["Localidade", "LOCALIDADE", "Municipio", "Município"])
    region_col = first_existing_column(df.columns, ["logisticsRegion", "Regiao Logistica", "Região Logística"])
    if not cep_ini or not cep_fim:
        return []

    ranges: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        ini = parse_cep(row.get(cep_ini))
        fim = parse_cep(row.get(cep_fim))
        if ini is None or fim is None:
            continue
        low, high = sorted((ini, fim))
        ranges.append({
            "ini": low,
            "fim": high,
            "uf": str(row.get(uf_col) or "") if uf_col else "",
            "cidade": str(row.get(city_col) or "") if city_col else "",
            "regiao": str(row.get(region_col) or "") if region_col else "",
        })
    return sorted(ranges, key=lambda item: item["ini"])
