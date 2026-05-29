Base principal de contratos vigentes.

Arquivos carregados pela aplicacao nesta pasta:
- `.sqlite` / `.db`: banco SQLite local, preferencial para bases consolidadas.
- `.xlsx`, `.xls` ou `.csv`: planilhas de contratos.

Arquivo atual:
- `dados.sqlite`: convertido de `data/dados.xlsx`, tabela `contratos_vigentes`.

Origem preservada:
- `origem/dados.xlsx`: arquivo Excel original, mantido apenas para auditoria e nao carregado automaticamente.

Templates/importacao:
- `../templates/template_contratos_fretelab.xlsx`: modelo recomendado para novas tabelas.
- Planilhas Intelipost de frete por peso tambem podem ser enviadas no modo ADM; a aplicacao converte e enriquece cidade/UF pela base de regioes logisticas.
