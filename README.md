# `tailstate`

Rotation-aware incremental reading of rotated log files with persisted state.

The importable package is `tailstate`, with code under `src/tailstate/`. The
distribution name in `pyproject.toml` is `tailstate`.

It persists `inode + byte offset` as JSON so a later run can continue from the
last fully processed line, or follow rotation to unread files with the same
basename prefix.

- Python: 3.11+
- Runtime dependencies: standard library only
- State format: JSON (UTF-8 text), human-readable and stable across Python
  versions
- License: MIT (see [LICENSE](LICENSE))

## Docs

- `README.md`: overview, install, quickstart
- [docs/development.md](docs/development.md): dev
  commands, tests, layout, portability notes
- `AGENTS.md`: non-obvious traps for coding agents
- `src/tailstate/`: module and class docstrings define the precise behavior

## Main Pieces

- `RotatedLogFileSavedState`: discovers matching log files in one directory,
  ordered by mtime, and yields open text streams from `logs()`
- `LogSavedState`: typed persisted `inode` / `seek` state
- `TimedLogProcessor`: processes yielded files under a total `SIGALRM` budget
- `PersistentObj` and `JsonPersistentObj`: generic JSON-backed persistence
  helpers
- `Log4jLogLineProcessor`: timed processor for log4j-style `%d{ISO8601} %p %m%n`
  lines
- `ensure_dir`, `tmp_file`, `find_file_by_inode`: filesystem helpers

## Important Behavior

- Matching uses a plain filename prefix in the same directory. `app.log.1` and
  `app.log-extra` both match `app.log`.
- `logs()` yields streams from inside an open-file context. The file stays open
  until the caller resumes the generator.
- If byte offsets matter, use `readline()` or explicit `tell()` / `seek()`
  instead of `for line in f`.
- Log streams are opened as UTF-8 with `errors="replace"`.
- Timed processing uses `SIGALRM` on Unix. Timeouts can still affect rotation
  state and partial progress in subtle ways.

## Install

Using `uv` from the project root:

```bash
uv sync
uv run pytest
uv run mypy src tests
uv run black src tests
```

Without `uv`:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
pip install black mypy pytest pytest-cov
python -m pytest
```

## Demo

Primary walkthrough:

```bash
uv run python examples/rotation_walkthrough.py
```

This zero-argument demo shows:

- initial reading from offset 0
- append-only continuation using saved `inode` + `seek`
- incomplete trailing-line deferral with explicit `readline()` / `seek()`
- rotation-aware continuation from `app.log.1` into a fresh `app.log`

Optional higher-level example:

```bash
uv run python examples/log4j_metrics.py
```

## Quickstart

Incremental rotation-aware reading:

```python
from tailstate import RotatedLogFileSavedState

with RotatedLogFileSavedState("/var/log/app/app.log", "/var/run/app-state.json") as state:
    for log_file in state.logs():
        while True:
            line = log_file.readline()
            if not line:
                break
            ...
```

Timed multi-file processing:

```python
from tailstate import RotatedLogFileSavedState, TimedLogProcessor


class MyProc(TimedLogProcessor):
    def process_log(self, log_file):
        ...  # return (value, skip_others)

    def combine_values(self, old, new):
        ...


with RotatedLogFileSavedState(log_path, state_path) as state:
    result = MyProc(max_duration=60).process(state)
```

log4j-style line parsing:

```python
from tailstate import Log4jLogLineProcessor


class MyScrape(Log4jLogLineProcessor):
    def get_metrics(self):
        return {"level": {"error": 0}}

    def process_level_error(self, message):
        return {"level": {"error": 1}}
```

## License

MIT. See [LICENSE](LICENSE).
