# Projeto Piloto — Integração Hermes + Home Assistant (API HTTP)

> **Versão:** 0.1 (Estudo de Viabilidade)

---

# Objetivo

Transformar o **Hermes** em um serviço central acessível através de uma **API HTTP**, permitindo que diferentes interfaces conversem com ele utilizando um único ponto de entrada.

Inicialmente, a integração será realizada apenas com o **Home Assistant**.

A Alexa será considerada apenas como uma interface futura, sem fazer parte desta primeira etapa do projeto.

---

# Objetivos do MVP

* Tornar o Hermes independente do Telegram.
* Expor uma API HTTP local.
* Permitir que o Home Assistant envie mensagens para o Hermes.
* Permitir que o Hermes retorne respostas estruturadas.
* Centralizar toda a inteligência no Hermes.

---

# Arquitetura Proposta

```text
                 Usuário
                     │
                     │
             Home Assistant
                     │
             HTTP (REST API)
                     │
               Hermes API
                     │
          ┌──────────┴──────────┐
          │                     │
    Motor Conversacional     Ferramentas
          │                     │
          ├────────────┬────────┤
          │            │        │
     Home Assistant   Sistema   APIs
     Docker           Linux     Externas
```

---

# Conceito Principal

O Hermes deixa de depender de uma plataforma específica.

Hoje:

```text
Telegram
    │
Hermes
```

Proposto:

```text
Telegram
Home Assistant
Site
Aplicativo
Alexa (futuro)
Discord (futuro)

        │
        ▼

     Hermes API

        │

 Inteligência Central
```

Todas as interfaces utilizam exatamente o mesmo backend.

---

# Componentes

## Hermes

Responsável por:

* interpretar mensagens
* decidir ações
* acessar ferramentas
* gerar respostas
* manter contexto

O Hermes não deve conhecer quem enviou a mensagem.

Para ele, todas as interfaces são apenas clientes.

---

## API HTTP

A API será responsável apenas por:

* receber mensagens
* validar autenticação
* encaminhar ao Hermes
* devolver respostas

Ela não contém lógica de IA.

---

## Home Assistant

O Home Assistant será responsável por:

* capturar eventos
* executar automações
* enviar requisições HTTP
* receber respostas
* executar serviços quando necessário

O HA funciona como orquestrador.

---

# Fluxo de Comunicação

## Consulta

```text
Usuário

↓

Home Assistant

↓

HTTP

↓

Hermes

↓

Processamento

↓

Resposta

↓

Home Assistant

↓

Usuário
```

---

## Comando

```text
Usuário

↓

Home Assistant

↓

Hermes

↓

Decisão

↓

Home Assistant

↓

Executa ação

↓

Hermes

↓

Confirmação
```

---

# Responsabilidades

## Hermes

Responsável por:

* IA
* memória
* contexto
* tomada de decisão
* planejamento
* execução de ferramentas

---

## Home Assistant

Responsável por:

* dispositivos
* sensores
* automações
* scripts
* notificações
* integração com equipamentos

---

# Comunicação

Formato esperado:

Entrada

```
Mensagem

Origem

Data/Hora

ID da Conversa
```

Saída

```
Resposta

Status

Tempo de Processamento

Ações Executadas
```

O formato exato será definido durante o desenvolvimento.

---

# Possíveis Endpoints

## Chat

Responsável pela conversa.

---

## Status

Retorna:

* versão
* disponibilidade
* uptime
* uso de recursos

---

## Ferramentas

Permite listar ferramentas disponíveis.

---

## Memória

Consulta informações persistidas pelo Hermes.

---

## Health Check

Utilizado para monitoramento.

---

# Ferramentas que o Hermes poderá utilizar

## Home Assistant

* ligar dispositivos
* desligar dispositivos
* consultar sensores
* executar scripts
* executar cenas
* obter estados

---

## Raspberry Pi

* CPU
* RAM
* temperatura
* espaço em disco
* containers
* processos

---

## Docker

* iniciar containers
* parar containers
* reiniciar containers
* consultar status

---

## Sistema Linux

* arquivos
* logs
* serviços
* comandos autorizados

---

## APIs Externas

Exemplos:

* clima
* calendário
* notícias
* modelos de IA
* outros serviços

---

# Segurança

Requisitos mínimos

* API disponível apenas na rede local
* autenticação obrigatória
* chave de API ou token
* logs de acesso
* validação das requisições

Futuramente:

* Tailscale
* HTTPS
* certificados
* controle de permissões

---

# Estrutura Lógica do Hermes

```text
Hermes

│

├── API

├── Autenticação

├── Conversação

├── Memória

├── Planejamento

├── Ferramentas

├── Home Assistant

├── Docker

├── Sistema

└── Logs
```

Cada módulo deve possuir responsabilidade única.

---

# Benefícios

* Uma única inteligência.
* Diversas interfaces.
* Fácil manutenção.
* Escalabilidade.
* Reutilização de código.
* Independência da interface de entrada.

---

# Roadmap

## Fase 1

* API HTTP
* Integração com Home Assistant
* Consulta simples
* Execução de comandos
* Logs

---

## Fase 2

* Histórico de conversas
* Contexto persistente
* Múltiplas ferramentas
* Melhor gerenciamento de memória

---

## Fase 3

* Dashboard Web
* Aplicativo móvel
* Discord
* Telegram utilizando a API
* Controle de permissões

---

## Fase 4

Integração por voz.

Nesta fase será avaliada a melhor estratégia para conectar a Alexa ao Home Assistant ou diretamente ao Hermes, reaproveitando integralmente a API criada nas fases anteriores.

---

# Critérios de Sucesso

O piloto será considerado bem-sucedido quando:

* O Home Assistant conseguir enviar mensagens ao Hermes.
* O Hermes responder através da API.
* O Hermes conseguir consultar o Home Assistant.
* O Hermes conseguir solicitar ações ao Home Assistant.
* Toda a lógica permanecer centralizada no Hermes.
* Novas interfaces possam ser adicionadas sem modificar a lógica interna do Hermes.

---

# Visão de Longo Prazo

O Hermes deve evoluir para uma plataforma central de automação e assistência pessoal.

Qualquer interface (Telegram, Home Assistant, aplicativo próprio, Discord, interface web ou assistentes de voz) deverá atuar apenas como um cliente da API, enquanto toda a inteligência, contexto e tomada de decisão permanecerão concentrados no Hermes.

Essa separação reduz o acoplamento entre interfaces e lógica de negócio, facilita testes, manutenção e expansão futura do ecossistema.
