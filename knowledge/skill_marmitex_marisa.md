# SKILL: Marmitex Marisa

## Quando usar
Quando o usuário perguntar sobre cardápio, se o Marisa está aberto, ou quiser pedir marmita.

## Configuração

| Item | Valor |
|---|---|
| Restaurante | Marmitex Marisa |
| URL pedido | https://www.marmitexmarisa.com.br/cardapio/ |
| Fonte cardápio | `https://raw.githubusercontent.com/michel23freitas/HermesPY/main/cardapio.json` |
| Tool Hermes | `marmitex_cardapio` |
| Horário aviso automático | ~12h (dias úteis) |

## Regras operacionais
- Sempre ler cardapio.json antes de responder sobre o cardápio
- Se "aberto": false → informar fechado, não exibir cardápio
- Se "itens": [] mas "aberto": true → cardápio não carregou, enviar link direto
- Sempre anexar url_pedido ao final da resposta sobre cardápio
- Não inventar itens ou preços

## Fluxo obrigatório
1. Chamar tool marmitex_cardapio
2. Se fechado → "Marisa fechado hoje."
3. Se aberto e com itens → listar itens + link
4. Se aberto sem itens → "Cardápio indisponível. Acesse: [url]"

## Diagnóstico
- Verificar: curl https://raw.githubusercontent.com/michel23freitas/HermesPY/main/cardapio.json
- Se JSON vazio ou erro → workflow GitHub Actions falhou
- Rodar manualmente: aba Actions no GitHub → Run workflow

## Observações
- Site usa JavaScript (SPA). Scraping só funciona via Playwright no GitHub Actions.
- Scraper roda seg-sex às 11h30 BRT. Fins de semana não atualiza.
- Se restaurante mudar layout do site, os seletores CSS do scraper.py precisam de ajuste.
