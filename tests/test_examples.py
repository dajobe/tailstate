"""Tests for runnable example scripts."""

from __future__ import annotations

import contextlib
import io
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_script(path: str) -> dict[str, object]:
    return runpy.run_path(str(ROOT / path))


def test_rotation_walkthrough_transcript_covers_core_behaviors():
    ns = _load_script("examples/rotation_walkthrough.py")

    build_transcript = ns["build_transcript"]
    assert callable(build_transcript)

    transcript = build_transcript()

    assert "Phase 1: Initial read" in transcript
    assert "Phase 2: Append-only continuation" in transcript
    assert "Phase 3: Partial line deferral" in transcript
    assert "Phase 4: Rotation-aware continuation" in transcript
    assert "Files read: app.log" in transcript
    assert "Files read: app.log.1, app.log" in transcript
    assert "  - alpha" in transcript
    assert "  - gamma" in transcript
    assert "Lines consumed: (none)" in transcript
    assert "delta still buffering now complete" in transcript
    assert "epsilon after rotate" in transcript
    assert '"inode":' in transcript
    assert '"seek":' in transcript
    assert "The saved seek stayed pinned before the partial line: True." in transcript


def test_log4j_metrics_example_prints_expected_json():
    ns = _load_script("examples/log4j_metrics.py")

    main = ns["main"]
    assert callable(main)

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        main()

    output = buf.getvalue()
    assert '"error": 1' in output
    assert '"warn": 1' in output
