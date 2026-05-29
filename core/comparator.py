
from __future__ import annotations
from typing import List
import numpy as np
import pandas as pd

class FreightComparator:
    """
    Cálculo de diferença percentual vs transportadora principal
    e utilitários de exportação.
    """
    def __init__(self, labels: List[str]):
        self.labels = labels

    def diff_percent_vs_primary(self, df_wide: pd.DataFrame, primary: str) -> pd.DataFrame:
        primary_row = df_wide[df_wide['carrier'] == primary]
        if primary_row.empty:
            return pd.DataFrame(columns=self.labels)

        principal_series = primary_row.set_index('carrier').iloc[0]
        comparison = df_wide.set_index('carrier').copy()

        def calc(a, b):
            try:
                if pd.isna(a) or a == 0:
                    return np.nan
                return (b - a) / a * 100
            except Exception:
                return np.nan

        pct = comparison.copy()
        for col in self.labels:
            pct[col] = pct[col].apply(lambda v: calc(principal_series[col], v))

        return pct[self.labels]

    def to_csv_bytes(self, df: pd.DataFrame) -> bytes:
        return df.to_csv(index=False).encode("utf-8")
