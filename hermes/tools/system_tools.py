"""Ferramentas de sistema: execução de comandos, uptime."""

import subprocess


def run_cmd(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip() or r.stderr.strip() or "Sem saida."
    except subprocess.TimeoutExpired:
        return "Timeout."
    except Exception as e:
        return f"Erro: {e}"


def tool_system_uptime():
    return run_cmd("uptime && cat /proc/loadavg")
