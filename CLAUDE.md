# GUSTO Agent — Documentação Técnica

Agente de atendimento via WhatsApp para o restaurante GUSTO (Vila Branca, Jacareí-SP).
Recebe pedidos de marmitas executivas de clientes individuais, processa com IA e salva no banco.

---

## Stack

| Camada | Tecnologia |
|---|---|
| Web server | FastAPI + Uvicorn |
| HTTP client | httpx (async) |
| Banco | MySQL 8 (aiomysql) |
| Cache de sessão | Redis (redis-py async) |
| Cardápio | Google Sheets (gspread) |
| LLM | Claude Haiku 4.5 (Anthropic API) |
| WhatsApp | UAZAPI |
| Scheduler | APScheduler 3.x (AsyncIOScheduler) |
| Deploy | Railway |

---

## Estrutura do Projeto

```
gusto-agent/
├── main.py                  → FastAPI app, webhook, endpoints de dashboard
├── config.py                → Variáveis de ambiente (.env)
├── requirements.txt
│
├── handlers/
│   ├── classifier.py        → Verifica se número é convênio (bloqueado)
│   ├── individual.py        → Fluxo completo de pedido individual
│   └── convenio.py          → Removido (atendimento convênio descontinuado)
│
├── services/
│   ├── uazapi.py            → Envio de mensagens e normalização de payload
│   ├── session.py           → Sessão por número no Redis (TTL 4h)
│   ├── cardapio.py          → Leitura do Google Sheets + cache 30min
│   ├── extrator.py          → Extração de dados do pedido via Claude Haiku
│   ├── cupom.py             → Cupons de desconto
│   └── redis_client.py      → Singleton do cliente Redis
│
├── db/
│   ├── connection.py        → Pool aiomysql + helpers fetchone/fetchall/execute
│   ├── pedidos.py           → INSERT pedidos/itens_pedido, upsert clientes, buscar nome
│   └── dashboard.py         → Queries do dashboard operacional
│
├── scheduler/
│   └── jobs.py              → broadcast_cardapio (placeholder — desativado)
│
├── dashboard/
│   └── index.html           → Dashboard operacional (fila de pedidos do dia)
│
└── windows_service/
    └── poller.py            → Serviço Windows para impressão de pedidos
```

---

## Fluxo Principal (Webhook)

```
POST /webhook
  └── normalizar_payload()        → extrai numero, texto, push_name, tipo_midia
        └── eh_convenio(numero)?  → se sim: ignora silenciosamente (return 200)
              └── individual.processar(msg)
                    ├── etapa=inicio         → _inicio(): saudação com nome + cardápio
                    ├── etapa=coletando      → _coletando(): extrai campos via LLM, pergunta o que falta
                    └── etapa=aguardando_confirmacao → _receber_confirmacao(): salva pedido
```

### Etapas da sessão (Redis)

| Etapa | Descrição |
|---|---|
| `inicio` | Primeira mensagem ou saudação — envia cardápio |
| `coletando` | Coleta incremental dos campos do pedido |
| `aguardando_confirmacao` | Exibe resumo e aguarda "sim" ou "não" |

### Campos do pedido (sessão Redis)

```
mistura            # prato escolhido
tamanho            # Mini | Normal | Executiva | Churrasco
valor_unitario     # preenchido automaticamente pelo tamanho
acomp_1            # primeiro acompanhamento (opcional)
acomp_2            # segundo acompanhamento (opcional)
sem_acompanhamento # true se lead disse explicitamente que não quer acompanhamento
observacoes        # ex: "sem feijão"
tipo_entrega       # "entrega" | "retirada"
endereco           # endereço (se entrega)
hora_retirada      # horário (se retirada)
```

---

## Empresas Conveniadas

Números cadastrados em `empresas_convenio` com `ativo = 1` são **ignorados silenciosamente** pelo bot — nenhuma mensagem é enviada de volta.

O atendimento automatizado para convênios foi descontinuado. A tabela `empresas_convenio` permanece no banco apenas como lista de bloqueio.

---

## Saudação Personalizada

`_inicio()` busca o nome do lead na seguinte ordem de prioridade:
1. `clientes.nome` no banco (cliente recorrente)
2. `chat.wa_name` do payload UAZAPI (nome do perfil WhatsApp)
3. `message.senderName` do payload UAZAPI (fallback)
4. Saudação genérica `"Olá!"` se nenhum disponível

---

## Cardápio (Google Sheets)

- Aba `Cardapio` na planilha configurada em `GOOGLE_SHEET_ID`
- Colunas B–G = Segunda a Sábado
- Campos lidos por linha (coluna A = nome do campo):
  - `ESPECIAL`, `PRATO_1..9`, `ACOMP_1..9`
  - `PRECO_MINI`, `PRECO_NORMAL`, `PRECO_EXECUTIVA`, `PRECO_CHURRASCO`
- Cache em memória de 30 minutos

---

## Banco de Dados (MySQL)

### Tabelas principais

| Tabela | Descrição |
|---|---|
| `pedidos` | Pedido raiz (tipo, número, data, endereço, status, impresso) |
| `itens_pedido` | Itens do pedido (mistura, tamanho, acompanhamentos, valor) |
| `clientes` | Histórico de clientes (numero_whatsapp, nome, endereço padrão) |
| `empresas_convenio` | Lista de números bloqueados (não atendidos pelo bot) |

### Status de pedido

`pendente` → `preparo` → `saiu` → `entregue`

Atualizado via `POST /pedidos/{id}/status` pelo dashboard operacional.

---

## Extrator de Pedido (LLM)

Usa **Claude Haiku 4.5** para extrair campos estruturados de mensagens em linguagem natural.

Campos extraídos:
- `mistura`, `tamanho`, `acomp_1`, `acomp_2`
- `sem_acompanhamento` — `true` se o lead disse explicitamente que não quer acompanhamento
- `observacoes`, `tipo_entrega`, `endereco`, `hora_retirada`

Se nenhum campo útil for extraído (`_nada_extraido()`), a mensagem é tratada como dúvida e respondida pelo assistente virtual (também Claude Haiku).

---

## Endpoints

| Método | Rota | Descrição |
|---|---|---|
| `POST` | `/webhook` | Recebe eventos do UAZAPI |
| `GET` | `/dashboard` | Interface operacional (HTML) |
| `GET` | `/api/dashboard` | Fila de pedidos do dia + totais (JSON) |
| `POST` | `/pedidos/{id}/status` | Atualiza status de um pedido |
| `GET` | `/health` | Health check (MySQL + Redis) |

---

## Variáveis de Ambiente (.env)

```env
# MySQL
MYSQL_HOST=
MYSQL_PORT=3306
MYSQL_DB=gusto_agent
MYSQL_USER=
MYSQL_PASSWORD=

# Redis
REDIS_URL=redis://localhost:6379

# UAZAPI
UAZAPI_BASE_URL=
UAZAPI_TOKEN=
UAZAPI_INSTANCE=
WEBHOOK_URL=        # URL pública deste servidor

# LLM
ANTHROPIC_API_KEY=

# Google Sheets
GOOGLE_SHEET_ID=
GOOGLE_CREDENTIALS_FILE=credentials/google_service_account.json
GOOGLE_CREDENTIALS_JSON=   # JSON inline (Railway — substitui o arquivo)

# Scheduler
HORARIO_BROADCAST_CARDAPIO=08:00   # placeholder, broadcast desativado

# App
PORT=8000
```

---

## Deploy (Railway)

- Entrada: `uvicorn main:app --host 0.0.0.0 --port $PORT` (via `Procfile`)
- Credenciais Google: variável `GOOGLE_CREDENTIALS_JSON` com o JSON inline
- Webhook configurado manualmente no painel do UAZAPI apontando para `$WEBHOOK_URL/webhook`

---

## Serviço de Impressão (Windows)

`windows_service/poller.py` — roda localmente na máquina do restaurante, consulta a API periodicamente e imprime pedidos novos com `impresso = 0`.
