"""Incremental reads of rotated logs (saved inode + seek), timed multi-file
processing, and optional log4j-style log line parsing.

User overview: project ``README.md``. API details: module and class docstrings
in this package.
"""

__version__ = "0.2.0"

from .fs_utils import ensure_dir, find_file_by_inode, tmp_file
from .log4j_line_processor import Log4jLogLineProcessor
from .persistent import JsonPersistentObj, PersistentObj
from .rotated import RotatedLogFileSavedState
from .timed_processor import TimedLogProcessor
from .types import LogSavedState, PathLike

__all__ = [
    "JsonPersistentObj",
    "LogSavedState",
    "Log4jLogLineProcessor",
    "PathLike",
    "PersistentObj",
    "RotatedLogFileSavedState",
    "TimedLogProcessor",
    "ensure_dir",
    "find_file_by_inode",
    "tmp_file",
]
