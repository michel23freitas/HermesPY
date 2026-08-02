"""Loop do agente LLM: run_agent com iteração de tools."""

import json
import logging
import os

from hermes.db import db_load_conversation, db_save_message
from hermes.tools.registry import TOOLS, execute_tool
from hermes.agent.prompts import get_system_prompt
from hermes.config import DB_PATH

logger = logging.getLogger(__name__)

# Configura logging para arquivo se ainda não configurado
_LOG_DIR = "/app/data"
_LOG_FILE = "/app/data/hermes_agent.log"

if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(_LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )

# Cliente OpenAI (OpenRouter) — lazy init
_ai_client = None


def _get_ai_client():
    global _ai_client
    if _ai_client is None:
        from openai import OpenAI
        from hermes.config import OPENROUTER_KEY
        _ai_client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_KEY)
    return _ai_client


# Ferramentas que exigem intenção explícita do usuário
_INTENTIONAL_TOOLS = {"ligar_windows", "ping_windows"}

# Palavras-chave que indicam intenção real de usar essas ferramentas
_INTENT_KEYWORDS = [
    "liga", "ligar", "acorda", "wake", "wol", "ping",
    "online", "pc", "computador", "windows",
]


def _has_intent(user_message):
    """Retorna True se a mensagem indica intenção explícita de usar WOL/ping."""
    msg_lower = user_message.lower()
    return any(kw in msg_lower for kw in _INTENT_KEYWORDS)


def _is_tool_leak(response_text, user_message):
    """Retorna True se a resposta parece ser output de ferramenta vazado sem intenção."""
    if not _has_intent(user_message):
        leak_indicators = [
            "WOL enviado",
            "PC ainda offline",
            "Verifique BIOS",
            "Windows ONLINE",
            "Windows OFFLINE",
        ]
        return any(indicator in response_text for indicator in leak_indicators)
    return False


def run_agent(user_message, chat_id):
    """Processa uma mensagem do usuário via LLM com chamadas de tools.

    Retorna (answer_text, tool_steps_list).
    """
    ai_client = _get_ai_client()
    conversation_history = db_load_conversation(chat_id, limit=20)
    db_save_message(chat_id, "user", user_message)

    messages = [{"role": "system", "content": get_system_prompt(user_message)}] + conversation_history
    messages.append({"role": "user", "content": user_message})

    from hermes.config import MODEL
    tool_steps = []

    # Ferramentas que exigem intenção explícita do usuário
    INTENTIONAL_TOOLS = {"ligar_windows", "ping_windows"}

    logger.info("run_agent: chat_id=%s msg=%r", chat_id, user_message)

    for i in range(7):
        resp = ai_client.chat.completions.create(
            model=MODEL, messages=messages, tools=TOOLS,
            tool_choice="auto", temperature=0.1, max_tokens=1200,
        )
        choice = resp.choices[0]
        msg = choice.message
        md = {"role": "assistant"}
        if msg.content:
            md["content"] = msg.content
        if msg.tool_calls:
            md["tool_calls"] = [{"id": tc.id, "type": "function",
                                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                                for tc in msg.tool_calls]
        messages.append(md)

        if msg.tool_calls:
            tool_names = [tc.function.name for tc in msg.tool_calls]
            logger.info("run_agent iteration %d: tool_calls=%s", i, tool_names)

            # Filtra ferramentas que exigem intenção explícita
            if any(t in INTENTIONAL_TOOLS for t in tool_names):
                msg_lower = user_message.lower()
                has_intent = any(
                    kw in msg_lower
                    for kw in ["liga", "ligar", "acorda", "wake", "wol", "ping", "online", "pc", "computador", "windows"]
                )
                if not has_intent:
                    logger.info("run_agent: blocked intentional tool %s for non-intent message %r", tool_names, user_message)
                    messages.pop()
                    messages.append({"role": "assistant", "content": "Como posso ajudar?"})
                    final = "Olá! 👋 Como posso ajudar?"
                    db_save_message(chat_id, "assistant", final)
                    return final, tool_steps

            for tc in msg.tool_calls:
                name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments)
                except Exception:
                    args = {}
                result = execute_tool(name, args)
                args_str = ", ".join(f"{k}={v}" for k, v in args.items()) if args else ""
                tool_steps.append(f"🔧 `{name}({args_str})`")
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": str(result)[:3000]})
            continue

        final = (msg.content or "").strip()
        if not final:
            messages.append({"role": "user", "content": "Responda após usar ferramentas."})
            continue

        # Filtra respostas de ferramenta que vazaram pro content sem intenção explícita
        if _is_tool_leak(final, user_message):
            logger.info("run_agent: blocked tool leak response for non-intent message %r", user_message)
            messages.pop()
            messages.append({"role": "assistant", "content": "Como posso ajudar?"})
            final = "Olá! 👋 Como posso ajudar?"
            db_save_message(chat_id, "assistant", final)
            return final, tool_steps

        db_save_message(chat_id, "assistant", final)
        logger.info("run_agent: final answer=%r", final[:100])
        return final, tool_steps

    # Loop esgotado sem resposta final de texto
    for m in reversed(messages):
        if m.get("role") == "assistant" and m.get("content"):
            db_save_message(chat_id, "assistant", m["content"])
            logger.info("run_agent: exhausted loop, returning last assistant msg")
            return m["content"], tool_steps
    logger.warning("run_agent: exhausted loop with no assistant content")
    return "Não consegui processar.", tool_steps
