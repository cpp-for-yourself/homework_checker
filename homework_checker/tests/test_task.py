#!/usr/bin/python3
"""Test the checker."""

import unittest
from pathlib import Path
from typing import Tuple

from homework_checker.tasks import Task, BUILD_SUCCESS_TAG, STYLE_ERROR_TAG
from homework_checker.schema_tags import Tags
from homework_checker.schema_manager import SchemaManager
from homework_checker import tools


class TestTask(unittest.TestCase):
    """Test the checker."""

    def setUp(self: "TestTask"):
        # pylint: disable=C0103
        self.maxDiff = None
        self.job_file_path = (
            tools.PROJECT_ROOT_FOLDER
            / "homework_checker"
            / "tests"
            / "data"
            / "homework"
            / "example_job.yml"
        )
        schema_manager = SchemaManager(self.job_file_path)
        base_node = schema_manager.validated_yaml
        self.assertIn(Tags.HOMEWORKS_TAG, base_node)
        self.homework_nodes = base_node[Tags.HOMEWORKS_TAG]
        self.assertEqual(len(self.homework_nodes), 4)
        self.checked_code_folder = tools.expand_if_needed(
            Path(base_node[Tags.FOLDER_TAG])
        )

    def __get_homework_name_and_task(
        self: "TestTask", homework_index: int, task_index: int
    ) -> Tuple[str, Task]:
        homework_node = self.homework_nodes[homework_index]
        homework_folder = self.checked_code_folder / homework_node[Tags.FOLDER_TAG]
        task_node = homework_node[Tags.TASKS_TAG][task_index]
        task = Task.from_yaml_node(
            task_node=task_node,
            student_hw_folder=homework_folder,
            job_file=self.job_file_path,
        )
        if task is None:
            # We cannot use assertIsNotNone as this confuses mypy.
            self.fail("Task cannot be None")
        return homework_node[Tags.NAME_TAG], task

    @staticmethod
    def __sanitize_results(results: dict) -> dict:
        """Sanitize the outputs of the tasks."""
        sanitized_results = {}
        for key, value in results.items():
            sanitized_results[tools.remove_number_from_name(key)] = value
        return sanitized_results

    def test_check_simple_cpp_io_task(self: "TestTask"):
        """Check that we can build and run cpp code and get some output."""

        homework_name, task = self.__get_homework_name_and_task(
            homework_index=0, task_index=0
        )
        self.assertEqual(homework_name, "Sample homework")
        self.assertEqual(task.name, "Simple cpp tasks")
        results = task.check()
        results = TestTask.__sanitize_results(results)
        expected_number_of_build_outputs = 1
        expected_number_of_test_outputs = 3
        self.assertEqual(
            len(results),
            expected_number_of_build_outputs + expected_number_of_test_outputs,
            "Wrong results: {}".format(results),
        )
        self.assertTrue(results[BUILD_SUCCESS_TAG].succeeded())
        self.assertEqual(results["String output test"].stderr, "")
        self.assertTrue(results["String output test"].succeeded())
        self.assertTrue(results["Input output test"].succeeded())
        self.assertFalse(results["Wrong output fail"].succeeded())

    def test_check_build_failure_task(self: "TestTask"):
        """Check that the task fails if code does not build."""

        homework_name, task = self.__get_homework_name_and_task(
            homework_index=0, task_index=1
        )
        self.assertEqual(homework_name, "Sample homework")
        self.assertEqual(task.name, "Build failure task")
        results = task.check()
        results = TestTask.__sanitize_results(results)
        expected_number_of_build_outputs = 1
        expected_number_of_test_outputs = 0
        self.assertEqual(
            len(results),
            expected_number_of_build_outputs + expected_number_of_test_outputs,
            "Wrong results: {}".format(results),
        )
        self.assertFalse(results[BUILD_SUCCESS_TAG].succeeded())

    def test_check_cmake_arithmetics_task(self: "TestTask"):
        """Check a simple cmake build on arithmetics example."""

        homework_name, task = self.__get_homework_name_and_task(
            homework_index=0, task_index=2
        )
        self.assertEqual(homework_name, "Sample homework")
        self.assertEqual(task.name, "CMake build arithmetics task")
        results = task.check()
        results = TestTask.__sanitize_results(results)
        expected_number_of_build_outputs = 1
        expected_number_of_test_outputs = 2
        expected_number_of_code_style_outputs = 0
        self.assertEqual(
            len(results),
            expected_number_of_build_outputs
            + expected_number_of_test_outputs
            + expected_number_of_code_style_outputs,
            "Wrong results: {}".format(results),
        )
        self.assertTrue(results[BUILD_SUCCESS_TAG].succeeded())
        self.assertTrue(results["Test integer arithmetics"].succeeded())
        self.assertFalse(results["Test float arithmetics"].succeeded())

    def test_check_bash_task(self: "TestTask"):
        """Check a simple cmake build on arithmetics example."""

        homework_name, task = self.__get_homework_name_and_task(
            homework_index=0, task_index=3
        )
        self.assertEqual(homework_name, "Sample homework")
        self.assertEqual(task.name, "Bash task")
        results = task.check()
        results = TestTask.__sanitize_results(results)
        expected_number_of_build_outputs = 0
        expected_number_of_test_outputs = 2
        expected_number_of_code_style_outputs = 0
        self.assertEqual(
            len(results),
            expected_number_of_build_outputs
            + expected_number_of_test_outputs
            + expected_number_of_code_style_outputs,
            "Wrong results: {}".format(results),
        )
        print(results)
        self.assertTrue(results["Test output"].succeeded())
        self.assertFalse(results["Test wrong output"].succeeded())

    def test_check_wrong_output_type(self: "TestTask"):
        """Check that we detect a wrong output type."""

        homework_name, task = self.__get_homework_name_and_task(
            homework_index=1, task_index=0
        )
        self.assertEqual(homework_name, "Homework where things go wrong")
        self.assertEqual(task.name, "Return number task")
        results = task.check()
        results = TestTask.__sanitize_results(results)
        expected_number_of_build_outputs = 1
        expected_number_of_test_outputs = 1
        expected_number_of_code_style_outputs = 0
        self.assertEqual(
            len(results),
            expected_number_of_build_outputs
            + expected_number_of_test_outputs
            + expected_number_of_code_style_outputs,
            "Wrong results: {}".format(results),
        )
        self.assertTrue(results[BUILD_SUCCESS_TAG].succeeded())
        self.assertFalse(results["Wrong output format"].succeeded())
        self.assertEqual(
            results["Wrong output format"].stderr,
            "could not convert string to float: 'hello world\\n'",
        )

    def test_timing_out_task(self: "TestTask"):
        """Check that we can deal with infinitely running code."""

        homework_name, task = self.__get_homework_name_and_task(
            homework_index=1, task_index=1
        )
        self.assertEqual(homework_name, "Homework where things go wrong")
        self.assertEqual(task.name, "While loop task")
        results = task.check()
        results = TestTask.__sanitize_results(results)
        expected_number_of_build_outputs = 1
        expected_number_of_test_outputs = 1
        expected_number_of_code_style_outputs = 0
        self.assertEqual(
            len(results),
            expected_number_of_build_outputs
            + expected_number_of_test_outputs
            + expected_number_of_code_style_outputs,
            "Wrong results: {}".format(results),
        )
        self.assertTrue(results[BUILD_SUCCESS_TAG].succeeded())
        self.assertFalse(results["Test timeout"].succeeded())
        if not results["Test timeout"].stderr:
            self.fail()
        self.assertRegex(
            results["Test timeout"].stderr,
            r"Timeout: command './main' ran longer than .* seconds",
        )

    def test_google_tests_task(self: "TestTask"):
        """Check that we can run google test."""

        homework_name, task = self.__get_homework_name_and_task(
            homework_index=2, task_index=0
        )
        self.assertEqual(homework_name, "Homework with injections")
        self.assertEqual(task.name, "Google Tests")
        results = task.check()
        results = TestTask.__sanitize_results(results)
        expected_number_of_build_outputs = 1
        expected_number_of_test_outputs = 3
        expected_number_of_code_style_outputs = 0
        self.assertEqual(
            len(results),
            expected_number_of_build_outputs
            + expected_number_of_test_outputs
            + expected_number_of_code_style_outputs,
            "Wrong results: {}".format(results),
        )
        self.assertTrue(results[BUILD_SUCCESS_TAG].succeeded())
        self.assertTrue(results["Just build"].succeeded())
        self.assertTrue(results["Inject pass"].succeeded())
        self.assertFalse(results["Inject fail"].succeeded())

    def test_bash_task_with_injections(self: "TestTask"):
        """Check that we can inject folders into bash tasks too."""

        homework_name, task = self.__get_homework_name_and_task(
            homework_index=2, task_index=1
        )
        self.assertEqual(homework_name, "Homework with injections")
        self.assertEqual(task.name, "Bash with many folders")
        results = task.check()
        results = TestTask.__sanitize_results(results)
        expected_number_of_build_outputs = 0
        expected_number_of_test_outputs = 1
        expected_number_of_code_style_outputs = 0
        self.assertEqual(
            len(results),
            expected_number_of_build_outputs
            + expected_number_of_test_outputs
            + expected_number_of_code_style_outputs,
            "Wrong results: {}".format(results),
        )
        self.assertTrue(results["ls"].succeeded())
