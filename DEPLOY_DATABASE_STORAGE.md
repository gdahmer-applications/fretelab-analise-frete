# FreteLab: Supabase Postgres + Vercel Blob

## Objetivo

O FreteLab agora usa Supabase Postgres para dados estruturados e Vercel Blob para arquivos. Em producao na Vercel, `storage/`, `logs/` e `input/` nao devem ser usados como persistencia definitiva. O diretorio `/tmp` e usado somente durante processamento da funcao serverless.

## Variaveis de ambiente

Configure na Vercel e no `.env` local:

```txt
DATABASE_URL=postgresql://postgres:<password>@<host>:5432/postgres?sslmode=require
BLOB_READ_WRITE_TOKEN=<token do Vercel Blob>
FRETELAB_SECRET_KEY=<chave forte>
FRETELAB_ADMIN_PASSWORD=<senha forte>
MAX_UPLOAD_MB=30
FLASK_DEBUG=0
ENABLE_CEP_API=1
```

`SUPABASE_URL` e `SUPABASE_SERVICE_ROLE_KEY` podem ficar cadastradas para automacoes futuras, mas a aplicacao usa `DATABASE_URL` no backend. Nunca exponha service role key no frontend.

## Criacao do banco

1. Abra o SQL Editor do Supabase.
2. Execute `migrations/001_database_storage.sql`.
3. Confirme que as tabelas `analyses`, `uploaded_files`, `dataset_versions`, `dataset_active_versions`, `admin_audit_logs` e `app_settings` foram criadas.
4. Use uma connection string com SSL em `DATABASE_URL`.

## Migrar historico JSON existente

Depois de configurar `DATABASE_URL` localmente:

```bash
pip install -r requirements.txt
python scripts/migrate_history_to_supabase.py
```

Para migrar de outro diretorio:

```bash
python scripts/migrate_history_to_supabase.py /caminho/para/storage/analises
```

O script faz upsert pelo `id` da analise, entao pode ser executado novamente.

## Fluxo ADM de bases

- Uploads `.xlsx` do ADM sao processados em `/tmp/fretelab/...`.
- O Excel original e salvo no Vercel Blob em `datasets/original/<kind>/`.
- Um SQLite de backup pode ser gerado e salvo no Blob em `datasets/sqlite/<kind>/`.
- Os dados consultaveis entram em `dataset_versions.rows_json`.
- `dataset_active_versions` define a versao ativa consumida pelas rotas de analise.
- Toda alteracao ADM relevante grava um registro em `admin_audit_logs`.

Na Vercel, Functions tem limite de payload de 4,5 MB. Uploads maiores que isso devem ser enviados por um fluxo direto ao Blob ou via ferramenta operacional antes de serem processados. O endpoint Flask atual continua aceitando uploads pequenos e salva o resultado em Blob/Postgres.

## Healthcheck

`/health` retorna:

- `databaseConfigured` e `databaseOk`
- `blobConfigured` e `blobOk`
- `persistenceMode`

Valores esperados em producao:

```json
{
  "status": "ok",
  "databaseConfigured": true,
  "databaseOk": true,
  "blobConfigured": true,
  "blobOk": true,
  "persistenceMode": "supabase_postgres+vercel_blob"
}
```

Se `DATABASE_URL` faltar na Vercel, operacoes persistentes retornam erro claro em vez de gravar no filesystem local.

## Exports

PDFs e HTMLs continuam sendo gerados sob demanda em memoria. Para salvar uma copia no Blob, use `save=1` em exports individuais:

```txt
/api/analyses/<analysis_id>/export/pdf?save=1
/api/analyses/<analysis_id>/export/html?save=1
```

Para export consolidado de sessao, envie `"save": true` no JSON do POST.

## Limites do plano gratuito

- Vercel Blob Hobby: armazenamento e operacoes mensais limitadas; ao exceder, uploads/leitura podem falhar ate renovacao do ciclo ou upgrade.
- Supabase Free: banco pequeno, egress limitado e pausa por inatividade. Bases grandes em `rows_json` podem consumir cota rapidamente.
- Conversao de Excel grande em serverless pode bater limite de tempo/memoria. Para bases pesadas, prefira processamento assinado/dedicado ou plano superior.
