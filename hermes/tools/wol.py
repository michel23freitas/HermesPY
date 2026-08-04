"""Ferramentas Wake-on-LAN (Windows): ping (TCP) e ligar via botão WOL do Home Assistant."""

import shutil
import socket
import subprocess
import time

from hermes.config import WINDOWS_IP
from hermes.tools.ha_tools import tool_ha_call_service

# Entidade botão WOL criada no Home Assistant (o HA envia o magic packet)
WOL_HA_BUTTON = "button.wake_on_lan_c8_7f_54_63_36_c2"

# Portas TCP do Windows para checar conectividade (mais confiável que ICMP dentro do Docker)
_WINDOWS_PORTS = [445, 139, 3389, 135, 22]


def acionar_botao_wol():
    """Aciona o botão WOL do Home Assistant. Retorna (ok: bool, mensagem: str)."""
    result = tool_ha_call_service("button", "press", WOL_HA_BUTTON)
    if "OK" not in result:
        return False, f"Falha ao acionar botão WOL no HA ({WOL_HA_BUTTON}):\n{result}"
    return True, "OK"


def _windows_tcp_reachable():
    """True se alguma porta TCP comum do Windows aceitar conexão."""
    for port in _WINDOWS_PORTS:
        try:
            with socket.create_connection((WINDOWS_IP, port), timeout=1):
                return True
        except OSError:
            continue
    return False


def _ping_windows_bool():
    """True se o PC responder ao ping ICMP (fallback, só se o binário existir)."""
    if shutil.which("ping") is None:
        return False
    try:
        r = subprocess.run(
            f"ping -c 1 -W 2 {WINDOWS_IP}",
            shell=True, capture_output=True, text=True, timeout=10
        )
        return r.returncode == 0
    except Exception:
        return False


def is_windows_online():
    """True se o PC responder à rede agora (TCP primeiro; fallback ICMP)."""
    if _windows_tcp_reachable():
        return True
    return _ping_windows_bool()


def tool_ping_windows():
    """Verifica conectividade atual do PC Windows. Live-state only — no DB/memory."""
    if is_windows_online():
        return f"Windows ONLINE ({WINDOWS_IP})"
    return f"Windows OFFLINE ({WINDOWS_IP})"


def tool_ligar_windows():
    """Liga o PC Windows acionando o botão WOL do Home Assistant e confirma a conectividade."""
    # 1. Verifica se já está ligado
    if is_windows_online():
        return "PC já está ligado e conectado."

    # 2. Aciona o botão WOL do Home Assistant (o HA envia o magic packet)
    ok, msg = acionar_botao_wol()
    if not ok:
        return msg

    # 3. Poll curto de confirmação (~45s)
    for tentativa in range(3):  # 3 * 15s = 45s
        time.sleep(15)
        if is_windows_online():
            return f"PC ligado e conectado após ~{(tentativa + 1) * 15}s.\nWindows ONLINE ({WINDOWS_IP})"

    return "WOL acionado via Home Assistant. PC ainda não respondeu após ~45s (pode demorar um pouco mais)."
