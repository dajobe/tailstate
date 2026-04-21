#!/usr/bin/env python3
"""Saved offset, partial line and rotation demo

Demo to walk through tailstate's saved offsets, partial-line
deferral, and rotation features one by one.

Run from the project root with:

    uv run python examples/rotation_walkthrough.py

"""

from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from tailstate import RotatedLogFileSavedState


@dataclass
class PhaseResult:
    files_read: list[str]
    lines_consumed: list[str]
    state: dict[str, int]


def read_complete_lines(log_file: TextIO) -> list[str]:
    """Read only complete newline-terminated lines from ``log_file``.

    When the final line is incomplete, rewind to its starting offset so the
    saved seek position stays at the last fully processed line.

    The README spells out the rule this implements: "If byte offsets matter,
    use ``readline()`` or explicit ``tell()`` / ``seek()`` instead of
    ``for line in f``." Iterating with ``for line in f`` would buffer
    ahead and leave ``tell()`` pointing past data we haven't committed
    to having processed, so partial lines could be silently dropped on
    the next run. ``readline()`` plus ``tell()``/``seek()`` keeps the
    saved offset honest.
    """

    lines: list[str] = []
    while True:
        # Capture the offset *before* reading the line so we can rewind
        # to it if the line turns out to be incomplete.
        pos = log_file.tell()
        line = log_file.readline()
        if not line:
            # Empty string from ``readline`` means EOF, not a blank line
            # (a blank line would be ``"\n"``).
            break
        if not line.endswith("\n"):
            # Partial line: rewind so the next pass re-reads it from the
            # start, presumably after more bytes have been appended.
            log_file.seek(pos)
            break
        lines.append(line.rstrip("\n"))
    return lines


def run_pass(log_path: Path, state_path: Path) -> PhaseResult:
    """Process one pass over the matching log files and return a summary."""

    files_read: list[str] = []
    lines_consumed: list[str] = []

    # The context manager loads any prior state from ``state_path`` (or
    # starts empty), runs the body, then saves the updated ``inode`` +
    # ``seek`` on clean exit. ``state.logs()`` is a generator that opens
    # each matching file in mtime order, seeks to the saved offset on
    # the first one, and yields it for processing.
    with RotatedLogFileSavedState(log_path, state_path) as state:
        for log_file in state.logs():
            files_read.append(Path(log_file.name).name)
            lines_consumed.extend(read_complete_lines(log_file))

    # Re-read the saved JSON from disk so the transcript can show what
    # actually got persisted, not just what's in memory.
    saved = json.loads(state_path.read_text(encoding="utf-8"))
    return PhaseResult(
        files_read=files_read,
        lines_consumed=lines_consumed,
        state=saved,
    )


def format_phase(
    title: str,
    action: str,
    result: PhaseResult,
    note: str | None = None,
) -> str:
    """Render one phase of the walkthrough as readable text."""

    lines = [title, f"Action: {action}"]
    files = ", ".join(result.files_read) if result.files_read else "(none)"
    lines.append(f"Files read: {files}")
    if result.lines_consumed:
        lines.append("Lines consumed:")
        lines.extend(f"  - {line}" for line in result.lines_consumed)
    else:
        lines.append("Lines consumed: (none)")
    lines.append("Saved state:")
    lines.append(json.dumps(result.state, indent=2, sort_keys=True))
    if note:
        lines.append(f"Note: {note}")
    return "\n".join(lines)


def build_transcript() -> str:
    """Create the full multi-pass walkthrough transcript."""

    transcript: list[str] = ["tailstate rotation walkthrough"]
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        log_path = td_path / "app.log"
        rotated_path = td_path / "app.log.1"
        state_path = td_path / "app-state.json"

        # Phase 1: a fresh log with two complete lines and no prior
        # state file. ``run_pass`` should read both lines and persist
        # the inode plus the byte offset just past ``beta\n``.
        log_path.write_text("alpha\nbeta\n", encoding="utf-8")
        phase1 = run_pass(log_path, state_path)
        transcript.append(
            format_phase(
                "Phase 1: Initial read",
                "Seed app.log with two complete lines and process from offset 0.",
                phase1,
            )
        )

        # Phase 2: append one more complete line. The state file from
        # phase 1 is still there, so ``RotatedLogFileSavedState`` should
        # seek past ``alpha\nbeta\n`` and only emit ``gamma``.
        with log_path.open("a", encoding="utf-8", newline="") as log_file:
            log_file.write("gamma\n")
        phase2 = run_pass(log_path, state_path)
        transcript.append(
            format_phase(
                "Phase 2: Append-only continuation",
                (
                    "Append one newline-terminated line and rerun with the same "
                    "state file."
                ),
                phase2,
            )
        )

        # Phase 3: append a line *without* a trailing newline, simulating
        # a writer mid-flush. ``read_complete_lines`` rewinds past it so
        # the saved offset must stay equal to the phase-2 offset; the
        # partial bytes will be picked up on a later pass.
        with log_path.open("a", encoding="utf-8", newline="") as log_file:
            log_file.write("delta still buffering")
        phase3 = run_pass(log_path, state_path)
        transcript.append(
            format_phase(
                "Phase 3: Partial line deferral",
                "Append an incomplete final line with no trailing newline.",
                phase3,
                note=(
                    "The incomplete line is deferred because the reader rewinds before "
                    "saving state."
                ),
            )
        )

        # Phase 4: simulate a logrotate-style rotation.
        #   1. Move ``app.log`` aside to ``app.log.1`` (same inode).
        #   2. Finish the deferred line by appending ``" now complete\n"``
        #      to the rotated file.
        #   3. Sleep briefly so the new ``app.log`` we're about to create
        #      has a strictly later mtime than ``app.log.1``.
        #      ``RotatedLogFileSavedState.logs()`` orders matches by mtime
        #      with the saved-inode file first; without the sleep the two
        #      files can share an mtime and ordering becomes filesystem-
        #      dependent. A small real delay is the simplest fix in a demo.
        #   4. Create a brand new ``app.log`` with one fresh line.
        # The expected outcome: this pass opens ``app.log.1`` first
        # (because the saved inode still lives there), reads
        # ``"delta still buffering now complete"`` from where phase 3
        # rewound to, then opens the new ``app.log`` and reads
        # ``"epsilon after rotate"``. The persisted state ends up
        # pointing at the new file's inode and offset.
        os.rename(log_path, rotated_path)
        with rotated_path.open("a", encoding="utf-8", newline="") as log_file:
            log_file.write(" now complete\n")
        time.sleep(0.01)
        log_path.write_text("epsilon after rotate\n", encoding="utf-8")
        phase4 = run_pass(log_path, state_path)
        transcript.append(
            format_phase(
                "Phase 4: Rotation-aware continuation",
                (
                    "Rotate app.log to app.log.1, finish the deferred line, then "
                    "create a new app.log."
                ),
                phase4,
                note=(
                    "This pass resumes from the saved offset in app.log.1 before "
                    "moving on to the fresh app.log."
                ),
            )
        )

        same_seek = phase2.state["seek"] == phase3.state["seek"]
        transcript.append("Summary")
        transcript.append("- Initial data was read from offset 0.")
        transcript.append("- The second pass consumed only appended bytes.")
        transcript.append(
            f"- The saved seek stayed pinned before the partial line: {same_seek}."
        )
        transcript.append(
            "- After rotation, the reader finished unread data from app.log.1 and "
            "then continued into the new app.log."
        )

    return "\n\n".join(transcript)


def main() -> None:
    print(build_transcript())


if __name__ == "__main__":
    main()
