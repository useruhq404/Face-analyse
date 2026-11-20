@echo off
REM ============================================================
REM  FACE ANALYSE - construction de l'executable Windows
REM  Prerequis : Python 3.12+ (python.org, case "Add to PATH")
REM ============================================================
setlocal
cd /d "%~dp0"

if not exist .venv (
    echo [1/5] Creation de l'environnement virtuel...
    py -3 -m venv .venv || python -m venv .venv || goto :error
)
call .venv\Scripts\activate.bat || goto :error

echo [2/5] Installation des dependances...
python -m pip install --upgrade pip >nul
pip install -r requirements-dev.txt || goto :error

echo [3/5] Verification des modeles (SHA-256)...
python scripts\download_models.py || goto :error

echo [4/5] Tests unitaires...
python -m pytest -q || goto :error

echo [5/5] Compilation PyInstaller...
pyinstaller --noconfirm face_analyse.spec || goto :error

echo.
echo  OK : dist\FaceAnalyse\FaceAnalyse.exe
exit /b 0

:error
echo.
echo  ECHEC de la construction (voir messages ci-dessus).
exit /b 1
