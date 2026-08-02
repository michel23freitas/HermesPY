"""Loop do agente LLM: run_agent com iteração de tools."""

import json

from hermes.db import db_load_conversation, db_save_message
from hermes.tools.registry import TOOLS, execute_tool
from hermes.agent.prompts import get_system_prompt

# Cliente OpenAI (OpenRouter) — lazy init
_ai_client = None


def _get_ai_client():
    global _ai_client
    if _ai_client is None:
        from openai import OpenAI
        from hermes.config import OPENROUTER_KEY
        _ai_client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_KEY)
    return _ai_client


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

    for _ in range(7):
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
        db_save_message(chat_id, "assistant", final)
        return final, tool_steps

    # Loop esgotado sem resposta final de texto
    for m in reversed(messages):
        if m.get("role") == "assistant" and m.get("content"):
            db_save_message(chat_id, "assistant", m["content"])
            return m["content"], tool_steps
    return "Não consegui processar.", tool_steps
