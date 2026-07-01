# SKILL: Docker

## Quando usar
Perguntas sobre containers, logs, RAM por container, reinicialização, status, redes, volumes.

## Containers ativos
| Nome | Porta | Função |
|---|---|---|
| homeassistant | 8123 | Automação residencial |
| music-assistant | 8095 | Servidor de áudio |
| netdata | 19999 | Métricas do sistema |
| portainer | 9002 / 9442 | Gerenciamento Docker |
| ytmusic-po-token | interno | Token YouTube Music |
| hermes | — | Este agente |

## Regras operacionais
- Logs: padrão 50 linhas. Para diagnóstico use docker_logsum.
- Restart do homeassistant: aguardar 30s antes de verificar status.
- Stats de RAM: preferir netdata_metrics antes de docker_stats.
- docker.sock montado em /var/run/docker.sock — comandos docker funcionam.
- Todos os containers principais usam network_mode host.

## Volumes principais
| Container | Host | Container |
|---|---|---|
| homeassistant | /opt/homeassistant/config | /config |
| music-assistant | /opt/musicassistant | /data |
| hermes data | /opt/hermes/data | /app/data |
| hermes knowledge | /opt/hermes/knowledge | /app/knowledge |

## Imagens
- homeassistant: ghcr.io/home-assistant/home-assistant:stable
- music-assistant: ghcr.io/music-assistant/server:latest
- hermes: build local em /opt/hermes

## Compose files
- hermes: /opt/hermes/docker-compose.yml
- alexa bridge: /opt/alexa/music-assistant-alexa-skill-prototype/docker-compose.yml
