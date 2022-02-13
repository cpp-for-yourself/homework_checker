#!/usr/bin/python3
"""Test the checker."""
from __future__ import annotations

import unittest

from pathlib import Path
from typing import Dict

from homework_checker.core.checker import Checker
from homework_checker.core.md_writer import MdWriter
from homework_checker.core import tools


class TestChecker(unittest.TestCase):
    """Test the checker."""

    @staticmethod
    def __sanitize_results(results: Dict[str, Dict[str, tools.CmdResult]]):
        sanitized_results = {}
        for key, value in results.items():
            sanitized_value = {}
            for inner_key, inner_value in value.items():
                sanitized_value[tools.remove_number_from_name(inner_key)] = inner_value
            sanitized_results[tools.remove_number_from_name(key)] = sanitized_value
        return sanitized_results

    def test_everything(self: TestChecker):
        """Check all homeworks and Tasks."""
        path_to_job = (
            tools.PROJECT_ROOT_FOLDER
            / "homework_checker"
            / "core"
            / "tests"
            / "data"
            / "homework"
            / "example_job.yml"
        )
        checker = Checker(path_to_job)
        results = checker.check_all_homeworks()
        results = TestChecker.__sanitize_results(results)
        self.assertEqual(len(results), 3)
        self.assertNotIn("Non existing homework", results)

        self.assertIn("Homework where things go wrong", results)
        self.assertIn(tools.EXPIRED_TAG, results["Homework where things go wrong"])

        self.assertEqual(
            len(results["Homework where things go wrong"]),
            3,
            "Wrong results: {}".format(results["Homework where things go wrong"]),
        )
        self.assertIn("Return number task", results["Homework where things go wrong"])
        self.assertIn("While loop task", results["Homework where things go wrong"])
        self.assertNotIn("Non existing task", results["Homework where things go wrong"])

        writer = MdWriter()
        writer.update(results)
        writer.write_md_file(Path("results.md"))
