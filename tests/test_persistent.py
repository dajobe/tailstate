"""Tests for tailstate.persistent."""

import tempfile
import unittest
from pathlib import Path

from tailstate.persistent import JsonPersistentObj


class _DictStore(JsonPersistentObj[dict[str, int]]):
    def default_object(self) -> dict[str, int]:
        return {}


class TestJsonPersistentObj(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "state.json"
            with _DictStore(path) as po:
                po.obj = {"k": 1}
            with _DictStore(path) as po2:
                self.assertEqual(po2.obj, {"k": 1})

    def test_on_disk_is_readable_json(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "state.json"
            with _DictStore(path) as po:
                po.obj = {"k": 1}
            self.assertEqual(path.read_text(encoding="utf-8"), '{"k": 1}')

    def test_corrupt_json_falls_back_to_default(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "state.json"
            path.write_bytes(b"not a valid json stream")
            with _DictStore(path) as po:
                self.assertEqual(po.obj, {})

    def test_exception_in_body_skips_save(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "state.json"
            with _DictStore(path) as po:
                po.obj = {"k": 1}

            with self.assertRaises(RuntimeError), _DictStore(path) as po:
                po.obj = {"k": 999}
                raise RuntimeError("abort")

            with _DictStore(path) as po:
                self.assertEqual(po.obj, {"k": 1})

    def test_base_default_object_must_be_overridden(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "state.json"
            with (
                self.assertRaises(NotImplementedError),
                JsonPersistentObj[dict[str, int]](path),
            ):
                pass

    def test_timestamp_is_negative_when_file_not_on_disk(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "state.json"
            with _DictStore(path) as po:
                self.assertEqual(po.timestamp, -1.0)

    def test_timestamp_matches_saved_file_mtime(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "state.json"
            with _DictStore(path) as po:
                po.obj = {"k": 1}
            with _DictStore(path) as po2:
                self.assertGreater(po2.timestamp, 0.0)
                self.assertEqual(po2.timestamp, path.stat().st_mtime)
