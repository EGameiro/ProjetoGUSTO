================================================================
  GUSTO — Serviço de Impressão Automática
  Instalação e Configuração
================================================================

REQUISITOS
----------
- Windows 10 ou superior
- Python 3.10 ou superior instalado (https://www.python.org/downloads/)
- Impressora térmica instalada e configurada no Windows
- Acesso à internet (para conexão com o banco MySQL remoto)


ARQUIVOS DA PASTA
-----------------
  poller.py         → programa principal do serviço
  .env              → configurações de conexão e impressora (editar antes de instalar)
  .env.example      → modelo em branco para referência
  gusto_impressao.log → log gerado automaticamente após o primeiro start
  README.txt        → este arquivo


PASSO 1 — Instalar dependências Python
---------------------------------------
Abra o Prompt de Comando (cmd) como Administrador e execute:

  pip install mysql-connector-python python-dotenv pywin32


PASSO 2 — Configurar o arquivo .env
-------------------------------------
Edite o arquivo .env com o Bloco de Notas e preencha:

  MYSQL_HOST=       → endereço do banco (fornecido pelo suporte)
  MYSQL_PORT=3306
  MYSQL_DB=         → nome do banco (fornecido pelo suporte)
  MYSQL_USER=       → usuário do banco
  MYSQL_PASSWORD=   → senha do banco

  NOME_IMPRESSORA=  → nome EXATO da impressora como aparece em:
                      Painel de Controle > Dispositivos e Impressoras
                      (deixe vazio para usar a impressora padrão)

  INTERVALO_IMPRESSAO=15   → intervalo em segundos entre verificações


PASSO 3 — Testar em modo console (antes de instalar o serviço)
----------------------------------------------------------------
No Prompt de Comando (cmd), navegue até esta pasta e execute:

  python poller.py

O programa deve iniciar, conectar ao banco e imprimir os pedidos
pendentes. Pressione Ctrl+C para encerrar.

Se aparecer "win32print não encontrado", o pywin32 não foi instalado
corretamente. Repita o Passo 1.


PASSO 4 — Instalar como serviço Windows
-----------------------------------------
No Prompt de Comando (cmd) como Administrador, navegue até esta pasta:

  python poller.py install    → registra o serviço
  python poller.py start      → inicia o serviço

Para verificar se está rodando:
  Abra services.msc e procure por "GUSTO — Impressão Automática"
  O status deve ser "Em execução"

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
  [INFO] GUSTO Poller iniciado (intervalo=15s)
  [INFO] Imprimindo pedido #55 (individual)
  [INFO] Pedido #55 marcado como impresso


SUPORTE
-------
Em caso de dúvidas ou problemas, entre em contato com o suporte GUSTO.

================================================================
