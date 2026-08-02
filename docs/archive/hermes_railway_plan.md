# Hermes + Railway — Plano de Integração

## Problem Statement
> *Como monitorar o Pi inteiro (não só o Hermes) a partir da cloud, garantir alertas mesmo com queda de energia/internet, e rodar o scraper do Marmitex num ambiente que não seja bloqueado por captcha — sem sobrecarregar o Raspberry Pi 3?*

---

## Direção 1: Railway como "Guardian do Pi" (Watchdog Ampliado)

### O que faz
- Verifica se o Pi está online a cada **1 hora** (não 60s)
- Monitora mais do que o Hermes: **ping geral do Pi**, opcionalmente porta do HA (8123) e Netdata (19999)
- Se o Pi não responder → envia alerta no Telegram
- Se o Pi voltar a responder → envia confirmação de recuperação
- Pode checar IP público do Pi e avisar se mudou (útil pra quem usa IP dinâmico)

### Implementação no Railway
```
railway-guardian/
  main.py          ← loop de checagem + Telegram alert
  requirements.txt ← requests, pyTelegramBotAPI
  Procfile         ← worker: python main.py
```

**Lógica principal:**
```python
# Checa a cada 1h se o Pi responde
# Endpoints a monitorar (configuráveis via env vars):
# PI_HOST = IP ou domínio do Pi (Tailscale, DDNS, etc.)
# Portas: 80 (nginx?), 8123 (HA), 19999 (Netdata)
```

### Limitações a aceitar (Not Doing por ora)
- ❌ Não vai checar RAM/temperatura (precisa do Pi online pra isso)
- ❌ Não vai reiniciar serviços remotamente (fora do escopo do Railway)
- ❌ Railway free tem **500h/mês** = ~21 dias rodando 24/7. Como worker contínuo, vai hibernar no fim do mês. Solução: usar Railway como **cron job** (trigger a cada hora) em vez de processo contínuo.

### Assumption a validar
- [ ] O Pi tem IP acessível externamente (IP fixo, DDNS, ou Tailscale) para o Railway alcançar
- [ ] Se usar Tailscale: o Railway precisaria de um exit node ou integração VPN (complexo no free tier)
- [ ] Alternativa simples: Railway só checa via HTTP público — se você não tiver IP público, não funciona sem túnel

> **Recomendação:** Se o Pi não tem IP público estável, considerar **Uptime Robot** (gratuito, especializado nisso) em vez do Railway. Mas se quiser manter tudo num lugar só, Railway funciona como cron.

---

## Direção 2: Railway como Worker do Scraper (Marmitex)

### O Problema Real
O GitHub Actions usa IPs de datacenters conhecidos → o site identifica e bloqueia com captcha.
O Railway usa IPs de providers de cloud **menos conhecidos** e com rotação → menor chance de bloqueio.

### O que faz
- Roda o `scraper.py` com **Playwright** no Railway
- Executa de manhã (ex: 10:00 BRT via cron)
- Salva o resultado num **endpoint HTTP simples** (pode ser o próprio servidor Railway ou um storage externo)
- O Hermes no Pi faz `requests.get()` para buscar o cardápio já processado

### Implementação no Railway

```
railway-scraper/
  scraper.py           ← o scraper atual adaptado
  server.py            ← FastAPI/Flask mini servidor que guarda o último cardápio
  requirements.txt     ← playwright, fastapi, uvicorn
  Procfile             ← web: uvicorn server:app
```

**Fluxo:**
```
Railway Cron (10h) → scraper.py → salva resultado em memória/arquivo
Hermes (Pi)        → GET railway-scraper.railway.app/cardapio → retorna JSON
```

### Assumptions Críticas a Validar ANTES de implementar

- [ ] **Playwright roda no Railway free?** Chromium precisa de ~300MB RAM + libs extras. O free tier tem ~512MB. **TESTE OBRIGATÓRIO** antes de construir tudo.
- [ ] **O Railway free tem cron nativo?** Sim, via "Cron Service" no dashboard Railway — pode agendar `python scraper.py` sem precisar de loop.
- [ ] **O site ainda bloqueia no Railway?** IPs do Railway são cloud, mas menos conhecidos que GitHub Actions. **Precisa testar** com o site real.
- [ ] **E se bloquear?** Fallback: usar proxy residencial (brightdata free tier) ou User-Agent rotation.

### MVP Scope (o mínimo que testa a hipótese)
1. Criar projeto Railway com `scraper.py` mínimo (só abre a URL e verifica se carrega sem captcha)
2. Se carregar: construir o scraper completo + endpoint
3. Hermes Pi consome o endpoint em vez de rodar o scraper localmente

---

## Arquitetura Final (se ambas funcionarem)

```
                     CLOUD (Railway)
              ┌─────────────────────────────┐
              │  Guardian Worker (cron/1h)  │
              │  Scraper Worker (cron/10h)  │
              │  → cardapio endpoint HTTP   │
              └───────────┬─────────────────┘
                          │ HTTP
              ┌───────────▼─────────────────┐
              │   Raspberry Pi 3 (LAN)      │
              │   Hermes (bot Telegram)     │
              │   Home Assistant            │
              │   Netdata                   │
              └─────────────────────────────┘
```

**Pi faz:** controle local (HA, Docker, sensores, WoL, memória)
**Railway faz:** vigilância externa, scraping pesado, tarefas agendadas

---

## Not Doing (e Por Quê)

- **Mover o bot Telegram para o Railway** — o bot precisa de acesso à LAN para controlar HA/Docker/sensores. Separar isso criaria um canal de comunicação Pi↔Railway desnecessariamente complexo.
- **Módulo de IA no Railway** — adiciona latência + complexidade sem ganho real (OpenRouter já é externo, o Pi só faz a chamada HTTP).
- **Hermes Lite no Railway (API HTTP)** — boa ideia a longo prazo (está no roadmap), mas não agora. O MVP da API HTTP deve ser construído primeiro localmente.
- **Monitoramento em tempo real (a cada 60s)** — desnecessário e vai consumir as 500h do Railway free em 20 dias.

---

## Próximos Passos (em ordem)

### Esta semana
1. **Testar Playwright no Railway** (30min) — cria um projeto mínimo, instala playwright, faz `page.goto(url)` e verifica se carrega sem captcha
2. Se funcionar → **implementar Guardian** (é mais simples, 2h de trabalho)
3. **Implementar Scraper** baseado no resultado do teste

### Próximo sprint
4. Conectar Hermes no Pi para consumir o endpoint do cardápio Railway
5. Configurar alertas do Guardian via Telegram

---

## Open Questions

- O Pi tem IP público acessível externamente? (ou usa Tailscale/DDNS?)
- Qual é a frequência atual do scraper do Marmitex? (diário? a cada X horas?)
- O Railway cron consegue passar variáveis de ambiente para o scraper? (sim, via env vars do projeto)
