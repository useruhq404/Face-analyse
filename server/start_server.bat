@echo off
REM ============================================================
REM  FACE ANALYSE - serveur local (double-cliquez ce fichier)
REM  Prerequis : Python 3.12+ installe (python.org, "Add to PATH")
REM ============================================================
setlocal
cd /d "%~dp0"

if not exist .venv (
    echo [1/2] Premiere installation...
    py -3 -m venv .venv 2>nul || python -m venv .venv || goto :error
    call .venv\Scripts\activate.bat
    python -m pip install --upgrade pip >nul
    pip install -r requirements.txt || goto :error
) else (
    call .venv\Scripts\activate.bat
)

echo [2/2] Demarrage du serveur...
python start_local.py
goto :eof

:error
echo.
echo  ECHEC. Verifiez que Python 3.12+ est installe.
pause
