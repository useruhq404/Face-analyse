"""Point d'entrée de l'application graphique."""

from __future__ import annotations

import logging
import sys

from face_analyse import __app_name__, __author__, __version__
from face_analyse.core.logging_setup import setup_logging

log = logging.getLogger(__name__)


def check_dependencies() -> list[str]:
    """Vérifie les dépendances critiques ; retourne la liste des problèmes."""
    problems = []
    try:
        import cv2

        if not hasattr(cv2, "FaceDetectorYN") or not hasattr(cv2, "FaceRecognizerSF"):
            problems.append(f"OpenCV {cv2.__version__} trop ancien (>= 4.8 requis).")
    except ImportError:
        problems.append("OpenCV (opencv-python) n'est pas installé.")
    for mod, name in (("numpy", "numpy"), ("sqlalchemy", "SQLAlchemy"), ("cryptography", "cryptography"),
                      ("requests", "requests")):
        try:
            __import__(mod)
        except ImportError:
            problems.append(f"{name} n'est pas installé.")
    return problems


def main(argv: list[str] | None = None) -> int:
    setup_logging()
    log.info("%s v%s — fait par %s", __app_name__, __version__, __author__)

    from PySide6.QtCore import Qt
    from PySide6.QtGui import QIcon, QPixmap
    from PySide6.QtWidgets import QApplication, QMessageBox

    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(__app_name__)
    app.setOrganizationName(__author__)
    app.setApplicationVersion(__version__)

    from face_analyse.core.paths import resource_path
    from face_analyse.ui import theme

    app.setStyleSheet(theme.stylesheet())
    theme.apply_fonts(app)
    icon_path = resource_path("images", "icon.png")
    if icon_path.exists():
        app.setWindowIcon(QIcon(QPixmap(str(icon_path))))

    problems = check_dependencies()
    if problems:
        QMessageBox.critical(None, __app_name__, "Dépendances manquantes :\n\n" + "\n".join(problems))
        return 2

    from face_analyse.core.config import Settings
    from face_analyse.core.errors import FaceAnalyseError
    from face_analyse.database.repository import Repository
    from face_analyse.ui.context import AppContext
    from face_analyse.ui.login_window import TOKEN_SECRET, LoginWindow
    from face_analyse.ui.main_window import MainWindow
    from face_analyse.ui.splash import WelcomeWindow

    try:
        repo = Repository()
    except FaceAnalyseError as exc:
        QMessageBox.critical(None, __app_name__, exc.user_message)
        return 3
    settings = Settings.load()

    # Mode avec comptes si un serveur est configuré, sinon mode autonome.
    auth = None
    server_url = settings.server_url()
    if server_url:
        from face_analyse.auth.client import AuthClient

        auth = AuthClient(server_url)
        stored = repo.get_secret(TOKEN_SECRET)
        if settings.auth.remember and stored:
            try:
                auth.resume(stored)  # reprise silencieuse de session
            except FaceAnalyseError:
                pass

    ctx = AppContext(settings, repo, auth=auth)
    ctx.load_engine()  # en tâche de fond pendant l'écran d'accueil

    holder: dict[str, MainWindow] = {}

    def open_dashboard(page_key: str):
        win = MainWindow(ctx)
        holder["main"] = win
        ctx.account_revoked.connect(lambda msg: _on_revoked(win, msg))
        win.show_page(page_key)
        win.fade_in()
        if ctx.engine is not None:
            win._engine_ready()
            win._gallery_changed()
        ctx.start_heartbeat()
        if ctx.account:
            ctx.log_event("app", "open", {"page": page_key})

    def _on_revoked(win: MainWindow, msg: str):
        ctx.stop_heartbeat()
        if auth:
            auth.logout()
            repo.set_secret(TOKEN_SECRET, "")
        QMessageBox.warning(win, __app_name__, msg or "Session fermée.")
        win.close()

    def enter(page_key: str):
        # Serveur configuré et pas de session valide : exiger la connexion.
        if auth is not None and auth.account is None:
            login = LoginWindow(auth, repo, settings.auth.remember)
            if not login.exec():
                return  # connexion annulée : on reste sur l'accueil
        open_dashboard(page_key)

    welcome = WelcomeWindow()
    welcome.entered.connect(enter)
    welcome.show()
    code = app.exec()
    ctx.stop_heartbeat()
    repo.close()
    return code


if __name__ == "__main__":
    sys.exit(main())
