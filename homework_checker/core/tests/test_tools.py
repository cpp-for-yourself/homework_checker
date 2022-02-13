#!/usr/bin/python3
"""Test the tools."""
from __future__ import annotations

import unittest

from time import monotonic as timer
from pathlib import Path
from homework_checker.core import tools
from homework_checker.core.schema_tags import OutputTags


class TestTools(unittest.TestCase):
    """Test the checker."""

    def test_pkg_name(self: TestTools):
        """Pkg name test."""
        self.assertEqual(tools.PKG_NAME, "homework_checker")
        if tools.PROJECT_ROOT_FOLDER.exists():
            self.assertEqual(tools.PROJECT_ROOT_FOLDER.name, "homework_checker")

    def test_temp_directory_copy(self: TestTools):
        """Test that we can create and remove a temp folder."""
        folder_name = tools.PROJECT_ROOT_FOLDER
        old_temp_folder = None

        with tools.TempDirCopy(source_folder=folder_name) as tempdir:
            self.assertIn(tools.get_unique_str(str(folder_name)), str(tempdir))
            self.assertTrue(tempdir.exists())
            self.assertTrue((tempdir / tools.PKG_NAME / "core" / "tests").exists())
            with self.assertRaises(Exception):
                with tools.TempDirCopy(folder_name):
                    pass
            old_temp_folder = tempdir
        self.assertFalse(old_temp_folder.exists())

        prefix = "blah"
        with tools.TempDirCopy(source_folder=folder_name, prefix=prefix) as tempdir:
            self.assertIn(prefix, str(tempdir))

    def test_convert_to(self: TestTools):
        """Test conversion to expected type."""
        output, error = tools.convert_to(OutputTags.NUMBER, "value")
        self.assertEqual(output, None)
        self.assertEqual(error, "could not convert string to float: 'value'")

        output, error = tools.convert_to(OutputTags.STRING, 3.14)
        self.assertEqual(output, "3.14")
        self.assertEqual(error, "OK")

        output, error = tools.convert_to(OutputTags.NUMBER, "3.14")
        self.assertEqual(output, 3.14)
        self.assertEqual(error, "OK")

    def test_max_date(self: TestTools):
        """Make sure we can rely on max date."""
        self.assertEqual(tools.MAX_DATE_STR, "9999-12-31 23:59:59")

    def test_sleep_timeout(self: TestTools):
        """Test that we can break an endless loop."""
        start = timer()
        timout = 1
        cmd_result = tools.run_command("sleep 10", timeout=timout)
        self.assertFalse(cmd_result.succeeded())
        self.assertLess(timer() - start, 5)
        self.assertEqual(
            cmd_result.stderr,
            "Timeout: command 'sleep 10' ran longer than {} seconds".format(timout),
        )

    def test_git_url(self: TestTools):
        """Test that we can break an endless loop."""
        domain, user, project = tools.parse_git_url(
            "https://gitlab.ipb.uni-bonn.de/igor/some_project.git"
        )
        self.assertEqual(domain, "gitlab.ipb.uni-bonn.de")
        self.assertEqual(user, "igor")
        self.assertEqual(project, "some_project")
        domain, user, project = tools.parse_git_url(
            "git@gitlab.ipb.uni-bonn.de:igor/some_project.git"
        )
        self.assertEqual(domain, "gitlab.ipb.uni-bonn.de")
        self.assertEqual(user, "igor")
        self.assertEqual(project, "some_project")
        domain, user, project = tools.parse_git_url(
            "git@github.com:PRBonn/depth_clustering.git"
        )
        self.assertEqual(domain, "github.com")
        self.assertEqual(user, "PRBonn")
        self.assertEqual(project, "depth_clustering")

    def test_endless_loop_timeout(self: TestTools):
        """Test that we can break an endless loop."""
        path_to_file = Path(__file__).parent / "data" / "endless.cpp"
        cmd_build = "c++ -o endless -O0 {path}".format(path=str(path_to_file))
        timeout = 1.0
        cmd_result = tools.run_command(cmd_build, timeout=timeout)
        self.assertTrue(cmd_result.succeeded())
        start = timer()
        cmd_result = tools.run_command("./endless", timeout=timeout)
        self.assertFalse(cmd_result.succeeded())
        self.assertLess(timer() - start, 5)
        self.assertEqual(
            cmd_result.stderr,
            "Timeout: command './endless' ran longer than {} seconds".format(timeout),
        )
