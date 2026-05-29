# Relatório de Validação - FreteLab V2

Data da validação: 2026-05-29

## Resultado geral

A aplicação Flask carregou corretamente, as dependências instalaram sem conflito e o fluxo principal de análise funcionou com a base incluída no pacote.

## Testes executados

- Descompactação e inspeção do projeto.
- Instalação de dependências via `requirements.txt` em ambiente virtual limpo.
- `python -m py_compile app.py core/*.py utils/*.py` sem erro.
- Importação do Flask app com 31 rotas registradas.
- `pip check` sem conflitos de dependências.
- Smoke test dos principais endpoints:
  - `/`
  - `/health`
  - `/api/files`
  - `/api/options`
  - `/api/preview`
  - `/api/cep/resolve`
  - `/api/carriers/location`
  - `/api/analyses`
  - export HTML/PDF por análise
  - endpoints ADM sem sessão
- Geração real de análise para CEP `95700000`, Bento Gonçalves/RS, ESTB `21`, com transportadora principal e secundárias.
- Exportação HTML e PDF da análise gerada.
- Remoção da análise de teste após validação.

## Achados críticos

1. O arquivo `.env` do pacote original continha senha ADM. A senha deve ser rotacionada e o `.env` não deve ser versionado nem enviado para Vercel.
2. A aplicação persiste histórico e bases em filesystem local. Isso é adequado para execução local/VM, mas não para persistência definitiva em Vercel/serverless.
3. O modo ADM substitui arquivos SQLite locais. Em Vercel, esse fluxo precisa ser migrado para banco externo e storage externo.

## Achados médios

1. `/api/preview?limit=abc` retornava erro 500. Corrigido neste pacote para retornar 400 com mensagem controlada.
2. Não há suíte automatizada de testes. Recomenda-se adicionar `pytest` com testes de cálculo, cobertura por CEP/IBGE e APIs principais.
3. Histórico em JSON pode ter concorrência frágil em ambiente com múltiplas instâncias.
4. Logs em arquivo local devem ser substituídos por logs stdout/stderr ou serviço de observabilidade.

## Banco recomendado

PostgreSQL, preferencialmente Neon para início gratuito/serverless ou Supabase se também quiser autenticação e storage integrados.

## Próximo passo recomendado

Antes de produção real na Vercel, migrar pelo menos `storage/analises/*.json` para PostgreSQL. Depois migrar uploads e substituição de bases para storage externo + tabelas de metadados.
