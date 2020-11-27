"""Different types of Tasks."""
from __future__ import annotations

import logging
import abc
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from shutil import copytree, rmtree

from . import tools
from .schema_tags import Tags, LangTags, BuildTags


log = logging.getLogger("GHC")


OUTPUT_MISMATCH_MESSAGE = """Given input: '{input}'
Your output '{actual}'
Expected output: '{expected}'"""

BUILD_SUCCESS_TAG = "0. Build succeeded"
STYLE_ERROR_TAG = "0. Style errors"

TOTAL_ERRORS_FOUND_TAG = "Total errors found"


class Task:
    """Define an abstract Task."""

    BACKUP_FOLDER = ".backup"

    ResultDictType = Dict[str, tools.CmdResult]

    class Injection:
        """A small class that encapsulates an injection source and destination."""

        def __init__(self: Task.Injection, source: Path, destination: Path):
            self._source = source
            self._destination = destination

        @property
        def source(self) -> Path:
            """Get the source folder."""
            return self._source

        @property
        def destination(self) -> Path:
            """Get the destination folder."""
            return self._destination

    @staticmethod
    def from_yaml_node(
        task_node: dict, student_hw_folder: Path, job_file: Path
    ) -> Optional[Task]:
        """Create an Task appropriate for the language."""
        student_task_folder = student_hw_folder / task_node[Tags.FOLDER_TAG]
        if not student_task_folder.exists():
            log.warning("Folder '%s' does not exist. Skipping.", student_task_folder)
            return None
        language_tag = task_node[Tags.LANGUAGE_TAG]
        if language_tag == LangTags.CPP:
            return CppTask(task_node, student_task_folder, job_file)
        if language_tag == LangTags.BASH:
            return BashTask(task_node, student_task_folder, job_file)
        log.error("Unknown Task language.")
        return None

    def __init__(
        self: Task, task_node: dict, student_task_folder: Path, job_file: Path
    ):
        """Initialize a generic Task."""
        self.name = task_node[Tags.NAME_TAG]
        self._job_root_folder = job_file.parent
        self._output_type = task_node[Tags.OUTPUT_TYPE_TAG]
        self._student_task_folder = student_task_folder
        self._binary_name = task_node[Tags.BINARY_NAME_TAG]
        self._pipe_through = task_node[Tags.PIPE_TAG]
        self._build_timeout = task_node[Tags.BUILD_TIMEOUT_TAG]
        if Tags.TESTS_TAG in task_node:
            self._test_nodes = task_node[Tags.TESTS_TAG]
        else:
            self._test_nodes = []  # Sometimes we don't have tests.

    def check(self: Task) -> Task.ResultDictType:
        """Iterate over the tests and check them."""
        # Generate empty results.
        results: Task.ResultDictType = {}

        def run_all_tests(
            test_node: dict, executable_folder: Path
        ) -> Task.ResultDictType:
            """Run all tests in the task."""
            results: Task.ResultDictType = {}
            if Tags.INJECT_FOLDER_TAG not in test_node:
                # There is no need to rebuild the code. We can just run our tests.
                test_result = self._run_test(test_node, executable_folder)
                results[test_node[Tags.NAME_TAG]] = test_result
                return results
            # There are folders to inject, so we will have to rebuild with the newly
            # injected folders. We do it in a new temp folder.
            with tools.TempDirCopy(
                source_folder=self._student_task_folder, prefix="build_injected"
            ) as code_folder:
                folders_to_inject = self.__get_folders_to_inject(
                    node=test_node, destination_root=code_folder
                )
                Task.__inject_folders(folders_to_inject)
                build_result, build_folder = self._build_if_needed(code_folder)
                if build_result and not build_result.succeeded():
                    raise Exception("Build with inserted folders must ALWAYS succeed!")
                test_result = self._run_test(
                    test_node=test_node, executable_folder=build_folder
                )
                results[test_node[Tags.NAME_TAG]] = test_result
            return results

        with tools.TempDirCopy(self._student_task_folder) as code_folder:
            # Build the source if this is needed.
            build_result, build_folder = self._build_if_needed(code_folder)
            if build_result:
                results[BUILD_SUCCESS_TAG] = build_result
                if not build_result.succeeded():
                    # The build has failed, so no further testing needed.
                    return results
            # The build is either not needed or succeeded. Continue testing.
            for test_node in self._test_nodes:
                results.update(
                    run_all_tests(test_node=test_node, executable_folder=build_folder)
                )

        style_errors = self._code_style_errors()
        if style_errors:
            results[STYLE_ERROR_TAG] = style_errors
        return results

    def __get_folders_to_inject(
        self: Task, node: dict, destination_root: Path
    ) -> List[Injection]:
        folders_to_inject = []
        if Tags.INJECT_FOLDER_TAG in node:
            # Inject all needed folders.
            for injection in node[Tags.INJECT_FOLDER_TAG]:
                source_folder = (
                    self._job_root_folder / injection[Tags.INJECT_SOURCE_TAG]
                )
                destination_folder = (
                    destination_root / injection[Tags.INJECT_DESTINATION_TAG]
                )
                folders_to_inject.append(
                    Task.Injection(source=source_folder, destination=destination_folder)
                )
        return folders_to_inject

    @staticmethod
    def __inject_folders(folders_to_inject: List[Task.Injection]):
        """Inject all folders overwriting existing folders in case of conflict."""
        for injection in folders_to_inject:
            if injection.destination.exists():
                rmtree(injection.destination)
            copytree(injection.source, injection.destination)

    @abc.abstractmethod
    def _run_test(self: Task, test_node: dict, executable_folder: Path):
        return None

    @abc.abstractmethod
    def _build_if_needed(self: Task, code_folder: Path):
        return None, code_folder

    @abc.abstractmethod
    def _code_style_errors(self: Task):
        return None


class CppTask(Task):
    """Define a C++ Task."""

    CMAKE_BUILD_CMD = "cmake .. && make -j2"
    REMAKE_AND_TEST = "make clean && rm -r * && cmake .. && make -j2 && ctest -VV"
    BUILD_CMD_SIMPLE = "clang++ -std=c++14 -o {binary} {compiler_flags} {binary}.cpp"

    def __init__(self: CppTask, task_node: dict, root_folder: Path, job_file: Path):
        """Initialize the C++ Task."""
        super().__init__(task_node, root_folder, job_file)
        self._compiler_flags = task_node[Tags.COMPILER_FLAGS_TAG]
        self._build_type = task_node[Tags.BUILD_TYPE_TAG]

    def _build_if_needed(
        self: CppTask, code_folder: Path
    ) -> Tuple[tools.CmdResult, Path]:
        if self._build_type == BuildTags.CMAKE:
            build_folder = code_folder / "build"
            build_folder.mkdir(parents=True, exist_ok=True)
            return (
                tools.run_command(
                    CppTask.CMAKE_BUILD_CMD,
                    cwd=build_folder,
                    timeout=self._build_timeout,
                ),
                build_folder,
            )
        return (
            tools.run_command(
                CppTask.BUILD_CMD_SIMPLE.format(
                    binary=self._binary_name, compiler_flags=self._compiler_flags
                ),
                cwd=code_folder,
                timeout=self._build_timeout,
            ),
            code_folder,
        )

    def _code_style_errors(self: CppTask) -> Optional[tools.CmdResult]:
        """Check if code conforms to Google Style."""
        command = (
            "cpplint --counting=detailed "
            + "--filter=-legal,-readability/todo,"
            + "-build/include_order,-runtime/threadsafe_fn,"
            + "-runtime/arrays"
            + ' $( find . -name "*.h" -o -name "*.cpp" | grep -vE "^./build/" )'
        )
        result = tools.run_command(
            command,
            cwd=self._student_task_folder,
            timeout=self._build_timeout,
        )
        if result.stderr and TOTAL_ERRORS_FOUND_TAG in result.stderr:
            return result
        if result.stdout and TOTAL_ERRORS_FOUND_TAG in result.stdout:
            return result
        return None

    def _run_test(self: CppTask, test_node: dict, executable_folder: Path):
        if test_node[Tags.RUN_GTESTS_TAG]:
            return tools.run_command(
                CppTask.REMAKE_AND_TEST,
                cwd=executable_folder,
                timeout=test_node[Tags.TIMEOUT_TAG],
            )
        input_str = ""
        if Tags.INPUT_TAG in test_node:
            input_str = test_node[Tags.INPUT_TAG]
        run_cmd = "./{binary_name} {args}".format(
            binary_name=self._binary_name, args=input_str
        )
        if self._pipe_through:
            run_cmd += " " + self._pipe_through
        run_result = tools.run_command(
            run_cmd, cwd=executable_folder, timeout=test_node[Tags.TIMEOUT_TAG]
        )
        if not run_result.succeeded():
            return run_result
        # TODO(igor): do I need explicit error here?
        our_output, error = tools.convert_to(self._output_type, run_result.stdout)
        if not our_output:
            # Conversion has failed.
            run_result.stderr = error
            return run_result
        expected_output, error = tools.convert_to(
            self._output_type, test_node[Tags.EXPECTED_OUTPUT_TAG]
        )
        if our_output != expected_output:
            run_result.stderr = OUTPUT_MISMATCH_MESSAGE.format(
                actual=our_output, input=input_str, expected=expected_output
            )
        return run_result


class BashTask(Task):
    """Define a Bash Task."""

    RUN_CMD = "sh {binary_name}.sh {args}"

    def __init__(self: BashTask, task_node: dict, root_folder: Path, job_file: Path):
        """Initialize the Task."""
        super().__init__(task_node, root_folder, job_file)

    def _build_if_needed(self: BashTask, code_folder: Path):
        return None, code_folder  # There is nothing to build in Bash.

    def _code_style_errors(self: BashTask):
        return None

    def _run_test(
        self: BashTask, test_node: dict, executable_folder: Path
    ) -> tools.CmdResult:
        input_str = ""
        if Tags.INPUT_TAG in test_node:
            input_str = test_node[Tags.INPUT_TAG]
        run_cmd = BashTask.RUN_CMD.format(binary_name=self._binary_name, args=input_str)
        if self._pipe_through:
            run_cmd += " " + self._pipe_through
        run_result = tools.run_command(
            run_cmd, cwd=executable_folder, timeout=test_node[Tags.TIMEOUT_TAG]
        )
        if not run_result.succeeded():
            return run_result
        our_output, error = tools.convert_to(self._output_type, run_result.stdout)
        if not our_output:
            # Conversion has failed.
            run_result.stderr = error
            return run_result
        expected_output, error = tools.convert_to(
            self._output_type, test_node[Tags.EXPECTED_OUTPUT_TAG]
        )
        if our_output != expected_output:
            run_result.stderr = OUTPUT_MISMATCH_MESSAGE.format(
                actual=our_output, input=input_str, expected=expected_output
            )
        return run_result
