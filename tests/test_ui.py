"""Tests de fumée de l'interface (Qt hors écran)."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from face_analyse.ui import theme

    app.setStyleSheet(theme.stylesheet())
    theme.apply_fonts(app)
    return app


@pytest.fixture
def ctx(qapp, tmp_path):
    from face_analyse.core.config import Settings
    from face_analyse.database.repository import Repository
    from face_analyse.ui.context import AppContext

    repo = Repository(tmp_path / "ui.db")
    yield AppContext(Settings.load(), repo)
    repo.close()


def test_welcome_menu_keyboard(qapp):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeyEvent

    from face_analyse.ui.splash import MENU, WelcomeWindow

    w = WelcomeWindow()
    assert w.width() == 750 and w.height() == 450
    w.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_4, Qt.KeyboardModifier.NoModifier))
    assert w._selected == 3 and w.items[3].isChecked()
    got = []
    w.entered.connect(got.append)
    w._outro_and_emit(MENU[w._selected][0])
    w._outro.setCurrentTime(w._outro.duration())
    assert got == ["osint"]


def test_main_window_all_pages(ctx):
    from face_analyse.ui.main_window import NAV, MainWindow

    win = MainWindow(ctx)
    for key, _label, _cls in NAV:
        win.show_page(key)
        assert win.stack.currentWidget() is win.pages[key]
    win.close()


def test_analysis_without_engine_warns(ctx):
    from face_analyse.ui.pages.analysis import AnalysisPage, AnalyzeTab

    msgs = []
    ctx.notify.connect(lambda m, lvl: msgs.append(lvl))
    page = AnalysisPage(ctx)
    page.findChild(AnalyzeTab).analyze("x.jpg")
    assert msgs == ["warning"]


def test_worker_delivers_result(qapp):
    from PySide6.QtCore import QEventLoop, QTimer

    from face_analyse.ui.workers import run_async

    out = []
    loop = QEventLoop()
    run_async(lambda: 41 + 1, on_done=lambda r: (out.append(r), loop.quit()))
    QTimer.singleShot(3000, loop.quit)
    loop.exec()
    assert out == [42]


def test_camera_pipeline_tracks_and_names(qapp, lfw_root, tmp_path, monkeypatch):
    """Flux vidéo simulé : un visage enregistré qui se déplace + un visage absent."""
    import cv2
    import numpy as np
    from PySide6.QtCore import QEventLoop, QTimer

    import face_analyse.ui.camera_thread as ct
    from face_analyse.core.config import EngineSettings
    from face_analyse.engine.matcher import GalleryEntry
    from face_analyse.engine.pipeline import FaceEngine
    from face_analyse.engine.preprocessing import load_image

    e = FaceEngine.from_settings(EngineSettings())
    refs = []
    for i in (1, 2, 3):
        a, _ = e.embed_single(load_image(lfw_root / "Tony_Blair" / f"Tony_Blair_{i:04d}.jpg"))
        refs.append(GalleryEntry(i, 1, "Tony Blair", a.embedding.vector, a.embedding.model_id))
    e.matcher.load(refs, e.embedder.model_id)
    known = load_image(lfw_root / "Tony_Blair" / "Tony_Blair_0020.jpg")
    absent = load_image(lfw_root / "Jennifer_Aniston" / "Jennifer_Aniston_0003.jpg")
    video = tmp_path / "cam.avi"
    vw = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"MJPG"), 25, (1280, 720))
    for f in range(60):
        frame = np.full((720, 1280, 3), 30, np.uint8)
        x = 100 + f * 6
        frame[200:450, x:x + 250] = known
        frame[200:450, 900:1150] = absent
        vw.write(frame)
    vw.release()
    monkeypatch.setattr(ct, "open_capture", lambda idx: cv2.VideoCapture(str(video)))

    th = ct.CameraThread(e, 0, mirror=False, recognition_interval=3)
    frames = []
    th.frame_ready.connect(lambda _img, views: frames.append(views))
    th.start()
    loop = QEventLoop()
    th.finished.connect(loop.quit)
    QTimer.singleShot(15000, loop.quit)
    loop.exec()
    th.stop()

    last = sorted(frames[-1], key=lambda v: v.box[0])
    assert [v.label for v in last] == ["Tony Blair", "UNKNOWN"]
    assert len({v.track_id for f in frames for v in f}) == 2  # identités de piste stables
