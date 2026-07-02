# scraper.py
# Roda via GitHub Actions. Acessa marmitexmarisa.com.br com Playwright,
# extrai cardápio do dia e salva em cardapio.json

import asyncio
import json
from datetime import datetime
import re

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


def extrair_itens_do_bloco(texto_pagina: str, titulo_bloco: str) -> list[dict]:
    linhas = [linha.strip() for linha in texto_pagina.splitlines()]
    inicio = None
    for idx, linha in enumerate(linhas):
        if linha == f"### {titulo_bloco}":
            inicio = idx + 1
            break

    if inicio is None:
        return []

    fim = len(linhas)
    for idx in range(inicio, len(linhas)):
        if linhas[idx].startswith("### ") and linhas[idx] != f"### {titulo_bloco}":
            fim = idx
            break

    bloco = [linha for linha in linhas[inicio:fim] if linha and linha not in {"Comprar", "Indisponível"}]
    itens = []
    i = 0
    while i < len(bloco):
        nome = bloco[i]
        if nome.startswith("Nenhum item encontrado"):
            break

        if i + 2 >= len(bloco):
            break

        descricao = bloco[i + 1]
        preco = bloco[i + 2]

        if not preco.startswith("R$"):
            i += 1
            continue

        itens.append(
            {
                "nome": nome,
                "preco": preco,
                "descricao": descricao if not descricao.startswith("R$") else None,
            }
        )
        i += 3

    return itens


async def extrair_itens_do_dom(page, titulo_bloco: str) -> list[dict]:
    return await page.evaluate(
        """(tituloBloco) => {
            const normalizar = (texto) => (texto || '').replace(/\\s+/g, ' ').trim();
            const textoTitulo = normalizar(tituloBloco).toLowerCase();
            const headings = [...document.querySelectorAll('h1,h2,h3,h4,h5')];
            const heading = headings.find((h) => normalizar(h.textContent).toLowerCase() === textoTitulo);
            if (!heading) return [];

            const isHeading = (node) => node && /^H[1-5]$/.test(node.tagName);
            const itens = [];
            let node = heading.nextElementSibling;

            while (node && !isHeading(node)) {
                const texto = normalizar(node.innerText || node.textContent);
                const textoLower = texto.toLowerCase();

                if (texto && !["bebidas", "sobremesas", "promoções", "promocao", "promoção"].some((p) => textoLower.includes(p))) {
                    const precoMatch = texto.match(/R\\$\\s*\\d+(?:[.,]\\d{2})?/);
                    const nomeNode = node.querySelector('h1,h2,h3,h4,.nome,.title,[class*="name"]');
                    let nome = nomeNode ? normalizar(nomeNode.textContent) : '';

                    if (!nome) {
                        const linhas = texto.split('\\n').map(normalizar).filter(Boolean);
                        nome = linhas.find((linha) => !linha.toLowerCase().startsWith('r$') && !['comprar', 'indisponível', 'indisponivel'].includes(linha.toLowerCase())) || '';
                    }

                    if (nome && precoMatch) {
                        const linhas = texto.split('\\n').map(normalizar).filter(Boolean);
                        const nomeIndex = linhas.indexOf(nome);
                        const resto = nomeIndex >= 0 ? linhas.slice(nomeIndex + 1).filter((linha) => !linha.toLowerCase().startsWith('r$') && !['comprar', 'indisponível', 'indisponivel'].includes(linha.toLowerCase())) : [];
                        const descricao = resto[0] || null;
                        itens.push({
                            nome,
                            preco: precoMatch[0].replace('.', ','),
                            descricao,
                        });
                    }
                }

                node = node.nextElementSibling;
            }

            return itens;
        }""",
        titulo_bloco,
    )


async def scrape():
    agora = datetime.now(TZ)
    dia_semana_slug = DIAS_SEMANA[agora.weekday()]
    dia_semana_titulo = DIAS_SEMANA_TITULO[agora.weekday()]
    url_cardapio = montar_url_cardapio(dia_semana_slug)
    resultado = {
        "data": agora.strftime("%Y-%m-%d"),
        "dia_semana": dia_semana_slug,
        "hora_scraping": agora.strftime("%H:%M"),
        "aberto": False,
        "itens": [],
        "url_pedido": url_cardapio,
    }

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 390, "height": 844})
        page.set_default_timeout(TIMEOUT_MS)
        page.set_default_navigation_timeout(TIMEOUT_MS)

        try:
            await page.goto(url_cardapio, wait_until="networkidle", timeout=TIMEOUT_MS)
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
            resultado["itens"] = await extrair_itens_do_dom(page, f"Cardápio {dia_semana_titulo}")

        await browser.close()

    with open("cardapio.json", "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    print(json.dumps(resultado, ensure_ascii=False, indent=2))


asyncio.run(scrape())
