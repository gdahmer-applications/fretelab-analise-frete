Base de regioes logisticas por UF, localidade e faixa de CEP.

Arquivos aceitos: `.xlsx`, `.xls`, `.csv`, `.sqlite` ou `.db`.

Arquivo atual:
- `regioes_logisticas.sqlite`: base operacional em tabela SQLite.

Origem preservada:
- `origem/1 faixas_cep_correios_consolidado.xlsx`: planilha original mantida apenas para auditoria.

A aplicacao cria uma coluna virtual `Tipo` durante a leitura:

- `FAIXA UNICA` para localidade sem repeticao.
- `FAIXA 1`, `FAIXA 2`, `FAIXA 3` para localidades com mais de uma faixa.
