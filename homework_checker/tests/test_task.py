#!/usr/bin/python3
"""Test the checker."""

import unittest
from pathlib import Path

from homework_checker.tasks import Task
from homework_checker.schema_tags import Tags
from homework_checker.schema_manager import SchemaManager
from homework_checker import tools


class TestTask(unittest.TestCase):
    """Test the checker."""

    def test_injecting_new(self: "TestTask"):
        """Check that we can inject folders that are not present yet."""
        # pylint: disable=C0103
        self.maxDiff = None

        job_file_path = (
            tools.PROJECT_ROOT_FOLDER
            / "homework_checker"
            / "tests"
            / "data"
            / "dummy"
            / "dummy_solution"
            / "solution.yml"
        )
        schema_manager = SchemaManager(job_file_path)
        base_node = schema_manager.validated_yaml
        self.assertIn(Tags.HOMEWORKS_TAG, base_node)
        self.assertGreater(len(base_node[Tags.HOMEWORKS_TAG]), 0)
        homework_node = base_node[Tags.HOMEWORKS_TAG][0]
        checked_code_folder = tools.expand_if_needed(Path(base_node[Tags.FOLDER_TAG]))
        current_folder = checked_code_folder / homework_node[Tags.FOLDER_TAG]
        task_node = homework_node[Tags.TASKS_TAG][0]
        task = Task.from_yaml_node(
            task_node=task_node,
            student_hw_folder=current_folder,
            job_file=job_file_path,
        )
        self.assertIsNotNone(task)
        if task is None:
            self.fail()
        self.assertTrue(task.student_task_folder.exists())
        folder_to_inject = Path("blah")
        task.inject_folder(folder_to_inject, folder_to_inject)
        self.assertTrue(task.backup_folder.exists())
        self.assertTrue(task.backup_folder.is_dir())
        self.assertTrue(
            (task.student_task_folder / folder_to_inject / "blah.cpp").exists()
        )
        task.revert_injections(folder_to_inject)
        self.assertFalse((task.backup_folder / folder_to_inject).exists())
        self.assertFalse((task.backup_folder / folder_to_inject / "blah.cpp").exists())

    def test_injecting_existing(self):
        """Check that we can inject folders that are already in the folder safely."""
        self.maxDiff = None

        job_file_path = (
            tools.PROJECT_ROOT_FOLDER
            / "homework_checker"
            / "tests"
            / "data"
            / "dummy"
            / "dummy_solution"
            / "solution.yml"
        )
        schema_manager = SchemaManager(job_file_path)
        base_node = schema_manager.validated_yaml
        self.assertIn(Tags.HOMEWORKS_TAG, base_node)
        self.assertGreater(len(base_node[Tags.HOMEWORKS_TAG]), 0)
        homework_node = base_node[Tags.HOMEWORKS_TAG][0]
        checked_code_folder = tools.expand_if_needed(Path(base_node[Tags.FOLDER_TAG]))
        current_folder = checked_code_folder / homework_node[Tags.FOLDER_TAG]
        task_node = homework_node[Tags.TASKS_TAG][0]
        task = Task.from_yaml_node(
            task_node=task_node,
            student_hw_folder=current_folder,
            job_file=job_file_path,
        )
        self.assertTrue(task.student_task_folder.exists())
        self.assertTrue(task.student_task_folder.is_dir())
        folder_to_inject = Path("tests")
        task.inject_folder(folder_to_inject, folder_to_inject)
        self.assertTrue(task.backup_folder.is_dir())
        self.assertTrue(
            (task.student_task_folder / folder_to_inject / "CMakeLists.txt").exists()
        )
        self.assertTrue(
            (task.student_task_folder / folder_to_inject / "test_dummy.cpp").exists()
        )
        task.revert_injections(folder_to_inject)
        self.assertFalse((task.backup_folder / folder_to_inject).is_dir())
        self.assertFalse(
            (task.backup_folder / folder_to_inject / "CMakeLists.txt").exists()
        )
        self.assertFalse(
            (task.backup_folder / folder_to_inject / "test_dummy.cpp").exists()
        )
