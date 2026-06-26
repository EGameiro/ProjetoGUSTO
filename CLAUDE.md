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
| Cardápio | MySQL (`cardapio_web`) via portal web GustoConvenio.Web |
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
│   └── individual.py        → Fluxo completo de pedido individual
│
├── services/
│   ├── uazapi.py            → Envio de mensagens e normalização de payload
│   ├── session.py           → Sessão por número no Redis (TTL 4h)
│   ├── cardapio.py          → Leitura do MySQL (cardapio_web) + cache 15min
│   ├── extrator.py          → Extração de dados do pedido via Claude Haiku
│   ├── cupom.py             → Montagem do cupom de impressão (individual e convênio)
│   └── redis_client.py      → Singleton do cliente Redis
│
├── db/
│   ├── connection.py        → Pool aiomysql + helpers fetchone/fetchall/execute
│   ├── pedidos.py           → INSERT pedidos/itens_pedido, upsert clientes, busca nome/pedido aberto/preferências
│   └── dashboard.py         → Queries do dashboard operacional
│
├── dashboard/
│   └── index.html           → Dashboard operacional (fila de pedidos do dia)
│
└── windows_service/
    └── GustoImpressao/      → Serviço de impressão em VB.NET (.NET 8)
        ├── dist-cliente/    → Pasta pronta para deploy no cliente
        │   ├── GustoImpressao.exe
        │   ├── appsettings.json
        │   ├── instalar_servico.bat
        │   └── desinstalar_servico.bat
        ├── Program.vb
        ├── PollerWorker.vb
        ├── ApiClient.vb
        ├── Cupom.vb
        ├── Impressora.vb
        └── GustoConfig.vb
```

---

## Fluxo Principal (Webhook)

```
POST /webhook
  └── normalizar_payload()        → extrai numero, texto, push_name, tipo_midia
        └── eh_convenio(numero)?  → se sim: ignora silenciosamente (return 200)
              └── individual.processar(msg)
                    ├── saudação detectada           → _inicio()
                    ├── etapa=inicio (com texto)     → _inicio() → tenta extrair pedido direto
                    ├── etapa=inicio (sem texto útil)→ _inicio() → exibe cardápio
                    ├── etapa=coletando              → _coletando()
                    ├── etapa=aguardando_confirmacao → _receber_confirmacao()
                    └── etapa=aguardando_intencao   → _receber_intencao()
```

### Etapas da sessão (Redis)

| Etapa | Descrição |
|---|---|
| `inicio` | Primeira mensagem — verifica pedido aberto, tenta extrair pedido direto, ou exibe cardápio |
| `aguardando_intencao` | Lead tem pedido aberto — aguarda "novo pedido" ou "só queria saber" |
| `coletando` | Coleta incremental dos campos do pedido (suporta múltiplos itens) |
| `aguardando_confirmacao` | Exibe resumo e aguarda "sim" ou "não" |

### Detecção de pedido aberto

Ao iniciar a conversa (`_inicio`), o bot consulta `buscar_pedido_aberto()`:
- Se existe pedido `individual` do dia com `status != 'entregue'`, envia mensagem com status e lista de itens
- Status exibidos: `preparo → "em preparo 🍳"` | `saiu → "saiu para entrega 🛵"`
- Se o lead responde que quer novo pedido → inicia coleta normalmente
- Se responde que só queria saber → encerra sessão com mensagem de confirmação

### Pedido direto sem saudação

Se o lead manda a primeira mensagem já com o pedido (ex: "quero uma carne assada mini"), o bot:
1. Tenta extrair dados com o LLM antes de exibir o cardápio
2. Se extraiu algo útil → exibe só "Bem-vindo ao GUSTO 🍽️" e já pergunta o que falta
3. Se não extraiu nada → exibe o cardápio normalmente

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
      "mistura": "Carne Assada",
      "tamanho": "Normal",
      "acomp_1": "Farofa",
      "acomp_2": null,
      "sem_acompanhamento": null,
      "observacoes": null,
      "valor_unitario": null
    }
  ],
  "tipo_entrega": "entrega",
  "endereco": "Rua das Flores, 123",
  "hora_retirada": null,
  "pref_tipo_entrega": "entrega",
  "pref_endereco": "Rua das Flores, 123"
}
```

> `valor_unitario` é calculado em `_enviar_resumo` via `get_preco_prato(mistura, tamanho)` — não é armazenado na sessão.

---

## Múltiplos Itens por Pedido

O bot suporta pedidos com N pratos na mesma sessão.

**Casos suportados:**
- "Quero um macarrão e uma carne assada" → 2 itens distintos
- "Quero 3 feijoadas" → 3 cópias do mesmo item (`quantidade=3` extraído pelo LLM)

**Coleta por item:**
- O bot pergunta tamanho e acompanhamentos de um grupo de mistura por vez
- Itens com a mesma mistura são agrupados: "Sobre *3x Carne Assada*: Tamanho | Acomp"
- Tamanho simples ("mini", "normal", "executiva") detectado antes de chamar o LLM — aplicado ao primeiro grupo incompleto
- "não precisa" / "sem acompanhamento" detectado antes do LLM — marca `sem_acompanhamento=True`

**Banco:** 1 linha em `pedidos` + N linhas em `itens_pedido` (uma por marmita).

**Resumo para o cliente:** itens iguais agrupados ("3x Carne Assada — Normal | Farofa | R$ 87,60").

---

## Preferências do Cliente

Ao finalizar um pedido, `upsert_cliente()` salva em `clientes`:
- `tipo_entrega_pref` — última preferência (entrega/retirada)
- `endereco_padrao` — último endereço de entrega

Na próxima conversa (`_iniciar_coleta`), as preferências são carregadas na sessão (`pref_tipo_entrega`, `pref_endereco`) e usadas para personalizar a pergunta:
- "Na última vez entregamos em *Rua X*. Mesmo endereço ou vai mudar?"
- "Na última vez você *retirou*. Vai retirar novamente ou prefere entrega?"

A confirmação ("sim", "mesmo") é detectada **antes** de chamar o LLM nos dois casos:
1. `tipo_entrega` ainda não definido → confirma tipo + endereço da preferência
2. `tipo_entrega` já definido como entrega mas `endereco` faltando → confirma endereço

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

## Cardápio (MySQL)

- Tabela `cardapio_web` no banco MySQL
- Gerenciado pelo portal web **GustoConvenio.Web** em Admin → Cardápio
- Cache em memória de 15 minutos por `restaurante_id`
- Colunas relevantes: `tipo` ("prato" | "acompanhamento"), `nome`, `preco_mini`, `preco_normal`, `preco_executiva`, `dia_semana` (0=Seg…5=Sab), `empresa_id` (NULL = cardápio WhatsApp)

**Função principal:** `get_cardapio_hoje(restaurante_id)` retorna:
```python
{
  "dia": "Quinta-feira",
  "pratos": [("Carne Assada", {"Mini": 21.90, "Normal": 23.90, "Executiva": 24.90}), ...],
  "acompanhamentos": ["Farofa", "Maionese"],
  "tamanhos": ["Mini", "Normal", "Executiva"]
}
```

**Preço por tamanho:** `get_preco_prato(nome, tamanho, restaurante_id)` — usado no resumo do pedido.

---

## Empresas Conveniadas

Números cadastrados em `empresas_convenio` com `ativo = 1` são **ignorados silenciosamente** pelo bot — nenhuma mensagem é enviada de volta.

O atendimento automatizado para convênios foi descontinuado. A tabela permanece no banco apenas como lista de bloqueio.

---

## Banco de Dados (MySQL)

### Tabelas principais

| Tabela | Descrição |
|---|---|
| `pedidos` | Pedido raiz (tipo, número, data, endereço, status, impresso) |
| `itens_pedido` | Itens do pedido (mistura, tamanho, acompanhamentos, valor) |
| `clientes` | Histórico de clientes (numero_whatsapp, nome, tipo_entrega_pref, endereco_padrao) |
| `cardapio_web` | Cardápio por dia/empresa com preços Mini/Normal/Executiva por prato |
| `empresas_convenio` | Lista de números bloqueados (não atendidos pelo bot) |

### Status de pedido

`pendente` → `preparo` → `saiu` → `entregue`

Atualizado via `POST /pedidos/{id}/status` pelo dashboard operacional ou pelo app web.

---

## Serviço de Impressão (Windows)

Reescrito em **VB.NET (.NET 8)** — Windows Service nativo, sem dependências externas além do .NET 8 Runtime.

### Arquitetura

| Arquivo | Responsabilidade |
|---|---|
| `Program.vb` | Entry point — configura o host Windows Service |
| `PollerWorker.vb` | `BackgroundService` — loop a cada N segundos |
| `ApiClient.vb` | HTTP para a API: buscar pendentes + marcar impresso |
| `Cupom.vb` | Monta o texto do cupom (individual e convênio) |
| `Impressora.vb` | Imprime via `PrintDocument` — margem mínima 5px, fonte Courier New 8pt |
| `GustoConfig.vb` | Configuração lida do `appsettings.json` |

### Configuração (`appsettings.json`)

```json
{
  "Gusto": {
    "ApiUrl": "https://projetogusto-production.up.railway.app",
    "ApiKey": "...",
    "NomeImpressora": "",
    "IntervaloSegundos": 15
  }
}
```

> `NomeImpressora` vazio = impressora padrão do Windows.

### Segurança
- Nenhuma credencial de banco na máquina do cliente
- Autenticação via `API_KEY` no header `X-Api-Key`
- Endpoints: `GET /api/impressao/pendentes` e `POST /api/impressao/{id}/marcar`

### Instalação no cliente
```
Pré-requisito: instalar .NET 8 Runtime (x64) na máquina do cliente

1. Copiar a pasta dist-cliente\ para C:\AgenteFood\ (ou qualquer pasta sem espaços)
2. Editar appsettings.json: preencher NomeImpressora se não for a impressora padrão
3. Botão direito em instalar_servico.bat → Executar como administrador
4. Verificar em services.msc: status "Em execução"
```

### Desinstalação
```
Botão direito em desinstalar_servico.bat → Executar como administrador
```
Ou manualmente:
```cmd
sc stop GustoImpressao
sc delete GustoImpressao
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

# Impressão (validação de API Key do poller)
API_KEY_IMPRESSORA=

# App
PORT=8000
```

---

## Deploy (Railway)

- Entrada: `uvicorn main:app --host 0.0.0.0 --port $PORT` (via `Procfile`)
- Webhook configurado manualmente no painel do UAZAPI apontando para `$WEBHOOK_URL/webhook`
- Deploy automático a cada push na branch `master`

---

## Migrations SQL

| Arquivo | Descrição |
|---|---|
| `migration_cardapio_empresa_preco.sql` | Adiciona `empresa_id` e `preco` em `cardapio_web` |
| `migration_preco_tamanho.sql` | Adiciona `preco_mini`, `preco_normal`, `preco_executiva` em `cardapio_web` |
