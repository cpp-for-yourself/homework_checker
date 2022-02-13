#!/usr/bin/python3
"""Script to check this homework."""
import argparse
import logging
from pathlib import Path

if __name__ == "__main__":
    from core.checker import Checker
    from core.md_writer import MdWriter
    from core.tools import expand_if_needed
else:
    from homework_checker.core.checker import Checker
    from homework_checker.core.md_writer import MdWriter
    from homework_checker.core.tools import expand_if_needed

logging.basicConfig()
log = logging.getLogger("GHC")
log.setLevel(logging.INFO)


def main():
    """Run this script."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-v", "--verbose", help="Make the output verbose.", action="store_true"
    )
    parser.add_argument(
        "-i",
        "--input",
        help="An input *.yml file with the job definition.",
        required=True,
    )
    parser.add_argument(
        "-o", "--output", help="An output *.md file with the results.", required=True
    )
    args = parser.parse_args()
    if args.verbose:
        log.setLevel(logging.DEBUG)
        log.debug("Enable DEBUG logging.")
    input_file = expand_if_needed(Path(args.input))
    log.debug('Reading from file "%s"', input_file)
    checker = Checker(input_file)
    results = checker.check_all_homeworks()
    md_writer = MdWriter()
    md_writer.update(results)
    output_file = expand_if_needed(Path(args.output))
    log.debug('Writing to file "%s"', output_file)
    md_writer.write_md_file(output_file)


if __name__ == "__main__":
    main()
