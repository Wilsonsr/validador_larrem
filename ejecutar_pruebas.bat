@echo off
REM Ejecuta las pruebas automaticas del validador.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" ( echo Ejecute primero iniciar_validador.bat & pause & exit /b 1 )
".venv\Scripts\python.exe" -m pip install -q pytest
".venv\Scripts\python.exe" -m pytest -q tests
pause
