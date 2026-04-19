"""JSON-backed persistent objects with context-manager load/save."""

import json
import logging
from pathlib import Path
from types import TracebackType
from typing import IO, Generic, Self, TypeVar, cast

from .fs_utils import ensure_dir, tmp_file
from .types import PathLike

_logger = logging.getLogger(__name__)
_T = TypeVar("_T")


class PersistentObj(Generic[_T]):
    """Load/save a Python object via a subclass-defined serialization.

    ``file_path`` is stored as a :class:`~pathlib.Path`. On enter, :meth:`_load`
    reads the file or uses :meth:`default_object`. Load failures that are
    ``OSError``, :exc:`ValueError`, or ``EOFError`` are logged and the default
    object is kept; other exceptions propagate. On exit without exception,
    :meth:`_save` writes atomically via :func:`~tailstate.fs_utils.tmp_file`.
    """

    obj: _T | None

    def __init__(self, file_path: PathLike, log: logging.Logger | None = None):
        self._file_path = Path(file_path)
        ensure_dir(self._file_path.parent)
        self._log = _logger if log is None else log
        self.obj = None

    def default_object(self) -> _T:
        """Return the initial value used when no saved file exists or load fails.

        Subclasses must override; the base class does not assume a shape for ``_T``.
        """
        raise NotImplementedError

    def load_from_file(self, f: IO[str]) -> _T:
        raise NotImplementedError

    def save_to_file(self, f: IO[str], obj: _T) -> None:
        raise NotImplementedError

    @property
    def timestamp(self) -> float:
        if self._file_path.is_file():
            return self._file_path.stat().st_mtime
        return -1.0

    def _load(self) -> _T:
        obj = self.default_object()
        if self._file_path.is_file():
            self._log.debug("Found saved object, reading...")
            try:
                with self._file_path.open("r", encoding="utf-8") as f:
                    obj = self.load_from_file(f)
            except (OSError, ValueError, EOFError) as e:
                self._log.warning("Exception while reading object from file: %s", e)
            self._log.debug("Saved object: %s", obj)
        else:
            self._log.debug("Saved object not found")
        return obj

    def _save(self) -> None:
        if self.obj is None:
            return
        with tmp_file(self._file_path, binary=False, log=self._log) as f:
            self.save_to_file(f, self.obj)
            self._log.debug("Saved current object %s to file", self.obj)

    def __enter__(self) -> Self:
        self.obj = self._load()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            self._log.warning("Exception occurred, will not save object")
        else:
            self._save()
        self.obj = None


class JsonPersistentObj(PersistentObj[_T], Generic[_T]):
    """Save object as a JSON (UTF-8 text) file.

    Only JSON-serializable payloads are supported. The on-disk format is
    human-readable and stable across Python versions.
    """

    def load_from_file(self, f: IO[str]) -> _T:
        return cast(_T, json.load(f))

    def save_to_file(self, f: IO[str], obj: _T) -> None:
        json.dump(obj, f)
