from __future__ import annotations

from typing import Any

import pandas as pd

from .normalization import first_existing_column, parse_cep, safe_json_value
from .repository import load_dataset


LOGISTICS_COLUMNS = {
    "uf": ["UF"],
    "localidade": ["Localidade", "LOCALIDADE", "Municipio", "Município"],
    "nome_unico": ["Nome Único", "Nome Unico", "UF - LOCALIDADE"],
    "cep_ini": ["CEP INI", "CEP INICIAL", "CEPI"],
    "cep_fim": ["CEP FIM", "CEP FINAL", "CEPF"],
    "region": ["logisticsRegion", "Regiao Logistica", "Região Logística"],
}


def _columns(df: pd.DataFrame) -> dict[str, str | None]:
    return {key: first_existing_column(df.columns, aliases) for key, aliases in LOGISTICS_COLUMNS.items()}


def load_logistics_table() -> pd.DataFrame:
    df, _files, _errors = load_dataset("regioes_logisticas")
    if df.empty:
        return df

    cols = _columns(df)
    if not cols.get("nome_unico") and cols.get("uf") and cols.get("localidade"):
        df["Nome Único"] = df[cols["uf"]].astype(str).str.strip() + " - " + df[cols["localidade"]].astype(str).str.strip()
        cols["nome_unico"] = "Nome Único"

    name_col = cols.get("nome_unico")
    if name_col:
        group_sizes = df.groupby(name_col, dropna=False)[name_col].transform("size")
        seq = df.groupby(name_col, dropna=False).cumcount() + 1
        df["Tipo"] = ["FAIXA UNICA" if size == 1 else f"FAIXA {idx}" for size, idx in zip(group_sizes, seq)]
    elif "Tipo" not in df.columns:
        df["Tipo"] = "FAIXA UNICA"

    return df


def logistics_metadata() -> dict[str, Any]:
    df = load_logistics_table()
    if df.empty:
        return {"available": False, "regions": [], "rows": 0, "columns": []}
    cols = _columns(df)
    region_col = cols.get("region")
    regions = sorted({str(v).strip() for v in df[region_col].dropna() if str(v).strip()}) if region_col else []
    return {"available": True, "regions": regions, "rows": len(df), "columns": list(df.columns)}


def logistics_options(region: str | None = None, uf: str | None = None) -> dict[str, Any]:
    df = load_logistics_table()
    if df.empty:
        return {"regions": [], "ufs": [], "municipios": []}
    cols = _columns(df)
    scoped = df
    region_col = cols.get("region")
    uf_col = cols.get("uf")
    city_col = cols.get("localidade")

    regions = sorted({str(v).strip() for v in df[region_col].dropna() if str(v).strip()}) if region_col else []
    if region and region_col:
        scoped = scoped[scoped[region_col].astype(str).str.strip() == str(region).strip()]
    ufs = sorted({str(v).strip() for v in scoped[uf_col].dropna() if str(v).strip()}) if uf_col else []
    if uf and uf_col:
        scoped = scoped[scoped[uf_col].astype(str).str.strip() == str(uf).strip()]
    municipios = sorted({str(v).strip() for v in scoped[city_col].dropna() if str(v).strip()}) if city_col else []
    return {"regions": regions, "ufs": ufs, "municipios": municipios}


def resolve_cep_in_logistics(cep_value: Any) -> dict[str, Any] | None:
    cep = parse_cep(cep_value)
    if cep is None:
        return None
    df = load_logistics_table()
    if df.empty:
        return None
    cols = _columns(df)
    ini_col = cols.get("cep_ini")
    fim_col = cols.get("cep_fim")
    if not ini_col or not fim_col:
        return None

    for _, row in df.iterrows():
        ini = parse_cep(row.get(ini_col))
        fim = parse_cep(row.get(fim_col))
        if ini is None or fim is None:
            continue
        low, high = sorted((ini, fim))
        if low <= cep <= high:
            return {
                "cep": str(cep).zfill(8),
                "uf": safe_json_value(row.get(cols.get("uf"))),
                "city": safe_json_value(row.get(cols.get("localidade"))),
                "logisticsRegion": safe_json_value(row.get(cols.get("region"))),
                "tipo": safe_json_value(row.get("Tipo")),
                "cepInicial": str(low).zfill(8),
                "cepFinal": str(high).zfill(8),
                "source": "regioes_logisticas",
            }
    return None


def preview_logistics(limit: int = 100, query: str = "") -> tuple[list[str], list[dict[str, Any]]]:
    df = load_logistics_table()
    if df.empty:
        return [], []
    if query:
        mask = pd.Series(False, index=df.index)
        for col in df.columns:
            mask = mask | df[col].astype(str).str.contains(query, case=False, na=False)
        df = df[mask]
    rows = [
        {str(key): safe_json_value(value) for key, value in row.items()}
        for row in df.head(limit).to_dict(orient="records")
    ]
    return list(df.columns), rows

