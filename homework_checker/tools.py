"""Handle various utility tasks."""
from __future__ import annotations
import os
import re
from os import environ
from subprocess import Popen, TimeoutExpired, CalledProcessError, CompletedProcess
from typing import Union, List, Optional, Mapping, Any, Tuple
from pathlib import Path
import tempfile
import subprocess
import logging
import datetime
import signal
import shutil
import hashlib

from .schema_tags import OutputTags

PKG_NAME = "homework_checker"
PROJECT_ROOT_FOLDER = Path(__file__).parent.parent
DATE_PATTERN = "%Y-%m-%d %H:%M:%S"
MAX_DATE_STR = datetime.datetime.max.strftime(DATE_PATTERN)

EXPIRED_TAG = "expired"

log = logging.getLogger("GHC")


def get_unique_str(seed: str) -> str:
    """Generate md5 unique sting hash given init_string."""
    return hashlib.md5(seed.encode("utf-8")).hexdigest()


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
        self.__temporary_folder = (
            Path(tempfile.gettempdir()) / PKG_NAME / unique_temp_folder_name
        )

    def __enter__(self: TempDirCopy) -> Path:
        assert (
            not self.__temporary_folder.exists()
        ), "Cannot create a temporary folder as it already exists."
        self.__temporary_folder.mkdir(parents=True, exist_ok=True)
        return self.__temporary_folder

    def __exit__(self: TempDirCopy, *exc_info: Any):
        shutil.rmtree(self.__temporary_folder)


def get_temp_dir() -> Path:
    """Create a temporary folder if needed and return it."""
    tempdir = Path(tempfile.gettempdir(), PKG_NAME)
    tempdir.mkdir(parents=True, exist_ok=True)
    return tempdir


def expand_if_needed(input_path: Path) -> Path:
    """Expand the path if it is not absolute."""
    if input_path.is_absolute():
        return Path(input_path)
    new_path = input_path.expanduser()
    if new_path.is_absolute():
        # This path needed user expansion. Now that the user home directory is
        # expanded this is a full absolute path.
        return new_path
    # The user could not be expanded, so we assume it is just another relative
    # path to the project directory. Mostly used for testing purposes here.
    return Path(PROJECT_ROOT_FOLDER, new_path)


def convert_to(
    output_type: int, value: Any
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


class CmdResult:
    """A small container for command result."""

    SUCCESS = 0
    FAILURE = 13

    def __init__(
        self: CmdResult, returncode: int = None, stdout: str = None, stderr: str = None
    ):
        """Initialize either stdout of stderr."""
        self._returncode = returncode
        self._stdout = stdout
        self._stderr = stderr

    def succeeded(self: CmdResult) -> bool:
        """Check if the command succeeded."""
        if self.returncode is not None:
            return self.returncode == CmdResult.SUCCESS
        if self.stderr:
            return False
        return True

    @property
    def returncode(self: CmdResult) -> Optional[int]:
        """Get returncode."""
        return self._returncode

    @property
    def stdout(self: CmdResult) -> Optional[str]:
        """Get stdout."""
        return self._stdout

    @property
    def stderr(self: CmdResult) -> Optional[str]:
        """Get stderr."""
        return self._stderr

    @stderr.setter
    def stderr(self, value: str):
        self._returncode = None  # We can't rely on returncode anymore
        self._stderr = value

    @staticmethod
    def success() -> CmdResult:
        """Return a cmd result that is a success."""
        return CmdResult(stdout="Success!")

    def __repr__(self: CmdResult) -> str:
        """Representatin of command result."""
        stdout = self.stdout
        if not stdout:
            stdout = ""
        if self.stderr:
            return "stdout: {}, stderr: {}".format(stdout.strip(), self.stderr.strip())
        return stdout.strip()


def run_command(
    command: Union[List[str], str],
    shell: bool = True,
    cwd: Path = Path.cwd(),
    env: Optional[Mapping[str, Any]] = None,
    timeout: float = 20,
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
            shell=shell,
            cwd=str(cwd),
            env=env,
            startupinfo=startupinfo,
            timeout=timeout,
        )
        return CmdResult(
            returncode=process.returncode,
            stdout=process.stdout.decode("utf-8"),
            stderr=process.stderr.decode("utf-8"),
        )
    except subprocess.CalledProcessError as error:
        output_text = error.output.decode("utf-8")
        log.error("command '%s' finished with code: %s", error.cmd, error.returncode)
        log.debug("command output: \n%s", output_text)
        return CmdResult(returncode=error.returncode, stderr=output_text)
    except subprocess.TimeoutExpired as error:
        output_text = "Timeout: command '{}' ran longer than {} seconds".format(
            error.cmd.strip(), error.timeout
        )
        log.error(output_text)
        return CmdResult(returncode=1, stderr=output_text)


def __run_subprocess(
    command: Union[List[str], str],
    str_input: str = None,
    timeout: float = None,
    check: bool = False,
    **kwargs
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
        retcode = process.poll()
        if retcode is None:
            retcode = 1
        if check and retcode:
            raise CalledProcessError(
                retcode, process.args, output=stdout, stderr=stderr
            )
    return CompletedProcess(process.args, retcode, stdout, stderr)
