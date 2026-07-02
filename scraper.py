# scraper.py
# Roda via GitHub Actions. Acessa marmitexmarisa.com.br com Playwright,
# extrai cardápio do dia e salva em cardapio.json

import asyncio
import json
from datetime import datetime, timedelta

import pytz
from playwright.async_api import async_playwright

BASE_URL = "https://www.marmitexmarisa.com.br"
TIMEOUT_MS = 60000
TZ = pytz.timezone("America/Sao_Paulo")
DIAS_SEMANA = {
    0: "segunda-feira",
    1: "terça-feira",
    2: "quarta-feira",
    3: "quinta-feira",
    4: "sexta-feira",
    5: "sábado",
    6: "domingo",
}
DIAS_SEMANA_TITULO = {
    0: "Segunda-feira",
    1: "Terça-feira",
    2: "Quarta-feira",
    3: "Quinta-feira",
    4: "Sexta-feira",
    5: "Sábado",
    6: "Domingo",
}


def montar_url_cardapio(dia_semana_slug: str) -> str:
    return f"{BASE_URL}/cardapio/itens/cardapio-{dia_semana_slug}"


def montar_url_cardapio_mobile(dia_semana_slug: str) -> str:
    return f"{BASE_URL}/cardapio/itens/cardapio-{dia_semana_slug}?dvc=mobile&ed_mobile_iframe=1"


def resolver_dia_cardapio(agora: datetime) -> tuple[str, str]:
    # O site costuma virar o cardápio no fim da tarde; após 18h já mostramos o próximo dia.
    dia_base = agora
    if agora.hour >= 18:
        dia_base = agora + timedelta(days=1)

    return DIAS_SEMANA[dia_base.weekday()], DIAS_SEMANA_TITULO[dia_base.weekday()]


async def extrair_itens_do_dom(page, dia_semana_slug: str) -> list[dict]:
    return await page.evaluate(
        """(diaSemanaSlug) => {
            const normalizar = (texto) => (texto || '').replace(/\\s+/g, ' ').trim();
            const formatarPreco = (valor) => {
                const numero = Number.parseFloat(String(valor || '').replace(',', '.'));
                if (Number.isNaN(numero)) return null;
                return `R$ ${numero.toFixed(2).replace('.', ',')}`;
            };
            const itens = [];

            for (const card of document.querySelectorAll('.card-item-menu[data-dadositem]')) {
                let dados = {};
                try {
                    dados = JSON.parse(card.getAttribute('data-dadositem') || '{}');
                } catch {
                    dados = {};
                }

                if (dados.sessionLink && dados.sessionLink !== `cardapio-${diaSemanaSlug}`) {
                    continue;
                }

                const nome = normalizar(dados.nomeitem) || normalizar(card.querySelector('.nome-item-menu')?.textContent);
                const preco = formatarPreco(dados.precoitem) || normalizar(card.querySelector('.lowest-price')?.textContent).replace(/^.*?(R\\$\\s*\\d+[,.]\\d{2}).*$/, '$1');
                const descricao = normalizar(card.querySelector('.desc-item-menu')?.textContent) || null;

                if (nome && preco && !itens.some((item) => item.nome === nome && item.preco === preco)) {
                    itens.push({ nome, preco, descricao });
                }
            }

            return itens;
        }""",
        dia_semana_slug,
    )


async def scrape():
    agora = datetime.now(TZ)
    dia_semana_slug, _ = resolver_dia_cardapio(agora)
    url_cardapio = montar_url_cardapio(dia_semana_slug)
    url_cardapio_mobile = montar_url_cardapio_mobile(dia_semana_slug)
    resultado = {
        "data": agora.strftime("%Y-%m-%d"),
        "dia_semana": dia_semana_slug,
        "hora_scraping": agora.strftime("%H:%M"),
        "aberto": False,
        "itens": [],
        "url_pedido": url_cardapio,
        "url_scraping": url_cardapio_mobile,
    }

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 390, "height": 844})
        page.set_default_timeout(TIMEOUT_MS)
        page.set_default_navigation_timeout(TIMEOUT_MS)

        try:
            await page.goto(url_cardapio_mobile, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
            try:
                await page.wait_for_selector(".card-item-menu[data-dadositem]", state="attached", timeout=10000)
            except Exception:
                pass
        except Exception as e:
            resultado["erro"] = f"Timeout ao carregar site: {e}"
            with open("cardapio.json", "w", encoding="utf-8") as f:
                json.dump(resultado, f, ensure_ascii=False, indent=2)
            await browser.close()
            return

        fechado = (
            await page.query_selector("text=fechado")
            or await page.query_selector("text=Fechado")
            or await page.query_selector(".loja-fechada")
            or await page.query_selector("[class*='closed']")
        )

        if fechado:
            resultado["aberto"] = False
            resultado["itens"] = await extrair_itens_do_dom(page, dia_semana_slug)
        else:
            resultado["aberto"] = True
            resultado["itens"] = await extrair_itens_do_dom(page, dia_semana_slug)

        await browser.close()

    with open("cardapio.json", "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    print(json.dumps(resultado, ensure_ascii=False, indent=2))


asyncio.run(scrape())
