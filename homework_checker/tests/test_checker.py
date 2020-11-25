#!/usr/bin/python3
"""Test the checker."""
from __future__ import annotations

import unittest

from homework_checker.checker import Checker
from homework_checker import tools
from homework_checker import tasks


class TestChecker(unittest.TestCase):
    """Test the checker."""

    def test_everything(self: TestChecker):
        """Check all homeworks and Tasks."""
        path_to_job = (
            tools.PROJECT_ROOT_FOLDER
            / "homework_checker"
            / "tests"
            / "data"
            / "homework"
            / "example_job.yml"
        )
        checker = Checker(path_to_job)
        results = checker.check_all_homeworks()
        self.assertEqual(len(results), 3)
        self.assertEqual(len(results["Homework 1"]), 4)
        self.assertEqual(len(results["Homework 1"]["Task 1"]), 3)
        self.assertEqual(len(results["Homework 2"]), 4)
        self.assertEqual(results["Homework 1"]["Task 1"]["Test 1"].stderr, "")
        self.assertTrue(results["Homework 1"]["Task 1"]["Test 1"].succeeded())
        self.assertTrue(results["Homework 1"]["Task 1"]["Test 2"].succeeded())

        self.assertEqual(len(results["Homework 1"]["Task 2"]), 1)
        self.assertNotIn("Test 1", results["Homework 1"]["Task 2"])
        self.assertIn(tasks.BUILD_SUCCESS_TAG, results["Homework 1"]["Task 2"])

        self.assertTrue(results["Homework 1"]["Task 3"]["Test 1"].succeeded())
        self.assertFalse(results["Homework 1"]["Task 3"]["Test 2"].succeeded())

        self.assertIn(tasks.STYLE_ERROR_TAG, results["Homework 1"]["Task 4"])
        self.assertTrue(results["Homework 1"]["Task 4"]["Test 1"].succeeded())
        self.assertFalse(results["Homework 1"]["Task 4"]["Test 2"].succeeded())

        self.assertIn(tools.EXPIRED_TAG, results["Homework 2"])
        self.assertIsNotNone(results["Homework 2"]["Task 2"]["Test 1"])
        self.assertFalse(results["Homework 2"]["Task 1"]["Test 1"].succeeded())
        self.assertEqual(results["Homework 2"]["Task 2"]["Test 1"].stderr, "")

        self.assertTrue(results["Homework 2"]["Task 2"]["Test 1"].succeeded())

        self.assertFalse(results["Homework 2"]["Task 3"]["Test 1"].succeeded())
        self.assertEqual(
            results["Homework 2"]["Task 3"]["Test 1"].stderr,
            "Timeout: command './main' ran longer than 20 seconds",
        )

        self.assertIsNotNone(results["Homework 3"]["Google Tests"]["Just build"])
        self.assertTrue(results["Homework 3"]["Google Tests"]["Just build"].succeeded())
        self.assertIsNotNone(results["Homework 3"]["Google Tests"]["Inject pass"])
        self.assertEqual(
            results["Homework 3"]["Google Tests"]["Inject pass"].stderr, ""
        )
        self.assertTrue(
            results["Homework 3"]["Google Tests"]["Inject pass"].succeeded()
        )
        self.assertIsNotNone(results["Homework 3"]["Google Tests"]["Inject fail"])
        self.assertEqual(
            results["Homework 3"]["Google Tests"]["Inject fail"].stderr,
            "Errors while running CTest\n",
        )
        self.assertFalse(
            results["Homework 3"]["Google Tests"]["Inject fail"].succeeded()
        )

        self.assertTrue(
            results["Homework 3"]["Bash with many folders"]["ls"].succeeded()
        )
