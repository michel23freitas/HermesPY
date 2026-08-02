"""Ferramenta de gerenciamento de tarefas de monitoramento dinâmico."""

from hermes.db import db_task_add, db_task_list, db_task_remove


def tool_task_manage(action, tipo=None, config=None, task_id=None):
    """Gerencia tarefas de monitoramento dinâmico.

    Tipos disponíveis: monitor_ram | monitor_container | monitor_temperatura.
    """
    if action == "add":
        if not tipo:
            return "Uso: task_manage add <tipo> <config>"
        db_task_add(tipo, config or {})
        return f"Tarefa criada: {tipo}"
    if action == "list":
        rows = db_task_list()
        if not rows:
            return "Nenhuma tarefa."
        lines = []
        for tid, tipo, cfg_j, criado in rows:
            lines.append(f"• {tid}: {tipo} ({cfg_j})")
        return "\n".join(lines)
    if action == "remove":
        if task_id is None:
            return "Uso: task_manage remove <task_id>"
        db_task_remove(task_id)
        return f"Tarefa {task_id} removida."
    return "Ação inválida: add | list | remove"
