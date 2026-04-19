"""Tests for tailstate.__init__ (public package API)."""

import unittest

import tailstate as rls


class TestPackageInit(unittest.TestCase):
    def test_all_names_importable(self):
        for name in rls.__all__:
            obj = getattr(rls, name)
            self.assertIsNotNone(obj, name)

    def test_all_is_complete(self):
        expected = {
            "JsonPersistentObj",
            "LogSavedState",
            "Log4jLogLineProcessor",
            "PathLike",
            "PersistentObj",
            "RotatedLogFileSavedState",
            "TimedLogProcessor",
            "ensure_dir",
            "find_file_by_inode",
            "tmp_file",
        }
        self.assertEqual(set(rls.__all__), expected)

    def test_reexports_match_source_modules(self):
        from tailstate import fs_utils, persistent, rotated

        self.assertIs(rls.RotatedLogFileSavedState, rotated.RotatedLogFileSavedState)
        self.assertIs(rls.JsonPersistentObj, persistent.JsonPersistentObj)
        self.assertIs(rls.tmp_file, fs_utils.tmp_file)
