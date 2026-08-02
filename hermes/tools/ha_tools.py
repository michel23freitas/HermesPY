"""Ferramentas Home Assistant: states, find_entity, call_service, restart."""

import json
import time
import requests

from hermes.config import HA_TOKEN, HA_URL


_HA_CACHE = {}
_HA_CACHE_TS = 0.0


def _ha_h():
    return {"Authorization": f"Bearer {HA_TOKEN}", "Content-Type": "application/json"}


def _refresh_ha_cache():
    global _HA_CACHE, _HA_CACHE_TS
    if not HA_TOKEN:
        return
    try:
        r = requests.get(f"{HA_URL}/api/states", headers=_ha_h(), timeout=10)
        if r.status_code == 200:
            _HA_CACHE = {
                s["entity_id"]: {"state": s["state"], "attrs": s.get("attributes", {})}
                for s in r.json()
            }
            _HA_CACHE_TS = time.time()
    except Exception:
        pass


def tool_ha_states(entity_id=None):
    if not HA_TOKEN:
        return "HA_TOKEN nao configurado"
    try:
        if entity_id:
            r = requests.get(f"{HA_URL}/api/states/{entity_id}", headers=_ha_h(), timeout=10)
            if r.status_code == 200:
                s = r.json()
                return json.dumps(
                    {"entity_id": s["entity_id"], "state": s["state"], "attributes": s.get("attributes", {})},
                    ensure_ascii=False,
                    indent=2,
                )
            return f"Erro {r.status_code}"
        else:
            r = requests.get(f"{HA_URL}/api/states", headers=_ha_h(), timeout=10)
            if r.status_code == 200:
                states = r.json()
                lista = [f"{s['entity_id']}: {s['state']}" for s in states[:30]]
                return "\n".join(lista) + f"\n\n(Total: {len(states)} entidades)"
            return f"Erro {r.status_code}"
    except Exception as e:
        return f"Erro HA: {e}"


def tool_ha_find_entity(description):
    global _HA_CACHE_TS
    if time.time() - _HA_CACHE_TS > 300:
        _refresh_ha_cache()
    if not _HA_CACHE:
        return "Cache HA vazio."
    words = description.lower().split()
    matches = []
    for entity_id, data in _HA_CACHE.items():
        score = sum(
            1 for w in words
            if w in entity_id.lower() or w in data["attrs"].get("friendly_name", "").lower()
        )
        if score > 0:
            matches.append((score, entity_id, data["state"], data["attrs"].get("friendly_name", "")))
    matches.sort(reverse=True)
    if not matches:
        return f"Nenhuma entidade encontrada para '{description}'."
    return "\n".join([f"• {m[1]} ({m[3]}): {m[2]}" for m in matches[:10]])


def tool_ha_call_service(domain, service, entity_id, extra_data=None):
    if not HA_TOKEN:
        return "HA_TOKEN nao configurado"
    # Valida se a entidade existe antes de chamar o serviço
    try:
        check = requests.get(f"{HA_URL}/api/states/{entity_id}", headers=_ha_h(), timeout=5)
        if check.status_code == 404:
            sugestoes = tool_ha_find_entity(entity_id.replace(".", " ").replace("_", " "))
            return (
                f"ENTIDADE NAO ENCONTRADA: '{entity_id}'\n"
                f"Use ha_find_entity para descobrir o entity_id correto.\n"
                f"Sugestoes:\n{sugestoes}"
            )
    except Exception as e:
        return f"Erro ao validar entidade: {e}"
    data = {"entity_id": entity_id}
    if extra_data:
        data.update(extra_data)
    try:
        r = requests.post(
            f"{HA_URL}/api/services/{domain}/{service}", headers=_ha_h(), json=data, timeout=10
        )
        if r.status_code in [200, 201]:
            try:
                s = requests.get(f"{HA_URL}/api/states/{entity_id}", headers=_ha_h(), timeout=5)
                novo_estado = s.json().get("state", "?") if s.status_code == 200 else "?"
                return f"OK — estado atual: {novo_estado}"
            except Exception:
                return "OK"
        return f"Erro {r.status_code}: {r.text[:200]}"
    except Exception as e:
        return f"Erro: {e}"


def tool_ha_restart():
    if not HA_TOKEN:
        return "HA_TOKEN nao configurado"
    try:
        r = requests.post(f"{HA_URL}/api/services/homeassistant/restart", headers=_ha_h(), timeout=10)
        return "HA reiniciando..." if r.status_code in [200, 201] else f"Erro {r.status_code}"
    except Exception as e:
        return f"Erro: {e}"
