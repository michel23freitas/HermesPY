"""Configuração e carregamento de ambiente."""

import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_TOKEN  = os.getenv("TELEGRAM_TOKEN")
ALLOWED_CHAT_ID = os.getenv("ALLOWED_CHAT_ID")

# LLM / OpenRouter
OPENROUTER_KEY  = os.getenv("OPENROUTER_KEY")
MODEL           = os.getenv("MODEL", "openrouter/auto")

# Home Assistant
HA_TOKEN = os.getenv("HA_TOKEN", "")
HA_URL   = os.getenv("HA_URL", "http://192.168.15.15:8123")

# Netdata
NETDATA_URL = os.getenv("NETDATA_URL", "http://192.168.15.15:19999")

# Wake-on-LAN (Windows)
WOL_MAC        = os.getenv("WOL_MAC", "C8:7F:54:63:36:C2")
WOL_BROADCAST  = os.getenv("WOL_BROADCAST", "192.168.15.255")
WINDOWS_IP     = os.getenv("WINDOWS_IP", "192.168.15.10")



# Paths
DB_PATH         = os.getenv("DB_PATH", "/app/data/hermes.db")
KNOWLEDGE_DIR   = os.getenv("KNOWLEDGE_DIR", "/app/knowledge")
SHUTDOWN_MARKER = os.getenv("SHUTDOWN_MARKER", "/app/data/.clean_shutdown")

# Runtime dirs
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
