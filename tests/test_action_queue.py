"""Actions queue up instead of replacing each other.

Starting a second action while one was running used to overwrite the worker
reference: the first batch kept running invisibly and its result was never
shown - and two batches at once fight over memory (the AI models are the
heavy part).  Now one runs at a time and the rest wait in a FIFO queue.
"""
from __future__ import annotations

import pytest
from PySide6.QtCore import QObject, Signal

import opal_studio.main as main_mod
from opal_studio.engine import BatchConversionResult


class FakeWorker(QObject):
    """Stands in for ConversionWorker: records that it started and stays
    "running" until the test calls finish(), like a real batch job would."""

    finished_signal = Signal(object)
    started: list = []
    live: list = []

    def __init__(self, file_paths, action_id, parent=None):
        super().__init__(parent)
        self.file_paths = file_paths
        self.action_id = action_id
        self._running = False
        FakeWorker.started.append(action_id)
        FakeWorker.live.append(self)

    def start(self):
        self._running = True

    def isRunning(self):
        return self._running

    def finish(self, succeed=True):
        self._running = False
        FakeWorker.live.remove(self)
        if succeed:
            result = BatchConversionResult(len(self.file_paths), len(self.file_paths),
                                           0, ["/tmp/out"], 0, "done")
        else:
            result = BatchConversionResult(len(self.file_paths), 0, len(self.file_paths),
                                           [], 0, "failed")
        self.finished_signal.emit(result)


@pytest.fixture
def queued_app(app, monkeypatch):
    FakeWorker.started = []
    FakeWorker.live = []
    monkeypatch.setattr(main_mod, "ConversionWorker", FakeWorker)
    from opal_studio.main import OpalApp
    opal = OpalApp(app)
    yield opal
    opal.shutdown()


def test_actions_run_one_at_a_time_in_fifo_order(queued_app, app, samples):
    f1 = str(samples.path("tiny.png"))
    f2 = str(samples.path("photo.jpg"))

    queued_app._enqueue_action([f1], "webp")
    assert FakeWorker.started == ["webp"], "the first action must start immediately"

    # These arrive while the first is still running: they must wait.
    queued_app._enqueue_action([f2], "png")
    queued_app._enqueue_action([f1, f2], "pdf")
    app.processEvents()
    assert FakeWorker.started == ["webp"], \
        f"a second action started while the first was running: {FakeWorker.started}"
    assert len(queued_app._action_queue) == 2, "the waiting actions were not queued"

    FakeWorker.live[0].finish()          # webp done -> png starts
    app.processEvents()
    assert FakeWorker.started == ["webp", "png"], FakeWorker.started
    assert len(queued_app._action_queue) == 1

    FakeWorker.live[0].finish()          # png done -> pdf starts
    app.processEvents()
    assert FakeWorker.started == ["webp", "png", "pdf"], FakeWorker.started
    assert not queued_app._action_queue, "the queue was not drained"

    FakeWorker.live[0].finish()          # pdf done -> nothing left
    app.processEvents()
    assert queued_app.current_worker is None


def test_a_failed_job_still_lets_the_queue_continue(queued_app, app, samples):
    f1 = str(samples.path("tiny.png"))

    queued_app._enqueue_action([f1], "webp")
    queued_app._enqueue_action([f1], "png")
    assert FakeWorker.started == ["webp"]

    FakeWorker.live[0].finish(succeed=False)   # the running job fails
    app.processEvents()
    assert FakeWorker.started == ["webp", "png"], \
        "a failed job blocked the rest of the queue"


def test_the_dashboard_pill_shows_the_queue(queued_app, app, samples):
    """The header pill is the user-visible side of the queue: it must say how
    many jobs are waiting, and go back to idle when the queue is empty."""
    f1 = str(samples.path("tiny.png"))
    pill = queued_app.dashboard.status_pill
    assert pill.text() == "Active & Running"

    queued_app._enqueue_action([f1], "webp")
    queued_app._enqueue_action([f1], "png")
    app.processEvents()
    assert pill.text() == "Working · 1 queued", f"pill said: {pill.text()!r}"

    FakeWorker.live[0].finish()          # webp done, png now running
    app.processEvents()
    assert pill.text() == "Working…", f"pill said: {pill.text()!r}"

    FakeWorker.live[0].finish()          # png done, queue empty
    app.processEvents()
    assert pill.text() == "Active & Running", f"pill said: {pill.text()!r}"
