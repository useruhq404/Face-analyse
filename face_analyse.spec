# -*- mode: python ; coding: utf-8 -*-
# PyInstaller — construction de l'exécutable Windows de FACE ANALYSE.
#   pyinstaller --noconfirm face_analyse.spec
# Résultat : dist/FaceAnalyse/FaceAnalyse.exe (mode dossier : démarrage rapide).

from pathlib import Path

ROOT = Path(SPECPATH)
RES = ROOT / "face_analyse" / "resources"

datas = [
    (str(RES / "models"), "face_analyse/resources/models"),
    (str(RES / "images"), "face_analyse/resources/images"),
    (str(RES / "benchmark.json"), "face_analyse/resources"),
    (str(RES / "deployment.json"), "face_analyse/resources"),
]

a = Analysis(
    [str(ROOT / "face_analyse" / "__main__.py")],
    pathex=[str(ROOT)],
    datas=datas,
    hiddenimports=["sqlalchemy.dialects.sqlite", "PySide6.QtPrintSupport", "phonenumbers", "PIL", "PIL.ExifTags"],
    excludes=["tkinter", "PIL", "matplotlib", "sklearn", "scipy", "pandas", "IPython", "pytest",
              "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.Qt3DCore", "PySide6.QtQuick",
              "PySide6.QtQml", "PySide6.QtMultimedia", "PySide6.QtCharts", "PySide6.QtDataVisualization"],
    noarchive=False,
)
# Allègement : modules Qt inutilisés (QML/Quick, WebEngine, 3D, PDF, multimédia) et traductions Qt.
_UNUSED_QT = ("Qt6Quick", "Qt6Qml", "Qt6WebEngine", "Qt63D", "Qt6Pdf", "Qt6Multimedia", "Qt6Charts",
              "Qt6DataVisualization", "Qt6VirtualKeyboard", "Qt6Designer", "Qt6ShaderTools", "Qt6Sensors",
              "Qt6Location", "Qt6Positioning", "Qt6Bluetooth", "Qt6Nfc", "Qt6SerialPort", "Qt6RemoteObjects")


def _keep(entry):
    name = entry[0].replace("\\", "/")
    if "/translations/" in name or "/qml/" in name:
        return False
    return not any(tag in name for tag in _UNUSED_QT)


a.binaries = [b for b in a.binaries if _keep(b)]
a.datas = [d for d in a.datas if _keep(d)]

pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FaceAnalyse",
    icon=str(RES / "images" / "icon.ico"),
    console=False,
    upx=False,
    version=None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="FaceAnalyse")
