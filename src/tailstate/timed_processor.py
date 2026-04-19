"""Timed iteration over :meth:`RotatedLogFileSavedState.logs` with SIGALRM bounds."""

import io
import logging
import signal
import threading
import time
from types import FrameType
from typing import TYPE_CHECKING, Any, TextIO

if TYPE_CHECKING:
    from .rotated import RotatedLogFileSavedState

default_log = logging.getLogger(__name__)


class _LogProcessTimeout(Exception):
    """Raised when a timeout happens."""


class TimedLogProcessor:
    """Run a per-file hook over streams from ``state.logs()`` under a SIGALRM
    budget (Unix).

    Only :exc:`OSError` and :exc:`UnicodeDecodeError` from the read path are
    caught; exceptions from :meth:`process_log` propagate. ``process`` must be
    called from the main thread of the main interpreter (``signal.signal``
    limitation).
    """

    def __init__(self, max_duration: float):
        self.max_duration = max_duration

    @staticmethod
    def _start_timeout(seconds: float) -> None:
        if hasattr(signal, "setitimer"):
            signal.setitimer(signal.ITIMER_REAL, seconds)
        else:
            signal.alarm(max(int(seconds), 1))

    @staticmethod
    def _clear_timeout() -> None:
        if hasattr(signal, "setitimer"):
            signal.setitimer(signal.ITIMER_REAL, 0.0)
        else:
            signal.alarm(0)

    def process(
        self,
        state: "RotatedLogFileSavedState",
        log: logging.Logger = default_log,
    ) -> Any:
        """Walk ``state.logs()``, calling :meth:`process_log` until time runs out.

        Remaining wall time is split across files via ``SIGALRM``. If
        :meth:`process_log` returns ``(_, True)``, later opened segments are
        skipped for processing (seek to EOF) but the generator still runs so
        rotation state can advance.
        """
        if threading.current_thread() is not threading.main_thread():
            raise RuntimeError(
                "TimedLogProcessor.process requires the main thread (SIGALRM)"
            )

        def _sigalrm_handler(signum: int, frame: FrameType | None) -> None:
            raise _LogProcessTimeout()

        value: Any = None
        elapsed_time: float = 0.0
        timeout = False
        skip_others = False

        previous_handler = signal.signal(signal.SIGALRM, _sigalrm_handler)
        try:
            for log_file in state.logs():
                if skip_others:
                    log_file.seek(0, io.SEEK_END)
                    continue
                if timeout:
                    break

                remaining = self.max_duration - elapsed_time
                if remaining <= 0:
                    timeout = True
                    log.warning("Log reading time budget exhausted before file")
                    log_file.seek(0, io.SEEK_END)
                    continue

                self._start_timeout(remaining)

                ret = None
                start_time = time.monotonic()
                try:
                    log.debug("Started processing of %s ...", log_file.name)
                    ret, _skip = self.process_log(log_file)
                    skip_others |= _skip
                except _LogProcessTimeout:
                    timeout = True
                    log.warning("Log reading timeout, stopping...")
                    continue
                except (OSError, UnicodeDecodeError):
                    log.exception("I/O or decoding error while processing log file")
                    break
                else:
                    log.debug("Processing done!")
                finally:
                    self._clear_timeout()
                    elapsed_time += time.monotonic() - start_time

                if ret is not None:
                    value = ret if value is None else self.combine_values(value, ret)
            else:
                if not timeout:
                    log.debug("Processed all logs!")
        finally:
            self._clear_timeout()
            signal.signal(signal.SIGALRM, previous_handler)

        return value

    def process_log(self, log_file: TextIO) -> tuple[Any, bool]:
        """Process one open log stream; return ``(value, skip_others)``."""
        raise NotImplementedError("Must implement process_log(log) --> value, boolean")

    def combine_values(self, old_val: Any, new_val: Any) -> Any:
        """Merge return values from :meth:`process_log` when both are non-``None``."""
        raise NotImplementedError("Must implement combine_value(old, new) --> Any")
