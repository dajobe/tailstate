# TODO

Deferred items from the code review. None are required for current behavior;
each is a design or scope decision left open.

## Windows / non-POSIX portability

`src/tailstate/timed_processor.py` references `signal.SIGALRM` at module import
time, and `__init__.py` imports `TimedLogProcessor` eagerly. On Windows,
`signal.SIGALRM` does not exist, so `import tailstate` raises `AttributeError` —
which also takes out the pure-POSIX-agnostic helpers (`fs_utils`, `persistent`)
for Windows consumers.

Not fixing: project is POSIX-only by intent. Options if this ever needs to
change:

- Lazy-import `signal.SIGALRM` inside `TimedLogProcessor.process` and raise a
  clear `RuntimeError("TimedLogProcessor requires POSIX SIGALRM")` there.
- Guard the `__init__.py` re-export of `TimedLogProcessor` behind
  `hasattr(signal, "SIGALRM")` so `fs_utils` / `persistent` stay importable.
- Document "POSIX only" in `README.md`.

## `TimedLogProcessor` typing: `Any` → `Generic[T]`

`process`, `process_log`, and `combine_values` all use `Any` for the per-file
return value. Making the class `Generic[T]` with `process_log (...) -> tuple[T,
bool]` and `combine_values(T, T) -> T` would give subclasses real type checking.
`Log4jLogLineProcessor` would become `TimedLogProcessor[dict[Any, Any]]`.

Not trivial: involves the public subclass API, and `Log4jLogLineProcessor`'s own
inner dict shape is already `dict[Any, Any]` so the benefit at that layer is
modest. Worth doing if/when a second concrete subclass is written.
