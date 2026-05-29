from __future__ import annotations

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
WEB_DIR = BASE_DIR / "web"
STATIC_DIR = BASE_DIR / "static"

INPUT_DIR = BASE_DIR / "input"
CONTRATOS_VIGENTES_DIR = INPUT_DIR / "contratos_vigentes"
PEDIDOS_DIR = INPUT_DIR / "pedidos"
CONTRATOS_NEGOCIACOES_DIR = INPUT_DIR / "contratos_negociacoes"
CEP_IBGE_DIR = INPUT_DIR / "cep_ibge"
REGIOES_LOGISTICAS_DIR = INPUT_DIR / "regioes_logisticas"

LEGACY_DATA_DIR = BASE_DIR / "data"

STORAGE_DIR = BASE_DIR / "storage"
ANALISES_DIR = STORAGE_DIR / "analises"
EXPORTS_DIR = STORAGE_DIR / "exports"
LOGS_DIR = BASE_DIR / "logs"

SUPPORTED_EXTENSIONS = {".xlsx", ".xls", ".csv", ".sqlite", ".db"}

DEFAULT_CONFIG = {
    "weights": {"start": 20, "end": 200, "step": 20},
    "flags": {
        "addFixed": True,
        "addPerc": False,
        "applyMinFrete": False,
    },
    "nota": 1000,
    "columns": {
        "nome": "NOME",
        "id": "ID INTELIPOST",
        "estoque": "ESTOQUE",
        "cidade": "CIDADE",
        "uf": "UF",
        "cepInicial": "CEPI",
        "cepFinal": "CEPF",
        "ibgeInicial": "",
        "ibgeFinal": "",
        "ibge": "",
        "freteMinimo": "FRETE TOTAL MINIMO",
    },
    "pedidoColumns": {
        "id": "ID_PEDIDO",
        "data": "DATA_PEDIDO",
        "estoque": "ESTOQUE",
        "carrier": "TRANSPORTADORA_UTILIZADA",
        "uf": "UF_DESTINO",
        "cep": "CEP_DESTINO",
        "peso": "PESO_KG",
        "nota": "VALOR_NOTA",
        "fretePago": "VALOR_FRETE_PAGO",
        "freteCotacao": "VALOR_FRETE_COTACAO",
        "extra": "VALOR_DE_CUSTO_EXTRA_PAGO",
        "extraTipo": "TIPO_DE_VALOR_DE_CUSTO_EXTRA_PAGO",
        "prevista": "DATA_ENTREGA_PREVISTA",
        "real": "DATA_ENTREGA_REAL",
        "noPrazo": "ENTREGA_NO_PRAZO",
        "adicional": "VALOR_ADICIONAL",
        "motivo": "MOTIVO_ADICIONAL",
        "avaria": "VALOR_AVARIA_DEVOLUCAO",
    },
    "fixedFields": [
        "OUTRA TAXA VALOR FIXO",
        "TAS VALOR FIXO",
        "TDA VALOR FIXO",
        "TDE VALOR FIXO",
        "PEDAGIO VALOR FIXO",
        "COLETA VALOR FIXO",
        "CTE VALOR FIXO",
        "SECCAT VALOR FIXO",
        "ADEME VALOR FIXO",
        "SEGURO VALOR FIXO",
    ],
    "percentFields": [
        "SEGURO(%)",
        "GRIS(%)",
        "FRETE VALOR SOBRE A NOTA(%)",
    ],
}

CONTRACT_COLUMN_ALIASES = {
    "nome": ["NOME", "TRANSPORTADORA", "TRANSPORTADORA NOME"],
    "id": ["ID INTELIPOST", "ID", "CODIGO TRANSPORTADORA", "COD TRANSPORTADORA"],
    "estoque": ["ESTOQUE", "CD", "ORIGEM"],
    "cidade": ["CIDADE", "MUNICIPIO", "MUNICÍPIO", "CIDADE DESTINO"],
    "uf": ["UF", "ESTADO", "UF DESTINO"],
    "cepInicial": ["CEPI", "CEP INICIAL", "CEP_INICIAL", "CEP INI"],
    "cepFinal": ["CEPF", "CEP FINAL", "CEP_FINAL", "CEP FIM"],
    "ibge": ["IBGE", "CODIGO IBGE", "CÓDIGO IBGE", "COD IBGE", "CODIGO MUNICIPIO IBGE"],
    "ibgeInicial": ["IBGE INICIAL", "CODIGO IBGE INICIAL", "CÓDIGO IBGE INICIAL", "IBGEI"],
    "ibgeFinal": ["IBGE FINAL", "CODIGO IBGE FINAL", "CÓDIGO IBGE FINAL", "IBGEF"],
}

PEDIDO_REQUIRED_ALIASES = {
    "cep": ["CEP_DESTINO", "CEP", "CEP DESTINO"],
    "peso": ["PESO_KG", "PESO", "PESO KG"],
    "nota": ["VALOR_NOTA", "VALOR DA NOTA", "NOTA"],
}
