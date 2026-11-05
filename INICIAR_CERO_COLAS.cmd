@echo off
setlocal
title Iniciar Cero Colas
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-local.ps1"
set "resultado=%ERRORLEVEL%"
echo.
if not "%resultado%"=="0" (
    echo No se pudo completar el inicio. Revisa el mensaje anterior.
) else (
    echo Abre http://127.0.0.1:5173 en tu navegador.
    echo Para apagar los servicios, usa DETENER_CERO_COLAS.cmd.
    echo Cerrar esta ventana no apaga el proyecto.
)
if /I not "%~1"=="--sin-pausa" pause
exit /b %resultado%
