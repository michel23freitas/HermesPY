"""Ferramentas Wake-on-LAN (Windows): ping, ligar."""

import subprocess
import time

from hermes.config import WINDOWS_IP, WOL_MAC, WOL_BROADCAST
from wakeonlan import send_magic_packet


def tool_ping_windows():
    """Verifica conectividade atual do PC Windows via IP. Live-state only — no DB/memory."""
    try:
        r = subprocess.run(
            f"ping -c 3 -W 2 {WINDOWS_IP}",
            shell=True, capture_output=True, text=True, timeout=15
        )
        if r.returncode == 0:
            return f"Windows ONLINE ({WINDOWS_IP})"
        return f"Windows OFFLINE ({WINDOWS_IP})"
    except Exception as e:
        return f"Erro ao pingar: {e}"


def _ping_windows_bool():
    """Retorna True se o PC estiver online no momento."""
    try:
        r = subprocess.run(
            f"ping -c 1 -W 2 {WINDOWS_IP}",
            shell=True, capture_output=True, text=True, timeout=10
        )
        return r.returncode == 0
    except Exception:
        return False


def tool_ligar_windows():
    """Liga o PC Windows via WOL. Live-state: se já online, retorna sem enviar WOL."""
    # 1. Verifica se já está ligado
    if _ping_windows_bool():
        return "PC já está ligado e conectado…"

    # 2. Envia WOL e poll a cada ~15s por até ~3 minutos
    try:
        send_magic_packet(WOL_MAC, ip_address=WOL_BROADCAST)
    except Exception as e:
        return f"Erro ao enviar WOL: {e}"

    for tentativa in range(12):  # 12 * 15s = 180s = 3 minutos
        time.sleep(15)
        if _ping_windows_bool():
            return f"PC ligado e conectado após {tentativa + 1} tentativa(s).\nWindows ONLINE ({WINDOWS_IP})"

    return "WOL enviado, mas PC não respondeu ao ping após ~3 minutos."
