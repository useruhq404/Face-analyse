"""Exécution des traitements lourds hors du fil de l'interface."""

from __future__ import annotations

import logging
import traceback
from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from face_analyse.core.errors import FaceAnalyseError

log = logging.getLogger(__name__)


class WorkerSignals(QObject):
    finished = Signal(object)
    failed = Signal(str)
    progress = Signal(str, int, int)


class Worker(QRunnable):
    """Exécute ``fn(*args, progress=..., **kwargs)`` dans le pool de threads.

    ``fn`` reçoit un callback ``progress(label, done, total)`` s'il accepte
    l'argument ``progress``.
    """

    def __init__(self, fn: Callable[..., Any], *args, with_progress: bool = False, **kwargs):
        super().__init__()
        self.fn, self.args, self.kwargs = fn, args, kwargs
        self.with_progress = with_progress
        self.signals = WorkerSignals()
        # Python garde la propriété de l'objet (voir _ACTIVE ci-dessous).
        self.setAutoDelete(False)

    def run(self):
        try:
            if self.with_progress:
                self.kwargs["progress"] = lambda label, done, total: self.signals.progress.emit(label, done, total)
            result = self.fn(*self.args, **self.kwargs)
        except FaceAnalyseError as exc:
            log.warning("Erreur métier : %s", exc)
            self.signals.failed.emit(exc.user_message)
        except Exception as exc:  # noqa: BLE001 - dernier rempart : on journalise tout
            log.error("Erreur inattendue : %s\n%s", exc, traceback.format_exc())
            self.signals.failed.emit(f"Erreur inattendue : {exc}")
        else:
            self.signals.finished.emit(result)


#: Références fortes vers les workers en cours : sans elles, le ramasse-miettes
#: peut détruire le worker (et ses signaux) avant la livraison du résultat.
_ACTIVE: set[Worker] = set()


def run_async(fn, *args, on_done=None, on_error=None, on_progress=None, **kwargs) -> Worker:
    w = Worker(fn, *args, with_progress=on_progress is not None, **kwargs)
    _ACTIVE.add(w)
    w.signals.finished.connect(lambda _r: _ACTIVE.discard(w))
    w.signals.failed.connect(lambda _m: _ACTIVE.discard(w))
    if on_done:
        w.signals.finished.connect(on_done)
    if on_error:
        w.signals.failed.connect(on_error)
    if on_progress:
        w.signals.progress.connect(on_progress)
    QThreadPool.globalInstance().start(w)
    return w
