================================================================
  GUSTO — Serviço de Impressão Automática
  Instalação e Configuração
================================================================

REQUISITOS
----------
- Windows 10 ou superior
- Python 3.10 ou superior instalado (https://www.python.org/downloads/)
- Impressora térmica instalada e configurada no Windows
- Acesso à internet (para comunicação com a API GUSTO)


ARQUIVOS DA PASTA
-----------------
  poller.py             → programa principal do serviço
  impressao_client.py   → cliente HTTP para a API de impressão
  .env                  → configurações de conexão e impressora (editar antes de instalar)
  .env.example          → modelo em branco para referência
  gusto_impressao.log   → log gerado automaticamente após o primeiro start
  README.txt            → este arquivo


PASSO 1 — Instalar dependências Python
---------------------------------------
Abra o Prompt de Comando (cmd) como Administrador e execute:

  pip install httpx python-dotenv pywin32


PASSO 2 — Registrar o pywin32 no Windows
------------------------------------------
Ainda como Administrador, execute:

  python Scripts\pywin32_postinstall.py -install

  (substitua "Scripts\" pelo caminho completo se necessário,
   ex: C:\Users\SeuUsuario\AppData\Local\Programs\Python\Python311\Scripts\pywin32_postinstall.py)


PASSO 3 — Configurar o arquivo .env
-------------------------------------
Edite o arquivo .env com o Bloco de Notas e preencha:

  API_URL=https://projetogusto-production.up.railway.app
  API_KEY=      → chave fornecida pelo suporte GUSTO

  NOME_IMPRESSORA=  → nome EXATO da impressora como aparece em:
                      Painel de Controle > Dispositivos e Impressoras
                      (deixe vazio para usar a impressora padrão)

  INTERVALO_IMPRESSAO=15   → intervalo em segundos entre verificações


PASSO 4 — Testar em modo console (antes de instalar o serviço)
----------------------------------------------------------------
No Prompt de Comando (cmd), navegue até esta pasta e execute:

  python poller.py

O programa deve iniciar e começar a consultar a API a cada 15 segundos.
Pressione Ctrl+C para encerrar.

Se aparecer erro de "API Key inválida", verifique o valor de API_KEY no .env.


PASSO 5 — Instalar como serviço Windows
-----------------------------------------
No Prompt de Comando (cmd) como Administrador, navegue até esta pasta:

  python poller.py install    → registra o serviço
  python poller.py start      → inicia o serviço

Para verificar se está rodando:
  Abra services.msc e procure por "GUSTO — Impressão Automática"
  O status deve ser "Em execução"

IMPORTANTE: Configure o logon do serviço com sua conta Windows:
  services.msc → GUSTO Impressão Automática → Propriedades → aba Logon
  → "Esta conta" → digite .\SeuUsuario e sua senha
  Isso garante que a impressora fique visível para o serviço.

Configure o tipo de inicialização como "Automático" para que o serviço
suba automaticamente junto com o Windows.


COMANDOS ÚTEIS
--------------
  python poller.py start      → iniciar o serviço
  python poller.py stop       → parar o serviço
  python poller.py restart    → reiniciar o serviço
  python poller.py remove     → remover o serviço do Windows
  python poller.py install    → reinstalar após alterações no .env


VERIFICANDO O LOG
-----------------
O arquivo gusto_impressao.log nesta mesma pasta registra todas as
atividades do serviço. Em caso de erro, verifique este arquivo primeiro.

Exemplo de log saudável:
  [INFO] Serviço iniciado
  [INFO] HTTP Request: GET .../api/impressao/pendentes "HTTP/1.1 200 OK"
  [INFO] Imprimindo pedido #67 (individual)
  [INFO] HTTP Request: POST .../api/impressao/67/marcar "HTTP/1.1 200 OK"
  [INFO] Pedido #67 marcado como impresso


SUPORTE
-------
Em caso de dúvidas ou problemas, entre em contato com o suporte GUSTO.

================================================================
