# Release Notes — Hermes v2.0 (Refatoração Maior)

Esta atualização traz a maior mudança estrutural do projeto Hermes desde a sua criação, focada em organização, performance e usabilidade. O monolito `hermes.py` foi completamente convertido em um pacote modular, o bot ganhou menus interativos no Telegram, a IA ficou mais esperta para injetar contexto (Skills), e os processos de monitoramento foram desacoplados.

## 🏗 Arquitetura & Modularização
- **Fim do monolito:** O antigo arquivo `hermes.py` de +800 linhas foi fragmentado num novo pacote Python estruturado (`hermes/`).
- **Nova Estrutura:**
  - `hermes/telegram/`: Handlers, botões (inline keyboards) e comandos isolados.
  - `hermes/tools/`: Funções puras (Docker, HA, WOL, Netdata, Backup, db), separadas do LLM.
  - `hermes/agent/`: Centralização da chamada ao OpenRouter e injeção do LLM.
  - `hermes/services/`: Loops de background isolados (Watchdog).
  - `hermes/db.py`: Conexão sqlite Thread-safe com modo e suporte a versionamento (`user_version`).

## 📱 Telegram — Fim da Poluição Visual
- **Interface baseada em menus interativos**: Criação do comando `/menu` e do `/status` em blocos condensados, reduzindo o flood no chat.
- **Merge de comandos**: Os comandos `/memoria`, `/temperatura` e `/disco` foram absorvidos pelo comando `/status`.
- **Acesso Delineado**: Comandos `/ha` e `/logs` agora oferecem botões diretos (ex: *Resumo via IA* no de logs, *Exibir Entidades* no HA).

## 🧠 LLM & Economy (Keyword Selector)
- **Prompt Dinâmico**: A injeção de `# Skills` parou de empurrar centenas de linhas de todos os arquivos `*.md` de uma vez. Agora as skills são filtradas com *keyword matching*. Somente regras relevantes ao papo são passadas, reduzindo latência e economizando limites mensais de Token do OpenRouter.

## 🔧 Ferramentas, Segurança & Correções 
- **WOL Resiliente (`/ligar_windows`)**: A lógica de Wake-On-Lan foi desvinculada de fatos do banco de dados (que causavam o erro *"PC já está ligado"* por sujeira no BD). Agora pinga ao vivo (`ICMP Ping`).
- **Segurança Shell**: Removido bash/prompting-injection, tudo agora ocorre por ferramentas declaradas estaticamente no `TOOL_MAP`.
- **Docker Mount Fix**: F-Strings que integravam parâmetros JSON de docker inspect (`{}` vs `{{}}`) devidamente escapadas. Correção para templates format do Docker (`{{.Config.Image}}`).

## 🗑 Limpeza e Descarte (Housekeeping)
- **Fim do Marmitex**: Removidos Playwright/Selenium, dependências gigantes e scripts de scraping (`railway-scraper/`, `scraper.py`, `cardapio.json` e arquivo `.github/workflows/scrape.yml`).
- Todos arquivos defasados movidos e documentados na pasta `docs/archive/`.

---

**⚠️ Pós-Deploy:**
Um simples `docker compose up -d --build` irá instalar e mapear a nova estrutura. Devido ao SQLite manter o volume persistente em `/app/data/hermes.db`, as tarefas e memórias não vão ser perdidas com esse commit.