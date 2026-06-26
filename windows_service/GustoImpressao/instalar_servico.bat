@echo off
:: Deve ser executado como Administrador
cd /d "%~dp0"

echo Instalando servico GUSTO Impressao...
sc create GustoImpressao binPath= "%~dp0GustoImpressao.exe" start= auto DisplayName= "GUSTO - Impressao Automatica"
sc description GustoImpressao "Monitora pedidos do GUSTO e imprime automaticamente."
sc start GustoImpressao

echo.
echo Servico instalado e iniciado.
echo Para verificar: services.msc
pause
