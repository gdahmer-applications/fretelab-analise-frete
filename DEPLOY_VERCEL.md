# Deploy FreteLab na Vercel

## Status deste pacote

Este pacote foi higienizado para deploy inicial na Vercel:

- `.env` removido do pacote.
- `__pycache__`, logs e históricos locais removidos.
- `public/` criado para servir HTML/CSS/JS conforme recomendação da Vercel.
- `vercel.json` adicionado com rewrites para `/api/*` e `/health` apontarem para o Flask `app.py`.
- `pyproject.toml` fixa Python `>=3.12`.

## Variáveis obrigatórias na Vercel

Configure em Project Settings > Environment Variables:

```txt
FRETELAB_ADMIN_PASSWORD=<senha forte>
FRETELAB_SECRET_KEY=<chave aleatória forte>
MAX_UPLOAD_MB=30
FLASK_DEBUG=0
```

Não suba `.env` para GitHub/Vercel.

## Comandos locais

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Para testar pelo runtime da Vercel:

```bash
npm i -g vercel
vercel dev
```

Para publicar:

```bash
vercel login
vercel
vercel --prod
```

## Observação crítica sobre persistência

A aplicação atual usa arquivos locais para:

- bases em `input/*.sqlite`;
- histórico em `storage/analises/*.json`;
- logs em `logs/*.log`;
- substituição de bases pelo modo ADM.

Na Vercel, isso deve ser tratado como leitura/temporário. Para produção real, migre histórico, usuários, auditoria e configuração para PostgreSQL. Uploads de bases e arquivos originais devem ir para um storage externo, como Vercel Blob, Supabase Storage, Cloudflare R2 ou S3.


## Correção de entrypoint Vercel

Este pacote usa `api/index.py` como wrapper da aplicação Flask em `app.py`, porque a configuração `functions` da Vercel espera funções Python dentro da pasta `api/`.

O fluxo de rotas está configurado em `vercel.json` para enviar as requisições para `/api/index.py`.
