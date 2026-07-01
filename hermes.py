import os, signal, telebot, subprocess, json, traceback, threading, time, requests, re, sqlite3
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN  = os.getenv("TELEGRAM_TOKEN")
ALLOWED_CHAT_ID = os.getenv("ALLOWED_CHAT_ID")
OPENROUTER_KEY  = os.getenv("OPENROUTER_KEY")
HA_TOKEN        = os.getenv("HA_TOKEN", "")
HA_URL          = os.getenv("HA_URL", "http://192.168.15.15:8123")
NETDATA_URL     = os.getenv("NETDATA_URL", "http://192.168.15.15:19999")
MODEL           = os.getenv("MODEL", "openrouter/auto")

SHUTDOWN_MARKER = "/app/data/.clean_shutdown"
DB_PATH         = "/app/data/hermes.db"
KNOWLEDGE_DIR   = "/app/knowledge"
os.makedirs("/app/data", exist_ok=True)

bot       = telebot.TeleBot(TELEGRAM_TOKEN)
ai_client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_KEY)

# ============================================================
# PERSISTÊNCIA SQLITE
# ============================================================

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS conversation (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id   TEXT    NOT NULL,
        role      TEXT    NOT NULL,
        content   TEXT    NOT NULL,
        timestamp TEXT    NOT NULL
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS memory (
        key     TEXT PRIMARY KEY,
        value   TEXT NOT NULL,
        source  TEXT,
        updated TEXT NOT NULL
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS tasks (
        id      INTEGER PRIMARY KEY AUTOINCREMENT,
        tipo    TEXT    NOT NULL,
        config  TEXT    NOT NULL,
        ativo   INTEGER DEFAULT 1,
        criado  TEXT    NOT NULL
    )''')
    conn.commit()
    conn.close()

def db_save_message(chat_id, role, content):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO conversation (chat_id, role, content, timestamp) VALUES (?,?,?,?)",
        (str(chat_id), role, content, datetime.now().isoformat())
    )
    conn.execute(
        "DELETE FROM conversation WHERE chat_id=? AND id NOT IN "
        "(SELECT id FROM conversation WHERE chat_id=? ORDER BY id DESC LIMIT 100)",
        (str(chat_id), str(chat_id))
    )
    conn.commit()
    conn.close()

def db_load_conversation(chat_id, limit=20):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT role, content FROM conversation WHERE chat_id=? ORDER BY id DESC LIMIT ?",
        (str(chat_id), limit)
    ).fetchall()
    conn.close()
    return [{"role": r[0], "content": r[1]} for r in reversed(rows)]

def db_clear_conversation(chat_id):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM conversation WHERE chat_id=?", (str(chat_id),))
    conn.commit()
    conn.close()

def db_memory_save(key, value, source="user"):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR REPLACE INTO memory (key, value, source, updated) VALUES (?,?,?,?)",
        (key.lower().strip(), value, source, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

def db_memory_get(key):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT value FROM memory WHERE key=?", (key.lower().strip(),)).fetchone()
    conn.close()
    return row[0] if row else None

def db_memory_search(query):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT key, value, updated FROM memory WHERE key LIKE ? OR value LIKE ? ORDER BY updated DESC LIMIT 10",
        (f"%{query}%", f"%{query}%")
    ).fetchall()
    conn.close()
    if not rows: return "Nenhum resultado na memória."
    return "\n".join(f"• {r[0]}: {r[1]} (salvo em {r[2][:10]})" for r in rows)

def db_memory_list():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT key, value FROM memory ORDER BY updated DESC").fetchall()
    conn.close()
    if not rows: return "Memória vazia."
    return "\n".join(f"• {r[0]}: {r[1]}" for r in rows)

def db_task_add(tipo, config_dict):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO tasks (tipo, config, criado) VALUES (?,?,?)",
        (tipo, json.dumps(config_dict), datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

def db_task_list():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT id, tipo, config, criado FROM tasks WHERE ativo=1").fetchall()
    conn.close()
    return rows

def db_task_remove(task_id):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE tasks SET ativo=0 WHERE id=?", (task_id,))
    conn.commit()
    conn.close()

# ============================================================
# KNOWLEDGE BASE & TOOLS
# ============================================================

def run_cmd(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip() or r.stderr.strip() or "Sem saida."
    except subprocess.TimeoutExpired:
        return "Timeout."
    except Exception as e:
        return f"Erro: {e}"

def sync_knowledge_base():
    os.makedirs(KNOWLEDGE_DIR, exist_ok=True)
    sources = [
        ("/opt/homeassistant/config/configuration.yaml", "ha_configuration.yaml"),
        ("/opt/homeassistant/config/automations.yaml",    "ha_automations.yaml"),
        ("/opt/musicassistant/settings.json",             "music_assistant_settings.json"),
        ("/usr/local/bin/homeassistant-backup.sh",        "backup_script.sh"),
    ]
    found_yml = run_cmd("find /opt -name 'docker-compose.yml' 2>/dev/null | head -10")
    for path in found_yml.splitlines():
        if path.strip():
            name = path.replace("/", "_").lstrip("_") + ".yml"
            sources.append((path, name))
    
    for src, dst in sources:
        if os.path.exists(src):
            run_cmd(f"cp '{src}' '{KNOWLEDGE_DIR}/{dst}'")
    
    all_files = os.listdir(KNOWLEDGE_DIR)
    if not all_files: return "Knowledge base vazia."
    
    return f"📚 Base de Conhecimento Atualizada ({len(all_files)} arquivos):\n" + \
           "\n".join(f"• {f}" for f in all_files)

def tool_search_knowledge(query):
    if not os.path.exists(KNOWLEDGE_DIR): return "Knowledge base vazia. Use /sync."
    files_raw = run_cmd(f"grep -r -i -l '{query}' '{KNOWLEDGE_DIR}' 2>/dev/null")
    if not files_raw or files_raw == "Sem saida.": return f"Nenhum resultado para '{query}'."
    files = [f for f in files_raw.splitlines() if f.strip()][:3]
    output = []
    for f in files:
        filename = os.path.basename(f)
        ctx = run_cmd(f"grep -i -n -A 3 -B 3 '{query}' '{f}' 2>/dev/null | head -40")
        output.append(f"### {filename}\n{ctx}")
    return "\n\n".join(output)

def tool_read_file(path):
    blocked = ["/etc/shadow", "/etc/passwd", ".env", "secrets", ".key", ".pem"]
    for b in blocked:
        if b in path: return f"Bloqueado: arquivo sensível ({b})"
    if not os.path.exists(path): return f"Arquivo não encontrado: {path}"
    return run_cmd(f"cat '{path}' 2>/dev/null | head -200")

def tool_file_search(pattern):
    safe_paths = "/opt /home /usr/local/bin /host_cron /app"
    result = run_cmd(f"find {safe_paths} -iname '*{pattern}*' 2>/dev/null | head -15")
    return result or "Nenhum arquivo encontrado."

def tool_list_knowledge():
    if not os.path.exists(KNOWLEDGE_DIR): return "Pasta de conhecimento não existe."
    files = os.listdir(KNOWLEDGE_DIR)
    return "\n".join(f"• {f}" for f in files) if files else "Knowledge base vazia."

def load_skills():
    skills_content = []
    if not os.path.exists(KNOWLEDGE_DIR):
        return ""
    for filename in sorted(os.listdir(KNOWLEDGE_DIR)):
        if filename.startswith("skill_") and filename.endswith(".md"):
            filepath = os.path.join(KNOWLEDGE_DIR, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    skills_content.append(f.read().strip())
            except Exception:
                pass
    if not skills_content:
        return ""
    return "\n\n---\n\n".join(skills_content)

SYSTEM_PROMPT_BASE = """Voce e o NUCLEO DE CONTROLE HERMES de um Raspberry Pi 3. Voce nao e um chatbot comum, voce e um controlador de hardware.

REGRAS OBRIGATORIAS DE EXECUCAO:
1. ACÃO = FERRAMENTA: Se o usuario pedir para ligar, desligar, ler ou buscar, voce DEVE obrigatoriamente chamar uma ferramenta. É PROIBIDO responder "Ok" ou "Feito" sem antes ter o resultado da ferramenta.
2. DOMINIOS HA: NUNCA use o dominio "ha". Para luzes use "light", para cenas "scene", para tomadas "switch".
3. ORDEM HA: Ao usar ha_call_service, use obrigatoriamente a ordem: service, domain, entity_id.
4. MENTIR É ERRO FATAL: Nunca afirme que um comando foi executado se voce nao recebeu o retorno "OK" da ferramenta.
4. MEMORIA PRIMEIRO: Para nomes como "luz forte", "projetor", etc, use memory_search ANTES de qualquer acao.
5. INVESTIGACAO OBRIGATORIA: NUNCA invente entity_id. SEMPRE use ha_find_entity antes de ha_call_service se o entity_id nao estiver na memoria. Se ha_call_service retornar ENTIDADE NAO ENCONTRADA, use ha_find_entity imediatamente e tente novamente com o entity_id correto.
5b. SALVAR APOS SUCESSO: Se ha_call_service retornar OK, salve o entity_id na memoria (memory_save) para uso futuro.
6. APRENDIZADO: Se o usuario ensinar algo novo ou corrigir uma info, pergunte: "Deseja salvar isso na memoria?". Se sim, use memory_save. Nao pergunte para infos ja salvas.
7. ATUALIZACAO: Se o usuario pedir para mudar uma info (ex: "mude X para Y"), use memory_save com a nova info sobrescrevendo a antiga.

ESTILO DE RESPOSTA (RESPOSTA FINAL):
- Seja extremamente breve. Vá direto ao ponto.
- Use frases curtas (3 a 6 palavras).
- Responda APENAS o solicitado. Não narre o processo.
- Se a ferramenta falhar, relate o erro real, nao finja sucesso.

AMBIENTE: DietPi, RPi 3, HA (8123), Netdata (19999), Knowledge (/app/knowledge).

## CONHECIMENTO DO AMBIENTE
{skills}
"""

def get_system_prompt():
    return SYSTEM_PROMPT_BASE.replace("{skills}", load_skills())

TOOLS = [
    {"type":"function","function":{"name":"docker_ps","description":"Lista containers Docker com status","parameters":{"type":"object","properties":{},"required":[]}}},
    {"type":"function","function":{"name":"docker_logs","description":"Logs de um container","parameters":{"type":"object","properties":{"container":{"type":"string"},"lines":{"type":"integer"}},"required":["container"]}}},
    {"type":"function","function":{"name":"docker_stats","description":"CPU e RAM por container","parameters":{"type":"object","properties":{},"required":[]}}},
    {"type":"function","function":{"name":"docker_restart","description":"Reinicia container","parameters":{"type":"object","properties":{"container":{"type":"string"}},"required":["container"]}}},
    {"type":"function","function":{"name":"docker_stop","description":"Para container","parameters":{"type":"object","properties":{"container":{"type":"string"}},"required":["container"]}}},
    {"type":"function","function":{"name":"docker_start","description":"Inicia container parado","parameters":{"type":"object","properties":{"container":{"type":"string"}},"required":["container"]}}},
    {"type":"function","function":{"name":"docker_inspect","description":"Inspeciona detalhes de um container: volumes, networks, variáveis de ambiente, portas.","parameters":{"type":"object","properties":{"container":{"type":"string"}},"required":["container"]}}},
    {"type":"function","function":{"name":"docker_networks","description":"Lista redes Docker e containers em cada rede.","parameters":{"type":"object","properties":{},"required":[]}}},
    {"type":"function","function":{"name":"docker_volumes","description":"Lista volumes Docker e seus mountpoints.","parameters":{"type":"object","properties":{},"required":[]}}},
    {"type":"function","function":{"name":"docker_logsum","description":"Resume os erros mais importantes dos logs de qualquer container usando IA. Melhor que docker_logs para diagnóstico.","parameters":{"type":"object","properties":{"container":{"type":"string"},"lines":{"type":"integer","description":"Quantas linhas de log analisar (padrão 60)"}},"required":["container"]}}},
    {"type":"function","function":{"name":"netdata_metrics","description":"Metricas do sistema via Netdata: cpu | ram | disk | temperature | network | overview","parameters":{"type":"object","properties":{"metric":{"type":"string","description":"cpu | ram | disk | temperature | network | overview"}},"required":["metric"]}}},
    {"type":"function","function":{"name":"system_uptime","description":"Uptime e carga do sistema","parameters":{"type":"object","properties":{},"required":[]}}},
    {"type":"function","function":{"name":"ha_states","description":"Estado de entidades do Home Assistant","parameters":{"type":"object","properties":{"entity_id":{"type":"string","description":"ID da entidade. Se omitido lista todas."}},"required":[]}}},
    {"type":"function","function":{"name":"ha_find_entity","description":"Busca entidades do Home Assistant por descrição em português. Use quando o usuário disser 'a luz da sala', 'o ar do quarto', 'câmera da garagem' — sem saber o entity_id exato.","parameters":{"type":"object","properties":{"description":{"type":"string","description":"Descrição em português do dispositivo. Ex: luz sala, ar quarto, camera garagem, switch cortina"}},"required":["description"]}}},
    {"type":"function","function":{"name":"ha_call_service","description":"Executa servico no Home Assistant","parameters":{"type":"object","properties":{"domain":{"type":"string"},"service":{"type":"string"},"entity_id":{"type":"string"},"extra_data":{"type":"object"}},"required":["domain","service","entity_id"]}}},
    {"type":"function","function":{"name":"ha_restart","description":"Reinicia o Home Assistant","parameters":{"type":"object","properties":{},"required":[]}}},
    {"type":"function","function":{"name":"memory_save","description":"Salva um fato na memória persistente do Hermes. Use quando o usuário mencionar IPs, caminhos de arquivos, preferências, configurações ou qualquer informação relevante do ambiente que deva ser lembrada.","parameters":{"type":"object","properties":{"key":{"type":"string","description":"Chave descritiva sem espaços. Ex: ip_camera_garagem, porta_music_assistant, caminho_compose_alexa"},"value":{"type":"string","description":"Valor a salvar. Ex: 192.168.15.50, 8095, /opt/alexa/docker-compose.yml"}},"required":["key","value"]}}},
    {"type":"function","function":{"name":"memory_search","description":"Busca fatos salvos na memória do Hermes. Use ANTES de responder perguntas sobre IPs, portas, caminhos, configurações que o usuário já mencionou em conversas anteriores.","parameters":{"type":"object","properties":{"query":{"type":"string","description":"Termo a buscar. Ex: camera, backup, compose, music"}},"required":["query"]}}},
    {"type":"function","function":{"name":"list_knowledge","description":"Lista todos os nomes de arquivos (manuais, documentações, logs) disponíveis na base de conhecimento local. Use para descobrir quais documentos ler.","parameters":{"type":"object","properties":{},"required":[]}}},
    {"type":"function","function":{"name":"search_knowledge","description":"Busca termos nos arquivos de configuração do sistema (docker-compose, configuration.yaml, scripts). Use para responder perguntas sobre configurações, portas, volumes, variáveis de ambiente.","parameters":{"type":"object","properties":{"query":{"type":"string","description":"Termo a buscar. Ex: porta, volume, LOCALE, backup, alexa"}},"required":["query"]}}},
    {"type":"function","function":{"name":"read_file","description":"Lê o conteúdo de um arquivo de configuração ou script. Use quando precisar analisar um arquivo específico.","parameters":{"type":"object","properties":{"path":{"type":"string","description":"Caminho absoluto do arquivo. Ex: /opt/homeassistant/config/configuration.yaml"}},"required":["path"]}}},
    {"type":"function","function":{"name":"file_search","description":"Busca arquivos no sistema por nome ou padrão. Use para localizar compose files, scripts, configurações.","parameters":{"type":"object","properties":{"pattern":{"type":"string","description":"Padrão de nome. Ex: docker-compose, backup, configuration"}},"required":["pattern"]}}},
    {"type":"function","function":{"name":"task_manage","description":"Gerencia tarefas de monitoramento dinâmico. Tipos disponíveis: monitor_ram | monitor_container | monitor_temperatura.","parameters":{"type":"object","properties":{"action":{"type":"string","enum":["add","list","remove"]},"tipo":{"type":"string","description":"Tipo da tarefa: monitor_ram | monitor_container | monitor_temperatura"},"config":{"type":"object","description":"Configuração: {limit: 85} para ram/temp, {container: 'nome'} para container"},"task_id":{"type":"integer","description":"ID da tarefa (necessário para remove)"}},"required":["action"]}}},
    {"type":"function","function":{"name":"shell_read","description":"Executa comandos de leitura no sistema. Use para: dmesg, journalctl, crontab, ps, df, free, ip, cat, systemctl. NAO use para comandos que modificam o sistema.","parameters":{"type":"object","properties":{"command":{"type":"string","description":"Comando shell de leitura a executar."}},"required":["command"]}}},
    {"type":"function","function":{"name":"marmitex_cardapio","description":"Busca o cardápio do dia do Marmitex Marisa. Retorna se está aberto, os itens disponíveis com preços e o link para pedido.","parameters":{"type":"object","properties":{},"required":[]}}},
]

def tool_docker_ps():
    raw = run_cmd("docker ps -a --format '{{.Names}}||{{.Status}}||{{.Image}}'")
    if "Erro" in raw or "Sem saida" in raw: return raw
    lines = raw.split("\n")
    output = ""
    for line in lines:
        if not line.strip(): continue
        parts = line.split("||")
        if len(parts) < 3: continue
        name, status, image = parts[0], parts[1], parts[2]
        if "Up" in status:
            output += f"✅ {name}\n"
        else:
            time_part = status.replace("Exited", "").replace("(", "").replace(")", "").strip()
            output += f"⚠️ {name} ({time_part})\n"
    return output

def tool_docker_logs(container, lines=50): return run_cmd(f"docker logs --tail {lines} {container} 2>&1")
def tool_docker_stats(): return run_cmd("docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}'")
def tool_docker_restart(c): return run_cmd(f"docker restart {c}", timeout=60)
def tool_docker_stop(c):    return run_cmd(f"docker stop {c}", timeout=60)
def tool_docker_start(c):   return run_cmd(f"docker start {c}", timeout=60)
def tool_system_uptime():   return run_cmd("uptime && cat /proc/loadavg")

def netdata_get(chart):
    try:
        r = requests.get(f"{NETDATA_URL}/api/v1/data", params={"chart":chart,"points":1,"format":"json"}, timeout=5)
        return r.json() if r.status_code == 200 else None
    except: return None

def tool_netdata_metrics(metric="overview"):
    res = {}
    if metric in ("cpu","overview"):
        d = netdata_get("system.cpu")
        if d and d.get("data"):
            labels = d.get("labels",[])
            vals   = d["data"][0][1:]
            total  = round(sum(v for v in vals if v), 2)
            res["cpu_uso_%"] = total
            res["cpu_detalhes"] = {labels[i]: round(vals[i],2) for i in range(min(len(labels),len(vals)))}
        else: res["cpu"] = run_cmd("top -bn1 | grep 'Cpu' | head -1")

    if metric in ("ram","overview"):
        d = netdata_get("system.ram")
        if d and d.get("data"):
            labels = d.get("labels",[])
            vals   = d["data"][0][1:]
            res["ram_MB"] = {labels[i]: round(vals[i],1) for i in range(min(len(labels),len(vals)))}
        else: res["ram"] = run_cmd("free -h")

    if metric in ("disk","overview"):
        d = netdata_get("disk_space._")
        if d and d.get("data"):
            labels = d.get("labels",[])
            vals   = d["data"][0][1:]
            res["disk_GB"] = {labels[i]: round(vals[i],2) for i in range(min(len(labels),len(vals)))}
        else: res["disk"] = run_cmd("df -h /")

    if metric in ("temperature","overview"):
        found = False
        for chart in ["sensors.cpu_thermal_zone0_temp_input","sensors.thermal_zone0_temp_input","sensors.rpi_cpu_thermal"]:
            d = netdata_get(chart)
            if d and d.get("data"):
                res["temperatura_C"] = round(d["data"][0][1], 1)
                found = True; break
        if not found:
            raw = run_cmd("cat /sys/class/thermal/thermal_zone0/temp")
            try: res["temperatura_C"] = round(int(raw)/1000, 1)
            except: res["temperatura_C"] = "indisponivel"

    if metric == "network":
        d = netdata_get("system.net")
        if d and d.get("data"):
            labels = d.get("labels",[])
            vals   = d["data"][0][1:]
            res["rede_kbps"] = {labels[i]: round(vals[i],2) for i in range(min(len(labels),len(vals)))}
        else: res["rede"] = run_cmd("cat /proc/net/dev | grep -v lo")

    return json.dumps(res, ensure_ascii=False, indent=2) if res else "Netdata indisponivel."

def _ha_h(): return {"Authorization":f"Bearer {HA_TOKEN}","Content-Type":"application/json"}

def tool_ha_states(entity_id=None):
    if not HA_TOKEN: return "HA_TOKEN nao configurado"
    try:
        if entity_id:
            r = requests.get(f"{HA_URL}/api/states/{entity_id}", headers=_ha_h(), timeout=10)
            if r.status_code == 200:
                s = r.json()
                return json.dumps({"entity_id":s["entity_id"],"state":s["state"],"attributes":s.get("attributes",{})}, ensure_ascii=False, indent=2)
            return f"Erro {r.status_code}"
        else:
            r = requests.get(f"{HA_URL}/api/states", headers=_ha_h(), timeout=10)
            if r.status_code == 200:
                states = r.json()
                lista = [f"{s['entity_id']}: {s['state']}" for s in states[:30]]
                return "\n".join(lista) + f"\n\n(Total: {len(states)} entidades)"
            return f"Erro {r.status_code}"
    except Exception as e: return f"Erro HA: {e}"

def tool_ha_call_service(domain, service, entity_id, extra_data=None):
    if not HA_TOKEN: return "HA_TOKEN nao configurado"
    # Valida se a entidade existe antes de chamar o serviço
    try:
        check = requests.get(f"{HA_URL}/api/states/{entity_id}", headers=_ha_h(), timeout=5)
        if check.status_code == 404:
            # Tenta sugerir entidades parecidas
            sugestoes = tool_ha_find_entity(entity_id.replace(".", " ").replace("_", " "))
            return f"ENTIDADE NAO ENCONTRADA: '{entity_id}'\nUse ha_find_entity para descobrir o entity_id correto.\nSugestoes:\n{sugestoes}"
    except Exception as e:
        return f"Erro ao validar entidade: {e}"
    data = {"entity_id": entity_id}
    if extra_data: data.update(extra_data)
    try:
        r = requests.post(f"{HA_URL}/api/services/{domain}/{service}", headers=_ha_h(), json=data, timeout=10)
        if r.status_code in [200, 201]:
            # Confirma o novo estado da entidade
            try:
                s = requests.get(f"{HA_URL}/api/states/{entity_id}", headers=_ha_h(), timeout=5)
                novo_estado = s.json().get("state", "?") if s.status_code == 200 else "?"
                return f"OK — estado atual: {novo_estado}"
            except:
                return "OK"
        return f"Erro {r.status_code}: {r.text[:200]}"
    except Exception as e: return f"Erro: {e}"

def tool_ha_restart():
    if not HA_TOKEN: return "HA_TOKEN nao configurado"
    try:
        r = requests.post(f"{HA_URL}/api/services/homeassistant/restart", headers=_ha_h(), timeout=10)
        return "HA reiniciando..." if r.status_code in [200,201] else f"Erro {r.status_code}"
    except Exception as e: return f"Erro: {e}"

def tool_shell_read(command):
    blocked = ["rm ", "mkfs", "dd ", "> /", "shutdown", "reboot", "halt", "chmod 777", "curl | sh", "wget | sh", ":(){", "fork bomb"]
    cmd_lower = command.lower()
    for b in blocked:
        if b in cmd_lower: return f"Bloqueado: comando destrutivo ({b})"
    return run_cmd(command, timeout=15)

def tool_marmitex_cardapio():
    JSON_URL = "https://raw.githubusercontent.com/michel23freitas/HermesPY/main/cardapio.json"
    try:
        r = requests.get(JSON_URL, timeout=10)
        if r.status_code != 200:
            return f"Erro ao buscar cardápio: HTTP {r.status_code}"
        data = r.json()

        if not data.get("aberto", False):
            return f"❌ Marmitex Marisa fechado hoje ({data.get('data', '?')})."

        itens = data.get("itens", [])
        url = data.get("url_pedido", "https://www.marmitexmarisa.com.br/cardapio/")

        if not itens:
            return f"🍱 Marisa aberto, mas cardápio não carregou.\nPeça aqui: {url}"

        linhas = [f"🍱 Cardápio Marmitex Marisa — {data.get('data', '?')}"]
        for item in itens:
            nome = item.get("nome", "")
            preco = item.get("preco", "")
            desc = item.get("descricao", "")
            linha = f"• {nome}"
            if preco: linha += f" — {preco}"
            if desc: linha += f"\n  {desc}"
            linhas.append(linha)
        linhas.append(f"\n🔗 Pedir: {url}")
        return "\n".join(linhas)

    except Exception as e:
        return f"Erro ao buscar cardápio Marisa: {e}"

def tool_docker_inspect(container):
    result = run_cmd(f"docker inspect {container} --format 'Imagem: {{{{.Config.Image}}}}\\nStatus: {{{{.State.Status}}}}\\nNetwork: {{{{.HostConfig.NetworkMode}}}}\\nRestart: {{{{.HostConfig.RestartPolicy.Name}}}}' 2>&1")
    volumes = run_cmd(f"docker inspect {container} --format '{{{{range .Mounts}}}}{{{{.Source}}}} → {{{{.Destination}}}}\\n{{{{end}}}}'")
    ports = run_cmd(f"docker inspect {container} --format '{{{{range $k,$v := .NetworkSettings.Ports}}}}{{{{$k}}}}\\n{{{{end}}}}'")
    return f"{result}\n\nVolumes:\n{volumes}\nPortas:\n{ports}"

def tool_docker_networks(): return run_cmd("docker network ls --format '{{.Name}}\t{{.Driver}}'")
def tool_docker_volumes(): return run_cmd("docker volume ls --format '{{.Name}}' | xargs -I{} docker volume inspect {} --format '{{.Name}}: {{.Mountpoint}}' 2>/dev/null")
def tool_docker_logsum(container, lines=60):
    logs = tool_docker_logs(container, lines)
    if not logs or "Sem saida" in logs: return "Nenhum log."
    prompt = f"Analise logs do container '{container}' e liste apenas erros criticos (max 5), em portugues:\n\n{logs}"
    try:
        resp = ai_client.chat.completions.create(model=MODEL, messages=[{"role": "user", "content": prompt}], temperature=0.2, max_tokens=400)
        return f"📋 Resumo logs ({container}):\n\n{resp.choices[0].message.content.strip()}"
    except: return f"Erro ao resumir logs. Brutos:\n" + "\n".join(logs.splitlines()[-15:])

_HA_CACHE = {}
_HA_CACHE_TS = 0.0
def _refresh_ha_cache():
    global _HA_CACHE, _HA_CACHE_TS
    if not HA_TOKEN: return
    try:
        r = requests.get(f"{HA_URL}/api/states", headers=_ha_h(), timeout=10)
        if r.status_code == 200:
            _HA_CACHE = {s["entity_id"]: {"state": s["state"], "attrs": s.get("attributes", {})} for s in r.json()}
            _HA_CACHE_TS = time.time()
    except: pass

def tool_ha_find_entity(description):
    global _HA_CACHE, _HA_CACHE_TS
    if time.time() - _HA_CACHE_TS > 300: _refresh_ha_cache()
    if not _HA_CACHE: return "Cache HA vazio."
    words = description.lower().split()
    matches = []
    for entity_id, data in _HA_CACHE.items():
        score = sum(1 for w in words if w in entity_id.lower() or w in data["attrs"].get("friendly_name", "").lower())
        if score > 0: matches.append((score, entity_id, data["state"], data["attrs"].get("friendly_name", "")))
    matches.sort(reverse=True)
    if not matches: return f"Nenhuma entidade encontrada para '{description}'."
    return "\n".join([f"• {m[1]} ({m[3]}): {m[2]}" for m in matches[:10]])

def tool_task_manage(action, tipo=None, config=None, task_id=None):
    if action == "add": db_task_add(tipo, config); return "Tarefa criada."
    if action == "list": return str(db_task_list())
    if action == "remove": db_task_remove(task_id); return "Tarefa removida."
    return "Acao invalida"

TOOL_MAP = {
    "docker_ps":       lambda a: tool_docker_ps(),
    "docker_logs":     lambda a: tool_docker_logs(a["container"], a.get("lines",50)),
    "docker_stats":    lambda a: tool_docker_stats(),
    "docker_restart":  lambda a: tool_docker_restart(a["container"]),
    "docker_stop":     lambda a: tool_docker_stop(a["container"]),
    "docker_start":    lambda a: tool_docker_start(a["container"]),
    "docker_inspect":  lambda a: tool_docker_inspect(a["container"]),
    "docker_networks": lambda a: tool_docker_networks(),
    "docker_volumes":  lambda a: tool_docker_volumes(),
    "docker_logsum":   lambda a: tool_docker_logsum(a["container"], a.get("lines", 60)),
    "netdata_metrics": lambda a: tool_netdata_metrics(a.get("metric","overview")),
    "system_uptime":   lambda a: tool_system_uptime(),
    "ha_states":       lambda a: tool_ha_states(a.get("entity_id")),
    "ha_find_entity":  lambda a: tool_ha_find_entity(a["description"]),
    "ha_call_service": lambda a: tool_ha_call_service(a["domain"],a["service"],a["entity_id"],a.get("extra_data")),
    "ha_restart":      lambda a: tool_ha_restart(),
    "memory_save":     lambda a: (db_memory_save(a["key"], a["value"]), f"Memorizado: {a['key']}")[1],
    "memory_search":   lambda a: db_memory_search(a["query"]),
    "list_knowledge":  lambda a: tool_list_knowledge(),
    "search_knowledge":lambda a: tool_search_knowledge(a["query"]),
    "read_file":       lambda a: tool_read_file(a["path"]),
    "file_search":     lambda a: tool_file_search(a["pattern"]),
    "task_manage":     lambda a: tool_task_manage(a["action"], a.get("tipo"), a.get("config"), a.get("task_id")),
    "shell_read":      lambda a: tool_shell_read(a["command"]),
    "marmitex_cardapio": lambda a: tool_marmitex_cardapio(),
}

def execute_tool(name, args):
    fn = TOOL_MAP.get(name)
    if not fn: return f"Ferramenta desconhecida: {name}"
    try: return fn(args)
    except Exception as e: return f"Erro em {name}: {e}"

def run_agent(user_message, chat_id):
    conversation_history = db_load_conversation(chat_id, limit=20)
    db_save_message(chat_id, "user", user_message)
    messages = [{"role":"system","content":get_system_prompt()}] + conversation_history
    messages.append({"role":"user","content":user_message})
    tool_steps = []
    for _ in range(7):
        resp = ai_client.chat.completions.create(model=MODEL, messages=messages, tools=TOOLS, tool_choice="auto", temperature=0.1, max_tokens=1200)
        choice = resp.choices[0]; msg = choice.message
        md = {"role":"assistant"}
        if msg.content: md["content"] = msg.content
        if msg.tool_calls: md["tool_calls"] = [{"id":tc.id,"type":"function","function":{"name":tc.function.name,"arguments":tc.function.arguments}} for tc in msg.tool_calls]
        messages.append(md)
        if msg.tool_calls:
            for tc in msg.tool_calls:
                name = tc.function.name
                try: args = json.loads(tc.function.arguments)
                except: args = {}
                result = execute_tool(name, args)
                args_str = ", ".join(f"{k}={v}" for k,v in args.items()) if args else ""
                tool_steps.append(f"🔧 `{name}({args_str})`")
                messages.append({"role":"tool","tool_call_id":tc.id,"content":str(result)[:3000]})
            continue
        final = (msg.content or "").strip()
        if not final:
            messages.append({"role":"user","content":"Responda apos usar ferramentas."})
            continue
        db_save_message(chat_id, "assistant", final)
        return final, tool_steps
    for m in reversed(messages):
        if m.get("role") == "assistant" and m.get("content"):
            db_save_message(chat_id, "assistant", m["content"])
            return m["content"], tool_steps
    return "Nao consegui processar.", tool_steps

# ============================================================
# COMANDOS FIXOS (RESTAURADOS DO BACKUP)
# ============================================================

def format_ram_output(raw_json):
    try:
        data = json.loads(raw_json)
        if "ram_MB" in data:
            r = data["ram_MB"]; used = r.get("used", 0); free = r.get("free", 0); cached = r.get("cached", 0)
            total = used + free + cached; percent = round((used / total) * 100, 1) if total > 0 else 0
            return f"📈 Uso de RAM: {percent}%  ({used:.1f} MB de {total:.1f} MB)"
        return data.get("ram", raw_json)
    except: return raw_json

def format_disk_output(raw_json):
    try:
        data = json.loads(raw_json)
        if "disk" in data:
            df_line = data["disk"]
            for line in df_line.splitlines():
                if 'overlay' in line or '/dev/' in line:
                    parts = line.split()
                    if len(parts) >= 6: return f"💾 Disco: {parts[4]} usado  (Usado: {parts[2]}, Total: {parts[1]}, Livre: {parts[3]})"
            return df_line
        return raw_json
    except: return raw_json

def format_temp_output(raw_json):
    try:
        data = json.loads(raw_json)
        return f"🌡️ Temperatura CPU: {data['temperatura_C']}°C" if "temperatura_C" in data else raw_json
    except: return raw_json

def cmd_status():
    ram_line = format_ram_output(tool_netdata_metrics("ram"))
    disk_line = format_disk_output(tool_netdata_metrics("disk"))
    temp_line = format_temp_output(tool_netdata_metrics("temperature"))
    return f"📊 RESUMO GERAL\n\n{ram_line}\n{disk_line}\n{temp_line}\n\n📦 *CONTAINERS:*\n{tool_docker_ps()}"

def cmd_memoria(): return format_ram_output(tool_netdata_metrics("ram"))
def cmd_temperatura(): return format_temp_output(tool_netdata_metrics("temperature"))
def cmd_disco(): return format_disk_output(tool_netdata_metrics("disk"))
def cmd_containers(): return tool_docker_ps()

def cmd_logs():
    logs = tool_docker_logs("homeassistant", 30)
    if not logs or "Sem saida" in logs: return "❌ Erro logs."
    linhas = [l for l in logs.splitlines() if "duplicate key" not in l.lower()]
    ultimas = linhas[-15:] if len(linhas) > 15 else linhas
    return f"📜 Últimos logs HA:\n```\n" + "\n".join(ultimas) + "\n```"

def cmd_ha():
    if not HA_TOKEN: return "⚠️ HA_TOKEN ausente."
    try:
        r = requests.get(f"{HA_URL}/api/", headers=_ha_h(), timeout=5)
        version = r.json().get('version', 'desconhecida') if r.status_code == 200 else "desconhecida"
        states_r = requests.get(f"{HA_URL}/api/states", headers=_ha_h(), timeout=5)
        num_entities = len(states_r.json()) if states_r.status_code == 200 else "?"
        return f"🏠 Home Assistant\n✅ Status: Online\n📦 Versão: {version}\n🔢 Entidades: {num_entities}\n🌐 URL: {HA_URL}"
    except Exception as e: return f"Erro HA: {e}"

def cmd_entidades(): return tool_ha_states()
def cmd_reiniciar(c=None): return tool_docker_restart(c) if c else "Uso: /reiniciar <nome>"
def cmd_limpar(chat_id): db_clear_conversation(chat_id); return "🧹 Histórico limpo."
def cmd_mem(): return f"🧠 Memória do Hermes:\n\n{db_memory_list()}"
def cmd_sync(): return sync_knowledge_base()

def cmd_ajuda():
    return """📋 Comandos:
/status, /containers, /memoria, /temperatura, /disco
/ha, /entidades, /logs, /logsum, /backup, /mem, /sync, /reiniciar, /limpar, /ajuda"""

def cmd_logsum(): return tool_docker_logsum("homeassistant")

def cmd_backup_status():
    import glob
    tmp_dir = "/opt/backup-pending"; pc_dir = "/mnt/backups/windows"; log_file = f"{pc_dir}/backup.log"
    pending = len(glob.glob(f"{tmp_dir}/*.tar.gz"))
    pc_mounted = os.path.exists(pc_dir) and os.path.ismount(pc_dir)
    if not pc_mounted: return f"⏳ {pending} backup(s) pendentes. 💻 PC offline."
    if os.path.exists(log_file):
        try:
            with open(log_file, "r") as f: ultimas = "".join(f.readlines()[-7:])
            prompt = f"Com base neste log de backup, responda em portugues de forma natural, amigável e MUITO BREVE (max 3 linhas). Diga a data/hora do ultimo sucesso e o status geral. Log:\n{ultimas}"
            resp = ai_client.chat.completions.create(model=MODEL, messages=[{"role": "user", "content": prompt}], temperature=0.3, max_tokens=300)
            return f"💾 {resp.choices[0].message.content.strip()}"
        except: return "Erro log backup."
    return f"⏳ {pending} backup(s) pendentes. Log nao encontrado."

FIXED_COMMANDS = {
    "/status": cmd_status, "/containers": cmd_containers, "/memoria": cmd_memoria, "/temperatura": cmd_temperatura,
    "/disco": cmd_disco, "/logs": cmd_logs, "/ha": cmd_ha, "/entidades": cmd_entidades, "/reiniciar": cmd_reiniciar,
    "/limpar": cmd_limpar, "/ajuda": cmd_ajuda, "/logsum": cmd_logsum, "/backup": cmd_backup_status, "/mem": cmd_mem, "/sync": cmd_sync,
    "/updateskills": lambda: sync_knowledge_base() + "\n✅ Skills recarregadas.",
}

def handle_fixed_command(cmd_text, chat_id):
    parts = cmd_text.strip().split()
    cmd = parts[0].lower()
    if cmd in FIXED_COMMANDS:
        f = FIXED_COMMANDS[cmd]
        if cmd == "/reiniciar": return f(parts[1] if len(parts) > 1 else None)
        return f(chat_id) if cmd == "/limpar" else f()
    return None

@bot.message_handler(func=lambda m: True)
def handle(message):
    if str(message.chat.id) != ALLOWED_CHAT_ID: return
    text = message.text.strip()
    res = handle_fixed_command(text, message.chat.id)
    if res: bot.reply_to(message, res); return
    status_msg = bot.reply_to(message, "🧠 Analisando...")
    try:
        answer, steps = run_agent(text, message.chat.id)
        final = ("\n".join(steps) + "\n\n" if steps else "") + answer
        bot.edit_message_text(final[:4000], chat_id=message.chat.id, message_id=status_msg.message_id)
    except: bot.edit_message_text("Erro processamento.", chat_id=message.chat.id, message_id=status_msg.message_id)

def get_containers_status():
    out = run_cmd("docker ps -a --format '{{.Names}}\t{{.Status}}'")
    return {l.split("\t")[0]: ("+" if "Up" in l.split("\t")[1] else "-") for l in out.splitlines() if "\t" in l}

def wait_containers_stable():
    for _ in range(9):
        s = get_containers_status()
        if s.get("homeassistant") == "+": return s
        time.sleep(10)
    return get_containers_status()

def send_startup_notification():
    try:
        time.sleep(8); clean = os.path.exists(SHUTDOWN_MARKER)
        if clean: os.remove(SHUTDOWN_MARKER)
        s = wait_containers_stable(); ct = "\n".join([f"{v} {k}" for k, v in s.items()])
        bot.send_message(ALLOWED_CHAT_ID, f"Hermes Online ({'Normal' if clean else 'Forcado'})\nContainers:\n{ct}")
    except: pass

def watchdog():
    prev = {}
    _ultimo_aviso_marisa = None
    while True:
        try:
            time.sleep(60); curr = get_containers_status()
            for n, s in curr.items():
                if n in prev and s != prev[n]: bot.send_message(ALLOWED_CHAT_ID, f"[{'✅' if s == '+' else '❌'}] {n}")
            prev = curr; _run_dynamic_tasks()
            agora = datetime.now()
            if agora.weekday() < 5 and agora.hour == 12 and agora.minute < 2:
                hoje = agora.strftime("%Y-%m-%d")
                if _ultimo_aviso_marisa != hoje:
                    _ultimo_aviso_marisa = hoje
                    cardapio = tool_marmitex_cardapio()
                    bot.send_message(ALLOWED_CHAT_ID, f"🕛 Hora do almoço!\n\n{cardapio}")
        except: pass

def _run_dynamic_tasks():
    try:
        for tid, tipo, cfg_j, _ in db_task_list():
            cfg = json.loads(cfg_j)
            if tipo == "monitor_ram":
                pct = int(run_cmd("awk '/MemTotal/{t=$2}/MemAvailable/{a=$2}END{printf \"%.0f\",(1-a/t)*100}' /proc/meminfo"))
                if pct > cfg.get("limit", 85): bot.send_message(ALLOWED_CHAT_ID, f"⚠️ RAM: {pct}%")
            elif tipo == "monitor_container":
                if "false" in run_cmd(f"docker inspect -f '{{{{.State.Running}}}}' {cfg.get('container')}").lower():
                    bot.send_message(ALLOWED_CHAT_ID, f"⚠️ Parado: {cfg.get('container')}")
    except: pass

def on_shutdown(signum, frame):
    try:
        with open(SHUTDOWN_MARKER, "w") as f: f.write(datetime.now().isoformat())
    except: pass
    exit(0)

signal.signal(signal.SIGTERM, on_shutdown); signal.signal(signal.SIGINT, on_shutdown)

if __name__ == "__main__":
    init_db(); sync_knowledge_base()
    threading.Thread(target=watchdog, daemon=True).start()
    threading.Thread(target=send_startup_notification, daemon=True).start()
    bot.infinity_polling()
gnal.signal(signal.SIGINT, on_shutdown)

if __name__ == "__main__":
    init_db(); sync_knowledge_base()
    threading.Thread(target=watchdog, daemon=True).start()
    threading.Thread(target=send_startup_notification, daemon=True).start()
    bot.infinity_polling()
