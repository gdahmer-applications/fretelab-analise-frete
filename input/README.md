Entrada de dados da aplicacao.

Todas as bases operacionais devem ficar dentro desta pasta para que o projeto continue funcionando depois de movido para outro diretorio.

Pastas:
- `contratos_vigentes`: base principal de contratos ativos/vigentes. A base atual esta em `dados.sqlite`.
- `contratos_negociacoes`: contratos candidatos para comparacao. Padrao: `negociacoes.sqlite`.
- `pedidos`: historico de pedidos para representatividade, frete pago e prazo. Padrao: `pedidos.sqlite`.
- `cep_ibge`: base local opcional para resolver CEP, cidade, UF e IBGE. Padrao: `cep_ibge.sqlite`.
- `regioes_logisticas`: faixas de CEP, municipio, UF e regiao logistica. A base atual esta em `regioes_logisticas.sqlite`.

Formatos aceitos pela aplicacao: `.sqlite`, `.db`, `.xlsx`, `.xls` e `.csv`.

Evite colocar arquivos de exemplo com extensoes aceitas nestas pastas, pois a aplicacao carrega automaticamente tudo que encontrar.

No modo ADM do portal, o replace inteiro deve receber um arquivo `.xlsx`. A aplicacao converte a primeira aba para o arquivo SQLite padronizado da pasta e move o Excel original para `origem/`.
