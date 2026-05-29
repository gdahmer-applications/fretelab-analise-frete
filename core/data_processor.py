
from __future__ import annotations
from typing import List
import numpy as np
import pandas as pd

class DataProcessor:
    """
    Converte e normaliza o DataFrame para o formato 'wide' esperado pelo app.
    Aceita:
      - Wide: colunas 'carrier' + labels de faixa
      - Long: colunas 'carrier','weight','price'
    """
    def __init__(self, labels: List[str], bins: List[int]):
        self.labels = labels
        self.bins = bins

    def ensure_wide(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        cols_lower = [c.lower().strip() for c in df.columns]

        # Caso wide (tem 'carrier' e alguma label)
        if ('carrier' in cols_lower) and any(l.lower() in cols_lower for l in self.labels):
            df = df.rename(columns={c: c.strip() for c in df.columns})
            return df

        # Caso long
        if set(['carrier','weight','price']).issubset(set(cols_lower)):
            rename_map = {}
            for c in df.columns:
                cl = c.lower().strip()
                if cl in ['carrier','weight','price']:
                    rename_map[c] = cl
            df = df.rename(columns=rename_map)

            def assign_label(w):
                try:
                    w = float(w)
                except Exception:
                    return None
                for i in range(len(self.bins) - 1):
                    low = self.bins[i] if i == 0 else self.bins[i] + 1
                    high = self.bins[i + 1]
                    if i == 0 and w <= high:
                        return self.labels[i]
                    if w >= low and w <= high:
                        return self.labels[i]
                return self.labels[-1]

            df['label'] = df['weight'].apply(assign_label)
            df_pivot = df.pivot_table(index='carrier', columns='label', values='price', aggfunc='mean')
            df_wide = df_pivot.reset_index()

            for lab in self.labels:
                if lab not in df_wide.columns:
                    df_wide[lab] = np.nan
            return df_wide

        # Formato desconhecido -> retorna vazio com colunas padrão
        out = pd.DataFrame(columns=['carrier'] + self.labels)
        return out
