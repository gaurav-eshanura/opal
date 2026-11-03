"""The watch folder has to do the whole job on its own.

Drop a file in, walk away: Opal has to notice it, convert it, move the result
into Output/ and move the original into Originals/ - all without a click.
"""

import time
from pathlib import Path

from opal_artifacts import validate_file


def _wait_for(condition, app, timeout: float = 40.0) -> bool:
    """Wait for something to happen, keeping the Qt event loop alive so the
    worker's signal can actually reach us."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        app.processEvents()
        if condition():
            return True
        time.sleep(0.2)
    return False


def test_a_dropped_file_is_converted_without_a_click(tmp_path, app):
    from opal_studio.watch_folder import WatchFolderWorker

    watch = tmp_path / "watch"
    watch.mkdir()

    worker = WatchFolderWorker(str(watch))
    events = []
    worker.file_processed_signal.connect(
        lambda name, output, message: events.append((name, output, message)))
    worker.start()
    try:
        # Let the worker take its first look at the (empty) folder, so the
        # file we drop below is a genuinely new arrival.
        time.sleep(2.0)

        source = watch / "dropped_note.txt"
        source.write_text("Opal watch folder test", encoding="utf-8")

        assert _wait_for(lambda: bool(events), app), \
            "the watch folder never reported the dropped file"

        name, output_path, message = events[0]
        assert name == "dropped_note.txt", f"it reported the wrong file: {name}"
        assert "dropped_note" in message, f"the message says nothing useful: {message}"

        produced = Path(output_path)
        assert produced.exists(), f"the message promised an output that is not there: {produced}"
        assert produced.parent.name == "Output", \
            f"the converted file was left in {produced.parent}, not in Output/"

        ok, detail = validate_file(produced)
        assert ok, f"the watch folder produced an unusable file: {detail}"

        assert (watch / "Originals" / "dropped_note.txt").exists(), \
            "the original file was not moved into Originals/"
    finally:
        worker.stop()
        worker.wait(5000)


def test_a_file_that_keeps_failing_is_quarantined_in_failed(tmp_path, app):
    """A broken file must not be retried forever: after a few attempts it
    lands in Failed/ and the worker says so, instead of silently vanishing."""
    from opal_studio.watch_folder import WatchFolderWorker

    watch = tmp_path / "watch"
    watch.mkdir()

    worker = WatchFolderWorker(str(watch))
    events = []
    failures = []
    worker.file_processed_signal.connect(
        lambda name, output, message: events.append((name, output, message)))
    worker.file_failed_signal.connect(
        lambda name, reason: failures.append((name, reason)))
    worker.start()
    try:
        time.sleep(2.0)

        # A .png with garbage bytes: routed to webp, which cannot read it.
        source = watch / "broken.png"
        source.write_bytes(b"this is not a real png" * 40)

        assert _wait_for(lambda: bool(failures), app, timeout=60.0), \
            "the broken file was never quarantined in Failed/"

        name, reason = failures[0]
        assert name == "broken.png"
        assert "failed" in reason.lower(), f"the failure says nothing useful: {reason}"

        assert (watch / "Failed" / "broken.png").exists(), \
            "the broken file was not moved into Failed/"
        assert not source.exists(), "the broken file was left in the watch folder"
        assert not events, f"a failed file was reported as processed: {events}"
        assert not (watch / "Originals" / "broken.png").exists()
    finally:
        worker.stop()
        worker.wait(5000)


def test_unroutable_and_temporary_files_are_left_alone(tmp_path, app):
    """Files Opal has no rule for (and half-downloaded temp files) stay where
    they are - the watch folder must not eat or move them."""
    from opal_studio.watch_folder import WatchFolderWorker

    watch = tmp_path / "watch"
    watch.mkdir()

    worker = WatchFolderWorker(str(watch))
    events = []
    failures = []
    worker.file_processed_signal.connect(
        lambda name, output, message: events.append((name, output, message)))
    worker.file_failed_signal.connect(
        lambda name, reason: failures.append((name, reason)))
    worker.start()
    try:
        time.sleep(2.0)

        mystery = watch / "mystery.xyz"
        mystery.write_text("no rule for this", encoding="utf-8")
        partial = watch / "download.crdownload"
        partial.write_bytes(b"half a download")

        # Give the worker several scans to see both files.
        deadline = time.time() + 6.0
        while time.time() < deadline:
            app.processEvents()
            time.sleep(0.2)

        assert mystery.exists(), "the watch folder moved a file it has no rule for"
        assert partial.exists(), "the watch folder moved a half-downloaded temp file"
        assert not events, f"unroutable files were reported as converted: {events}"
        assert not failures, f"unroutable files were reported as failures: {failures}"
        assert not (watch / "Originals" / "mystery.xyz").exists()
        assert not (watch / "Failed" / "mystery.xyz").exists()
    finally:
        worker.stop()
        worker.wait(5000)
