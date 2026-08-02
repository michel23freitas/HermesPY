"""Persistência SQLite: conversas, memória, tarefas, migrations."""

import json
import sqlite3
import threading
from datetime import datetime

from hermes.config import DB_PATH

_lock = threading.Lock()


def _connect():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """Cria tabelas, índices e roda migrations leves via PRAGMA user_version."""
    conn = _connect()
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS conversation (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id   TEXT    NOT NULL,
        role      TEXT    NOT NULL,
        content   TEXT    NOT NULL,
        timestamp TEXT    NOT NULL
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS memory (
        key     TEXT PRIMARY KEY,
        value   TEXT NOT NULL,
        source  TEXT,
        updated TEXT NOT NULL
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS tasks (
        id      INTEGER PRIMARY KEY AUTOINCREMENT,
        tipo    TEXT    NOT NULL,
        config  TEXT    NOT NULL,
        ativo   INTEGER DEFAULT 1,
        criado  TEXT    NOT NULL
    )''')

    # Índices para performance
    c.execute("CREATE INDEX IF NOT EXISTS idx_conv_chat ON conversation(chat_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_memory_key ON memory(key)")

    # Migrations baseadas em user_version
    version = c.execute("PRAGMA user_version").fetchone()[0]

    if version < 1:
        # Remove stale pc_status-like memory entries from old versions
        c.execute("DELETE FROM memory WHERE key LIKE 'pc_status%'")
        c.execute("DELETE FROM memory WHERE key = 'ultimo_status_pc'")
        c.execute("PRAGMA user_version = 1")

    conn.commit()
    conn.close()


# ---------- Conversation ----------

def db_save_message(chat_id, role, content):
    with _lock:
        conn = _connect()
        conn.execute(
            "INSERT INTO conversation (chat_id, role, content, timestamp) VALUES (?,?,?,?)",
            (str(chat_id), role, content, datetime.now().isoformat())
        )
        # Mantém apenas as últimas 100 mensagens por chat
        conn.execute(
            "DELETE FROM conversation WHERE chat_id=? AND id NOT IN "
            "(SELECT id FROM conversation WHERE chat_id=? ORDER BY id DESC LIMIT 100)",
            (str(chat_id), str(chat_id))
        )
        conn.commit()
        conn.close()


def db_load_conversation(chat_id, limit=20):
    conn = _connect()
    rows = conn.execute(
        "SELECT role, content FROM conversation WHERE chat_id=? ORDER BY id DESC LIMIT ?",
        (str(chat_id), limit)
    ).fetchall()
    conn.close()
    return [{"role": r[0], "content": r[1]} for r in reversed(rows)]


def db_clear_conversation(chat_id):
    with _lock:
        conn = _connect()
        conn.execute("DELETE FROM conversation WHERE chat_id=?", (str(chat_id),))
        conn.commit()
        conn.close()


# ---------- Memory ----------

def db_memory_save(key, value, source="user"):
    with _lock:
        conn = _connect()
        conn.execute(
            "INSERT OR REPLACE INTO memory (key, value, source, updated) VALUES (?,?,?,?)",
            (key.lower().strip(), value, source, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()


def db_memory_get(key):
    conn = _connect()
    row = conn.execute("SELECT value FROM memory WHERE key=?", (key.lower().strip(),)).fetchone()
    conn.close()
    return row[0] if row else None


def db_memory_search(query):
    conn = _connect()
    rows = conn.execute(
        "SELECT key, value, updated FROM memory WHERE key LIKE ? OR value LIKE ? ORDER BY updated DESC LIMIT 10",
        (f"%{query}%", f"%{query}%")
    ).fetchall()
    conn.close()
    if not rows:
        return "Nenhum resultado na memória."
    return "\n".join(f"• {r[0]}: {r[1]} (salvo em {r[2][:10]})" for r in rows)


def db_memory_list():
    conn = _connect()
    rows = conn.execute("SELECT key, value FROM memory ORDER BY updated DESC").fetchall()
    conn.close()
    if not rows:
        return "Memória vazia."
    return "\n".join(f"• {r[0]}: {r[1]}" for r in rows)


# ---------- Tasks ----------

def db_task_add(tipo, config_dict):
    with _lock:
        conn = _connect()
        conn.execute(
            "INSERT INTO tasks (tipo, config, criado) VALUES (?,?,?)",
            (tipo, json.dumps(config_dict), datetime.now().isoformat())
        )
        conn.commit()
        conn.close()


def db_task_list():
    conn = _connect()
    rows = conn.execute("SELECT id, tipo, config, criado FROM tasks WHERE ativo=1").fetchall()
    conn.close()
    return rows


def db_task_remove(task_id):
    with _lock:
        conn = _connect()
        conn.execute("UPDATE tasks SET ativo=0 WHERE id=?", (task_id,))
        conn.commit()
        conn.close()
