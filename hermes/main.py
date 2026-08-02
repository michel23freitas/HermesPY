"""Hermes v2 - Entry point principal.

Inicializa: DB, knowledge sync, bot Telegram com handlers, watchdog e notificação de startup.
"""

import os
import signal
import threading
from datetime import datetime

# Aplicar .env antes de tudo
from dotenv import load_dotenv
load_dotenv()

from hermes.config import SHUTDOWN_MARKER
from hermes.db import init_db
from hermes.services.knowledge import sync_knowledge_base
from hermes.telegram.bot import start_bot, get_bot
from hermes.services.watchdog import watchdog, send_startup_notification


def on_shutdown(signum=None, frame=None):
    """Handler de shutdown limpo: escreve marker e encerra."""
    try:
        with open(SHUTDOWN_MARKER, "w") as f:
            f.write(datetime.now().isoformat())
    except Exception:
        pass
    print(f"Hermes shutdown signal ({signum})")
    raise SystemExit(0)


def main():
    # 1. Inicializa DB (cria tabelas + migrations)
    init_db()

    # 2. Sincroniza base de conhecimento
    sync_knowledge_base()

    # 3. Registra handlers de sinal
    signal.signal(signal.SIGTERM, on_shutdown)
    signal.signal(signal.SIGINT, on_shutdown)

    # 4. Inicia threads de background
    threading.Thread(target=watchdog, daemon=True).start()
    threading.Thread(target=send_startup_notification, daemon=True).start()

    # 5. Inicia bot (infinity_polling — bloqueante)
    print("Hermes v2 online. Iniciando polling...")
    start_bot()


if __name__ == "__main__":
    main()
