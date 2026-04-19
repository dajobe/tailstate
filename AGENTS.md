# Guidance for coding agents

Behavioral traps that are easy to get wrong when editing this codebase. Commands
and layout are in **`README.md`**; precise behavior is defined in **source
docstrings** under **`src/tailstate/`**.

## Log segments are streamed from inside an open-file context

Each segment is produced from within a **`with … open`** block and **yielded**
to the caller. The descriptor stays valid until the consumer **resumes** the
generator after handling that segment. Refactors that read files eagerly, close
early, or stop using a generator usually break byte offset and inode
bookkeeping.

## Time limits vs partial progress

When wall-clock limits fire during multi-file processing, later segments may no
longer run user-supplied per-file logic, but iteration and generator teardown
can still interact with rotation state in non-obvious ways. Do not assume a
timeout leaves persisted offsets unchanged or that every segment was handled
uniformly.

## Which errors are absorbed during timed processing

Low-level read/decode failures on the log stream are caught and stop the loop.
Failures raised from application code inside the per-file hook are **not**
converted into friendly messages—they propagate. Deliberate separation between
transport errors and caller/subclass logic.

## How “matching” log filenames work

Discovery uses a **string prefix** on the base name, not a dedicated
rotation-scheme parser. Small changes to naming or filtering have surprising
inclusion/exclusion effects.
