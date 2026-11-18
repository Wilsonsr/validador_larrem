@echo off
REM Validador LARREM - inicia la aplicacion en el navegador.
REM La primera vez crea un entorno de Python en la carpeta .venv e instala las dependencias.
setlocal
cd /d "%~dp0"
chcp 65001 >nul

set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY ( where python >nul 2>nul && set "PY=python" )
if not defined PY (
  echo No se encontro Python en este equipo.
  echo Instale Python 3.10 o superior desde https://www.python.org/downloads/ ^(marque "Add python.exe to PATH"^)
  echo y vuelva a ejecutar este archivo.
  pause
  exit /b 1
)

%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"
if errorlevel 1 (
  echo Se requiere Python 3.10 o superior. Version encontrada:
  %PY% --version
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creando el entorno de Python ^(solo la primera vez^)...
  %PY% -m venv .venv
  if errorlevel 1 ( echo No se pudo crear el entorno .venv & pause & exit /b 1 )
)

REM Instala las dependencias la primera vez y cada vez que cambie requirements.txt
REM (por ejemplo, al reemplazar la carpeta por una version nueva).
set "INSTALAR="
if not exist ".venv\requisitos_instalados.txt" set "INSTALAR=1"
if not defined INSTALAR (
  fc /b "requirements.txt" ".venv\requisitos_instalados.txt" >nul 2>nul || set "INSTALAR=1"
)
if defined INSTALAR (
  echo Instalando o actualizando dependencias ^(requiere internet, puede tardar unos minutos^)...
  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 (
    echo.
    echo No se pudieron instalar las dependencias. Si la red usa proxy, configure:
    echo   set HTTPS_PROXY=http://usuario:clave@proxy:puerto
    echo y vuelva a ejecutar este archivo.
    pause
    exit /b 1
  )
  copy /y "requirements.txt" ".venv\requisitos_instalados.txt" >nul
)

echo Abriendo el validador en el navegador. Para cerrarlo, cierre esta ventana.
".venv\Scripts\python.exe" -m streamlit run app.py --server.headless false --browser.gatherUsageStats false
pause
