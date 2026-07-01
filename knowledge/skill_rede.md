# SKILL: Rede e Infraestrutura

## Quando usar
Perguntas sobre IPs, acesso remoto, Tailscale, portas, conectividade, DNS.

## IPs locais
| Host | IP |
|---|---|
| Raspberry Pi 3 | 192.168.15.15 |
| PC Windows (SMB/backup) | 192.168.15.10 |

## Tailscale
- IP do Pi: 100.84.31.60
- MagicDNS: dietpi
- Funnel URL: https://dietpi.tail8eef55.ts.net

## Acesso remoto por serviço
| Serviço | URL Tailscale |
|---|---|
| Home Assistant | http://dietpi:8123 |
| Portainer | https://dietpi:9442 |
| Music Assistant | http://dietpi:8095 |

## Segurança
- Sem portas abertas no roteador.
- Acesso externo exclusivamente via Tailscale.
- ALLOWED_CHAT_ID protege o bot Telegram.

## Ferramentas de diagnóstico
- Interfaces: shell_read "ip addr"
- Ping: shell_read "ping -c 3 <ip>"
- Tráfego: netdata_metrics metric=network

## Path routing Tailscale Funnel (Alexa)
| Path | Destino |
|---|---|
| / | skill bridge porta 5000 |
| /single/... | Music Assistant porta 8095 |
