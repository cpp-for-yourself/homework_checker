"""Check the homework."""

import logging
from datetime import datetime
from typing import Dict
from pathlib import Path

from . import tools
from .schema_manager import SchemaManager
from .schema_tags import Tags
from .tasks import Task


log = logging.getLogger("GHC")

HomeworkResultDict = Dict[str, Dict[str, tools.CmdResult]]


class Checker:
    """Check homework."""

    TESTS_TAG = "tests"

    def __init__(self: "Checker", job_file_path: Path):
        """Initialize the checker from file."""
        self._job_file_path = tools.expand_if_needed(job_file_path)
        schema_manager = SchemaManager(self._job_file_path)
        self._base_node = schema_manager.validated_yaml
        self._checked_code_folder = tools.expand_if_needed(
            Path(self._base_node[Tags.FOLDER_TAG])
        )

    def check_homework(self: "Checker", homework_node: dict) -> HomeworkResultDict:
        """Run over all Tasks in a single homework."""
        results: HomeworkResultDict = {}
        current_folder = Path(self._checked_code_folder, homework_node[Tags.FOLDER_TAG])
        if not current_folder.exists():
            log.warning("Folder '%s' does not exist. Skiping.", current_folder)
            return results
        deadline_str = homework_node[Tags.DEADLINE_TAG]
        deadline_datetime = datetime.strptime(deadline_str, tools.DATE_PATTERN)
        if datetime.now() > deadline_datetime:
            results[tools.EXPIRED_TAG] = {}
        for task_node in homework_node[Tags.TASKS_TAG]:
            task = Task.from_yaml_node(
                task_node=task_node,
                student_hw_folder=current_folder,
                job_file=self._job_file_path,
            )
            if not task:
                continue
            results[task.name] = task.check_all_tests()
        return results

    def check_all_homeworks(self: "Checker") -> Dict[str, HomeworkResultDict]:
        """Run over all Tasks in all homeworks."""
        results: Dict[str, HomeworkResultDict] = {}
        for homework_node in self._base_node[Tags.HOMEWORKS_TAG]:
            hw_name = homework_node[Tags.NAME_TAG]
            current_homework_results = self.check_homework(homework_node)
            if current_homework_results:
                results[hw_name] = current_homework_results
        return results
