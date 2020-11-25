"""Different types of Tasks."""
from __future__ import annotations

import logging
import abc
from pathlib import Path
from typing import Optional, Dict, List
from shutil import copytree, move, rmtree

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
        self._job_yaml_folder = job_file.parent
        self._output_type = task_node[Tags.OUTPUT_TYPE_TAG]
        self._cwd = student_task_folder
        self._student_task_folder = student_task_folder
        self._binary_name = task_node[Tags.BINARY_NAME_TAG]
        self._pipe_through = task_node[Tags.PIPE_TAG]
        self._backup_folder = student_task_folder / Task.BACKUP_FOLDER
        if Tags.TESTS_TAG in task_node:
            self._test_nodes = task_node[Tags.TESTS_TAG]
        else:
            self._test_nodes = []  # Sometimes we don't have tests.
        self._task_node = task_node

    def check_all_tests(self: Task) -> Task.ResultDictType:
        """Iterate over the tests and check them."""
        # Generate empty results.
        results: Task.ResultDictType = {}
        # Build the source if this is needed.
        injected_folders = self.__inject_folders_if_needed(self._task_node)
        build_result = self._build_if_needed()
        # TODO(igor): cleanup after build
        self.__restore_injected_folders(self._task_node, injected_folders)
        if build_result:
            results[BUILD_SUCCESS_TAG] = build_result
            if not build_result.succeeded():
                # The build has failed, so no further testing needed.
                return results
        # The build is either not needed or succeeded. Continue testing.
        for test_node in self._test_nodes:
            injected_folders = self.__inject_folders_if_needed(test_node)
            test_result = self._run_test(test_node)
            self.__restore_injected_folders(test_node, injected_folders)
            results[test_node[Tags.NAME_TAG]] = test_result
        style_errors = self._code_style_errors()
        if style_errors:
            results[STYLE_ERROR_TAG] = style_errors
        return results

    def inject_folder(self: Task, dest_folder_name: str, inject_folder: Path):
        """Inject a folder into the student's code."""
        # TODO(igor): specify the destination folder in yaml
        # TODO(igor): make injection a wrapper
        full_path_from = inject_folder
        if not full_path_from.is_absolute():
            full_path_from = self._job_yaml_folder / full_path_from
        full_path_to = self._student_task_folder / dest_folder_name
        if not self._backup_folder.is_dir():
            self._backup_folder.mkdir(parents=True, exist_ok=True)

        if full_path_to.exists():
            # Move the existing data to the backup folder if needed.
            dest = move(str(full_path_to), str(self._backup_folder))
        copytree(full_path_from, full_path_to)

    def revert_injections(self: Task, dest_folder_name: str):
        """Revert injections from the backup folder."""
        injected_folder = self._student_task_folder / dest_folder_name
        backed_up_folder = self._backup_folder / dest_folder_name
        if injected_folder.exists() and injected_folder.is_dir():
            rmtree(injected_folder)
        if not backed_up_folder.exists():
            # There is no backup, so nothing to restore.
            return
        move(str(backed_up_folder), str(self._student_task_folder))

    def __inject_folders_if_needed(self: Task, node: dict) -> List[Path]:
        injected_folders = []
        if Tags.INJECT_FOLDER_TAG in node:
            # Inject all needed folders.
            for folder in node[Tags.INJECT_FOLDER_TAG]:
                inject_folder = self._job_yaml_folder / folder
                # TODO(igor): destination path must be specified in yaml
                self.inject_folder(Path(folder).name, inject_folder)
                injected_folders.append(folder)
        return injected_folders

    def __restore_injected_folders(
        self: Task, node: dict, injected_folders: List[Path]
    ):
        if Tags.INJECT_FOLDER_TAG in node:
            for folder in injected_folders:
                self.revert_injections(Path(folder).name)
            rmtree(self._backup_folder)

    @abc.abstractmethod
    def _run_test(self: Task, test_node: dict):
        return None

    @abc.abstractmethod
    def _build_if_needed(self: Task):
        return None

    @abc.abstractmethod
    def _code_style_errors(self: Task):
        return None

    @property
    def student_task_folder(self: Task):
        """Get the folder with the student's task."""
        return self._student_task_folder

    @property
    def backup_folder(self: Task):
        """Get the folder with the backup of any overwritten by injection folders."""
        return self._backup_folder


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
        if self._build_type == BuildTags.CMAKE:
            # The cmake project will always work from build folder.
            self._cwd = self._cwd / "build"
            self._cwd.mkdir(parents=True, exist_ok=True)

    def _build_if_needed(self: CppTask) -> tools.CmdResult:
        if self._build_type == BuildTags.CMAKE:
            return tools.run_command(CppTask.CMAKE_BUILD_CMD, cwd=self._cwd, timeout=60)
        return tools.run_command(
            CppTask.BUILD_CMD_SIMPLE.format(
                binary=self._binary_name, compiler_flags=self._compiler_flags
            ),
            cwd=self._cwd,
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
        result = tools.run_command(command, cwd=self._student_task_folder)
        if result.stderr and TOTAL_ERRORS_FOUND_TAG in result.stderr:
            return result
        if result.stdout and TOTAL_ERRORS_FOUND_TAG in result.stdout:
            return result
        return None

    def _run_test(self: CppTask, test_node: dict):
        # TODO(igor): remove the hardcoded timeout here.
        if test_node[Tags.RUN_GTESTS_TAG]:
            return tools.run_command(CppTask.REMAKE_AND_TEST, cwd=self._cwd, timeout=60)
        input_str = ""
        if Tags.INPUT_TAG in test_node:
            input_str = test_node[Tags.INPUT_TAG]
        run_cmd = "./{binary_name} {args}".format(
            binary_name=self._binary_name, args=input_str
        )
        if self._pipe_through:
            run_cmd += " " + self._pipe_through
        run_result = tools.run_command(run_cmd, cwd=self._cwd)
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

    def _build_if_needed(self: BashTask):
        return None  # There is nothing to build in Bash.

    def _code_style_errors(self: BashTask):
        return None

    def _run_test(self: BashTask, test_node: dict) -> tools.CmdResult:
        input_str = ""
        if Tags.INPUT_TAG in test_node:
            input_str = test_node[Tags.INPUT_TAG]
        run_cmd = BashTask.RUN_CMD.format(binary_name=self._binary_name, args=input_str)
        if self._pipe_through:
            run_cmd += " " + self._pipe_through
        run_result = tools.run_command(run_cmd, cwd=self._cwd)
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
