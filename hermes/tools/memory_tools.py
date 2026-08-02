"""Ferramentas de memória e conhecimento: memory_save, memory_search, list_knowledge, search_knowledge, read_file, file_search."""

import os
import json

from hermes.config import KNOWLEDGE_DIR
from hermes.db import db_memory_save, db_memory_search, db_memory_list
from hermes.tools.system_tools import run_cmd

# Alias para compatibilidade com nomes de tool usados pelo LLM
memory_save = db_memory_save


def memory_search(query):
    return db_memory_search(query)


def memory_list():
    return db_memory_list()


# ---------- Knowledge base ----------

def tool_list_knowledge():
    if not os.path.exists(KNOWLEDGE_DIR):
        return "Pasta de conhecimento não existe."
    files = sorted(os.listdir(KNOWLEDGE_DIR))
    return "\n".join(f"• {f}" for f in files) if files else "Knowledge base vazia."


def tool_search_knowledge(query):
    if not os.path.exists(KNOWLEDGE_DIR):
        return "Knowledge base vazia. Use /sync."
    files_raw = run_cmd(f"grep -r -i -l '{query}' '{KNOWLEDGE_DIR}' 2>/dev/null")
    if not files_raw or files_raw == "Sem saida.":
        return f"Nenhum resultado para '{query}'."
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
        if b in path:
            return f"Bloqueado: arquivo sensível ({b})"
    if not os.path.exists(path):
        return f"Arquivo não encontrado: {path}"
    return run_cmd(f"cat '{path}' 2>/dev/null | head -200")


def tool_file_search(pattern):
    safe_paths = "/opt /home /usr/local/bin /host_cron /app"
    result = run_cmd(f"find {safe_paths} -iname '*{pattern}*' 2>/dev/null | head -15")
    return result or "Nenhum arquivo encontrado."


def tool_shell_read(command):
    blocked = ["rm ", "mkfs", "dd ", "> /", "shutdown", "reboot", "halt", "chmod 777", "curl | sh", "wget | sh", ":(){", "fork bomb"]
    cmd_lower = command.lower()
    for b in blocked:
        if b in cmd_lower:
            return f"Bloqueado: comando destrutivo ({b})"
    return run_cmd(command, timeout=15)
