"""Handle various utility tasks."""
from __future__ import annotations
import os
import re
from os import environ
from subprocess import Popen, TimeoutExpired, CalledProcessError, CompletedProcess
from sys import stdin
from typing import Union, List, Optional, Mapping, Any, Tuple
from pathlib import Path
import tempfile
import subprocess
import logging
import datetime
import signal
import shutil
import difflib
import hashlib

from .schema_tags import OutputTags

PKG_NAME = "homework_checker"
PROJECT_ROOT_FOLDER = Path(__file__).parent.parent.parent
DATE_PATTERN = "%Y-%m-%d %H:%M:%S"
MAX_DATE_STR = datetime.datetime.max.strftime(DATE_PATTERN)

EXPIRED_TAG = "expired"
NUMBER_SPLIT_TAG = "____"

log = logging.getLogger("GHC")


def get_unique_str(seed: str) -> str:
    """Generate md5 unique sting hash given init_string."""
    return hashlib.md5(seed.encode("utf-8")).hexdigest()


def add_number_to_name(number: int, name: str) -> str:
    """Add a number before a string."""
    return str(number) + NUMBER_SPLIT_TAG + name


def remove_number_from_name(name: str) -> str:
    """Add a number before a string."""
    if NUMBER_SPLIT_TAG not in name:
        return name
    return name.split(NUMBER_SPLIT_TAG)[1]


class TempDirCopy:
    """docstring for TempDirCopy"""

    def __init__(self: TempDirCopy, source_folder: Path, prefix: Optional[str] = None):
        if prefix:
            unique_temp_folder_name = "{prefix}_{name}_{unique_hash}".format(
                prefix=prefix,
                name=source_folder.name,
                unique_hash=get_unique_str(str(source_folder)),
            )
        else:
            unique_temp_folder_name = "{name}_{unique_hash}".format(
                name=source_folder.name,
                unique_hash=get_unique_str(str(source_folder)),
            )
        self.__source_folder = source_folder
        self.__temporary_folder = (
            Path(tempfile.gettempdir()) / PKG_NAME / unique_temp_folder_name
        )

    def __enter__(self: TempDirCopy) -> Path:
        if self.__temporary_folder.exists():
            raise Exception("Cannot create a temporary folder as it already exists.")
        self.__temporary_folder.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copytree(
                self.__source_folder, self.__temporary_folder, dirs_exist_ok=True
            )
        except Exception as exception:
            shutil.rmtree(self.__temporary_folder)
            raise exception
        return self.__temporary_folder

    def __exit__(self: TempDirCopy, *exc_info: Any):
        shutil.rmtree(self.__temporary_folder)


def expand_if_needed(input_path: Path) -> Path:
    """Expand the path if it is not absolute."""
    if input_path.is_absolute():
        return input_path
    new_path = input_path.expanduser()
    if new_path.is_absolute():
        # This path needed user expansion. Now that the user home directory is
        # expanded this is a full absolute path.
        return new_path
    # The user could not be expanded, so we assume it is just another relative
    # path to the current working directory.
    return Path.cwd() / new_path


def convert_to(
    output_type: str, value: Any
) -> Union[Tuple[Optional[str], str], Tuple[Optional[float], str]]:
    """Convert the value to a specified type."""
    if not value:
        return None, "No value. Cannot convert {} to '{}'.".format(value, output_type)
    try:
        if output_type == OutputTags.STRING:
            return str(value).strip(), "OK"
        if output_type == OutputTags.NUMBER:
            return float(value), "OK"
    except ValueError as error:
        log.error("Exception: %s.", error)
        return None, str(error)
    return None, "Unknown output type {}. Cannot convert.".format(output_type)


def parse_git_url(git_url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Parse the git url.

    Args:
        git_url (str): url of a git repository (https or ssh)

    Returns:
        (str, str, str): tupple of domain, user and project name parsed from url
    """
    regex = re.compile(
        r"(?:git@|https:\/\/)"  # Prefix
        r"([\w\-_\.]+)"  # Domain
        r"[:\/]"  # Separator : or /
        r"([\w\-_\.\/]+)"  # User or folders
        r"[\/]"  # Separator /
        r"([\w\-_]+)"  # Project name
        r"(?:.git)*$"
    )  # .git or nothing
    match = regex.search(git_url)
    if not match:
        return None, None, None
    domain, user, project = match.groups()
    return domain, user, project


class OutputMismatch:
    def __init__(self, input: str, expected_output: str, actual_output: str) -> None:
        """Initialize the output mismatch class."""
        self._input = input
        self._expected_output = expected_output
        self._actual_output = actual_output

    @property
    def input(self: OutputMismatch) -> str:
        """Get input."""
        return self._input

    @property
    def expected_output(self: OutputMismatch) -> str:
        """Get expected output."""
        return self._expected_output

    @property
    def actual_output(self: OutputMismatch) -> str:
        """Get actual output."""
        return self._actual_output

    def diff(self: OutputMismatch) -> str:
        actual = str(self._actual_output)
        expected = str(self._expected_output)
        diff = difflib.unified_diff(
            actual.split("\n"),
            expected.split("\n"),
            fromfile="Actual output",
            tofile="Expected output",
        )
        diff_str = ""
        for line in diff:
            diff_str += line + "\n"
        return diff_str

    def __repr__(self: OutputMismatch) -> str:
        """Representation of the output mismatch object."""
        return "input: {}, expected: {}, actual: {}".format(
            self._input, self._expected_output, self._actual_output
        )


class CmdResult:
    """A small container for command result."""

    SUCCESS = 0
    FAILURE = 13
    TIMEOUT = 42

    def __init__(
        self: CmdResult,
        status: int,
        stdout: str = None,
        stderr: str = None,
        output_mismatch: OutputMismatch = None,
    ):
        """Initialize either stdout of stderr."""
        self._status = status
        self._stdout = stdout
        self._stderr = stderr
        self._output_mismatch = output_mismatch

    def succeeded(self: CmdResult) -> bool:
        """Check if the command succeeded."""
        return self._status == CmdResult.SUCCESS

    @property
    def status(self: CmdResult) -> int:
        """Get status."""
        return self._status

    @property
    def stdout(self: CmdResult) -> Optional[str]:
        """Get stdout."""
        return self._stdout

    @property
    def stderr(self: CmdResult) -> Optional[str]:
        """Get stderr."""
        return self._stderr

    @property
    def output_mismatch(self: CmdResult) -> Optional[OutputMismatch]:
        """Get output_mismatch."""
        return self._output_mismatch

    @staticmethod
    def success() -> CmdResult:
        """Return a cmd result that is a success."""
        return CmdResult(status=CmdResult.SUCCESS)

    def __repr__(self: CmdResult) -> str:
        """Representation of command result."""
        repr = "status: {} ".format(self._status)
        if self._stdout:
            repr += "stdout: {} ".format(self._stdout)
        if self._stderr:
            repr += "stderr: {} ".format(self._stderr)
        if self._output_mismatch:
            repr += "output_mismatch: {}".format(self._output_mismatch)
        return repr.strip()


def run_command(
    command: Union[List[str], str],
    timeout: float,
    shell: bool = True,
    cwd: Path = Path.cwd(),
    env: Optional[Mapping[str, Any]] = None,
) -> CmdResult:
    """Run a generic command in a subprocess.

    Args:
        command (str): command to run
    Returns:
        str: raw command output
    """
    try:
        startupinfo = None
        if shell and isinstance(command, list):
            command = subprocess.list2cmdline(command)
            log.debug("running command: \n%s", command)
        if env is None:
            env = environ
        process = __run_subprocess(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
            shell=shell,
            cwd=str(cwd),
            env=env,
            startupinfo=startupinfo,
            timeout=timeout,
        )
        return CmdResult(
            status=process.returncode,
            stdout=process.stdout.decode("utf-8"),
            stderr=process.stderr.decode("utf-8"),
        )
    except subprocess.CalledProcessError as error:
        output_text = error.output.decode("utf-8")
        log.error("command '%s' finished with code: %s", error.cmd, error.status)
        log.debug("command output: \n%s", output_text)
        return CmdResult(status=error.status, stderr=output_text)
    except subprocess.TimeoutExpired as error:
        output_text = "Timeout: command '{}' ran longer than {} seconds".format(
            error.cmd.strip(), error.timeout
        )
        log.error(output_text)
        return CmdResult(status=CmdResult.TIMEOUT, stderr=output_text)


def __run_subprocess(
    command: Union[List[str], str],
    str_input: str = None,
    timeout: float = None,
    check: bool = False,
    **kwargs,
) -> subprocess.CompletedProcess:
    """Run a command as a subprocess.

    Using the guide from StackOverflow:
    https://stackoverflow.com/a/36955420/1763680
    This command has been adapted from:
    https://github.com/python/cpython/blob/3.5/Lib/subprocess.py#L352-L399

    This code does essentially the same as subprocess.run(...) but makes sure to
    kill the whole process tree which allows to use the timeout even when using
    shell=True. The reason I don't want to stop using shell=True here is the
    convenience of piping arguments from one function to another.
    """
    if str_input is not None:
        if "stdin" in kwargs:
            raise ValueError("stdin and str_input arguments may not both be used.")
        kwargs["stdin"] = subprocess.PIPE

    if timeout is None:
        timeout = 20
    with Popen(command, start_new_session=True, **kwargs) as process:
        try:
            stdout, stderr = process.communicate(str_input, timeout=timeout)
        except TimeoutExpired as timeout_error:
            # Kill the whole group of processes.
            os.killpg(process.pid, signal.SIGINT)
            stdout, stderr = process.communicate()
            raise TimeoutExpired(
                process.args, timeout, output=stdout, stderr=stderr
            ) from timeout_error
        return_code = process.poll()
        if return_code is None:
            return_code = 1
        if check and return_code:
            raise CalledProcessError(
                return_code, process.args, output=stdout, stderr=stderr
            )
    return CompletedProcess(process.args, return_code, stdout, stderr)
