@echo off
setlocal
set PGBIN=%USERPROFILE%\pg\pgsql\bin
set PGDATA=%USERPROFILE%\pgdata

echo Iniciando PostgreSQL...
"%PGBIN%\pg_ctl.exe" -D "%PGDATA%" -l "%PGDATA%\server.log" -o "-p 5432" start

echo Iniciando Kaldi...
cd /d "%~dp0.."
python run.py
