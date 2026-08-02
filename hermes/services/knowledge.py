"""Serviços de conhecimento: sincronização da base knowledge/."""

import os

from hermes.config import KNOWLEDGE_DIR
from hermes.tools.system_tools import run_cmd


def sync_knowledge_base():
    """Sincroniza arquivos de configuração do ambiente para a pasta knowledge/.

    Copia: configuration.yaml, automations.yaml, music_assistant_settings.json,
    script de backup e todos os docker-compose.yml encontrados.
    """
    os.makedirs(KNOWLEDGE_DIR, exist_ok=True)
    sources = [
        ("/opt/homeassistant/config/configuration.yaml", "ha_configuration.yaml"),
        ("/opt/homeassistant/config/automations.yaml", "ha_automations.yaml"),
        ("/opt/musicassistant/settings.json", "music_assistant_settings.json"),
        ("/usr/local/bin/homeassistant-backup.sh", "backup_script.sh"),
    ]
    found_yml = run_cmd("find /opt -name 'docker-compose.yml' 2>/dev/null | head -10")
    for path in found_yml.splitlines():
        if path.strip():
            name = path.replace("/", "_").lstrip("_") + ".yml"
            sources.append((path, name))

    for src, dst in sources:
        if os.path.exists(src):
            run_cmd(f"cp '{src}' '{KNOWLEDGE_DIR}/{dst}'")

    all_files = os.listdir(KNOWLEDGE_DIR)
    if not all_files:
        return "Knowledge base vazia."

    return f"📚 Base de Conhecimento Atualizada ({len(all_files)} arquivos):\n" + \
           "\n".join(f"• {f}" for f in sorted(all_files))
