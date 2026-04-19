"""Rotation-aware saved read offset for log files sharing a basename prefix."""

import logging
import os
from collections.abc import Iterator
from pathlib import Path
from typing import NamedTuple, Self, TextIO

from .fs_utils import find_file_by_inode
from .persistent import JsonPersistentObj
from .types import LogSavedState, PathLike

_logger = logging.getLogger(__name__)

_LOG_ENCODING = "utf-8"
_LOG_ERRORS = "replace"


class _Segment(NamedTuple):
    path: Path
    seek: int


class RotatedLogFileSavedState(JsonPersistentObj[LogSavedState]):
    """Persist inode + seek across runs; yield open text streams from :meth:`logs`.

    Discovery: consider files in ``log_path.parent`` whose filename begins with
    ``log_path.name`` (plain string prefix). Order by ``st_mtime`` ascending.
    On the first run (saved ``inode == -1``) the stored inode is anchored to
    the newest file. If the saved inode matches no oldest file and the inode
    is not found in the directory, ``seek`` resets to 0.
    """

    def __init__(
        self,
        log_path: PathLike,
        state_path: PathLike,
        log: logging.Logger | None = None,
    ):
        super().__init__(state_path, log)
        self._log_path = Path(log_path)
        self._segments: list[_Segment] = []

    def default_object(self) -> LogSavedState:
        return {"inode": -1, "seek": 0}

    def __enter__(self) -> Self:
        super().__enter__()
        if self.obj is None:
            self.obj = self.default_object()
        self._segments = self._discover_segments(self.obj)
        return self

    def _discover_segments(self, state: LogSavedState) -> list[_Segment]:
        lp = self._log_path
        logs_dir = lp.parent
        name = lp.name

        try:
            with_stat = [
                (p, p.stat()) for p in logs_dir.iterdir() if p.name.startswith(name)
            ]
        except OSError as e:
            self._log.error("Cannot list log directory %s: %s", logs_dir, e)
            return []

        if not with_stat:
            self._log.error("There is no log file at %s", lp)
            return []

        with_stat.sort(key=lambda ps: ps[1].st_mtime)
        oldest_path, oldest_stat = with_stat[0]
        newest_path, newest_stat = with_stat[-1]
        anchor_mtime = oldest_stat.st_mtime

        if state["inode"] < 0:
            state["inode"] = newest_stat.st_ino

        if state["inode"] != oldest_stat.st_ino:
            old_file = find_file_by_inode(state["inode"], directory=logs_dir)
            if old_file is not None:
                anchor_mtime = old_file.stat().st_mtime
            else:
                state["seek"] = 0

        included = [p for (p, st) in with_stat if st.st_mtime >= anchor_mtime]
        if not included:
            return []
        segments = [_Segment(p, 0) for p in included]
        segments[0] = _Segment(segments[0].path, state["seek"])
        return segments

    def logs(self) -> Iterator[TextIO]:
        """Yield each log segment as a text stream.

        Each segment is produced inside a ``with path.open(...)`` block so the
        file stays open until the caller resumes the generator. After each
        segment, the persisted state is updated with that file's inode and
        ``tell()``.
        """
        state = self.obj
        if state is None:
            raise RuntimeError(
                "RotatedLogFileSavedState.logs() called outside its context manager"
            )
        for segment in self._segments:
            with segment.path.open(
                encoding=_LOG_ENCODING,
                errors=_LOG_ERRORS,
                newline="",
            ) as log_file:
                log_file.seek(segment.seek)
                yield log_file
                state["inode"] = os.fstat(log_file.fileno()).st_ino
                state["seek"] = log_file.tell()
