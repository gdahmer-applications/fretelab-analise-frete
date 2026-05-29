Coloque aqui manualmente os arquivos de contratos em negociacao (`.xlsx`, `.xls`, `.csv`, `.sqlite` ou `.db`).

Use a mesma estrutura de colunas dos contratos vigentes:
- transportadora / nome
- cidade
- UF
- faixa de CEP ou codigo IBGE
- faixas numericas de peso
- prazo e taxas contratuais

Quando houver arquivos nesta pasta, eles passam a ser usados como base candidata da nova analise.
Quando estiver vazia, a aplicacao compara apenas dentro dos contratos vigentes.

No modo ADM, envie o template FreteLab ou uma planilha Intelipost de frete por peso em `.xlsx`; a aplicacao converte para `negociacoes.sqlite`.
