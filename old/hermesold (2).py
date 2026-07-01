import os, signal, telebot, subprocess, json, traceback, threading, time, requests
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
os.makedirs("/app/data", exist_ok=True)

bot       = telebot.TeleBot(TELEGRAM_TOKEN)
ai_client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_KEY)

conversation_history = []
MAX_HISTORY = 20

SYSTEM_PROMPT = """Voce e Hermes, agente de administracao de um Raspberry Pi 3 com DietPi.

Ambiente:
- Sistema: DietPi (Debian), Raspberry Pi 3, 1GB RAM
- Containers: homeassistant, music-assistant, portainer, netdata, ytmusic-po-token, hermes
- Home Assistant em network host na porta 8123
- Netdata em porta 19999 (metricas detalhadas)
- Tailscale MagicDNS: dietpi | IP: 100.84.31.60

Regras:
- Use ferramentas para investigar antes de responder.
- Para metricas do sistema prefira netdata_metrics (mais rico).
- Problemas complexos: use multiplas ferramentas em sequencia (max 5).
- Responda sempre em portugues, direto e tecnico.
- Nunca execute acoes destrutivas sem confirmacao explicita."""

TOOLS = [
    {"type":"function","function":{"name":"docker_ps","description":"Lista containers Docker com status","parameters":{"type":"object","properties":{},"required":[]}}},
    {"type":"function","function":{"name":"docker_logs","description":"Logs de um container","parameters":{"type":"object","properties":{"container":{"type":"string"},"lines":{"type":"integer"}},"required":["container"]}}},
    {"type":"function","function":{"name":"docker_stats","description":"CPU e RAM por container","parameters":{"type":"object","properties":{},"required":[]}}},
    {"type":"function","function":{"name":"docker_restart","description":"Reinicia container","parameters":{"type":"object","properties":{"container":{"type":"string"}},"required":["container"]}}},
    {"type":"function","function":{"name":"docker_stop","description":"Para container","parameters":{"type":"object","properties":{"container":{"type":"string"}},"required":["container"]}}},
    {"type":"function","function":{"name":"docker_start","description":"Inicia container parado","parameters":{"type":"object","properties":{"container":{"type":"string"}},"required":["container"]}}},
    {"type":"function","function":{"name":"netdata_metrics","description":"Metricas do sistema via Netdata: cpu | ram | disk | temperature | network | overview","parameters":{"type":"object","properties":{"metric":{"type":"string","description":"cpu | ram | disk | temperature | network | overview"}},"required":["metric"]}}},
    {"type":"function","function":{"name":"system_uptime","description":"Uptime e carga do sistema","parameters":{"type":"object","properties":{},"required":[]}}},
    {"type":"function","function":{"name":"ha_states","description":"Estado de entidades do Home Assistant","parameters":{"type":"object","properties":{"entity_id":{"type":"string","description":"ID da entidade. Se omitido lista todas."}},"required":[]}}},
    {"type":"function","function":{"name":"ha_call_service","description":"Executa servico no Home Assistant","parameters":{"type":"object","properties":{"domain":{"type":"string"},"service":{"type":"string"},"entity_id":{"type":"string"},"extra_data":{"type":"object"}},"required":["domain","service","entity_id"]}}},
    {"type":"function","function":{"name":"ha_restart","description":"Reinicia o Home Assistant","parameters":{"type":"object","properties":{},"required":[]}}},
]

def run_cmd(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip() or r.stderr.strip() or "Sem saida."
    except subprocess.TimeoutExpired:
        return "Timeout."
    except Exception as e:
        return f"Erro: {e}"

def tool_docker_ps():
    return run_cmd("docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'")

def tool_docker_logs(container, lines=50):
    return run_cmd(f"docker logs --tail {lines} {container} 2>&1")

def tool_docker_stats():
    return run_cmd("docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}'")

def tool_docker_restart(c): return run_cmd(f"docker restart {c}", timeout=60)
def tool_docker_stop(c):    return run_cmd(f"docker stop {c}", timeout=60)
def tool_docker_start(c):   return run_cmd(f"docker start {c}", timeout=60)
def tool_system_uptime():   return run_cmd("uptime && cat /proc/loadavg")

def netdata_get(chart):
    try:
        r = requests.get(f"{NETDATA_URL}/api/v1/data", params={"chart":chart,"points":1,"format":"json"}, timeout=5)
        return r.json() if r.status_code == 200 else None
    except:
        return None

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
        else:
            res["cpu"] = run_cmd("top -bn1 | grep 'Cpu' | head -1")

    if metric in ("ram","overview"):
        d = netdata_get("system.ram")
        if d and d.get("data"):
            labels = d.get("labels",[])
            vals   = d["data"][0][1:]
            res["ram_MB"] = {labels[i]: round(vals[i],1) for i in range(min(len(labels),len(vals)))}
        else:
            res["ram"] = run_cmd("free -h")

    if metric in ("disk","overview"):
        d = netdata_get("disk_space._")
        if d and d.get("data"):
            labels = d.get("labels",[])
            vals   = d["data"][0][1:]
            res["disk_GB"] = {labels[i]: round(vals[i],2) for i in range(min(len(labels),len(vals)))}
        else:
            res["disk"] = run_cmd("df -h /")

    if metric in ("temperature","overview"):
        found = False
        for chart in ["sensors.cpu_thermal_zone0_temp_input","sensors.thermal_zone0_temp_input","sensors.rpi_cpu_thermal"]:
            d = netdata_get(chart)
            if d and d.get("data"):
                res["temperatura_C"] = round(d["data"][0][1], 1)
                found = True
                break
        if not found:
            raw = run_cmd("cat /sys/class/thermal/thermal_zone0/temp")
            try:
                res["temperatura_C"] = round(int(raw)/1000, 1)
            except:
                res["temperatura_C"] = "indisponivel"

    if metric == "network":
        d = netdata_get("system.net")
        if d and d.get("data"):
            labels = d.get("labels",[])
            vals   = d["data"][0][1:]
            res["rede_kbps"] = {labels[i]: round(vals[i],2) for i in range(min(len(labels),len(vals)))}
        else:
            res["rede"] = run_cmd("cat /proc/net/dev | grep -v lo")

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
                return json.dumps([{"entity_id":s["entity_id"],"state":s["state"]} for s in states[:60]], ensure_ascii=False, indent=2) + f"\n(Total: {len(states)})"
            return f"Erro {r.status_code}"
    except Exception as e:
        return f"Erro HA: {e}"

def tool_ha_call_service(domain, service, entity_id, extra_data=None):
    if not HA_TOKEN: return "HA_TOKEN nao configurado"
    data = {"entity_id": entity_id}
    if extra_data: data.update(extra_data)
    try:
        r = requests.post(f"{HA_URL}/api/services/{domain}/{service}", headers=_ha_h(), json=data, timeout=10)
        return f"OK: {domain}.{service} em {entity_id}" if r.status_code in [200,201] else f"Erro {r.status_code}"
    except Exception as e:
        return f"Erro: {e}"

def tool_ha_restart():
    if not HA_TOKEN: return "HA_TOKEN nao configurado"
    try:
        r = requests.post(f"{HA_URL}/api/services/homeassistant/restart", headers=_ha_h(), timeout=10)
        return "HA reiniciando..." if r.status_code in [200,201] else f"Erro {r.status_code}"
    except Exception as e:
        return f"Erro: {e}"

TOOL_MAP = {
    "docker_ps":       lambda a: tool_docker_ps(),
    "docker_logs":     lambda a: tool_docker_logs(a["container"], a.get("lines",50)),
    "docker_stats":    lambda a: tool_docker_stats(),
    "docker_restart":  lambda a: tool_docker_restart(a["container"]),
    "docker_stop":     lambda a: tool_docker_stop(a["container"]),
    "docker_start":    lambda a: tool_docker_start(a["container"]),
    "netdata_metrics": lambda a: tool_netdata_metrics(a.get("metric","overview")),
    "system_uptime":   lambda a: tool_system_uptime(),
    "ha_states":       lambda a: tool_ha_states(a.get("entity_id")),
    "ha_call_service": lambda a: tool_ha_call_service(a["domain"],a["service"],a["entity_id"],a.get("extra_data")),
    "ha_restart":      lambda a: tool_ha_restart(),
}

def execute_tool(name, args):
    fn = TOOL_MAP.get(name)
    if not fn: return f"Ferramenta desconhecida: {name}"
    try:    return fn(args)
    except Exception as e: return f"Erro em {name}: {e}"

def run_agent(user_message):
    global conversation_history
    conversation_history.append({"role":"user","content":user_message})
    if len(conversation_history) > MAX_HISTORY:
        conversation_history = conversation_history[-MAX_HISTORY:]

    messages   = [{"role":"system","content":SYSTEM_PROMPT}] + conversation_history
    tool_steps = []

    for _ in range(5):
        resp   = ai_client.chat.completions.create(model=MODEL, messages=messages, tools=TOOLS, tool_choice="auto", temperature=0.1, max_tokens=1000)
        choice = resp.choices[0]
        msg    = choice.message

        md = {"role":"assistant"}
        if msg.content:     md["content"]    = msg.content
        if msg.tool_calls:  md["tool_calls"] = [{"id":tc.id,"type":"function","function":{"name":tc.function.name,"arguments":tc.function.arguments}} for tc in msg.tool_calls]
        messages.append(md)

        if not msg.tool_calls or choice.finish_reason == "stop":
            final = msg.content or "Sem resposta."
            conversation_history.append({"role":"assistant","content":final})
            return final, tool_steps

        for tc in msg.tool_calls:
            name = tc.function.name
            try:    args = json.loads(tc.function.arguments)
            except: args = {}
            result   = execute_tool(name, args)
            args_str = ", ".join(f"{k}={v}" for k,v in args.items()) if args else ""
            tool_steps.append(f"🔧 `{name}({args_str})`")
            messages.append({"role":"tool","tool_call_id":tc.id,"content":str(result)[:3000]})

    return "Limite de iteracoes atingido.", tool_steps

@bot.message_handler(func=lambda m: True)
def handle(message):
    if str(message.chat.id) != ALLOWED_CHAT_ID:
        bot.reply_to(message, "Acesso negado.")
        return
    status = bot.reply_to(message, "🧠 Analisando...")
    try:
        answer, steps = run_agent(message.text)
        text = ("\n".join(steps) + "\n\n" if steps else "") + answer
        if len(text) > 4000: text = text[:3900] + "\n\n[Truncado]"
        bot.edit_message_text(text, chat_id=message.chat.id, message_id=status.message_id)
    except Exception:
        err = traceback.format_exc()
        print(err)
        try: bot.edit_message_text(f"Erro:\n{err[:3000]}", chat_id=message.chat.id, message_id=status.message_id)
        except: pass

# ===== REBOOT DETECTION =====

def get_containers_status():
    out = run_cmd("docker ps -a --format '{{.Names}}\t{{.Status}}'")
    status = {}
    for line in out.splitlines():
        if "\t" in line:
            n, s = line.split("\t", 1)
            status[n] = ("+" if "Up" in s else "-")
    return status

def wait_containers_stable(timeout=90):
    deadline = time.time() + timeout
    while time.time() < deadline:
        s = get_containers_status()
        if s.get("homeassistant") == "+":
            return s
        time.sleep(10)
    return get_containers_status()

def send_startup_notification():
    try:
        time.sleep(8)
        now      = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        boot_raw = run_cmd("uptime -s")
        clean    = os.path.exists(SHUTDOWN_MARKER)
        tipo     = "Shutdown normal" if clean else "Queda de energia / reset forcado"
        if clean:
            try: os.remove(SHUTDOWN_MARKER)
            except: pass

        containers = wait_containers_stable()
        ct_lines   = "\n".join(
            ("+ " if v == "+" else "- ") + k
            for k, v in containers.items()
        )

        msg = (
            f"Hermes reiniciado\n"
            f"Motivo: {tipo}\n"
            f"Boot: {boot_raw}\n"
            f"Agora: {now}\n\n"
            f"Containers:\n{ct_lines}"
        )
        bot.send_message(ALLOWED_CHAT_ID, msg)
    except Exception as e:
        print(f"[startup] {e}")

# ===== WATCHDOG =====

CRITICAL = {"homeassistant", "music-assistant"}

def watchdog():
    prev        = {}
    ram_alerted = False
    while True:
        try:
            time.sleep(60)
            out  = run_cmd("docker ps -a --format '{{.Names}}\t{{.Status}}'")
            curr = {}
            for line in out.splitlines():
                if "\t" in line:
                    n, s = line.split("\t", 1)
                    curr[n] = s

            for name, status in curr.items():
                p = prev.get(name, "")
                if not p: continue
                if "Up" not in status and "Up" in p:
                    icon = "CRITICO" if name in CRITICAL else "AVISO"
                    bot.send_message(ALLOWED_CHAT_ID, f"[{icon}] Container caiu: {name}\n{status}")
                elif "Up" in status and "Up" not in p:
                    bot.send_message(ALLOWED_CHAT_ID, f"[OK] Container voltou: {name}")
            prev = curr

            mem = run_cmd("awk '/MemTotal/{t=$2}/MemAvailable/{a=$2}END{printf \"%.0f\",(1-a/t)*100}' /proc/meminfo")
            try:
                pct = int(mem)
                if pct > 85 and not ram_alerted:
                    bot.send_message(ALLOWED_CHAT_ID, f"[AVISO] RAM alta: {pct}% em uso")
                    ram_alerted = True
                elif pct <= 80:
                    ram_alerted = False
            except: pass
        except Exception as e:
            print(f"[watchdog] {e}")

# ===== GRACEFUL SHUTDOWN =====

def on_shutdown(signum, frame):
    print("[hermes] shutdown limpo")
    try:
        with open(SHUTDOWN_MARKER, "w") as f:
            f.write(datetime.now().isoformat())
    except: pass
    exit(0)

signal.signal(signal.SIGTERM, on_shutdown)
signal.signal(signal.SIGINT,  on_shutdown)

if __name__ == "__main__":
    print("[hermes] iniciando...")
    threading.Thread(target=watchdog,                daemon=True).start()
    threading.Thread(target=send_startup_notification, daemon=True).start()
    bot.infinity_polling()
