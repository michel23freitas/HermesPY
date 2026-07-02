# scraper.py
# Roda via GitHub Actions. Acessa marmitexmarisa.com.br com Playwright,
# extrai cardápio do dia e salva em cardapio.json

import json
import asyncio
from datetime import datetime

import pytz
from playwright.async_api import async_playwright

URL = "https://www.marmitexmarisa.com.br/cardapio/"
TZ = pytz.timezone("America/Sao_Paulo")


async def scrape():
    agora = datetime.now(TZ)
    resultado = {
        "data": agora.strftime("%Y-%m-%d"),
        "dia_semana": agora.strftime("%A"),
        "hora_scraping": agora.strftime("%H:%M"),
        "aberto": False,
        "itens": [],
        "url_pedido": URL,
    }

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            await page.goto(URL, wait_until="networkidle", timeout=60000)
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
        else:
            resultado["aberto"] = True

            itens_els = await page.query_selector_all(
                ".product-item, .item-cardapio, [class*='product'], [class*='item']"
            )

            itens = []
            for el in itens_els:
                nome_el = await el.query_selector("h2, h3, .nome, .title, [class*='name']")
                preco_el = await el.query_selector(".preco, .price, [class*='price'], [class*='valor']")
                desc_el = await el.query_selector(".descricao, .description, [class*='desc']")

                nome = (await nome_el.inner_text()).strip() if nome_el else None
                preco = (await preco_el.inner_text()).strip() if preco_el else None
                descricao = (await desc_el.inner_text()).strip() if desc_el else None

                if nome:
                    itens.append(
                        {
                            "nome": nome,
                            "preco": preco,
                            "descricao": descricao,
                        }
                    )

            resultado["itens"] = itens

        await browser.close()

    with open("cardapio.json", "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    print(json.dumps(resultado, ensure_ascii=False, indent=2))


asyncio.run(scrape())
