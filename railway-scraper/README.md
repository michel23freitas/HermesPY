# railway-scraper — Hermes Scraper Service

Serviço Railway que scrapa o cardápio do Marmitex Marisa e expõe via HTTP para o Hermes (Raspberry Pi) consumir.

## Endpoints

| Endpoint | Método | Descrição |
|---|---|---|
| `GET /` | — | Health check (sem auth) |
| `GET /cardapio` | — | Retorna o cardápio mais recente |
| `GET /status` | — | Status detalhado do serviço |
| `POST /scrape` | — | Força novo scraping manualmente |

> Se `API_TOKEN` estiver configurado, todos os endpoints (exceto `/`) exigem o header `X-API-Token: <token>`.

## Variáveis de Ambiente (Railway)

| Variável | Obrigatória | Descrição |
|---|---|---|
| `API_TOKEN` | Não | Token para proteger os endpoints. Se vazio, acesso livre. |
| `PORT` | Não | Porta do servidor (Railway injeta automaticamente) |

## Como usar no Hermes (Pi)

No `hermes.py`, a ferramenta `marmitex_cardapio` deve ser atualizada para chamar este serviço:

```python
import requests

RAILWAY_URL = os.getenv("RAILWAY_SCRAPER_URL", "")  # ex: https://xxx.railway.app
RAILWAY_TOKEN = os.getenv("RAILWAY_TOKEN", "")

def tool_marmitex_cardapio():
    if not RAILWAY_URL:
        return "❌ RAILWAY_SCRAPER_URL não configurado."
    try:
        headers = {"X-API-Token": RAILWAY_TOKEN} if RAILWAY_TOKEN else {}
        r = requests.get(f"{RAILWAY_URL}/cardapio", headers=headers, timeout=10)
        if r.status_code != 200:
            return f"❌ Erro do scraper: {r.status_code}"
        data = r.json()
        if data.get("erro"):
            return f"⚠️ Scraper com erro: {data['erro']}"
        status = "✅ Aberto" if data.get("aberto") else "🔴 Fechado"
        itens = data.get("itens", [])
        if not itens:
            return f"{status} — Nenhum item no cardápio de hoje."
        linhas = [f"{status} — {data.get('dia_semana', '')} ({data.get('hora_scraping', '')}):"]
        for item in itens:
            linhas.append(f"• {item['nome']} — {item['preco']}")
        linhas.append(f"\n🔗 {data.get('url_pedido', '')}")
        return "\n".join(linhas)
    except Exception as e:
        return f"❌ Erro ao consultar scraper: {e}"
```

## Deploy no Railway

1. Crie um novo projeto em [railway.app](https://railway.app)
2. Conecte este repositório (ou faça upload via CLI: `railway up`)
3. Railway detecta o `Dockerfile` automaticamente
4. Configure a variável `API_TOKEN` no painel do Railway (opcional mas recomendado)
5. Configure `RAILWAY_SCRAPER_URL` e `RAILWAY_TOKEN` no `.env` do Hermes (Pi)

## Arquitetura

```
Railway (cloud)
  └── server.py (FastAPI)
        ├── GET /cardapio  ←── Hermes Pi consome aqui
        └── scraper.py (Playwright + Chromium)
              └── marmitexmarisa.com.br
```

## Notas sobre o Railway free tier

- **500h/mês** de execução — suficiente para serviço contínuo por ~20 dias.
- Para economizar horas: configure o serviço para **hibernar** quando não receber requests (Railway faz isso automaticamente após inatividade).
- O cardápio fica em memória — se o serviço hibernar e acordar, faz novo scraping no startup.
