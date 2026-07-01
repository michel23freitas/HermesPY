# SKILL: Sistema e Hardware

## Quando usar
Temperatura, RAM, disco, uptime, CPU, hardware do Pi, DietPi.

## Hardware
| Item | Valor |
|---|---|
| Modelo | Raspberry Pi 3 Model B |
| RAM | 1 GB |
| Armazenamento | MicroSD 32GB classe 10 |
| Fonte | 5V 2.2A (temporariamente 5V 3A OK) |
| Rede | Cabo ethernet |
| OS | DietPi (Debian) |

## Métricas via Netdata (preferencial)
| Métrica | Ferramenta | Parâmetro |
|---|---|---|
| CPU | netdata_metrics | metric=cpu |
| RAM | netdata_metrics | metric=ram |
| Disco | netdata_metrics | metric=disk |
| Temperatura | netdata_metrics | metric=temperature |
| Rede | netdata_metrics | metric=network |
| Tudo | netdata_metrics | metric=overview |

Netdata URL: http://192.168.15.15:19999
Fallback automático para leitura do kernel se Netdata indisponível.

## Alertas watchdog ativos
- RAM > 85% → alerta Telegram
- Container caído → alerta imediato
- Reinicialização detectada → notificação com status dos containers

## Acesso a logs do sistema
- dmesg: shell_read "dmesg | tail -50" (requer privileged: true no compose)
- journalctl: shell_read "journalctl -n 50"
- Logs do host montados em /host_log

## Deploy do Hermes
- Diretório: /opt/hermes/
- Rebuild: docker compose up -d --build
- Sem down necessário — rebuild faz tudo
