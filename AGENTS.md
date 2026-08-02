# Hermes - OpenCode Agent Guide

## Core Architecture

**Hermes** = Central intelligence controller for DietPi RPi3
- **Interface**: Telegram bot (intended to be API-based for HA integration)
- **Controller**: Home Assistant (via HTTP API)
- **Monitor**: Netdata (CPU/RAM/Temp/Disk)
- **Storage**: SQLite (conversation history, memory, tasks)

**Environment**: DietPi, RPi3, HA on 8123, Netdata on 19999

## Running

```bash
docker compose up -d --build
docker logs -f hermes
docker restart hermes
```

**Critical commands** (fixed, telegram):
- `/status`, `/containers`, `/memoria`, `/temperatura`, `/disco`
- `/ha`, `/entidades`, `/logs`, `/logsum`, `/backup`
- `/mem`, `/sync`, `/reiniciar <name>`, `/limpar`, `/ajuda`

## Mandatory Rules

1. **AÇÃO = FERRAMENTA**: Never reply "Ok" or "Done" without tool result. Use tools for all actions.
2. **Never use domain "ha"**: Use `light`, `scene`, `switch` instead.
3. **HA service order**: `ha_call_service(domain, service, entity_id, extra_data)` - use service, domain, entity_id in that order.
4. **Mentir é erro fatal**: Never claim action succeeded if tool returned error.
5. **Memory first**: Always `memory_search` for named entities before actions.
6. **Investigação obrigatória**: Never invent entity_id. Always `ha_find_entity` before `ha_call_service`. If 404, call `ha_find_entity` and retry.
7. **Save after success**: If `ha_call_service` returns OK, call `memory_save` to store entity_id.

## Tool Patterns

- **Docker**: `docker_ps`, `docker_logs`, `docker_stats`, `docker_restart`, `docker_stop`, `docker_start`, `docker_inspect`
- **HA**: `ha_states`, `ha_find_entity` (required before `ha_call_service`), `ha_call_service`
- **System**: `netdata_metrics` (cpu/ram/disk/temperature/network), `system_uptime`
- **Knowledge**: `search_knowledge`, `read_file`, `file_search`
- **Memory**: `memory_save`, `memory_search`
- **Shell**: `shell_read` (blocked: rm, mkfs, dd, shutdown, reboot, halt, chmod 777, curl/wget | sh)

## Response Style

- **Extremely brief** (3-6 words)
- **Only answer requested**
- **Never narrate process**
- **Report real errors** if tool fails

## Persistent Data

- **DB**: `/app/data/hermes.db` (conversation, memory, tasks)
- **Knowledge**: `/app/knowledge/` (skill files, config backups)
- **Blocked files**: `/etc/shadow`, `/etc/passwd`, `.env`, secrets, `.key`, `.pem`

## Special Tools

- **Wake-on-LAN**: `ligar_windows`, `ping_windows` (MAC: C8:7F:54:63:36:C2, IP: 192.168.15.10)
- **Marmitex**: `marmitex_cardapio` (fallback to Railway or GitHub JSON)
- **Task management**: `task_manage` (add/list/remove) for monitoring (monitor_ram, monitor_container, monitor_temperatura)

## Warnings

- WOL is broadcast on LAN - doesn't work via Tailscale
- Home Assistant restart requires `ha_restart` tool
- Disk/network output needs formatting (`format_disk_output`, `format_ram_output`, `format_temp_output`)
