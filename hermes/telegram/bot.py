"""Bot Telegram: setup, handlers, callback routing."""

import telebot

from hermes.config import TELEGRAM_TOKEN, ALLOWED_CHAT_ID
from hermes.telegram.commands import FIXED_COMMANDS, run_fixed_command
from hermes.telegram.menus import handle_menu_callback
from hermes.agent.loop import run_agent

# Bot singleton (lazy — só instanciado no primeiro uso)
_bot = None


def get_bot():
    """Retorna a instância singleton do bot, criando-a se necessário."""
    global _bot
    if _bot is None:
        if not TELEGRAM_TOKEN:
            raise RuntimeError("TELEGRAM_TOKEN ausente.")
        _bot = telebot.TeleBot(TELEGRAM_TOKEN)
        register_handlers()
    return _bot


def _first_token(message):
    if not getattr(message, "text", None):
        return ""
    parts = message.text.strip().split()
    return parts[0].lower() if parts else ""


def register_handlers():
    """Registra todos os handlers de mensagem e callback no bot."""
    bot = get_bot()

    @bot.message_handler(func=lambda m: _first_token(m) in FIXED_COMMANDS)
    def _handle_command(message):
        _dispatch_command(message)

    @bot.message_handler(func=lambda m: _first_token(m) not in FIXED_COMMANDS)
    def _handle_message(message):
        _dispatch_message(message)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("hms:"))
    def _handle_callback(call):
        if str(call.message.chat.id) != str(ALLOWED_CHAT_ID):
            bot.answer_callback_query(call.id)
            return
        handle_menu_callback(bot, call)


def _dispatch_command(message):
    bot = get_bot()
    if str(message.chat.id) != str(ALLOWED_CHAT_ID):
        return
    cmd = message.text.strip().split()[0].lower()
    args = message.text.strip().split()[1:]

    if cmd == "/reiniciar":
        result = run_fixed_command(cmd, " ".join(args), message.chat.id)
    elif cmd == "/limpar":
        result = run_fixed_command(cmd, None, message.chat.id)
    else:
        result = run_fixed_command(cmd, None, message.chat.id)

    if result:
        # Se result for tupla (text, markup), usa markup
        if isinstance(result, tuple) and len(result) == 2:
            text, markup = result
            bot.send_message(message.chat.id, text, reply_markup=markup)
        else:
            bot.reply_to(message, str(result))


def _dispatch_message(message):
    bot = get_bot()
    if str(message.chat.id) != str(ALLOWED_CHAT_ID):
        return
    if not getattr(message, "text", None):
        return
    text = message.text.strip()
    if not text:
        return

    # Comandos não fixos vão para o agente
    status_msg = bot.reply_to(message, "🧠 Analisando...")
    try:
        answer, steps = run_agent(text, message.chat.id)
        final = ("\n".join(steps) + "\n\n" if steps else "") + answer
        bot.edit_message_text(final[:4000], chat_id=message.chat.id,
                              message_id=status_msg.message_id)
    except Exception:
        bot.edit_message_text("Erro processamento.",
                              chat_id=message.chat.id, message_id=status_msg.message_id)


def start_bot():
    """Registra handlers e inicia polling."""
    bot = get_bot()
    bot.infinity_polling()
