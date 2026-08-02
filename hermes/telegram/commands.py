"""Comandos fixos do Telegram (legacy compat + /menu).

Comandos mantidos: /status, /menu, /ha, /containers, /backup,
/logs, /reiniciar <nome>, /limpar, /sync.

Comandos removidos: /memoria, /temperatura, /disco (fundidos em /status),
/mem (removido), /entidades (vira botão HA), /logsum (vira botão logs),
/updateskills (fundido em /sync), /ajuda → alias de /menu.
"""

import json

from hermes.tools.docker_tools import (
    tool_docker_ps, tool_docker_logs, tool_docker_restart,
)
from hermes.tools.ha_tools import tool_ha_states
from hermes.tools.netdata_tools import tool_netdata_metrics
from hermes.tools.backup import cmd_backup_status
from hermes.db import db_clear_conversation


# --- Formatters (preservados do hermes.py original) ---

def format_ram_output(raw_json):
    try:
        data = json.loads(raw_json)
        if "ram_MB" in data:
            r = data["ram_MB"]
            used = r.get("used", 0)
            free = r.get("free", 0)
            cached = r.get("cached", 0)
            total = used + free + cached
            percent = round((used / total) * 100, 1) if total > 0 else 0
            return f"📈 Uso de RAM: {percent}%  ({used:.1f} MB de {total:.1f} MB)"
        return data.get("ram", raw_json)
    except Exception:
        return raw_json


def format_disk_output(raw_json):
    try:
        data = json.loads(raw_json)
        if "disk" in data:
            df_line = data["disk"]
            for line in df_line.splitlines():
                if "overlay" in line or "/dev/" in line:
                    parts = line.split()
                    if len(parts) >= 6:
                        return f"💾 Disco: {parts[4]} usado  (Usado: {parts[2]}, Total: {parts[1]}, Livre: {parts[3]})"
            return df_line
        return raw_json
    except Exception:
        return raw_json


def format_temp_output(raw_json):
    try:
        data = json.loads(raw_json)
        return f"🌡️ Temperatura CPU: {data['temperatura_C']}°C" if "temperatura_C" in data else raw_json
    except Exception:
        return raw_json


# --- Command handlers ---

def cmd_status():
    ram_line = format_ram_output(tool_netdata_metrics("ram"))
    disk_line = format_disk_output(tool_netdata_metrics("disk"))
    temp_line = format_temp_output(tool_netdata_metrics("temperature"))
    return (
        f"📊 RESUMO GERAL\n\n{ram_line}\n{disk_line}\n{temp_line}\n\n"
        f"📦 *CONTAINERS:*\n{tool_docker_ps()}"
    )


def cmd_containers():
    return tool_docker_ps()


def cmd_logs():
    logs = tool_docker_logs("homeassistant", 30)
    if not logs or "Sem saida" in logs:
        return "❌ Erro logs."
    linhas = [l for l in logs.splitlines() if "duplicate key" not in l.lower()]
    ultimas = linhas[-15:] if len(linhas) > 15 else linhas
    return f"📜 Últimos logs HA:\n```\n" + "\n".join(ultimas) + "\n```"


def cmd_ha():
    from hermes.tools.ha_tools import _ha_h
    from hermes.config import HA_TOKEN, HA_URL
    import requests
    if not HA_TOKEN:
        return "⚠️ HA_TOKEN ausente."
    try:
        r = requests.get(f"{HA_URL}/api/", headers=_ha_h(), timeout=5)
        version = r.json().get("version", "desconhecida") if r.status_code == 200 else "desconhecida"
        states_r = requests.get(f"{HA_URL}/api/states", headers=_ha_h(), timeout=5)
        num_entities = len(states_r.json()) if states_r.status_code == 200 else "?"
        return f"🏠 Home Assistant\n✅ Status: Online\n📦 Versão: {version}\n🔢 Entidades: {num_entities}\n🌐 URL: {HA_URL}"
    except Exception as e:
        return f"Erro HA: {e}"


def cmd_entidades():
    return tool_ha_states()


def cmd_reiniciar(c=None):
    if c:
        return tool_docker_restart(c)
    return "Uso: /reiniciar <nome>"


def cmd_limpar(chat_id):
    db_clear_conversation(chat_id)
    return "🧹 Histórico limpo."


def cmd_sync():
    from hermes.services.knowledge import sync_knowledge_base
    return sync_knowledge_base()


def cmd_menu():
    """Exibe o menu principal de comandos inline."""
    from hermes.telegram.menus import build_main_menu
    return "📋 Menu Hermes — escolha uma categoria:", build_main_menu()


# Alias compat: /ajuda aponta para /menu
cmd_ajuda = cmd_menu

# Logsum vira um comando fixo que delega para HA logsum
def cmd_logsum():
    from hermes.tools.docker_tools import tool_docker_logsum
    return tool_docker_logsum("homeassistant")


# --- Registry de comandos fixos ---

FIXED_COMMANDS = {
    "/status":       lambda chat_id, args: cmd_status(),
    "/menu":         lambda chat_id, args: cmd_menu(),
    "/containers":   lambda chat_id, args: cmd_containers(),
    "/logs":         lambda chat_id, args: cmd_logs(),
    "/ha":           lambda chat_id, args: cmd_ha(),
    "/reiniciar":    lambda chat_id, args: cmd_reiniciar(args),
    "/limpar":       lambda chat_id, args: cmd_limpar(chat_id),
    "/sync":         lambda chat_id, args: cmd_sync(),
    "/backup":       lambda chat_id, args: cmd_backup_status(),
    "/ajuda":        lambda chat_id, args: cmd_ajuda(),
}


def run_fixed_command(cmd_text, args, chat_id):
    """Executa um comando fixo. Retorna string ou (text, markup).

    cmd_text: comando sem espaço (ex: "/status")
    args: argumentos do comando (ex: nome do container para /reiniciar), ou None
    """
    handler = FIXED_COMMANDS.get(cmd_text)
    if not handler:
        return None
    try:
        result = handler(chat_id, args)
        return result
    except Exception as e:
        return f"Erro: {e}"
