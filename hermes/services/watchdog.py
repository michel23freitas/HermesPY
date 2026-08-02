"""Watchdog: monitor contínuo de containers, RAM, temperatura e tarefas dinâmicas."""

import json
import time
import threading
from datetime import datetime

from hermes.config import ALLOWED_CHAT_ID, SHUTDOWN_MARKER
from hermes.db import db_task_list
from hermes.tools.system_tools import run_cmd
from hermes.telegram.bot import get_bot

# Estado global de containers (para detectar transições)
_prev_containers = {}


def get_containers_status():
    """Retorna dict {nome: '+'/'-'} para containers ativos/inativos."""
    out = run_cmd("docker ps -a --format '{{.Names}}\t{{.Status}}'")
    result = {}
    for l in out.splitlines():
        if "\t" in l:
            name, status = l.split("\t", 1)
            result[name] = "+" if "Up" in status else "-"
    return result


def wait_containers_stable(max_attempts=9, interval=10):
    """Aguarda o container homeassistant ficar online."""
    for _ in range(max_attempts):
        s = get_containers_status()
        if s.get("homeassistant") == "+":
            return s
        time.sleep(interval)
    return get_containers_status()


def _run_dynamic_tasks():
    """Executa tarefas dinâmicas de monitoramento (RAM, container)."""
    try:
        for tid, tipo, cfg_j, _ in db_task_list():
            cfg = json.loads(cfg_j)
            if tipo == "monitor_ram":
                pct = int(run_cmd("awk '/MemTotal/{t=$2}/MemAvailable/{a=$2}END{printf \"%.0f\",(1-a/t)*100}' /proc/meminfo"))
                if pct > cfg.get("limit", 85):
                    get_bot().send_message(ALLOWED_CHAT_ID, f"⚠️ RAM: {pct}%")
            elif tipo == "monitor_container":
                cname = cfg.get("container")
                if "false" in run_cmd(f"docker inspect -f '{{{{.State.Running}}}}' {cname}").lower():
                    get_bot().send_message(ALLOWED_CHAT_ID, f"⚠️ Parado: {cname}")
    except Exception:
        pass


def watchdog():
    """Loop principal do watchdog — roda a cada 60s."""
    global _prev_containers

    while True:
        try:
            time.sleep(60)
            curr = get_containers_status()

            # Detecta transições de estado de containers
            for n, s in curr.items():
                if n in _prev_containers and s != _prev_containers[n]:
                    icon = "✅" if s == "+" else "❌"
                    get_bot().send_message(ALLOWED_CHAT_ID, f"[{icon}] {n}")

            _prev_containers = curr
            _run_dynamic_tasks()

        except Exception:
            pass


def send_startup_notification():
    """Notifica no Telegram após startup, indicando containers estáveis."""
    try:
        time.sleep(8)
        clean = False
        if __import__("os").path.exists(SHUTDOWN_MARKER):
            clean = True
            try:
                __import__("os").remove(SHUTDOWN_MARKER)
            except Exception:
                pass

        s = wait_containers_stable()
        ct = "\n".join([f"{v} {k}" for k, v in s.items()])
        mode = "Normal" if clean else "Forçado"
        get_bot().send_message(ALLOWED_CHAT_ID, f"Hermes Online ({mode})\nContainers:\n{ct}")
    except Exception:
        pass
