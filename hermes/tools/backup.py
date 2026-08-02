"""Ferramentas de backup: status do backup, leitura defensiva do mount do PC."""

import os
import glob

from hermes.config import MODEL, OPENROUTER_KEY
from hermes.tools.system_tools import run_cmd

# Backup paths — defensive: mount do PC Windows pode estar ausente
BACKUP_TMP_DIR = "/opt/backup-pending"
BACKUP_PC_DIR  = "/mnt/backups/windows"
BACKUP_LOG     = os.path.join(BACKUP_PC_DIR, "backup.log")


def cmd_backup_status():
    pending = len(glob.glob(f"{BACKUP_TMP_DIR}/*.tar.gz"))
    pc_mounted = os.path.exists(BACKUP_PC_DIR) and os.path.ismount(BACKUP_PC_DIR)

    if not pc_mounted:
        # PC offline — montagem ausente, mas não falha no startup
        return f"⏳ {pending} backup(s) pendente(s). 💻 PC offline."

    if os.path.exists(BACKUP_LOG):
        try:
            with open(BACKUP_LOG, "r") as f:
                ultimas = "".join(f.readlines()[-7:])
            prompt = (
                f"Com base neste log de backup, responda em portugues de forma natural, amigável e MUITO BREVE "
                f"(max 3 linhas). Diga a data/hora do ultimo sucesso e o status geral. Log:\n{ultimas}"
            )
            from hermes.agent.loop import _get_ai_client
            ai_client = _get_ai_client()
            resp = ai_client.chat.completions.create(
                model=MODEL, messages=[{"role": "user", "content": prompt}], temperature=0.3, max_tokens=300
            )
            return f"💾 {resp.choices[0].message.content.strip()}"
        except Exception:
            return "Erro log backup."
    return f"⏳ {pending} backup(s) pendente(s). Log não encontrado."
