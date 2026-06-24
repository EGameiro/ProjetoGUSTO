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
| Deploy | Railway |

---

## Estrutura do Projeto

```
gusto-agent/
├── main.py                  → FastAPI app, webhook, endpoints de dashboard e impressão
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
│   ├── cupom.py             → Montagem do cupom de impressão (individual e convênio)
│   └── redis_client.py      → Singleton do cliente Redis
│
├── db/
│   ├── connection.py        → Pool aiomysql + helpers fetchone/fetchall/execute
│   ├── pedidos.py           → INSERT pedidos/itens_pedido, upsert clientes, busca nome e pedido aberto
│   └── dashboard.py         → Queries do dashboard operacional
│
├── dashboard/
│   └── index.html           → Dashboard operacional (fila de pedidos do dia)
│
└── windows_service/
    ├── poller.exe            → Compilado PyInstaller — serviço de impressão para o cliente
    ├── impressao_client.py   → Cliente HTTP para os endpoints de impressão da API
    ├── nssm.exe              → Gerenciador de serviço Windows
    └── .env                  → API_URL, API_KEY, NOME_IMPRESSORA, INTERVALO_IMPRESSAO
```

---

## Fluxo Principal (Webhook)

```
POST /webhook
  └── normalizar_payload()        → extrai numero, texto, push_name, tipo_midia
        └── eh_convenio(numero)?  → se sim: ignora silenciosamente (return 200)
              └── individual.processar(msg)
                    ├── saudação detectada      → _inicio()
                    ├── etapa=inicio            → _inicio()
                    ├── etapa=coletando         → _coletando()
                    ├── etapa=aguardando_confirmacao → _receber_confirmacao()
                    └── etapa=aguardando_intencao   → _receber_intencao()
```

### Etapas da sessão (Redis)

| Etapa | Descrição |
|---|---|
| `inicio` | Primeira mensagem — verifica pedido aberto, depois envia cardápio |
| `aguardando_intencao` | Lead tem pedido aberto — aguarda "novo pedido" ou "só queria saber" |
| `coletando` | Coleta incremental dos campos do pedido (suporta múltiplos itens) |
| `aguardando_confirmacao` | Exibe resumo e aguarda "sim" ou "não" |

### Detecção de pedido aberto

Ao iniciar a conversa (`_inicio`), o bot consulta `buscar_pedido_aberto()`:
- Se existe pedido `individual` do dia com `status != 'entregue'`, envia mensagem com status e lista de itens do pedido
- Status exibidos: `preparo → "em preparo 🍳"` | `saiu → "saiu para entrega 🛵"`
- Se o lead responde que quer novo pedido → inicia coleta normalmente
- Se responde que só queria saber → encerra sessão com mensagem de confirmação

### Saudações reconhecidas

`oi`, `oie`, `ola`, `olá`, `eai`, `eaí`, `opa`, `bom dia`, `boa tarde`, `boa noite`, `hey`, `hello`, `hi`

Qualquer saudação **sempre reinicia o fluxo** (deleta sessão e chama `_inicio`), independente da etapa atual.

### Estrutura da sessão Redis (etapa `coletando`)

```json
{
  "etapa": "coletando",
  "restaurante_id": 1,
  "nome": "Eduardo",
  "itens": [
    {
      "mistura": "Feijoada Completa",
      "tamanho": "Normal",
      "acomp_1": "Farofa",
      "acomp_2": null,
      "sem_acompanhamento": null,
      "observacoes": null,
      "valor_unitario": 34.25
    }
  ],
  "tipo_entrega": "retirada",
  "endereco": null,
  "hora_retirada": "13h"
}
```

---

## Múltiplos Itens por Pedido

O bot suporta pedidos com N pratos na mesma sessão.

**Casos suportados:**
- "Quero um macarrão e uma carne assada" → 2 itens distintos
- "Quero 3 feijoadas" → 3 cópias do mesmo item (`quantidade=3` extraído pelo LLM)

**Coleta por item:**
- O bot pergunta tamanho e acompanhamentos de um grupo de mistura por vez
- Itens com a mesma mistura são agrupados: "Sobre *3x Feijoada Completa*: Tamanho | Acomp"
- Tamanho/acomp respondidos sem citar o prato são aplicados ao primeiro item incompleto

**Banco:** 1 linha em `pedidos` + N linhas em `itens_pedido` (uma por marmita).

**Resumo para o cliente:** itens iguais são agrupados ("3x Feijoada — Normal | R$ 102,75").

---

## Extrator de Pedido (LLM)

Usa **Claude Haiku 4.5** para extrair campos estruturados de mensagens em linguagem natural.

Retorna JSON no formato:
```json
{
  "itens": [
    {
      "mistura": "nome do prato",
      "quantidade": 1,
      "tamanho": "Mini | Normal | Executiva",
      "acomp_1": "nome exato da lista",
      "acomp_2": null,
      "sem_acompanhamento": null,
      "observacoes": null
    }
  ],
  "tipo_entrega": "entrega | retirada",
  "endereco": null,
  "hora_retirada": null
}
```

Se nenhum campo útil for extraído (`_nada_extraido()`), a mensagem é tratada como dúvida e respondida pelo assistente virtual (também Claude Haiku).

---

## Empresas Conveniadas

Números cadastrados em `empresas_convenio` com `ativo = 1` são **ignorados silenciosamente** pelo bot — nenhuma mensagem é enviada de volta.

O atendimento automatizado para convênios foi descontinuado. A tabela permanece no banco apenas como lista de bloqueio.

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

Atualizado via `POST /pedidos/{id}/status` pelo dashboard operacional ou pelo app web.

---

## Serviço de Impressão (Windows)

`windows_service/poller.exe` — roda localmente na máquina do restaurante como serviço Windows (via NSSM), consulta a API a cada `INTERVALO_IMPRESSAO` segundos e imprime pedidos com `impresso = 0`.

### Segurança
- Nenhuma credencial de banco na máquina do cliente
- Autenticação via `API_KEY` no header `X-Api-Key`
- Endpoints: `GET /api/impressao/pendentes` e `POST /api/impressao/{id}/marcar`

### Instalação no cliente
```
1. Copiar poller.exe, nssm.exe e .env para C:\Gusto\
2. Editar .env: preencher NOME_IMPRESSORA com o nome exato da impressora
3. (como Administrador):
   nssm install GustoImpressao "C:\Gusto\poller.exe"
   nssm set GustoImpressao AppDirectory "C:\Gusto"
   nssm start GustoImpressao
4. Verificar em services.msc: status "Em execução"
```

---

## Endpoints

| Método | Rota | Descrição |
|---|---|---|
| `POST` | `/webhook` | Recebe eventos do UAZAPI |
| `GET` | `/dashboard` | Interface operacional (HTML) |
| `GET` | `/api/dashboard` | Fila de pedidos do dia + totais (JSON) |
| `POST` | `/pedidos/{id}/status` | Atualiza status de um pedido |
| `GET` | `/api/impressao/pendentes` | Lista pedidos com impresso=0 (requer API_KEY) |
| `POST` | `/api/impressao/{id}/marcar` | Marca pedido como impresso (requer API_KEY) |
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

# Impressão (validação de API Key do poller)
API_KEY_IMPRESSORA=

# App
PORT=8000
```

---

## Deploy (Railway)

- Entrada: `uvicorn main:app --host 0.0.0.0 --port $PORT` (via `Procfile`)
- Credenciais Google: variável `GOOGLE_CREDENTIALS_JSON` com o JSON inline
- Webhook configurado manualmente no painel do UAZAPI apontando para `$WEBHOOK_URL/webhook`
- Deploy automático a cada push na branch `master`

---

## Pendências

- [ ] **Migrar cardápio do Google Sheets para MySQL.** O portal web (GustoConvenio.Web) passa a ser a fonte oficial do cardápio. O `services/cardapio.py` precisa ser reescrito para ler de `cardapio_web` via MySQL. Quando feito, remover `gspread`, `google-auth` e credenciais Google.
