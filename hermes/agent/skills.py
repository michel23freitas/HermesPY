"""Carregamento e seleção de skills (markdown) da base de conhecimento.

Carrega arquivos skill_*.md da pasta knowledge/, exceto Marmitex, e seleciona
skills relevantes por keyword matching antes de injetar no prompt do LLM.
"""

import os

from hermes.config import KNOWLEDGE_DIR

# Skills excluídas por decisão de redesign
SKILL_BLACKLIST = ("skill_marmitex_marisa.md",)

# Limite de tamanho total de skills injetadas no prompt (chars)
MAX_SKILLS_CHARS = 8000


def _load_skill_files():
    """Retorna lista de (filename, content) para skill_*.md, exceto blacklist."""
    if not os.path.exists(KNOWLEDGE_DIR):
        return []
    result = []
    for filename in sorted(os.listdir(KNOWLEDGE_DIR)):
        if not (filename.startswith("skill_") and filename.endswith(".md")):
            continue
        if filename in SKILL_BLACKLIST:
            continue
        filepath = os.path.join(KNOWLEDGE_DIR, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                result.append((filename, f.read().strip()))
        except Exception:
            pass
    return result


def _keyword_from_query(query):
    """Extrai keywords simples da query do usuário."""
    return query.lower().split()


def select_skills(user_query=""):
    """Seleciona skills relevantes por keyword. Se query vazia, carrega todas (cortando no limite)."""
    all_skills = _load_skill_files()
    if not all_skills:
        return ""

    query_lower = user_query.lower().strip()

    if not query_lower:
        # Sem query — injeta todas dentro do limite de tamanho
        selected = all_skills
    else:
        keywords = _keyword_from_query(query_lower)
        selected = []
        for filename, content in all_skills:
            # Se qualquer keyword aparece no conteúdo do skill, inclui
            if any(kw in content.lower() for kw in keywords if len(kw) > 2):
                selected.append((filename, content))
        # Fallback: se nada combinou, inclui skills de sistema e docker (gerais)
        if not selected:
            selected = [s for s in all_skills if s[0] in ("skill_sistema.md", "skill_docker.md", "skill_homeassistant.md")]

    # Monta texto respeitando limite de tamanho
    parts = []
    total = 0
    for filename, content in selected:
        # Sinaliza o nome do skill para o LLM saber de onde vem cada trecho
        block = f"### {filename}\n{content}"
        if total + len(block) > MAX_SKILLS_CHARS and parts:
            break
        parts.append(block)
        total += len(block)

    return "\n\n".join(parts)


def load_skills(user_query=""):
    """Interface de compat: carrega skills relevantes (ou todas) como texto único."""
    return select_skills(user_query)
