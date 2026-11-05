@echo off
setlocal
title Detener Cero Colas
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop-local.ps1"
set "resultado=%ERRORLEVEL%"
echo.
if not "%resultado%"=="0" (
    echo No se pudo completar el cierre. Revisa el mensaje anterior.
) else (
    echo Cierre completado. Los datos de PostgreSQL se conservan.
)
if /I not "%~1"=="--sin-pausa" pause
exit /b %resultado%
