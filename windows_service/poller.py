"""
Windows Service — Impressão automática GUSTO
============================================
Faz polling no MySQL a cada INTERVALO_SEGUNDOS, imprime pedidos pendentes
(impresso = 0) e marca impresso = 1.

Dependências (instalar no ambiente do Windows Service):
    pip install mysql-connector-python python-dotenv pywin32

Uso:
    python poller.py          # modo console (debug)
    python poller.py install  # instalar como serviço Windows
    python poller.py start    # iniciar serviço
    python poller.py stop     # parar serviço
    python poller.py remove   # remover serviço

Configuração:
    Copie .env.example para .env na mesma pasta e preencha as variáveis.
    A impressora padrão do Windows é usada automaticamente;
    defina NOME_IMPRESSORA para escolher outra.
"""

import os
import sys
import time
import logging
import msvcrt
from dotenv import load_dotenv

# Carrega .env do diretório do próprio script (necessário quando roda como serviço Windows)
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_BASE_DIR, ".env"))

# Adiciona o diretório do script e o pai ao path para importar impressao_client e services.cupom
sys.path.insert(0, _BASE_DIR)
sys.path.insert(0, os.path.join(_BASE_DIR, ".."))

from impressao_client import buscar_pendentes, marcar_impresso, buscar_nome_empresa
from services.cupom import montar_cupom_individual, montar_cupom_convenio

INTERVALO_SEGUNDOS = int(os.getenv("INTERVALO_IMPRESSAO", 15))
NOME_IMPRESSORA    = os.getenv("NOME_IMPRESSORA", "")  # "" = impressora padrão

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(_BASE_DIR, "gusto_impressao.log"), encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("gusto.poller")


# ── Impressão ────────────────────────────────────────────────────────────────

def imprimir_texto(texto: str):
    """Envia texto para a impressora via win32ui (GDI) ou RAW para térmica."""
    try:
        import win32print
        import win32ui
        import win32con

        impressora = NOME_IMPRESSORA or win32print.GetDefaultPrinter()

        dc = win32ui.CreateDC()
        dc.CreatePrinterDC(impressora)
        dc.StartDoc("Pedido GUSTO")
        dc.StartPage()

        # Fonte monoespaçada para alinhar colunas do cupom
        font = win32ui.CreateFont({
            "name": "Courier New",
            "height": 200,
            "weight": win32con.FW_NORMAL,
        })
        dc.SelectObject(font)

        x, y = 100, 100
        espacamento = 220
        for linha in texto.splitlines():
            dc.TextOut(x, y, linha)
            y += espacamento

        dc.EndPage()
        dc.EndDoc()
        dc.DeleteDC()

    except ImportError:
        log.warning("win32print não encontrado — imprimindo no console")
        print("\n" + "=" * 42)
        print(texto)
        print("=" * 42 + "\n")
    except Exception as e:
        log.error(f"Erro ao imprimir: {e}")


# ── Loop principal ───────────────────────────────────────────────────────────

def processar_pendentes():
    try:
        pendentes = buscar_pendentes()
    except Exception as e:
        log.error(f"Erro ao buscar pendentes: {e}")
        return

    for entrada in pendentes:
        pedido = entrada["pedido"]
        itens  = entrada["itens"]
        pid    = pedido["id"]
        tipo   = pedido.get("tipo", "individual")

        try:
            if tipo == "convenio":
                empresa_id   = pedido.get("empresa_id")
                nome_empresa = buscar_nome_empresa(empresa_id) if empresa_id else "EMPRESA"
                cupom = montar_cupom_convenio(pedido, itens, nome_empresa)
            else:
                cupom = montar_cupom_individual(pedido, itens)

            log.info(f"Imprimindo pedido #{pid} ({tipo})")
            imprimir_texto(cupom)
            marcar_impresso(pid)
            log.info(f"Pedido #{pid} marcado como impresso")

        except Exception as e:
            log.error(f"Erro ao processar pedido #{pid}: {e}")


def _adquirir_lock():
    """Garante que apenas uma instância do poller rode por vez usando um arquivo de lock."""
    lock_path = os.path.join(_BASE_DIR, "gusto_impressao.lock")
    lock_file = open(lock_path, "w")
    try:
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        log.error("Outra instância do poller já está rodando. Encerrando.")
        sys.exit(1)
    return lock_file  # manter referência para o lock não ser liberado


def loop_console():
    lock = _adquirir_lock()
    log.info(f"GUSTO Poller iniciado (intervalo={INTERVALO_SEGUNDOS}s)")
    while True:
        processar_pendentes()
        time.sleep(INTERVALO_SEGUNDOS)


# ── Windows Service (pywin32) ────────────────────────────────────────────────

try:
    import win32serviceutil
    import win32service
    import win32event
    import servicemanager

    class GustoImpressaoService(win32serviceutil.ServiceFramework):
        _svc_name_        = "GustoImpressao"
        _svc_display_name_ = "GUSTO — Impressão Automática"
        _svc_description_ = "Monitora pedidos do GUSTO e imprime automaticamente."

        def __init__(self, args):
            win32serviceutil.ServiceFramework.__init__(self, args)
            self._stop_event = win32event.CreateEvent(None, 0, 0, None)

        def SvcStop(self):
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            win32event.SetEvent(self._stop_event)

        def SvcDoRun(self):
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STARTED,
                (self._svc_name_, ""),
            )
            log.info("Serviço iniciado")
            while True:
                rc = win32event.WaitForSingleObject(self._stop_event, INTERVALO_SEGUNDOS * 1000)
                if rc == win32event.WAIT_OBJECT_0:
                    break
                processar_pendentes()
            log.info("Serviço encerrado")

    _SERVICE_AVAILABLE = True

except ImportError:
    _SERVICE_AVAILABLE = False


# ── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) == 1:
        loop_console()
    elif _SERVICE_AVAILABLE:
        win32serviceutil.HandleCommandLine(GustoImpressaoService)
    else:
        print("pywin32 não instalado. Use: pip install pywin32")
        sys.exit(1)
