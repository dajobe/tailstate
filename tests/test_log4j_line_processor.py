"""Tests for tailstate.log4j_line_processor."""

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
