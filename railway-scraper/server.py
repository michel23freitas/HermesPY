"""
server.py — FastAPI server para Railway
Guarda o último cardápio em memória e expõe via HTTP.
O Hermes no Pi consome GET /cardapio para obter o resultado.
"""

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime

import pytz
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from scraper import scrape

TZ = pytz.timezone("America/Sao_Paulo")

# Estado global em memória (Railway não tem disco persistente no free tier)
_estado = {
    "cardapio": None,           # último resultado do scraper
    "ultima_atualizacao": None, # ISO timestamp
    "rodando": False,           # lock para evitar scraping paralelo
}

API_TOKEN = os.getenv("API_TOKEN", "")  # token simples para proteger o endpoint


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Executa scraping inicial ao subir o servidor."""
    await executar_scraping()
    yield


app = FastAPI(
    title="Hermes Scraper",
    description="Cardápio do Marmitex Marisa para o Hermes",
    version="1.0.0",
    lifespan=lifespan,
)


async def executar_scraping():
    """Roda o scraper e atualiza o estado global."""
    if _estado["rodando"]:
        return  # Evita execuções paralelas
    _estado["rodando"] = True
    try:
        resultado = await scrape()
        _estado["cardapio"] = resultado
        _estado["ultima_atualizacao"] = datetime.now(TZ).isoformat()
    except Exception as e:
        if _estado["cardapio"] is None:
            _estado["cardapio"] = {"erro": str(e), "itens": []}
    finally:
        _estado["rodando"] = False


def verificar_token(request: Request):
    """Verifica o token de autenticação se API_TOKEN estiver configurado."""
    if not API_TOKEN:
        return  # Sem token configurado → acesso livre (dev)
    token = request.headers.get("X-API-Token", "")
    if token != API_TOKEN:
        raise HTTPException(status_code=401, detail="Token inválido")


@app.get("/")
async def health():
    """Health check — Railway usa isso para verificar que o serviço está vivo."""
    return {
        "status": "ok",
        "servico": "hermes-scraper",
        "ultima_atualizacao": _estado["ultima_atualizacao"],
        "tem_cardapio": _estado["cardapio"] is not None,
    }


@app.get("/cardapio")
async def get_cardapio(request: Request):
    """
    Retorna o cardápio mais recente.
    O Hermes no Pi chama este endpoint.
    Header opcional: X-API-Token
    """
    verificar_token(request)

    if _estado["cardapio"] is None:
        raise HTTPException(status_code=503, detail="Cardápio ainda não disponível. Aguarde o scraping inicial.")

    return JSONResponse(
        content={
            **_estado["cardapio"],
            "ultima_atualizacao": _estado["ultima_atualizacao"],
        }
    )


@app.post("/scrape")
async def forcar_scraping(request: Request):
    """
    Força um novo scraping manualmente.
    Útil para testar ou atualizar o cardápio fora do cron.
    """
    verificar_token(request)

    if _estado["rodando"]:
        return {"status": "ja_rodando", "msg": "Scraping em andamento, aguarde."}

    # Roda em background para não bloquear a resposta
    asyncio.create_task(executar_scraping())
    return {"status": "iniciado", "msg": "Scraping iniciado em background."}


@app.get("/status")
async def status(request: Request):
    """Status completo do serviço."""
    verificar_token(request)
    return {
        "rodando": _estado["rodando"],
        "ultima_atualizacao": _estado["ultima_atualizacao"],
        "tem_cardapio": _estado["cardapio"] is not None,
        "itens_count": len(_estado["cardapio"].get("itens", [])) if _estado["cardapio"] else 0,
        "aberto": _estado["cardapio"].get("aberto") if _estado["cardapio"] else None,
        "erro": _estado["cardapio"].get("erro") if _estado["cardapio"] else None,
    }
