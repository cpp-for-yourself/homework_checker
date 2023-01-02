"""Different types of Tasks."""
from __future__ import annotations

import logging
import abc
from pathlib import Path
from string import Template
from typing import Optional, Dict, List, Tuple
from shutil import copytree, rmtree

from . import tools
from .schema_tags import Tags


log = logging.getLogger("GHC")


class Task:
    """Define an abstract Task."""

    BACKUP_FOLDER = ".backup"

    ResultDictType = Dict[str, tools.CmdResult]

    @staticmethod
    def from_yaml_node(
        task_node: dict, student_hw_folder: Path, job_file: Path
    ) -> Optional[Task]:
        """Create an Task appropriate for the language."""
        student_task_folder = student_hw_folder / task_node[Tags.FOLDER_TAG]
        if not student_task_folder.exists():
            log.warning("Folder '%s' does not exist. Skipping.", student_task_folder)
            return None
        return Task(task_node, student_task_folder, job_file)

    def __init__(
        self: Task, task_node: dict, student_task_folder: Path, job_file: Path
    ):
        """Initialize a generic Task."""
        self.name = task_node[Tags.NAME_TAG]
        self._job_root_folder = job_file.parent
        self._student_task_folder = student_task_folder

        self._test_nodes = task_node[Tags.TESTS_TAG]
        self.__test_counter = 0

    def __with_number_prefix(self: Task, test_name: str) -> str:
        """Get the test name with number."""
        self.__test_counter += 1
        return tools.add_number_to_name(self.__test_counter, test_name)

    def check(self: Task) -> Task.ResultDictType:
        """Iterate over the tests and check them."""
        # Generate empty results.
        results: Task.ResultDictType = {}

        with tools.TempDirCopy(self._student_task_folder) as code_folder:
            for test_node in self._test_nodes:
                node_name = self.__with_number_prefix(test_node[Tags.NAME_TAG])
                test_result = self._run_test(
                    test_node=test_node, executable_folder=code_folder
                )
                results.update({node_name: test_result})
                if not test_result.succeeded():
                    break

        return results

    def _run_test(
        self: Task, test_node: dict, executable_folder: Path
    ) -> tools.CmdResult:
        command = Template(test_node[Tags.CMD_TAG]).substitute(
            JOB_ROOT=self._job_root_folder
        )
        run_result = tools.run_command(
            command,
            cwd=executable_folder,
            timeout=test_node[Tags.TIMEOUT_TAG],
        )
        if not run_result.succeeded():
            return run_result
        our_output = run_result.stdout.strip()
        if Tags.OUTPUT_TYPE_TAG in test_node:
            our_output, error = tools.convert_to(
                test_node[Tags.OUTPUT_TYPE_TAG], our_output
            )
            if not our_output:
                # Conversion has failed.
                return tools.CmdResult(
                    status=tools.CmdResult.FAILURE,
                    stdout=run_result.stdout,
                    stderr=error,
                )
        if Tags.EXPECTED_OUTPUT_TAG in test_node:
            expected_output = test_node[Tags.EXPECTED_OUTPUT_TAG]
            if isinstance(expected_output, str):
                expected_output = expected_output.strip()
            if Tags.OUTPUT_TYPE_TAG in test_node:
                expected_output, error = tools.convert_to(
                    test_node[Tags.OUTPUT_TYPE_TAG], expected_output
                )
            if our_output != expected_output:
                return tools.CmdResult(
                    status=tools.CmdResult.FAILURE,
                    stdout=run_result.stdout,
                    stderr=run_result.stderr,
                    output_mismatch=tools.OutputMismatch(
                        input=command,
                        expected_output=expected_output,
                        actual_output=our_output,
                    ),
                )
        return run_result
