# SKILL: Music Assistant e Alexa

## Quando usar
Perguntas sobre música, streaming, Alexa, skill bridge, players de mídia.

## Music Assistant
| Item | Valor |
|---|---|
| Porta | 8095 |
| URL local | http://192.168.15.15:8095 |
| URL Tailscale | http://dietpi:8095 |
| Data dir | /opt/musicassistant |
| Network | host |
| Container | music-assistant |

## Integração com Home Assistant
- Configurado via Long-Lived Access Token
- HA URL no MA: http://dietpi:8123
- Player Power Control: entidade do grupo de Alexas (ex: media_player.todo_lugar)
- Player Volume Control: grupo de Alexas unificado
- Requer integração Alexa Media Player ativa via HACS para Echo aparecer no MA

## YouTube Music
- Container: ytmusic-po-token
- Fornece PO Token para reprodução via Music Assistant

## Alexa Skill Bridge
| Item | Valor |
|---|---|
| Container | alexa-skill (ou similar) |
| Imagem | ghcr.io/alams154/music-assistant-skill:latest |
| Porta | 5000 |
| Compose | /opt/alexa/music-assistant-alexa-skill-prototype/docker-compose.yml |
| Skill ID | amzn1.ask.skill.e41752dd-4201-464d-b266-cac665ea3334 |
| Locale | pt-BR |

## Variáveis de ambiente do skill bridge
| Variável | Valor |
|---|---|
| SKILL_HOSTNAME | dietpi.tail8eef55.ts.net |
| MA_HOSTNAME | dietpi.tail8eef55.ts.net |
| PORT | 5000 |
| LOCALE | pt-BR |
| TZ | America/Sao_Paulo |

## Configuração no MA
- MA → Settings → Player Providers → Alexa
- API URL: http://localhost:5000
- Credenciais: em /opt/alexa/.../secrets/

## Tailscale Funnel (path routing)
- / → skill bridge porta 5000 (Alexa intents)
- /single/... → MA porta 8095 (streaming de áudio)

## Invocação
"Alexa, abre music assistant" — funciona em pt-BR

## Estado atual
Skill invocada com sucesso. Streaming via path /single em teste.
