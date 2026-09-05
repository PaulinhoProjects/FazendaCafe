@echo off
echo Configurando backup automático no Agendador de Tarefas do Windows...
echo.

REM Caminhos
set SCRIPT_DIR=%~dp0
set PYTHON_PATH=C:\Python311\python.exe
set BACKUP_SCRIPT=%SCRIPT_DIR%backup.py

REM Criar tarefa para executar todo dia as 02:00
schtasks /create /tn "FazendaCafe_Backup" /tr "%PYTHON_PATH% %BACKUP_SCRIPT%" /sc daily /st 02:00 /ru SYSTEM /f

echo.
echo ✅ Backup agendado para todos os dias as 02:00
echo.
echo Para testar agora, execute: python %BACKUP_SCRIPT%
pause