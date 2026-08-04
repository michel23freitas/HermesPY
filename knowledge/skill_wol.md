# SKILL: Wake-on-LAN (Windows)

## Quando usar
Usuário pedir: "liga meu pc", "liga o windows", "liga meu computador", "acorda o pc".

## Configuração

| Item | Valor |
|---|---|
| Entidade HA (botão WOL) | button.wake_on_lan_c8_7f_54_63_36_c2 |
| IP Windows | 192.168.15.10 |
| Tool ligar | ligar_windows (aciona o botão WOL no HA) |
| Tool checar | ping_windows |

> O magic packet NÃO é mais enviado pelo Hermes: o Home Assistant tem a entidade
> button.wake_on_lan_c8_7f_54_63_36_c2 que liga o PC. O Hermes apenas aciona esse
> botão via ha_call_service(domain="button", service="press", entity_id=...).

## Fluxo obrigatório
1. Chamar ligar_windows (aciona o botão WOL no HA e confirma via ping internamente)
2. Responder resultado direto ao usuário

## Diagnóstico se não ligar
- Confirmar que a entidade button.wake_on_lan_c8_7f_54_63_36_c2 existe no HA (ligar_windows retorna sugestões se não achar)
- Confirmar BIOS com WOL habilitado (já configurado)
- Confirmar Windows com "Inicialização rápida" desabilitada (afeta WOL)
- Confirmar placa de rede com "Allow this device to wake the computer" ativo
- PC precisa estar no mesmo segmento de rede (cabo, não wifi, geralmente)
