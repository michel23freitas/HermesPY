"""Menus inline do Telegram: teclados e roteamento de callbacks.

Formato de callback: hms:<categoria>:<acao>
Exemplo: hms:docker:ps, hms:ha:entities, hms:system:ram
"""

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton


# ---- Definições de menus ----

# Cada categoria: (label do botão principal, callback_data)
MAIN_MENU_BUTTONS = [
    ("⚡ Ligar PC",      "hms:system:wol"),
    ("🖥️ Sistema",       "hms:system"),
    ("🏠 Home Assistant", "hms:ha"),
    ("🐳 Docker",        "hms:docker"),
    ("💾 Backup",        "hms:backup"),
    ("📜 Logs",          "hms:logs"),
    ("💬 Conversa",      "hms:conversa"),
]

SUB_MENUS = {
    # Sistema
    "hms:system": [
        ("📊 Status geral",   "hms:system:status"),
        ("📈 RAM",            "hms:system:ram"),
        ("💾 Disco",          "hms:system:disk"),
        ("🌡️ Temperatura",   "hms:system:temp"),
        ("⏱️ Uptime",         "hms:system:uptime"),
        ("⚡ Ligar PC",      "hms:system:wol"),
    ],
    # Home Assistant
    "hms:ha": [
        ("🏠 HA status",       "hms:ha:status"),
        ("📋 Entidades",       "hms:ha:entities"),
    ],
    # Docker
    "hms:docker": [
        ("📦 Containers",     "hms:docker:ps"),
        ("🌐 Networks",        "hms:docker:networks"),
        ("💽 Volumes",         "hms:docker:volumes"),
        ("📝 Logsum HA",       "hms:docker:logsum"),
    ],
    # Backup
    "hms:backup": [
        ("💾 Status backup",  "hms:backup:status"),
    ],
    # Logs
    "hms:logs": [
        ("📜 Logs HA",         "hms:logs:ha_logs"),
        ("📝 Logsum HA",       "hms:logs:ha_logsum"),
    ],
    # Conversa
    "hms:conversa": [
        ("🧹 Limpar histórico", "hms:conversa:clear"),
        ("🔄 Sync skills",       "hms:conversa:sync"),
    ],
}


def build_main_menu():
    """Constrói o teclado inline do menu principal."""
    markup = InlineKeyboardMarkup()
    markup.row_width = 2
    for label, callback in MAIN_MENU_BUTTONS:
        markup.add(InlineKeyboardButton(label, callback_data=callback))
    return markup


def build_sub_menu(category_key):
    """Constrói um teclado inline para uma sub-categoria.

    category_key: ex "hms:system", "hms:docker", etc.
    """
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    buttons = SUB_MENUS.get(category_key, [])
    for label, callback in buttons:
        markup.add(InlineKeyboardButton(label, callback_data=callback))
    # Sempre oferece voltar ao menu principal
    markup.add(InlineKeyboardButton("⬅️ Voltar", callback_data="hms:main"))
    return markup


# ---- Callback dispatch ----

_CATEGORY_LABELS = {
    "hms:system":     "Sistema",
    "hms:ha":         "Home Assistant",
    "hms:docker":     "Docker",
    "hms:backup":     "Backup",
    "hms:logs":       "Logs",
    "hms:conversa":   "Conversa",
}


def _category_label(key):
    return _CATEGORY_LABELS.get(key, key)


def handle_menu_callback(bot, call):
    """Roteia callbacks do menu inline e responde via edit_message_text.

    call.data format: hms:<cat>[:<action>]
    """
    data = call.data
    chat_id = call.message.chat.id

    # Menu principal
    if data == "hms:main":
        bot.edit_message_text(
            "📋 Menu Hermes — escolha uma categoria:",
            chat_id=chat_id, message_id=call.message.message_id,
            reply_markup=build_main_menu(),
        )
        bot.answer_callback_query(call.id)
        return

    # Ligar PC: feedback imediato + confirmação assíncrona após 60s
    if data == "hms:system:wol":
        _start_wol_flow(bot, call)
        return

    # Navegar para uma sub-categoria (sem action)
    if data in SUB_MENUS:
        label = _category_label(data)
        bot.edit_message_text(
            f"📋 Menu {label} — escolha uma opção:",
            chat_id=chat_id, message_id=call.message.message_id,
            reply_markup=build_sub_menu(data),
        )
        bot.answer_callback_query(call.id)
        return

    # Ação específica: hms:<cat>:<action>
    parts = data.split(":")
    if len(parts) >= 3:
        cat, action = parts[1], parts[2]
        result = _dispatch_action(cat, action, chat_id)
        _edit_result(bot, call, result)
        return

    bot.answer_callback_query(call.id, "Callback não reconhecido.")


def _start_wol_flow(bot, call):
    """Liga o PC via botão WOL do HA: feedback imediato + confirmação após 60s."""
    import threading
    import time
    from hermes.tools.wol import acionar_botao_wol, is_windows_online

    chat_id = call.message.chat.id
    message_id = call.message.message_id

    # Já online?
    if is_windows_online():
        bot.answer_callback_query(call.id)
        bot.edit_message_text("✅ Computador já está online!", chat_id=chat_id,
                              message_id=message_id, reply_markup=build_main_menu())
        return

    # Aciona o botão WOL no HA (rápido)
    ok, msg = acionar_botao_wol()
    if not ok:
        bot.answer_callback_query(call.id)
        bot.edit_message_text(msg[:4000], chat_id=chat_id, message_id=message_id,
                              reply_markup=build_main_menu())
        return

    # Feedback imediato
    bot.answer_callback_query(call.id)
    bot.edit_message_text("⚡ Computador ligando...", chat_id=chat_id,
                          message_id=message_id, reply_markup=build_main_menu())

    # Confirmação assíncrona: após 60s pinga e atualiza a mensagem
    def _confirm():
        time.sleep(60)
        try:
            if is_windows_online():
                final = "✅ Computador já está online!"
            else:
                final = "⚠️ Computador ainda não respondeu na rede (WOL acionado)."
            bot.edit_message_text(final, chat_id=chat_id, message_id=message_id,
                                  reply_markup=build_main_menu())
        except Exception:
            pass

    threading.Thread(target=_confirm, daemon=True).start()


def _dispatch_action(cat, action, chat_id):
    """Retorna a resposta (string) para uma ação de menu."""
    from hermes.telegram.commands import (
        cmd_status, cmd_containers, cmd_logs, cmd_ha,
        cmd_entidades, cmd_logsum,
        cmd_limpar, cmd_sync,
    )
    from hermes.tools.backup import cmd_backup_status
    from hermes.tools.netdata_tools import tool_netdata_metrics
    from hermes.telegram.commands import format_ram_output, format_disk_output, format_temp_output
    from hermes.tools.system_tools import tool_system_uptime
    from hermes.tools.docker_tools import (
        tool_docker_networks, tool_docker_volumes, tool_docker_logsum,
    )

    if cat == "system":
        if action == "status":   return cmd_status()
        if action == "ram":      return format_ram_output(tool_netdata_metrics("ram"))
        if action == "disk":     return format_disk_output(tool_netdata_metrics("disk"))
        if action == "temp":     return format_temp_output(tool_netdata_metrics("temperature"))
        if action == "uptime":   return tool_system_uptime()

    if cat == "ha":
        if action == "status":     return cmd_ha()
        if action == "entities":   return cmd_entidades()

    if cat == "docker":
        if action == "ps":       return cmd_containers()
        if action == "networks": return tool_docker_networks()
        if action == "volumes":  return tool_docker_volumes()
        if action == "logsum":   return tool_docker_logsum("homeassistant", 80)

    if cat == "backup":
        if action == "status":   return cmd_backup_status()

    if cat == "logs":
        if action == "ha_logs":   return cmd_logs()
        if action == "ha_logsum": return tool_docker_logsum("homeassistant", 80)

    if cat == "conversa":
        if action == "clear":   return cmd_limpar(chat_id)
        if action == "sync":    return cmd_sync()

    return f"Ação desconhecida: {cat}:{action}"


def _edit_result(bot, call, result):
    """Edita a mensagem do callback com o resultado, preservando um botão de volta."""
    text = result if isinstance(result, str) else result[0] if isinstance(result, tuple) else str(result)
    bot.edit_message_text(
        text[:4000],
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=build_main_menu(),
    )
    bot.answer_callback_query(call.id)
