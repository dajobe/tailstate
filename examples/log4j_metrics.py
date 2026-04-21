#!/usr/bin/env python3
"""Minimal log4j metrics demo

Run from the project root with::

    uv run python examples/log4j_metrics.py
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from tailstate import Log4jLogLineProcessor, RotatedLogFileSavedState


class DemoErrorWarnCounter(Log4jLogLineProcessor):
    """Count WARN and ERROR lines in log4j PatternLayout output.

    ``Log4jLogLineProcessor`` parses each line into ``(timestamp, level,
    message)`` and then dispatches to a ``process_level_<level>`` method
    when one exists. Each handler returns a metrics delta which the base
    class merges into the running totals seeded by ``get_metrics()``.
    """

    def get_metrics(self) -> dict[str, dict[str, int]]:
        # Initial counters. Any level we want to count must appear here so
        # the merged result includes a zero even when no matching lines
        # are seen this run.
        return {"level": {"error": 0, "warn": 0}}

    def process_level_error(self, message: str) -> dict[str, dict[str, int]]:
        # Called once per ERROR line. Returning a delta of 1 lets the
        # framework do the addition into the running ``level.error`` total.
        return {"level": {"error": 1}}

    def process_level_warn(self, message: str) -> dict[str, dict[str, int]]:
        return {"level": {"warn": 1}}


def main() -> None:
    # Three lines at three different levels. Only WARN and ERROR have
    # handlers above, so the INFO line is parsed but contributes nothing.
    sample = """\
2024-01-01 12:00:00,000 INFO hello
2024-01-01 12:00:01,000 WARN disk slow
2024-01-01 12:00:02,000 ERROR java.io.IOException: boom
"""

    # Use a temp directory so the demo leaves nothing behind. In a real
    # deployment ``log_path`` would be the live log and ``state_path``
    # would live somewhere durable so the next run can resume.
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        log_path = td_path / "demo.log"
        state_path = td_path / "demo-state.json"
        log_path.write_text(sample, encoding="utf-8")

        # ``max_duration`` is the SIGALRM budget for the whole pass.
        # Thirty seconds is overkill for three lines but illustrates the
        # constructor argument.
        proc = DemoErrorWarnCounter(max_duration=30)

        # The context manager loads any prior state, runs the body, then
        # writes the updated ``inode`` + ``seek`` back to ``state_path``.
        with RotatedLogFileSavedState(log_path, state_path) as state:
            metrics = proc.process(state)

    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
