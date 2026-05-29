from __future__ import annotations

import math
import re
import unicodedata
from typing import Any, Iterable

import pandas as pd


def norm_key(value: Any) -> str:
    text = str(value or "").strip().upper()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", text)


def digits_only(value: Any) -> str:
    return re.sub(r"\D", "", str(value or ""))


def parse_cep(value: Any) -> int | None:
    digits = digits_only(value)
    if not digits or len(digits) > 8:
        return None
    return int(digits.zfill(8))


def parse_ibge(value: Any) -> int | None:
    digits = digits_only(value)
    if len(digits) < 6:
        return None
    return int(digits[:7])


def to_number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return None
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    cleaned = re.sub(r"[^\d,.\-]", "", text)
    if not cleaned or cleaned in {"-", ".", ","}:
        return None
    if "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        number = float(cleaned)
    except ValueError:
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def first_existing_column(columns: Iterable[Any], candidates: Iterable[str]) -> str | None:
    by_norm = {norm_key(col): str(col) for col in columns}
    for candidate in candidates:
        hit = by_norm.get(norm_key(candidate))
        if hit:
            return hit
    return None


def get_cell(row: pd.Series | dict[str, Any], column_name: str | None) -> Any:
    if not column_name:
        return None
    if isinstance(row, pd.Series):
        if column_name in row.index:
            return row[column_name]
        keys = row.index
    else:
        if column_name in row:
            return row[column_name]
        keys = row.keys()
    wanted = norm_key(column_name)
    for key in keys:
        if norm_key(key) == wanted:
            return row[key]
    return None


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(col).strip() for col in out.columns]
    out = out.dropna(how="all")
    return out.where(pd.notna(out), "")


def safe_json_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return None if math.isnan(value) or math.isinf(value) else value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def dataframe_sample(df: pd.DataFrame, limit: int = 50) -> list[dict[str, Any]]:
    return [
        {str(k): safe_json_value(v) for k, v in row.items()}
        for row in df.head(limit).to_dict(orient="records")
    ]
