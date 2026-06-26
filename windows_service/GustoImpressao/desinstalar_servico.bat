@echo off
:: Deve ser executado como Administrador
cd /d "%~dp0"

echo Parando e removendo servico GUSTO Impressao...
sc stop GustoImpressao
sc delete GustoImpressao

echo.
echo Servico removido.
pause
