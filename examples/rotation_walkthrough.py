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
    """

    lines: list[str] = []
    while True:
        pos = log_file.tell()
        line = log_file.readline()
        if not line:
            break
        if not line.endswith("\n"):
            log_file.seek(pos)
            break
        lines.append(line.rstrip("\n"))
    return lines


def run_pass(log_path: Path, state_path: Path) -> PhaseResult:
    """Process one pass over the matching log files and return a summary."""

    files_read: list[str] = []
    lines_consumed: list[str] = []

    with RotatedLogFileSavedState(log_path, state_path) as state:
        for log_file in state.logs():
            files_read.append(Path(log_file.name).name)
            lines_consumed.extend(read_complete_lines(log_file))

    state = json.loads(state_path.read_text(encoding="utf-8"))
    return PhaseResult(
        files_read=files_read,
        lines_consumed=lines_consumed,
        state=state,
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

        log_path.write_text("alpha\nbeta\n", encoding="utf-8")
        phase1 = run_pass(log_path, state_path)
        transcript.append(
            format_phase(
                "Phase 1: Initial read",
                "Seed app.log with two complete lines and process from offset 0.",
                phase1,
            )
        )

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
