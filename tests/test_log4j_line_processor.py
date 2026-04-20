"""Tests for tailstate.log4j_line_processor."""

import io
import tempfile
import unittest
from pathlib import Path

from tailstate import Log4jLogLineProcessor, RotatedLogFileSavedState


class _Tiny(Log4jLogLineProcessor):
    def get_metrics(self):
        return {"level": {"info": 0, "other": 0}}

    def process_level_info(self, message):
        return {"level": {"info": 1}}

    def process_non_log(self, line):
        return {"level": {"other": 1}}


class _Nested(Log4jLogLineProcessor):
    """Nested metric dicts; exercise deep merge in metric accumulation."""

    def get_metrics(self):
        return {"outer": {"inner": 0}}

    def process_level_info(self, message):
        return {"outer": {"inner": 1}}


class TestLog4jLogLineProcessor(unittest.TestCase):
    def test_counts_info_lines_and_non_log(self):
        with tempfile.TemporaryDirectory() as td:
            td_p = Path(td)
            lp = td_p / "x.log"
            sp = td_p / "st.json"
            body = (
                "2024-06-01 10:00:00,123 INFO ping\n"
                "2024-06-01 10:00:01,456 WARN x\n"
                "not a log line\n"
            )
            lp.write_text(body, encoding="utf-8")

            proc = _Tiny(max_duration=30)
            with RotatedLogFileSavedState(lp, sp) as state:
                m = proc.process(state)
        self.assertEqual(m["level"]["info"], 1)
        self.assertEqual(m["level"]["other"], 1)

    def test_nested_metrics_merge_across_lines(self):
        """Two lines contributing to the same nested dict sum via ``_recursive_sum``."""
        proc = _Nested(max_duration=30)
        buf = io.StringIO(
            "2024-06-01 10:00:00,123 INFO one\n2024-06-01 10:00:01,456 INFO two\n"
        )
        metrics, _ = proc.process_log(buf)
        self.assertEqual(metrics["outer"]["inner"], 2)

    def test_partial_final_line_without_newline_is_deferred(self):
        """Incomplete last line rewinds the read position; line is not counted yet."""
        proc = _Tiny(max_duration=30)
        buf = io.StringIO(
            "2024-06-01 10:00:00,123 INFO counted\n"
            "2024-06-01 10:00:01,456 WARN no_eol_yet"
        )
        metrics, _ = proc.process_log(buf)
        self.assertEqual(metrics["level"]["info"], 1)
        self.assertEqual(metrics["level"]["other"], 0)

    def test_blank_stripped_line_is_skipped(self):
        proc = _Tiny(max_duration=30)
        buf = io.StringIO(
            "2024-06-01 10:00:00,123 INFO ok\n\n2024-06-01 10:00:01,456 INFO ok2\n"
        )
        metrics, _ = proc.process_log(buf)
        self.assertEqual(metrics["level"]["info"], 2)
