
from __future__ import annotations
import os
from typing import Tuple, List
import pandas as pd

class DataLoader:
    """
    Carrega dados apenas de um arquivo local definido em configuração.
    """
    def __init__(self, labels: List[str]):
        self.labels = labels

    def load_local_only(
        self,
        file_path: str,
        strict: bool = True
    ) -> Tuple[pd.DataFrame, str]:
        """
        Carrega exclusivamente do caminho 'file_path'.
        Retorna: (df, mensagem)
        Se strict=True, lança FileNotFoundError/Exception ao falhar.
        """
        if not os.path.exists(file_path):
            msg = f"Arquivo de dados não encontrado em: {file_path}"
            if strict:
                raise FileNotFoundError(msg)
            else:
                return pd.DataFrame(), msg

        try:
            if file_path.lower().endswith(".csv"):
                df = pd.read_csv(file_path)
            else:
                df = pd.read_excel(file_path)
            return df.copy(), f"Dados carregados de '{file_path}'."
        except Exception as e:
            msg = f"Erro ao ler arquivo '{file_path}': {e}"
            if strict:
                raise RuntimeError(msg)
            else:
                return pd.DataFrame(), msg
