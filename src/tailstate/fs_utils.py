"""Filesystem helpers: inode lookup, directory creation, atomic file replace."""

import contextlib
import logging
import os
import shutil
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import IO, Literal, overload

from .types import PathLike

_logger = logging.getLogger(__name__)


def find_file_by_inode(inode: int, directory: PathLike) -> Path | None:
    """Return the path in ``directory`` whose inode matches, or ``None``.

    Non-recursive. ``OSError`` from ``stat`` on an entry is ignored (race with
    directory changes).
    """
    try:
        scanner = os.scandir(directory)
    except OSError:
        return None
    with scanner as entries:
        for entry in entries:
            try:
                if entry.inode() == inode:
                    return Path(entry.path)
            except OSError:
                continue
    return None


def ensure_dir(dir_path: PathLike | None) -> None:
    """Create ``dir_path`` and parents if missing; no-op for ``None`` or ``""``."""
    if dir_path is None or dir_path == "":
        return
    Path(dir_path).mkdir(parents=True, exist_ok=True)


@overload
def tmp_file(
    destination: PathLike,
    binary: Literal[True] = ...,
    log: logging.Logger | None = ...,
    tmp_dir: PathLike | None = ...,
) -> "contextlib._GeneratorContextManager[IO[bytes]]": ...


@overload
def tmp_file(
    destination: PathLike,
    binary: Literal[False],
    log: logging.Logger | None = ...,
    tmp_dir: PathLike | None = ...,
) -> "contextlib._GeneratorContextManager[IO[str]]": ...


@contextlib.contextmanager
def tmp_file(
    destination: PathLike,
    binary: bool = True,
    log: logging.Logger | None = None,
    tmp_dir: PathLike | None = None,
) -> Iterator[IO[bytes]] | Iterator[IO[str]]:
    """Write to a temporary path, then atomically replace ``destination`` on success.

    Uses :func:`tempfile.mkstemp` and wraps the returned file descriptor with
    :func:`os.fdopen` so the tmp path is never reopened by name. Temporary files
    default to the destination directory so the final :func:`shutil.move` stays
    on the same filesystem and keeps its atomic rename behavior.

    Text mode writes UTF-8 with ``newline=""``. Any exception raised inside the
    ``with`` body (or during the final move) removes the temporary file and
    leaves the destination untouched; the exception then propagates.
    """
    active_log = _logger if log is None else log
    dest = Path(destination)
    tmp_base = dest.parent if tmp_dir is None else Path(tmp_dir)
    fd, tmp_path = tempfile.mkstemp(dir=os.fspath(tmp_base))

    try:
        if binary:
            with os.fdopen(fd, "wb") as bf:
                yield bf
        else:
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as tf:
                yield tf
        shutil.move(tmp_path, dest)
    except BaseException as exc:
        active_log.warning("tmp_file write/move failed, cleaning up: %s", exc)
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise
