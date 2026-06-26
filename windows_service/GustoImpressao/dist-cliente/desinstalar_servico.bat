@echo off
:: Deve ser executado como Administrador

echo Parando e removendo GUSTO Impressao...
sc stop GustoImpressao
sc delete GustoImpressao

echo.
echo Servico removido.
pause
