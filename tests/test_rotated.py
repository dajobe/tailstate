"""Tests for tailstate.rotated."""

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from tailstate import RotatedLogFileSavedState


class TestRotatedLogFileSavedState(unittest.TestCase):
    def test_reads_full_file_and_advances_seek(self):
        with tempfile.TemporaryDirectory() as td:
            td_p = Path(td)
            log_path = td_p / "app.log"
            state_path = td_p / "state.json"
            log_path.write_text("one\ntwo\n", encoding="utf-8")

            with RotatedLogFileSavedState(log_path, state_path) as state:
                bodies = [lf.read() for lf in state.logs()]
                self.assertEqual(bodies, ["one\ntwo\n"])

            with RotatedLogFileSavedState(log_path, state_path) as state:
                tails = [lf.read() for lf in state.logs()]
                self.assertEqual(tails, [""])

    def test_appends_only_new_bytes_on_second_pass(self):
        with tempfile.TemporaryDirectory() as td:
            td_p = Path(td)
            log_path = td_p / "app.log"
            state_path = td_p / "state.json"
            log_path.write_text("a\n", encoding="utf-8")

            with RotatedLogFileSavedState(log_path, state_path) as state:
                for lf in state.logs():
                    self.assertEqual(lf.readline(), "a\n")

            with log_path.open("a", encoding="utf-8") as f:
                f.write("b\n")

            with RotatedLogFileSavedState(log_path, state_path) as state:
                for lf in state.logs():
                    self.assertEqual(lf.readline(), "b\n")
                    self.assertEqual(lf.readline(), "")

    def test_no_matching_log_file(self):
        with tempfile.TemporaryDirectory() as td:
            td_p = Path(td)
            log_path = td_p / "missing.log"
            state_path = td_p / "state.json"
            with RotatedLogFileSavedState(log_path, state_path) as state:
                self.assertEqual(list(state.logs()), [])

    def test_rotation_reads_both_segments_after_rotate(self):
        """Simulate a rotate: create .log, read it, move it aside, create new one."""
        with tempfile.TemporaryDirectory() as td:
            td_p = Path(td)
            log_path = td_p / "app.log"
            state_path = td_p / "state.json"

            log_path.write_text("first1\nfirst2\n", encoding="utf-8")

            with RotatedLogFileSavedState(log_path, state_path) as state:
                lines = []
                for lf in state.logs():
                    lines.extend(lf.readlines())
                self.assertEqual(lines, ["first1\n", "first2\n"])

            rotated = td_p / "app.log.1"
            os.rename(log_path, rotated)
            time.sleep(0.01)
            log_path.write_text("second1\n", encoding="utf-8")

            with RotatedLogFileSavedState(log_path, state_path) as state:
                lines = []
                for lf in state.logs():
                    lines.extend(lf.readlines())
                self.assertEqual(lines, ["second1\n"])

    def test_stale_inode_resets_seek_when_previous_file_removed(self):
        """Stale inode after delete/recreate; new log read from offset 0."""
        with tempfile.TemporaryDirectory() as td:
            td_p = Path(td)
            log_path = td_p / "app.log"
            state_path = td_p / "state.json"
            log_path.write_text("old\n", encoding="utf-8")

            with RotatedLogFileSavedState(log_path, state_path) as state:
                for lf in state.logs():
                    lf.read()

            log_path.unlink()
            log_path.write_text("fresh\n", encoding="utf-8")

            with RotatedLogFileSavedState(log_path, state_path) as state:
                bodies = [lf.read() for lf in state.logs()]
            self.assertEqual(bodies, ["fresh\n"])

    def test_listdir_oserror_yields_no_log_streams(self):
        """If the log directory cannot be listed, discovery returns no segments."""
        with tempfile.TemporaryDirectory() as td:
            td_p = Path(td)
            log_path = td_p / "app.log"
            state_path = td_p / "state.json"
            log_path.write_text("x\n", encoding="utf-8")

            real_iterdir = Path.iterdir

            def guarded_iterdir(self: Path):
                if self.resolve() == td_p.resolve():
                    raise OSError("permission denied")
                return real_iterdir(self)

            with (
                patch.object(Path, "iterdir", guarded_iterdir),
                RotatedLogFileSavedState(log_path, state_path) as state,
            ):
                self.assertEqual(list(state.logs()), [])

    def test_updates_state_when_active_segment_is_renamed_mid_iteration(self):
        with tempfile.TemporaryDirectory() as td:
            td_p = Path(td)
            log_path = td_p / "app.log"
            state_path = td_p / "state.json"
            rotated_path = td_p / "app.log.1"
            log_path.write_text("first\n", encoding="utf-8")

            with RotatedLogFileSavedState(log_path, state_path) as state:
                logs = state.logs()
                log_file = next(logs)
                self.assertEqual(log_file.read(), "first\n")
                os.rename(log_path, rotated_path)
                time.sleep(0.01)
                log_path.write_text("second\n", encoding="utf-8")
                with self.assertRaises(StopIteration):
                    next(logs)

            with RotatedLogFileSavedState(log_path, state_path) as state:
                lines = []
                for lf in state.logs():
                    lines.extend(lf.readlines())

            self.assertEqual(lines, ["second\n"])
