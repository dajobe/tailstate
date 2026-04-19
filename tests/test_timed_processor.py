"""Tests for tailstate.timed_processor."""

import signal
import tempfile
import time
import unittest
from pathlib import Path

from tailstate import RotatedLogFileSavedState, TimedLogProcessor


class _SumBytes(TimedLogProcessor):
    def process_log(self, log_file):
        return (len(log_file.read()), False)

    def combine_values(self, old_val, new_val):
        return old_val + new_val


class _SleepyProc(TimedLogProcessor):
    def process_log(self, log_file):
        log_file.read()
        time.sleep(5)
        return (1, False)

    def combine_values(self, old_val, new_val):
        return old_val + new_val


class _SkipRest(TimedLogProcessor):
    def process_log(self, log_file):
        log_file.read()
        return (1, True)

    def combine_values(self, old_val, new_val):
        return old_val + new_val


class TestTimedLogProcessor(unittest.TestCase):
    def test_combines_results_from_two_chunks(self):
        with tempfile.TemporaryDirectory() as td:
            log_path = Path(td) / "x.log"
            state_path = Path(td) / "st.json"
            log_path.write_text("abcd", encoding="utf-8")

            proc = _SumBytes(max_duration=30)
            with RotatedLogFileSavedState(log_path, state_path) as state:
                self.assertEqual(proc.process(state), 4)

    def test_timeout_stops_processing(self):
        with tempfile.TemporaryDirectory() as td:
            log_path = Path(td) / "x.log"
            state_path = Path(td) / "st.json"
            log_path.write_text("abcd", encoding="utf-8")

            proc = _SleepyProc(max_duration=1)
            start = time.monotonic()
            with RotatedLogFileSavedState(log_path, state_path) as state:
                result = proc.process(state)
            elapsed = time.monotonic() - start

            self.assertIsNone(result)
            self.assertLess(elapsed, 3.0)

    def test_subsecond_timeout_stops_processing_promptly(self):
        with tempfile.TemporaryDirectory() as td:
            log_path = Path(td) / "x.log"
            state_path = Path(td) / "st.json"
            log_path.write_text("abcd", encoding="utf-8")

            proc = _SleepyProc(max_duration=0.25)
            start = time.monotonic()
            with RotatedLogFileSavedState(log_path, state_path) as state:
                result = proc.process(state)
            elapsed = time.monotonic() - start

            self.assertIsNone(result)
            self.assertLess(elapsed, 0.9)

    def test_skip_others_skips_later_segments(self):
        with tempfile.TemporaryDirectory() as td:
            td_p = Path(td)
            log_path = td_p / "x.log"
            state_path = td_p / "st.json"
            older = td_p / "x.log.1"
            older.write_text("older\n", encoding="utf-8")
            time.sleep(0.01)
            log_path.write_text("newer\n", encoding="utf-8")

            proc = _SkipRest(max_duration=30)
            with RotatedLogFileSavedState(log_path, state_path) as state:
                self.assertEqual(proc.process(state), 1)

    def test_restores_previous_sigalrm_handler(self):
        prior = signal.signal(signal.SIGALRM, signal.SIG_IGN)
        try:
            with tempfile.TemporaryDirectory() as td:
                log_path = Path(td) / "x.log"
                state_path = Path(td) / "st.json"
                log_path.write_text("ab", encoding="utf-8")

                proc = _SumBytes(max_duration=5)
                with RotatedLogFileSavedState(log_path, state_path) as state:
                    proc.process(state)

            current = signal.getsignal(signal.SIGALRM)
            self.assertEqual(current, signal.SIG_IGN)
        finally:
            signal.signal(signal.SIGALRM, prior)
