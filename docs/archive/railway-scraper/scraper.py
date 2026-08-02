"""
scraper.py — adaptado para Railway
Fluxo real do site marmitexmarisa.com.br:
  1. Abre a home
  2. Clica em "Faça seu pedido online"
  3. Verifica popup "Delivery online fechado" → define aberto true/false
  4. Clica OK no popup (se existir)
  5. Navega para /cardapio/itens/cardapio-[dia]
  6. Extrai itens
  7. Retorna dict (sem salvar arquivo local)
"""

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
    1: "terca-feira",
    2: "quarta-feira",
    3: "quinta-feira",
    4: "sexta-feira",
    5: "sabado",
    6: "domingo",
}


async def extrair_itens_do_dom(page, dia_semana_slug: str) -> list:
    return await page.evaluate(
        """(diaSemanaSlug) => {
            const normalizar = (texto) => (texto || '').replace(/\\s+/g, ' ').trim();
            const formatarPreco = (valor) => {
                const numero = parseFloat(String(valor || '').replace(',', '.'));
                if (isNaN(numero)) return null;
                return 'R$ ' + numero.toFixed(2).replace('.', ',');
            };
            const itens = [];

            for (const card of document.querySelectorAll('.card-item-menu[data-dadositem]')) {
                let dados = {};
                try { dados = JSON.parse(card.getAttribute('data-dadositem') || '{}'); }
                catch { dados = {}; }

                if (dados.sessionLink && dados.sessionLink !== 'cardapio-' + diaSemanaSlug) {
                    continue;
                }

                const nome = normalizar(dados.nomeitem) || normalizar(card.querySelector('.nome-item-menu')?.textContent);
                const preco = formatarPreco(dados.precoitem) || normalizar(card.querySelector('.lowest-price')?.textContent);
                const descricao = normalizar(card.querySelector('.desc-item-menu')?.textContent) || null;

                if (nome && preco && !itens.some(i => i.nome === nome && i.preco === preco)) {
                    itens.push({ nome, preco, descricao });
                }
            }
            return itens;
        }""",
        dia_semana_slug,
    )


async def scrape() -> dict:
    """Executa o scraping e retorna o resultado como dict (sem salvar arquivo)."""
    agora = datetime.now(TZ)

    # Após 15h o restaurante já publica o cardápio do dia seguinte
    if agora.hour >= 15:
        data_referencia = agora + timedelta(days=1)
    else:
        data_referencia = agora

    dia_semana_slug = DIAS_SEMANA[data_referencia.weekday()]
    url_cardapio = f"{BASE_URL}/cardapio/itens/cardapio-{dia_semana_slug}"

    resultado = {
        "data": agora.strftime("%Y-%m-%d"),
        "dia_semana": dia_semana_slug,
        "hora_scraping": agora.strftime("%H:%M"),
        "aberto": False,
        "itens": [],
        "url_pedido": url_cardapio,
        "erro": None,
    }

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )
        # Viewport mobile — site renderiza versão mobile
        page = await browser.new_page(viewport={"width": 390, "height": 844})
        page.set_default_timeout(TIMEOUT_MS)
        page.set_default_navigation_timeout(TIMEOUT_MS)

        try:
            # PASSO 1: Abre a home
            await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
            await page.wait_for_timeout(4000)  # tempo extra pro JS renderizar

            # PASSO 2: Clica em "Faca seu pedido online"
            botao_pedido = page.get_by_text("Faça seu pedido online", exact=False)
            if await botao_pedido.count() == 0:
                botao_pedido = page.locator("text=/faça seu pedido/i")

            if await botao_pedido.count() > 0:
                await botao_pedido.first.click()
                await page.wait_for_timeout(2000)
            else:
                resultado["erro"] = "Botão 'Faça seu pedido' não encontrado. Site pode ter bloqueado o acesso."
                await browser.close()
                return resultado

            # PASSO 3: Verifica se popup "Delivery fechado" apareceu
            popup = page.locator("text=Delivery online fechado")
            popup_visivel = await popup.count() > 0

            if popup_visivel:
                resultado["aberto"] = False
                ok_btn = page.locator("button:has-text('OK'), button:has-text('Ok')")
                if await ok_btn.count() > 0:
                    await ok_btn.first.click()
                    await page.wait_for_timeout(1000)
            else:
                resultado["aberto"] = True

            # PASSO 4: Navega para o cardápio do dia
            await page.goto(url_cardapio, wait_until="domcontentloaded", timeout=TIMEOUT_MS)

            # Aguarda os cards carregarem
            try:
                await page.wait_for_selector(".card-item-menu[data-dadositem]", state="attached", timeout=15000)
            except Exception:
                pass  # Tenta extrair mesmo assim

            # PASSO 5: Extrai itens
            resultado["itens"] = await extrair_itens_do_dom(page, dia_semana_slug)

        except Exception as e:
            resultado["erro"] = str(e)

        await browser.close()

    return resultado


if __name__ == "__main__":
    # Execução direta para testes locais
    resultado = asyncio.run(scrape())
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
