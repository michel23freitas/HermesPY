# Regras e Integração com a Documentação (Anytype)

## Contexto do Projeto
- Este repositório está vinculado ao projeto na page **Hermes** no Anytype.
- **Space ID:** `bafyreibkdwauq635v262xzcxmlcxqa6fc7n5se7gvdxtslk4fcpn5aa7be.o5391nbvli06`

## Índice de Documentações Anytype (ID Rápido)
Use esses IDs para evitar buscar de página em página. Os acessos para download/update já podem ser feitos diretamente sabendo o target do arquivo correspondente dentro do espaço.

| Página | Object ID do Anytype |
|---|---|
| **Hermes — Visão Geral** | `bafyreifmftkkbmilzcy5irmlzwtfet7iabucph7wht6e47zpixv6sbx4ly` |
| **API — Hermes** | `bafyreibdln5auhja2cvywri5y2yr2mgwo6yqdq3xbjuk7iot6phn7nyaoi` |
| **Arquitetura — Hermes** | `bafyreid4vy55kodokar45e24yihjyhueugjup2pnbvpvinlxqlfgqs4nq4` |
| **Banco de Dados — Hermes** | `bafyreieeysk5dq5itnc37brk7tzumr4muclxcspcdpjxnc3tseuba76l2q` |
| **Ferramentas — Hermes** | `bafyreidt5g4ucs5ea4c6vsxq3z7i4wxjrdohqqmmkoksxwomxx24nnneq4` |
| **Monitoramentos — Hermes** | `bafyreieznjcu6qjsgp4nzex6ccbimss342my34tg43yhqyg4ion5gn6dwq` |
| **Skills — Hermes** | `bafyreihmz4s6v6s2b5zp2zzf3oswdpre36zdsy62zegevrupqdfwiykqsy` |
| **Telegram — Hermes** | `bafyreia2oxmmw3bhjtomp3ndns5nzr6x6jovxcrugwiqzle7xb27anbi2a` |
| **Memória — Hermes** | `bafyreibqhfluygsssmjhymhayvxfw7hfqyyiommxlpga3ggyd6znlpjz4u` |
| **ADR-001 — SQLite em vez de JSON** | `bafyreig6xxnwkyjnuxpy656nn3hd7r6fsz5asaeyh6xx3eynxnkmjz62ay` |
| **Arquivos** | `bafyreid6n5ty2v6ncung7zkhk3qg3jd66vro7mwanvwkxdxksp3ypihvam` |

## Diretrizes de Escrita e Atualização
- Sempre que concluirmos uma nova funcionalidade, refatoração ou alteração de arquitetura, atualize ou crie a documentação correspondente no Anytype.
- Adicione as notas na seção/espaço correta do projeto.
- Sempre vincule essa página nova com a página do Hermes mantendo a estrutura. Exemplo: Hermes > API — Hermes > Nova página.
- **Não apague** uma página nem zere seu conteúdo sem aprovação prévia do usuário.

## Dica Técnica p/ MCP do Agente (Fallbacks)
Caso a interface das ferramentas MCP oficiais (`anytype_API_...`) bloqueie ou de erro por hífens/underscores na hora do LLM chamar, contorne a ferramenta enviando a solicitação de leitura/edição diretamente via shell (Bash/Python via Request HTTP local) na porta do Helper (normalmente `31009`, `47800`):
- `GET http://127.0.0.1:31009/v1/spaces/<space_id>/objects/<object_id>?format=md`
- `PATCH http://127.0.0.1:31009/v1/spaces/<space_id>/objects/<object_id>` com JSON body `{"markdown": "# ...novo texto..."}`