Coloque aqui os arquivos de historico de pedidos (`.xlsx`, `.xls`, `.csv`, `.sqlite` ou `.db`).

Colunas esperadas para analises de representatividade:
- `ID_PEDIDO`
- `DATA_PEDIDO`
- `ESTOQUE`
- `TRANSPORTADORA_UTILIZADA`
- `UF_DESTINO`
- `CEP_DESTINO`
- `PESO_KG`
- `VALOR_NOTA`
- `VALOR_FRETE_PAGO`
- `VALOR_FRETE_COTACAO`
- `DATA_ENTREGA_PREVISTA`
- `DATA_ENTREGA_REAL`

Minimo obrigatorio para validacao: CEP, peso e valor da nota.
Os dados originais nao sao sobrescritos pela aplicacao.
