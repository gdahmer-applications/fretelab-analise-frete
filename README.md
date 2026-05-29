# FreteLab - Analise de Fretes

Aplicacao para analise de frete por CEP, cidade, codigo IBGE, faixas de peso e generalidades contratuais. Em producao na Vercel, dados estruturados ficam no Supabase Postgres e arquivos ficam no Vercel Blob.

## Pastas de entrada local

```text
input/
├── contratos_vigentes/       contratos vigentes
├── pedidos/                  historico de pedidos
├── contratos_negociacoes/    arquivos manuais de negociacao
├── cep_ibge/                 base opcional de CEP/IBGE
└── regioes_logisticas/       municipios, faixas de CEP e regiao logistica
```

Arquivos aceitos: `.sqlite`, `.db`, `.xlsx`, `.xls` e `.csv`.

A base principal local pode ficar em `input/contratos_vigentes`. Na Vercel, use o modo ADM para registrar a base ativa no Supabase e armazenar os arquivos no Vercel Blob.

Padrao recomendado para producao na VM Ubuntu:

```text
input/
├── contratos_vigentes/dados.sqlite
├── contratos_negociacoes/negociacoes.sqlite
├── pedidos/pedidos.sqlite
├── cep_ibge/cep_ibge.sqlite
└── regioes_logisticas/regioes_logisticas.sqlite
```

O modo ADM do portal permite baixar, excluir e substituir bases inteiras. No replace pelo portal, envie um arquivo `.xlsx`; a aplicacao converte a primeira aba para o SQLite padronizado da pasta e preserva o Excel original em `origem/`. Para habilitar, defina a variavel de ambiente `FRETELAB_ADMIN_PASSWORD`.
A aplicacao tambem le um arquivo local `.env` na raiz do projeto quando a variavel de ambiente nao estiver definida.

Para contratos, o portal ADM aceita dois modelos de Excel:
- template FreteLab: `input/templates/template_contratos_fretelab.xlsx`;
- planilha Intelipost de frete por peso: o importador detecta `CEPI`/`CEPF`, normaliza faixas como `10.000` para `10`, infere ID/nome/CNPJ pelo nome do arquivo e cruza CEP com `regioes_logisticas.sqlite` para preencher cidade e UF quando possivel.

## Como executar

```bash
pip install -r requirements.txt
python app.py
```

Acesse:

- http://127.0.0.1:5000

No Windows, tambem pode usar:

```bat
executar.bat
```

## Fluxo de uso

1. Coloque os contratos vigentes em `input/contratos_vigentes`.
2. Coloque o historico de pedidos em `input/pedidos`.
3. Em producao, cadastre negociacoes pelo modo ADM; localmente, tambem e possivel usar `input/contratos_negociacoes`.
4. Abra a aplicacao e confira a `Home`, as paginas de entrada e o `Resumo da Base`.
5. Em `Analise`, informe CEP, confirme Regiao Logistica, UF, Municipio e ESTB, escolha a transportadora principal e as secundarias.
6. Gere a analise. Ela sera salva automaticamente no historico.
7. Use `Replicar para outro CEP` para comparar a mesma selecao em outras localidades dentro da sessao.
8. No `Historico`, filtre por data, nome, responsavel, CEP, transportadora, melhor transportadora e status.
9. Abra, duplique, compare, arquive, restaure ou exclua analises conforme necessario.
10. Gere HTML/PDF por analise ou relatórios consolidados da sessao.

## Visao executiva

A Home consolida indicadores do historico ativo:

- total de analises ativas e arquivadas;
- custo medio de frete analisado;
- melhor transportadora por custo medio;
- menor prazo medio;
- economia potencial estimada;
- ranking de transportadoras;
- CEPs/regioes com maior custo;
- insights automaticos de otimizacao.

A pagina de Analise exibe cards executivos por CEP, ranking de transportadoras, insights, badges de status e a tabela comparativa por faixa de peso. O HTML/PDF usa um template executivo proprio para evitar cortes e sobreposicoes.

## Abrangencia por CEP e IBGE

A aplicacao tenta resolver cidade, UF e codigo IBGE do CEP por esta ordem:

1. Base local em `input/cep_ibge`.
2. Cache em `app_settings` no Supabase quando `DATABASE_URL` existir, ou cache local em `storage/cep_cache.json` apenas em desenvolvimento.
3. Consulta BrasilAPI.
4. Fallback por contratos, quando necessario.

Quando o contrato possui campos de IBGE (`IBGE`, `IBGE INICIAL`, `IBGE FINAL` ou aliases), a abrangencia usa IBGE como criterio principal. Em bases legadas sem IBGE, a aplicacao usa faixa de CEP (`CEPI`/`CEPF`) e exibe o motivo como fallback.

## Regioes logisticas

A base em `input/regioes_logisticas` alimenta o filtro de Regiao Logistica e tambem a pagina de preview. A aplicacao cria a coluna virtual `Tipo`:

- `FAIXA UNICA` quando `UF - Localidade` aparece uma vez.
- `FAIXA 1`, `FAIXA 2`, `FAIXA 3` quando a localidade possui multiplas faixas.

## Historico

Em producao, as analises ficam na tabela `analyses` do Supabase. Em desenvolvimento sem `DATABASE_URL`, o fallback local continua em:

```text
storage/analises/
```

Cada nova geracao cria um arquivo novo. Versoes antigas nao sao sobrescritas.

## Configuracoes de ambiente

- `APP_HOST`: padrao `127.0.0.1`
- `APP_PORT`: padrao `5000`
- `FLASK_DEBUG`: padrao `0`
- `MAX_UPLOAD_MB`: padrao `30`
- `FRETELAB_ADMIN_PASSWORD`: senha para ativar o modo ADM no icone FreteLab
- `FRETELAB_SECRET_KEY`: chave de sessao Flask recomendada para producao
- `DATABASE_URL`: conexao Postgres do Supabase para historico, bases e auditoria
- `BLOB_READ_WRITE_TOKEN`: token do Vercel Blob para arquivos ADM, backups e exports opcionais
- `FRETELAB_LOGIN_EMAIL` e `FRETELAB_LOGIN_PASSWORD`: login basico da aplicacao
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM`: envio do codigo de 6 digitos por email

## Logs

Localmente, mensagens tecnicas ficam em:

```text
logs/frete_app.log
```

Na Vercel, logs devem ir para stdout/stderr do runtime. Veja `DEPLOY_DATABASE_STORAGE.md` para o fluxo completo de banco, storage, migracao e deploy.
