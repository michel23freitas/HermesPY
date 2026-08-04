"""Registry de tools: mapeia nomes para funções e fornece o schema para o LLM."""

from hermes.tools.system_tools import tool_system_uptime
from hermes.tools.docker_tools import (
    tool_docker_ps, tool_docker_logs, tool_docker_stats,
    tool_docker_restart, tool_docker_stop, tool_docker_start,
    tool_docker_inspect, tool_docker_networks, tool_docker_volumes,
    tool_docker_logsum,
)
from hermes.tools.netdata_tools import tool_netdata_metrics
from hermes.tools.ha_tools import (
    tool_ha_states, tool_ha_find_entity, tool_ha_call_service, tool_ha_restart,
)
from hermes.tools.memory_tools import (
    memory_save, memory_search, memory_list,
    tool_list_knowledge, tool_search_knowledge, tool_read_file, tool_file_search, tool_shell_read,
)
from hermes.tools.wol import tool_ligar_windows, tool_ping_windows
from hermes.tools.backup import cmd_backup_status
from hermes.tools.tasks import tool_task_manage

# --- Tool functions registry ---

TOOL_MAP = {
    "docker_ps":       lambda a: tool_docker_ps(),
    "docker_logs":     lambda a: tool_docker_logs(a["container"], a.get("lines", 50)),
    "docker_stats":    lambda a: tool_docker_stats(),
    "docker_restart":  lambda a: tool_docker_restart(a["container"]),
    "docker_stop":     lambda a: tool_docker_stop(a["container"]),
    "docker_start":    lambda a: tool_docker_start(a["container"]),
    "docker_inspect":  lambda a: tool_docker_inspect(a["container"]),
    "docker_networks": lambda a: tool_docker_networks(),
    "docker_volumes":  lambda a: tool_docker_volumes(),
    "docker_logsum":   lambda a: tool_docker_logsum(a["container"], a.get("lines", 60)),
    "netdata_metrics": lambda a: tool_netdata_metrics(a.get("metric", "overview")),
    "system_uptime":   lambda a: tool_system_uptime(),
    "ha_states":       lambda a: tool_ha_states(a.get("entity_id")),
    "ha_find_entity":  lambda a: tool_ha_find_entity(a["description"]),
    "ha_call_service": lambda a: tool_ha_call_service(a["domain"], a["service"], a["entity_id"], a.get("extra_data")),
    "ha_restart":      lambda a: tool_ha_restart(),
    "memory_save":     lambda a: (memory_save(a["key"], a["value"]), f"Memorizado: {a['key']}")[1],
    "memory_search":   lambda a: memory_search(a["query"]),
    "memory_list":     lambda a: memory_list(),
    "list_knowledge":  lambda a: tool_list_knowledge(),
    "search_knowledge":lambda a: tool_search_knowledge(a["query"]),
    "read_file":       lambda a: tool_read_file(a["path"]),
    "file_search":     lambda a: tool_file_search(a["pattern"]),
    "shell_read":      lambda a: tool_shell_read(a["command"]),
    "ligar_windows":   lambda a: tool_ligar_windows(),
    "ping_windows":    lambda a: tool_ping_windows(),
    "task_manage":     lambda a: tool_task_manage(a["action"], a.get("tipo"), a.get("config"), a.get("task_id")),
}


def execute_tool(name, args):
    fn = TOOL_MAP.get(name)
    if not fn:
        return f"Ferramenta desconhecida: {name}"
    try:
        return fn(args)
    except Exception as e:
        return f"Erro em {name}: {e}"


# --- Tool schemas (declarative, for LLM) ---

TOOLS = [
    {"type": "function", "function": {"name": "docker_ps",
        "description": "Lista containers Docker com status",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "docker_logs",
        "description": "Logs de um container",
        "parameters": {"type": "object", "properties": {
            "container": {"type": "string"}, "lines": {"type": "integer"}},
            "required": ["container"]}}},
    {"type": "function", "function": {"name": "docker_stats",
        "description": "CPU e RAM por container",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "docker_restart",
        "description": "Reinicia container",
        "parameters": {"type": "object", "properties": {"container": {"type": "string"}},
            "required": ["container"]}}},
    {"type": "function", "function": {"name": "docker_stop",
        "description": "Para container",
        "parameters": {"type": "object", "properties": {"container": {"type": "string"}},
            "required": ["container"]}}},
    {"type": "function", "function": {"name": "docker_start",
        "description": "Inicia container parado",
        "parameters": {"type": "object", "properties": {"container": {"type": "string"}},
            "required": ["container"]}}},
    {"type": "function", "function": {"name": "docker_inspect",
        "description": "Inspeção de container: volumes, networks, variáveis, portas.",
        "parameters": {"type": "object", "properties": {"container": {"type": "string"}},
            "required": ["container"]}}},
    {"type": "function", "function": {"name": "docker_networks",
        "description": "Lista redes Docker e containers em cada rede.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "docker_volumes",
        "description": "Lista volumes Docker e seus mountpoints.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "docker_logsum",
        "description": "Resumo IA de erros críticos dos logs de um container.",
        "parameters": {"type": "object", "properties": {
            "container": {"type": "string"}, "lines": {"type": "integer"}},
            "required": ["container"]}}},
    {"type": "function", "function": {"name": "netdata_metrics",
        "description": "Métricas via Netdata: cpu | ram | disk | temperature | network | overview",
        "parameters": {"type": "object", "properties": {
            "metric": {"type": "string", "description": "cpu | ram | disk | temperature | network | overview"}},
            "required": ["metric"]}}},
    {"type": "function", "function": {"name": "system_uptime",
        "description": "Uptime e carga do sistema",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "ha_states",
        "description": "Estado de entidades do Home Assistant",
        "parameters": {"type": "object", "properties": {
            "entity_id": {"type": "string", "description": "ID da entidade. Se omitido lista todas."}},
            "required": []}}},
    {"type": "function", "function": {"name": "ha_find_entity",
        "description": "Busca entidades HA por descrição em português. Use quando o usuário disser 'a luz da sala', 'o ar do quarto', 'câmera da garagem' — sem saber o entity_id exato.",
        "parameters": {"type": "object", "properties": {
            "description": {"type": "string", "description": "Descrição em português. Ex: luz sala, ar quarto, camera garagem"}},
            "required": ["description"]}}},
    {"type": "function", "function": {"name": "ha_call_service",
        "description": "Executa serviço no Home Assistant. Ordem: domain, service, entity_id, extra_data.",
        "parameters": {"type": "object", "properties": {
            "domain": {"type": "string"}, "service": {"type": "string"},
            "entity_id": {"type": "string"},
            "extra_data": {"type": "object"}},
            "required": ["domain", "service", "entity_id"]}}},
    {"type": "function", "function": {"name": "ha_restart",
        "description": "Reinicia o Home Assistant",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "memory_save",
        "description": "Salva um fato na memória persistente. Use para IPs, portas, caminhos, configs.",
        "parameters": {"type": "object", "properties": {
            "key": {"type": "string"}, "value": {"type": "string"}},
            "required": ["key", "value"]}}},
    {"type": "function", "function": {"name": "memory_search",
        "description": "Busca fatos na memória antes de ações sobre IPs, portas, caminhos.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string"}},
            "required": ["query"]}}},
    {"type": "function", "function": {"name": "list_knowledge",
        "description": "Lista arquivos na base de conhecimento local.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "search_knowledge",
        "description": "Busca termos em arquivos de configuração.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string"}},
            "required": ["query"]}}},
    {"type": "function", "function": {"name": "read_file",
        "description": "Lê conteúdo de arquivo de configuração ou script.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "Caminho absoluto"}},
            "required": ["path"]}}},
    {"type": "function", "function": {"name": "file_search",
        "description": "Busca arquivos pelo nome.",
        "parameters": {"type": "object", "properties": {
            "pattern": {"type": "string"}},
            "required": ["pattern"]}}},
    {"type": "function", "function": {"name": "shell_read",
        "description": "Executa comando shell de leitura. Bloqueado para comandos destrutivos.",
        "parameters": {"type": "object", "properties": {
            "command": {"type": "string"}},
            "required": ["command"]}}},
    {"type": "function", "function": {"name": "ligar_windows",
        "description": "Liga PC Windows acionando o botão WOL do Home Assistant (button.wake_on_lan_c8_7f_54_63_36_c2).",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "ping_windows",
        "description": "Verifica se o PC Windows está ligado via ping (live-state).",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "task_manage",
        "description": "Gerencia tarefas de monitoramento dinâmico. Tipos: monitor_ram | monitor_container | monitor_temperatura.",
        "parameters": {"type": "object", "properties": {
            "action": {"type": "string", "enum": ["add", "list", "remove"]},
            "tipo": {"type": "string", "description": "monitor_ram | monitor_container | monitor_temperatura"},
            "config": {"type": "object", "description": "{limit: 85} para ram/temp, {container: 'nome'} para container"},
            "task_id": {"type": "integer"}},
            "required": ["action"]}}},
]
