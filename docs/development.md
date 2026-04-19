# Development Notes

This file holds the bulkier project and contributor reference material so the
top-level README can stay short.

## Tooling

Development uses:

- `uv` for environment management
- `pytest` for tests
- `black` for formatting
- `ruff` for linting
- `mypy` for type checking
- `bin/pre-submit` for the full local verification pass

From the project root:

```bash
uv sync
make install-git-hook
uv run pytest
uv run black src tests
uv run ruff check src tests
uv run mypy src tests
./bin/pre-submit
```

Convenience targets:

- `make sync`
- `make install-git-hook`
- `make test`
- `make fmt`
- `make ruff`
- `make typecheck`
- `make lint`
- `make verify`

Optional coverage:

```bash
uv run pytest --cov=src/tailstate --cov-report=term-missing
```

## Tests

Typical flows:

- `uv run pytest`
- `make test`
- `python3 -m unittest discover -s tests -p 'test_*.py' -v`

`tests/conftest.py` prepends `src/` when pytest runs without an editable
install. After `uv sync` or `pip install -e .`, the package is also available
through the environment itself.

Without an editable install, set `PYTHONPATH=src` if you want imports to work
from the project root with plain `python` or `unittest`.

## Package Layout

- `src/tailstate/`: library source
- `src/tailstate/__init__.py`: public re-exports and `__all__`
- `src/tailstate/types.py`: `LogSavedState` and `PathLike`
- `src/tailstate/fs_utils.py`: `find_file_by_inode`, `ensure_dir`, `tmp_file`
- `src/tailstate/persistent.py`: `PersistentObj`, `JsonPersistentObj`
- `src/tailstate/rotated.py`: `RotatedLogFileSavedState`
- `src/tailstate/timed_processor.py`: `TimedLogProcessor`
- `src/tailstate/log4j_line_processor.py`: `Log4jLogLineProcessor`
- `src/tailstate/example_standalone.py`: runnable demo
- `tests/`: unit tests
- `bin/pre-submit`: black + mypy + pytest
- `bin/git-hooks/pre-commit`: source for the local git hook
- `uv.lock`: locked dev dependency versions

## Portability And Behavior Notes

- Python 3.11 or newer is required.
- `TimedLogProcessor` depends on `SIGALRM`, so timed processing is Unix-only.
- `tmp_file()` defaults temporary files to the destination directory so the
  final replace stays on the same filesystem and preserves atomic rename
  behavior. If you override `tmp_dir`, cross-filesystem moves may lose that
  property.
- Log input is read as UTF-8 text with replacement for decode errors.
- State is stored as JSON (UTF-8 text); safe to load from untrusted sources and
  stable across Python versions.

## Where To Look For Precise Semantics

The docstrings in these modules are the authoritative behavior reference:

- `src/tailstate/rotated.py`
- `src/tailstate/timed_processor.py`
- `src/tailstate/log4j_line_processor.py`
- `src/tailstate/persistent.py`
