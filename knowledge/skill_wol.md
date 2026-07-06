# SKILL: Wake-on-LAN (Windows)

## Quando usar
Usuário pedir: "liga meu pc", "liga o windows", "liga meu computador", "acorda o pc".

## Configuração

| Item | Valor |
|---|---|
| MAC Windows | C8:7F:54:63:36:C2 |
| IP Windows | 192.168.15.10 |
| Broadcast | 192.168.15.255 |
| Tool ligar | ligar_windows |
| Tool checar | ping_windows |

## Fluxo obrigatório
1. Chamar ligar_windows (já envia WOL e confirma via ping internamente)
2. Responder resultado direto ao usuário

## Diagnóstico se não ligar
- Confirmar BIOS com WOL habilitado (já configurado)
- Confirmar Windows com "Inicialização rápida" desabilitada (afeta WOL)
- Confirmar placa de rede com "Allow this device to wake the computer" ativo
- PC precisa estar no mesmo segmento de rede (cabo, não wifi, geralmente)
