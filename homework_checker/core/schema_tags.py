"""Collection of schema related tags."""
from typing import Any


class Tags:
    """List of tags available."""

    CMD_TAG = "cmd"
    DEADLINE_TAG = "submit_by"
    EXPECTED_OUTPUT_TAG = "expected_output"
    FOLDER_TAG = "folder"
    HOMEWORKS_TAG = "homeworks"
    NAME_TAG = "name"
    OUTPUT_PIPE_TAG = "output_pipe_args"
    OUTPUT_TYPE_TAG = "output_type"
    TASKS_TAG = "tasks"
    TESTS_TAG = "tests"
    TIMEOUT_TAG = "timeout"


class OutputTags:
    """Define tags for output types."""

    STRING = "string"
    NUMBER = "number"
    ALL = [STRING, NUMBER]


class OneOf:
    """Check that an item is one of the list."""

    def __init__(self: "OneOf", some_list: list):
        """Set the list to choose from."""
        self.__items = some_list

    def __call__(self: "OneOf", item: Any):
        """Check that the list contains what is needed."""
        return item in self.__items

    def __str__(self: "OneOf"):
        """Override str for this class."""
        return "Possible values: {}".format(self.__items)
