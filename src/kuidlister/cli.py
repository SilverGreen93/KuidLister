"""Command line entry point.

Reads the kuids from stdin and writes the filtered, unique list to stdout, so
it can sit in a pipeline::

    Get-Content CM-copy.txt | kuidlister
    type CM-copy.txt | kuidlister.exe --upto 10

``--upto <n>`` is the GUI's "Generate asset versions up to" checkbox: each kuid
is replaced by its versions from 0 to n.  Without it every unique kuid is
listed once, rebuilt as a plain ``<kuid:author:id>``.

The result goes to stdout on a single line (the list is comma separated, so
newlines in the input carry no meaning); anything that helps the user -- an
empty input, an invalid limit -- goes to stderr.  Exit status: 0 listed
something, 1 found no kuids, 2 the limit was out of range.
"""

from __future__ import annotations

import argparse
import sys

from .kuids import MAX_VERSION, join, list_kuids

__all__ = ["main", "run_cli"]


def main(argv: list[str] | None = None) -> int:
    """Entry point for the ``kuidlister`` script."""
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(
        prog="kuidlister",
        description="List the unique Trainz KUIDs found on stdin.",
        epilog="Reads stdin, so pipe a Content Manager copy in: "
               "kuidlister < copy.txt",
    )
    parser.add_argument(
        "--upto",
        type=int,
        metavar="N",
        help=f"generate the asset versions of each kuid from 0 to N "
             f"(0-{MAX_VERSION}), like the GUI checkbox",
    )
    args = parser.parse_args(argv)

    if args.upto is not None and not 0 <= args.upto <= MAX_VERSION:
        print(f"Error: versions above {MAX_VERSION} or below 0 are invalid!", file=sys.stderr)
        return 2

    # read stdin before writing anything, so a bad --upto can still back out
    # with "no kuids found" instead of an empty line on stdout
    text = sys.stdin.read()
    if not list_kuids(text, args.upto):
        print("No KUIDs found on stdin.", file=sys.stderr)
        return 1
    return 0 if run_cli(text, upto=args.upto) else 1


def run_cli(text: str, upto: int | None = None, out=None, err=None) -> bool:
    """List the kuids in ``text``, writing them to ``out``.

    Returns False (and complains on ``err``) when the text holds no kuid at
    all, so a script can tell an empty paste from a good one.  The streams are
    parameters rather than prints so the tests can read the result directly.
    """
    out = out or sys.stdout
    err = err or sys.stderr

    tokens = list_kuids(text, upto)
    if not tokens:
        print("No KUIDs found on stdin.", file=err)
        return False

    print(join(tokens), file=out)
    out.flush()
    return True


if __name__ == "__main__":
    sys.exit(main())

