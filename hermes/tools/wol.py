"""Ferramentas Wake-on-LAN (Windows): ping e ligar via botão WOL do Home Assistant."""

import subprocess
import time

from hermes.config import WINDOWS_IP
from hermes.tools.ha_tools import tool_ha_call_service

# Entidade botão WOL criada no Home Assistant (o HA envia o magic packet)
WOL_HA_BUTTON = "button.wake_on_lan_c8_7f_54_63_36_c2"


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
    """Liga o PC Windows acionando o botão WOL do Home Assistant e confirma via ping."""
    # 1. Verifica se já está ligado
    if _ping_windows_bool():
        return "PC já está ligado e conectado."

    # 2. Aciona o botão WOL do Home Assistant (o HA envia o magic packet)
    result = tool_ha_call_service("button", "press", WOL_HA_BUTTON)
    if "OK" not in result:
        return f"Falha ao acionar botão WOL no HA ({WOL_HA_BUTTON}):\n{result}"

    # 3. Poll curto de confirmação (~45s)
    for tentativa in range(3):  # 3 * 15s = 45s
        time.sleep(15)
        if _ping_windows_bool():
            return f"PC ligado e conectado após ~{(tentativa + 1) * 15}s.\nWindows ONLINE ({WINDOWS_IP})"

    return "WOL acionado via Home Assistant. PC ainda não respondeu ao ping após ~45s (pode demorar um pouco mais)."
