"""Manage creation of schema."""
from __future__ import annotations
import sys
import logging
import operator
from pathlib import Path
from typing import Union, List, Dict, Any
from ruamel.yaml import YAML  # type: ignore[import]
from ruamel.yaml.comments import CommentedMap, CommentedSeq  # type: ignore[import]
from schema import Schema, SchemaError, Or, Optional  # type: ignore[import]

from .tools import MAX_DATE_STR
from .schema_tags import Tags, OutputTags, BuildTags, LangTags

log = logging.getLogger("GHC")

SCHEMA_FILE = Path(__file__).parent.parent / "schema" / "schema.yml"


class SchemaManager:
    """Manage schema creation."""

    GenericListType = List[Union[Any, Dict[str, Any], List[Any]]]
    GenericDictType = Dict[str, Union[Any, Dict[str, Any], List[Any]]]

    def __init__(self: SchemaManager, file_name: Path):
        """Create a schema for my tests."""

        injection_schema = {
            Tags.INJECT_SOURCE_TAG: str,
            Tags.INJECT_DESTINATION_TAG: str,
        }

        test_schema = {
            Tags.NAME_TAG: str,
            Optional(Tags.INPUT_TAG): str,
            Optional(Tags.INJECT_FOLDER_TAG): [injection_schema],
            Optional(Tags.RUN_GTESTS_TAG, default=False): bool,
            Optional(Tags.EXPECTED_OUTPUT_TAG): Or(str, float, int),
        }

        task_schema = {
            Tags.NAME_TAG: str,
            Tags.LANGUAGE_TAG: Or(LangTags.CPP, LangTags.BASH),
            Tags.FOLDER_TAG: str,
            Optional(Tags.OUTPUT_TYPE_TAG, default=OutputTags.STRING): Or(
                OutputTags.STRING, OutputTags.NUMBER
            ),
            Optional(Tags.COMPILER_FLAGS_TAG, default="-Wall"): str,
            Optional(Tags.BINARY_NAME_TAG, default="main"): str,
            Optional(Tags.PIPE_TAG, default=""): str,
            Optional(Tags.BUILD_TYPE_TAG, default=BuildTags.CMAKE): Or(
                BuildTags.CMAKE, BuildTags.SIMPLE
            ),
            Optional(Tags.TESTS_TAG): [test_schema],
        }

        homework_schema = {
            Tags.NAME_TAG: str,
            Tags.FOLDER_TAG: str,
            Optional(Tags.DEADLINE_TAG, default=MAX_DATE_STR): str,
            Tags.TASKS_TAG: [task_schema],
        }

        self.__schema = Schema(
            {
                Tags.FOLDER_TAG: str,
                Tags.HOMEWORKS_TAG: [homework_schema],
            }
        )
        yaml = YAML()
        # big enough value to prevent wrapping
        yaml.width = 4096  # type: ignore[assignment]
        yaml.explicit_start = True  # type: ignore[assignment]
        yaml.indent(mapping=2, sequence=4, offset=2)
        with open(file_name, "r") as stream:
            contents = SchemaManager.__to_simple_dict(yaml.load(stream))
            try:
                self.__validated_yaml = self.__schema.validate(contents)
            except SchemaError as exc:
                sys.exit(exc.code)
        # Write the schema every time we run this code while developing. We
        # don't want to run this when the package is installed as this we won't
        # have the permission. This is intended to keep the schema file up to
        # date when we add new stuff to it.
        try:
            with open(SCHEMA_FILE, "w") as outfile:
                str_dict = SchemaManager.__sanitize_value(self.__schema._schema)
                yaml.dump(str_dict, outfile)
        except OSError:
            log.debug("Cannot write schema file. We only use this while developing.")

    @staticmethod
    def __to_simple_list(
        commented_seq: List[Union[Any, CommentedSeq, CommentedMap]]
    ) -> SchemaManager.GenericListType:
        simple_list: SchemaManager.GenericListType = []
        for value in commented_seq:
            if isinstance(value, CommentedSeq):
                simple_list.append(SchemaManager.__to_simple_list(value))
            elif isinstance(value, CommentedMap):
                simple_list.append(SchemaManager.__to_simple_dict(value))
            else:
                simple_list.append(value)
        return simple_list

    @staticmethod
    def __to_simple_dict(
        commented_map: Dict[str, Union[Any, CommentedSeq, CommentedMap]],
    ) -> SchemaManager.GenericDictType:
        simple_dict: SchemaManager.GenericDictType = {}
        for key, value in commented_map.items():
            if isinstance(value, CommentedMap):
                simple_dict[key] = SchemaManager.__to_simple_dict(value)
            elif isinstance(value, CommentedSeq):
                simple_dict[key] = SchemaManager.__to_simple_list(value)
            else:
                simple_dict[key] = value
        return simple_dict

    @property
    def validated_yaml(self) -> dict:
        """Return validated yaml."""
        return self.__validated_yaml

    @property
    def schema(self):
        """Return schema."""
        return self.__schema

    # pylint: disable=R0911
    # This method needs this many returns.
    @staticmethod
    def __sanitize_value(input_var: Union[dict, Optional, Or, Any]):
        """Use the schema and create an example file from it."""
        # pylint: disable=W0212
        # This seems to be the only way to get to schema value.
        if isinstance(input_var, dict):
            new_dict = {}
            for key, val in input_var.items():
                new_dict[
                    SchemaManager.__sanitize_value(key)
                ] = SchemaManager.__sanitize_value(val)
            return CommentedMap(sorted(new_dict.items(), key=operator.itemgetter(0)))
        if isinstance(input_var, list):
            new_list = []
            for val in input_var:
                new_list.append(SchemaManager.__sanitize_value(val))
            return new_list
        if isinstance(input_var, Optional):
            if input_var._schema == Tags.DEADLINE_TAG:
                return SchemaManager.__sanitize_value(input_var._schema)
            return "~[optional]~ " + SchemaManager.__sanitize_value(input_var._schema)
        if isinstance(input_var, Or):
            return "Any of " + str(
                [SchemaManager.__sanitize_value(s) for s in input_var._args]
            )
        if input_var is str:
            return "String value"
        if input_var is float:
            return "Float value"
        if input_var is int:
            return "Int value"
        if input_var is bool:
            return "Boolean value"
        return str(input_var)
