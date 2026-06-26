@echo off
:: Deve ser executado como Administrador
setlocal

set "EXE=%~dp0GustoImpressao.exe"

echo Instalando GUSTO Impressao...
echo Executavel: %EXE%
echo.

sc stop GustoImpressao >nul 2>&1
sc delete GustoImpressao >nul 2>&1
timeout /t 2 /nobreak >nul

sc create GustoImpressao binPath= "\"%EXE%\"" start= auto DisplayName= "GUSTO - Impressao Automatica"
if errorlevel 1 (
    echo ERRO ao criar servico.
    pause
    exit /b 1
)

sc description GustoImpressao "Monitora pedidos do GUSTO e imprime automaticamente."
sc start GustoImpressao

if errorlevel 1 (
    echo ERRO ao iniciar servico.
    pause
    exit /b 1
)

echo.
echo Servico instalado e iniciado com sucesso!
echo Para verificar: services.msc
pause
