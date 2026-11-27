@echo off
setlocal
set PGBIN=%USERPROFILE%\pg\pgsql\bin
set PGDATA=%USERPROFILE%\pgdata

echo Iniciando PostgreSQL...
"%PGBIN%\pg_ctl.exe" -D "%PGDATA%" -l "%PGDATA%\server.log" -o "-p 5432" start

echo Iniciando Kaldi...
cd /d "%~dp0.."
rem Painel com vigia anti-travamento; sem o executável, usa o servidor de desenvolvimento
if exist "Kaldi Servidor.exe" (
    start "" "Kaldi Servidor.exe"
) else (
    python run.py
)
