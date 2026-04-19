"""Tests for tailstate.fs_utils."""

import os
import tempfile
import unittest
from pathlib import Path

from tailstate.fs_utils import ensure_dir, find_file_by_inode, tmp_file


class TestTmpFile(unittest.TestCase):
    def test_writes_destination_atomically(self):
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td) / "out.txt"
            with tmp_file(dest, binary=False) as f:
                f.write("payload")
            self.assertEqual(dest.read_text(encoding="utf-8"), "payload")

    def test_exception_inside_body_cleans_up_and_leaves_dest(self):
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td) / "out.txt"
            dest.write_text("original", encoding="utf-8")

            tmp_dir = Path(td) / "tmp"
            tmp_dir.mkdir()

            with (
                self.assertRaises(ValueError),
                tmp_file(dest, binary=False, tmp_dir=tmp_dir) as f,
            ):
                f.write("partial")
                raise ValueError("boom")

            self.assertEqual(dest.read_text(encoding="utf-8"), "original")
            self.assertEqual(list(tmp_dir.iterdir()), [])


class TestFindFileByInode(unittest.TestCase):
    def test_matches_inode(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "a.txt"
            path.write_text("x", encoding="utf-8")
            inode = os.stat(path).st_ino
            self.assertEqual(find_file_by_inode(inode, td), path)

    def test_missing_returns_none(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertIsNone(find_file_by_inode(9_999_999_999, td))

    def test_missing_directory_returns_none(self):
        self.assertIsNone(find_file_by_inode(1, "/nonexistent/path/xyzzy"))


class TestEnsureDir(unittest.TestCase):
    def test_nested(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td) / "x" / "y"
            ensure_dir(d)
            self.assertTrue(d.is_dir())

    def test_empty_path_no_op(self):
        ensure_dir("")
