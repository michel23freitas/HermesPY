import os
import telebot
import subprocess
import json
import traceback
import threading
import time
import requests
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# ===== CONFIG =====
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN")
ALLOWED_CHAT_ID  = os.getenv("ALLOWED_CHAT_ID")
OPENROUTER_KEY   = os.getenv("OPENROUTER_KEY")
HA_TOKEN         = os.getenv("HA_TOKEN", "")
HA_URL           = os.getenv("HA_URL", "http://192.168.15.15:8123")
MODEL            = os.getenv("MODEL", "google/gemma-4-31b-it:free")

bot       = telebot.TeleBot(TELEGRAM_TOKEN)
ai_client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_KEY)

# Histórico de conversa em memória
conversation_history = []
MAX_HISTORY = 20

# ===== SYSTEM PROMPT =====

SYSTEM_PROMPT = """Você é Hermes, agente de administração de um Raspberry Pi 3 com DietPi.

Ambiente:
- Sistema: DietPi (Debian), Raspberry Pi 3, 1GB RAM
- Containers: homeassistant, music-assistant, portainer, netdata, ytmusic-po-token, hermes
- Home Assistant em network host na porta 8123
- Tailscale MagicDNS: dietpi | IP: 100.84.31.60

Regras:
- Use ferramentas para investigar antes de responder.
- Problemas complexos: use múltiplas ferramentas em sequência (máx 5 por pergunta).
- Responda sempre em português, direto e técnico.
- Nunca execute ações destrutivas sem confirmação explícita do usuário."""

# ===== TOOLS SCHEMA =====

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "docker_ps",
            "description": "Lista todos os containers Docker com status",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "docker_logs",
            "description": "Retorna logs de um container",
            "parameters": {
                "type": "object",
                "properties": {
                    "container": {"type": "string", "description": "Nome do container"},
                    "lines":     {"type": "integer", "description": "Linhas a retornar (padrão 50)"}
                },
                "required": ["container"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "docker_stats",
            "description": "Mostra uso de CPU e RAM de todos os containers",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "docker_restart",
            "description": "Reinicia um container",
            "parameters": {
                "type": "object",
                "properties": {
                    "container": {"type": "string"}
                },
                "required": ["container"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "docker_stop",
            "description": "Para um container",
            "parameters": {
                "type": "object",
                "properties": {
                    "container": {"type": "string"}
                },
                "required": ["container"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "docker_start",
            "description": "Inicia um container parado",
            "parameters": {
                "type": "object",
                "properties": {
                    "container": {"type": "string"}
                },
                "required": ["container"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "system_memory",
            "description": "Uso de memória RAM do sistema",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "system_disk",
            "description": "Uso de disco",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "system_uptime",
            "description": "Uptime e carga do sistema",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "system_temperature",
            "description": "Temperatura da CPU do Raspberry Pi",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ha_states",
            "description": "Consulta estado de entidades do Home Assistant",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_id": {
                        "type": "string",
                        "description": "ID da entidade (ex: light.sala). Se omitido, lista todas (resumido)."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ha_call_service",
            "description": "Executa um serviço no Home Assistant (ligar luz, desligar switch, etc)",
            "parameters": {
                "type": "object",
                "properties": {
                    "domain":     {"type": "string", "description": "Domínio: light, switch, media_player, etc"},
                    "service":    {"type": "string", "description": "Serviço: turn_on, turn_off, toggle, etc"},
                    "entity_id":  {"type": "string", "description": "ID da entidade alvo"},
                    "extra_data": {"type": "object", "description": "Dados extras (brightness, temperature, etc)"}
                },
                "required": ["domain", "service", "entity_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ha_restart",
            "description": "Reinicia o Home Assistant",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
]

# ===== TOOL IMPLEMENTATIONS =====

def run_cmd(cmd, timeout=30):
    try:
        r = subprocess.run(
            cmd, shell=True, capture_output=True,
            text=True, timeout=timeout
        )
        out = r.stdout.strip()
        err = r.stderr.strip()
        return out or err or "Sem saída."
    except subprocess.TimeoutExpired:
        return "Timeout."
    except Exception as e:
        return f"Erro: {e}"


def tool_docker_ps():
    return run_cmd(
        "docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'"
    )

def tool_docker_logs(container, lines=50):
    return run_cmd(f"docker logs --tail {lines} {container} 2>&1")

def tool_docker_stats():
    return run_cmd(
        "docker stats --no-stream --format "
        "'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}'"
    )

def tool_docker_restart(container):
    return run_cmd(f"docker restart {container}", timeout=60)

def tool_docker_stop(container):
    return run_cmd(f"docker stop {container}", timeout=60)

def tool_docker_start(container):
    return run_cmd(f"docker start {container}", timeout=60)

def tool_system_memory():
    return run_cmd("free -h && echo '---' && cat /proc/meminfo | grep -E 'MemTotal|MemAvail|Cached'")

def tool_system_disk():
    return run_cmd("df -h /")

def tool_system_uptime():
    return run_cmd("uptime && echo '---' && cat /proc/loadavg")

def tool_system_temperature():
    # Raspberry Pi nativo
    result = run_cmd("cat /sys/class/thermal/thermal_zone0/temp")
    try:
        temp = int(result.strip()) / 1000
        return f"CPU: {temp:.1f}°C"
    except:
        pass
    result = run_cmd("vcgencmd measure_temp")
    if "temp=" in result:
        return result
    return "Temperatura indisponível."

def _ha_headers():
    return {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json"
    }

def tool_ha_states(entity_id=None):
    if not HA_TOKEN:
        return "HA_TOKEN não configurado no .env"
    try:
        if entity_id:
            r = requests.get(
                f"{HA_URL}/api/states/{entity_id}",
                headers=_ha_headers(), timeout=10
            )
            if r.status_code == 200:
                s = r.json()
                return json.dumps({
                    "entity_id": s["entity_id"],
                    "state": s["state"],
                    "attributes": s.get("attributes", {})
                }, ensure_ascii=False, indent=2)
            return f"Erro {r.status_code}: {r.text}"
        else:
            r = requests.get(
                f"{HA_URL}/api/states",
                headers=_ha_headers(), timeout=10
            )
            if r.status_code == 200:
                states = r.json()
                summary = [
                    {"entity_id": s["entity_id"], "state": s["state"]}
                    for s in states[:60]
                ]
                return (
                    json.dumps(summary, ensure_ascii=False, indent=2)
                    + f"\n\n(Total: {len(states)} entidades)"
                )
            return f"Erro {r.status_code}: {r.text}"
    except Exception as e:
        return f"Erro ao conectar no HA: {e}"

def tool_ha_call_service(domain, service, entity_id, extra_data=None):
    if not HA_TOKEN:
        return "HA_TOKEN não configurado no .env"
    data = {"entity_id": entity_id}
    if extra_data:
        data.update(extra_data)
    try:
        r = requests.post(
            f"{HA_URL}/api/services/{domain}/{service}",
            headers=_ha_headers(), json=data, timeout=10
        )
        if r.status_code in [200, 201]:
            return f"OK: {domain}.{service} executado em {entity_id}"
        return f"Erro {r.status_code}: {r.text}"
    except Exception as e:
        return f"Erro: {e}"

def tool_ha_restart():
    if not HA_TOKEN:
        return "HA_TOKEN não configurado no .env"
    try:
        r = requests.post(
            f"{HA_URL}/api/services/homeassistant/restart",
            headers=_ha_headers(), timeout=10
        )
        if r.status_code in [200, 201]:
            return "Home Assistant reiniciando..."
        return f"Erro {r.status_code}: {r.text}"
    except Exception as e:
        return f"Erro: {e}"


TOOL_MAP = {
    "docker_ps":       lambda a: tool_docker_ps(),
    "docker_logs":     lambda a: tool_docker_logs(a["container"], a.get("lines", 50)),
    "docker_stats":    lambda a: tool_docker_stats(),
    "docker_restart":  lambda a: tool_docker_restart(a["container"]),
    "docker_stop":     lambda a: tool_docker_stop(a["container"]),
    "docker_start":    lambda a: tool_docker_start(a["container"]),
    "system_memory":   lambda a: tool_system_memory(),
    "system_disk":     lambda a: tool_system_disk(),
    "system_uptime":   lambda a: tool_system_uptime(),
    "system_temperature": lambda a: tool_system_temperature(),
    "ha_states":       lambda a: tool_ha_states(a.get("entity_id")),
    "ha_call_service": lambda a: tool_ha_call_service(
        a["domain"], a["service"], a["entity_id"], a.get("extra_data")
    ),
    "ha_restart":      lambda a: tool_ha_restart(),
}

def execute_tool(name, args):
    fn = TOOL_MAP.get(name)
    if not fn:
        return f"Ferramenta desconhecida: {name}"
    try:
        return fn(args)
    except Exception as e:
        return f"Erro em {name}: {e}"

# ===== AGENT LOOP =====

def run_agent(user_message):
    global conversation_history

    conversation_history.append({"role": "user", "content": user_message})
    if len(conversation_history) > MAX_HISTORY:
        conversation_history = conversation_history[-MAX_HISTORY:]

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + conversation_history
    tool_steps = []
    max_iter = 5

    for _ in range(max_iter):
        response = ai_client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0.1,
            max_tokens=1000
        )

        choice = response.choices[0]
        msg    = choice.message

        # Serializa para adicionar ao histórico
        msg_dict = {"role": "assistant"}
        if msg.content:
            msg_dict["content"] = msg.content
        if msg.tool_calls:
            msg_dict["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                }
                for tc in msg.tool_calls
            ]
        messages.append(msg_dict)

        # Sem tool calls = resposta final
        if not msg.tool_calls or choice.finish_reason == "stop":
            final_text = msg.content or "Sem resposta."
            conversation_history.append({"role": "assistant", "content": final_text})
            return final_text, tool_steps

        # Executa ferramentas
        for tc in msg.tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments)
            except:
                args = {}

            result = execute_tool(name, args)

            # Log da ferramenta chamada
            args_str = ", ".join(f"{k}={v}" for k, v in args.items()) if args else ""
            tool_steps.append(f"🔧 `{name}({args_str})`")

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": str(result)[:3000]
            })

    return "Limite de iterações atingido.", tool_steps


# ===== TELEGRAM =====

@bot.message_handler(func=lambda m: True)
def handle(message):
    if str(message.chat.id) != ALLOWED_CHAT_ID:
        bot.reply_to(message, "Acesso negado.")
        return

    status = bot.reply_to(message, "🧠 Analisando...")

    try:
        answer, steps = run_agent(message.text)

        text = ""
        if steps:
            text += "\n".join(steps) + "\n\n"
        text += answer

        if len(text) > 4000:
            text = text[:3900] + "\n\n[Truncado]"

        bot.edit_message_text(
            text,
            chat_id=message.chat.id,
            message_id=status.message_id
        )

    except Exception:
        err = traceback.format_exc()
        print(err)
        try:
            bot.edit_message_text(
                f"❌ Erro:\n{err[:3000]}",
                chat_id=message.chat.id,
                message_id=status.message_id
            )
        except:
            pass


# ===== WATCHDOG =====

CRITICAL_CONTAINERS = {"homeassistant", "music-assistant"}

def watchdog():
    prev = {}
    while True:
        try:
            time.sleep(60)

            out = run_cmd("docker ps -a --format '{{.Names}}\t{{.Status}}'")
            curr = {}
            for line in out.splitlines():
                if "\t" in line:
                    name, status = line.split("\t", 1)
                    curr[name] = status

            for name, status in curr.items():
                p = prev.get(name, "")
                if p == "":
                    continue
                if "Up" not in status and "Up" in p:
                    icon = "🔴" if name in CRITICAL_CONTAINERS else "⚠️"
                    bot.send_message(
                        ALLOWED_CHAT_ID,
                        f"{icon} Container caiu: *{name}*\n`{status}`",
                        parse_mode="Markdown"
                    )
                elif "Up" in status and "Up" not in p:
                    bot.send_message(
                        ALLOWED_CHAT_ID,
                        f"✅ Container voltou: *{name}*",
                        parse_mode="Markdown"
                    )

            prev = curr

            # Alerta de RAM > 85%
            mem_raw = run_cmd(
                "awk '/MemTotal/{t=$2}/MemAvailable/{a=$2}END{printf \"%.0f\",(1-a/t)*100}'"
                " /proc/meminfo"
            )
            try:
                if int(mem_raw) > 85:
                    bot.send_message(
                        ALLOWED_CHAT_ID,
                        f"⚠️ RAM alta: *{mem_raw}%* em uso",
                        parse_mode="Markdown"
                    )
            except:
                pass

        except Exception as e:
            print(f"[watchdog] {e}")


def send_startup():
    try:
        time.sleep(5)
        containers = run_cmd(
            "docker ps --format '• {{.Names}} — {{.Status}}'"
        )
        bot.send_message(
            ALLOWED_CHAT_ID,
            f"🚀 *Hermes iniciado*\n\n{containers}",
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"[startup] {e}")


# ===== MAIN =====

if __name__ == "__main__":
    print("[hermes] iniciando...")
    threading.Thread(target=watchdog,      daemon=True).start()
    threading.Thread(target=send_startup,  daemon=True).start()
    bot.infinity_polling()
