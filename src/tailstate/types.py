"""Typed structures for persisted and in-memory state."""

import os
from typing import TypedDict

PathLike = str | os.PathLike[str]


class LogSavedState(TypedDict):
    """JSON-backed offset state for :class:`~tailstate.RotatedLogFileSavedState`.

    ``inode`` identifies the last file segment processed; ``seek`` is the byte
    offset for the next read in that segment's continuation (first segment only
    uses the saved seek when multiple files are queued).
    """

    inode: int
    seek: int
