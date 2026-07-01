# SKILL: Backup

## Quando usar
Status de backup, verificar se backup foi enviado ao PC, logs de backup.

## Configuração
| Item | Valor |
|---|---|
| Script | /usr/local/bin/homeassistant-backup.sh |
| Sync script | /usr/local/bin/sincroniza-backup.sh |
| Destino PC | /mnt/backups/windows |
| SMB Windows | \\192.168.15.10\Backup |
| Pasta Windows | C:\Apps\Diet Pi\Backup |
| Log | /mnt/backups/windows/backup.log |
| Retenção | 10 últimos backups |

## Agendamento cron
- Backup: 0 3 * * * (03:00 diário)
- Sync para PC: a cada 5 minutos via sincroniza-backup.sh

## Padrão de arquivo
homeassistant-backup-YYYY-MM-DD.tar.gz

## Diretórios monitorados
- /opt/backup-pending/ → backups aguardando envio
- /mnt/backups/windows/ → backups já no PC

## Diagnóstico
- PC offline → montagem /mnt/backups/windows falha
- Verificar montagem: shell_read "mountpoint /mnt/backups/windows"
- Ler log: read_file "/mnt/backups/windows/backup.log"
- Listar backups: shell_read "ls -lh /opt/backup-pending/"

## Volume no compose do Hermes
- /opt/backup-pending:/opt/backup-pending
- /mnt/backups/windows:/mnt/backups/windows:ro
