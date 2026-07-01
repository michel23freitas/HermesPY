# SKILL: Home Assistant

## Quando usar
Controle de luzes, tomadas, cenas, câmeras, sensores, automações, reinicialização do HA.

## Acesso
- URL local: http://192.168.15.15:8123
- URL via Tailscale: http://dietpi:8123
- Token: variável HA_TOKEN no .env

## Config files
- Principal: /opt/homeassistant/config/configuration.yaml
- Automações: /opt/homeassistant/config/automations.yaml

## Integrações ativas
- Tuya (luzes e tomadas)
- Câmeras
- Alexa Media Player via HACS (grupos de Echo)
- Samsung S23 (sensor de sono)

## Domínios corretos — CRÍTICO
| Dispositivo | Domínio |
|---|---|
| Luzes | light |
| Tomadas | switch |
| Cenas | scene |
| Ar / Climatizador | climate |
| Câmeras | camera |
| Sensores | sensor |
| Media players | media_player |
| Automações | automation |

NUNCA usar domínio "ha". Sempre o domínio específico acima.

## Fluxo obrigatório para controle
1. memory_search → entity_id salvo?
2. Não → ha_find_entity com descrição em português
3. ha_call_service com entity_id encontrado
4. Retornou OK → memory_save com entity_id
5. Retornou ENTIDADE NAO ENCONTRADA → ha_find_entity imediato, tentar novamente

## Ação obrigatória após ha_find_entity
Se o usuário pediu para LIGAR ou LIGA/DESLIGAR OU DESLIGA/ACIONAR OU ACIONA:
NÃO pare no ha_find_entity.
SEMPRE chamar ha_call_service logo em seguida com o entity_id encontrado.
ha_find_entity é apenas busca intermediária, nunca resposta final.

## Sensores relevantes
| Sensor | Entidade | Obs |
|---|---|---|
| Sono (minutos) | sensor.s23_michel_sleep_duration | Raw do S23 |
| Sono (horas) | sensor.s23_michel_sleep_duration_hours | Template sensor |

## Template sensor de sono (configuration.yaml)
```yaml
template:
  - sensor:
      - name: "S23 Michel Sleep Duration Hours"
        unique_id: s23_michel_sleep_duration_hours
        unit_of_measurement: "h"
        device_class: duration
        state: "{{ (states('sensor.s23_michel_sleep_duration') | float(0) / 60) | round(2) }}"
```

## Entidades memorizadas
<!-- Atualizar via memory_save após uso bem-sucedido -->
