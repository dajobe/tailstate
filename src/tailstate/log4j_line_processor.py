"""log4j PatternLayout line parsing: timestamp, level, message, with timed
rotation support.

Subclass :class:`Log4jLogLineProcessor`, implement :meth:`get_metrics`, optionally
``process_level_<level>`` and :meth:`process_non_log`. Combine with
:class:`~tailstate.RotatedLogFileSavedState` and call
:meth:`~tailstate.TimedLogProcessor.process`.
"""

import copy
import re
from collections.abc import Callable
from typing import Any, TextIO

from .timed_processor import TimedLogProcessor


def _recursive_sum(dict1: dict[Any, Any], dict2: dict[Any, Any]) -> None:
    """Sum leaf values from ``dict2`` into ``dict1`` in place.

    Missing nested dicts in ``dict1`` are deep-copied from ``dict2`` so later
    mutations of either side don't alias. Both dicts must agree on shape: a
    leaf in one where the other has a nested dict will raise ``TypeError`` at
    ``+=`` time, since the merge does not attempt structural reconciliation.
    """
    for k, v in dict2.items():
        if isinstance(v, dict):
            if k not in dict1:
                dict1[k] = copy.deepcopy(v)
                continue
            _recursive_sum(dict1[k], v)
        else:
            dict1[k] += v


class Log4jLogLineProcessor(TimedLogProcessor):
    """Line-oriented parser for log4j PatternLayout ``%d{ISO8601} %p %m%n`` output.

    Matches lines shaped like::

        YYYY-mm-dd HH:MM:SS,mmm LEVEL message...

    with ``LEVEL`` one of ``TRACE|DEBUG|INFO|WARN|ERROR|FATAL``. Metrics are
    nested dicts of numeric counters; use :meth:`get_metrics` for defaults and
    define ``process_level_<level_lower>`` callbacks (e.g. ``process_level_error``)
    returning partial metric dicts or ``None``. Non-matching lines go to
    :meth:`process_non_log`.
    """

    LOG_TIME_PATTERN = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}"
    LOG_LEVEL_PATTERN = r"DEBUG|INFO|TRACE|WARN|ERROR|FATAL"
    _LOG_LINE_RE = re.compile(
        rf"(?P<time>{LOG_TIME_PATTERN}) (?P<level>{LOG_LEVEL_PATTERN}) (?P<message>.+)$"
    )

    def process_log(self, log_file: TextIO) -> tuple[dict[Any, Any], bool]:
        """Parse full lines; accumulate metrics via :meth:`get_metrics` and level
        callbacks.

        A partial line without trailing newline rewinds via ``seek`` so the byte
        offset does not advance past incomplete data.
        """
        metrics = self.get_metrics()

        while True:
            pos = log_file.tell()
            line = log_file.readline()
            if not line:
                break
            if line[-1] != "\n":
                log_file.seek(pos)
                break
            line = line.strip()
            if not line:
                continue

            new_metrics: dict[Any, Any] | None = None
            m = self._LOG_LINE_RE.match(line)
            if m is not None:
                handler = self._level_handler(m.group("level"))
                if handler is not None:
                    new_metrics = handler(m.group("message"))
            else:
                new_metrics = self.process_non_log(line)

            if new_metrics is not None:
                _recursive_sum(metrics, new_metrics)

        return metrics, False

    def _level_handler(
        self, level: str
    ) -> Callable[[str], dict[Any, Any] | None] | None:
        handler = getattr(self, f"process_level_{level.lower()}", None)
        return handler if callable(handler) else None

    def get_metrics(self) -> dict[Any, Any]:
        raise NotImplementedError("Must implement get_metrics() --> dict")

    def process_non_log(self, line: str) -> dict[Any, Any] | None:
        return None

    def combine_values(
        self, old_val: dict[Any, Any], new_val: dict[Any, Any]
    ) -> dict[Any, Any]:
        _recursive_sum(old_val, new_val)
        return old_val
