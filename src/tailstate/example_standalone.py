#!/usr/bin/env python3
"""Minimal end-to-end demo: a tempfile log, JSON state, and counters.

Run from the project root after ``pip install -e .``::

    python -m tailstate.example_standalone
"""

import json
import logging
import tempfile
from pathlib import Path
from typing import Any

from tailstate import Log4jLogLineProcessor, RotatedLogFileSavedState


class DemoErrorWarnCounter(Log4jLogLineProcessor):
    """Counts ERROR and WARN lines in the log4j PatternLayout format."""

    def get_metrics(self) -> dict[str, dict[str, int]]:
        return {"level": {"error": 0, "warn": 0}}

    def process_level_error(self, message: str) -> dict[str, dict[str, int]]:
        return {"level": {"error": 1}}

    def process_level_warn(self, message: str) -> dict[str, dict[str, int]]:
        return {"level": {"warn": 1}}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    log = logging.getLogger("demo")

    sample = """\
2024-01-01 12:00:00,000 INFO hello
2024-01-01 12:00:01,000 WARN disk slow
2024-01-01 12:00:02,000 ERROR java.io.IOException: boom
"""

    metrics: Any = None
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        log_path = td_path / "demo.log"
        state_path = td_path / "demo-state.json"
        log_path.write_text(sample, encoding="utf-8")

        proc = DemoErrorWarnCounter(max_duration=30)
        with RotatedLogFileSavedState(log_path, state_path) as state:
            metrics = proc.process(state, log)

    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
