"""The KUID listing logic, free of any GUI or terminal handling.

Port of the body of ``Button1_Click`` in frmMain.vb: find every kuid mention
in a chunk of text, drop the duplicates and join the survivors with commas --
optionally replacing each kuid by all of its asset versions from 0 up to a
chosen maximum.

The original ran over the whole text twice (once for the matches, once to
strip duplicates) and drove its progress bar from three passes;
:func:`extract_kuids` and :func:`dedupe` keep those two stages apart so the GUI
can report progress between them, and each is a single ordered sweep instead of
the original's quadratic duplicate search.
"""

from __future__ import annotations

import re

__all__ = [
    "KUID_RE",
    "MAX_VERSION",
    "extract_kuids",
    "split_kuid",
    "dedupe",
    "format_kuid",
    "expand_versions",
    "list_kuids",
    "join",
]

# The same pattern as the VB.NET code: kuid or kuid2, an optional negative sign
# on each of the two numbers and an optional version number.  "KUID" in upper
# case matched too, so the pattern is case insensitive; the original's
# "(kuid|KUID)[2]?" also let "KUid2" through by accident.
KUID_RE = re.compile(r"kuid2?:[-]?\d*:[-]?\d*(?::\d*)?", re.IGNORECASE)

# Trainz stores the asset version in seven bits, so a version above this (or
# below zero) cannot exist; the GUI warns about it exactly like TextBox3's
# TextChanged handler did.
MAX_VERSION = 127


def extract_kuids(text: str) -> list[str]:
    """Every kuid mention in ``text``, in order, duplicates included.

    The bare token without its angle brackets, as the VB.NET code stored it in
    its ``str`` array: ``kuid:1234:12345`` or ``kuid2:4321:54321:2``.
    """
    return [match.group(0) for match in KUID_RE.finditer(text)]


def split_kuid(token: str) -> tuple[int, int]:
    """The author and content id of a kuid token as integers.

    ``token.split(":")[1]`` and ``[2]``, like the VB.NET code, but converted to
    numbers straight away: it compared the author against zero as a string, so
    only its negative sign was ever noticed.  Any version already written in
    the token is left out -- re-joining without it is what dropped it there.
    """
    parts = token.split(":")
    return int(parts[1]), int(parts[2])


def dedupe(kuids: list[str]) -> list[str]:
    """The kuids with repeats removed, keeping the first of each.

    Two mentions are the same asset when their author and content id match:
    the VB.NET code split every kuid and compared only those two parts, so a
    ``kuid2:A:C:6`` in the text folded onto an earlier ``kuid:A:C`` and its
    version went with it.  Later copies are skipped here rather than blanked
    out as they were there; the list that comes out is the same.
    """
    unique: dict[tuple[int, int], str] = {}
    for token in kuids:
        unique.setdefault(split_kuid(token), token)
    return list(unique.values())


def format_kuid(author: int, content_id: int, version: int | None = None) -> str:
    """One kuid as it appears in the output list, brackets included.

    With a version it is a kuid2 token, without one a plain kuid.  The VB.NET
    code rebuilt every kuid this way after splitting it, which quietly dropped
    any version already written in the source text.
    """
    if version is None:
        return f"<kuid:{author}:{content_id}>"
    return f"<kuid2:{author}:{content_id}:{version}>"


def expand_versions(kuids: list[str], upto: int) -> list[str]:
    """Each kuid's asset versions from 0 to ``upto``, as formatted tokens.

    A kuid whose author is negative (the built-in content Trainz numbers below
    zero) has no versions of its own, so it is listed once as a plain kuid --
    the same shortcut the VB.NET loop took.
    """
    result: list[str] = []
    for token in kuids:
        author, content_id = split_kuid(token)
        if author < 0:
            result.append(format_kuid(author, content_id))
        else:
            result.extend(
                format_kuid(author, content_id, version) for version in range(upto + 1)
            )
    return result


def list_kuids(text: str, upto: int | None = None) -> list[str]:
    """Turn pasted text into the list of kuids to show.

    Returns the quoted kuid tokens.  With ``upto`` set, each kuid is replaced
    by its versions from 0 to that number; with ``None`` (the checkbox off)
    every unique kuid is rebuilt as a plain kuid, dropping any version that was
    written in the input, just as re-joining the split pieces did in VB.NET.
    """
    unique = dedupe(extract_kuids(text))
    if upto is None:
        return [format_kuid(*split_kuid(token)) for token in unique]
    return expand_versions(unique, upto)


def join(tokens: list[str]) -> str:
    """The tokens separated by commas, no trailing comma.

    The VB.NET code appended a comma after every kuid and then cut the last one
    off the finished text.
    """
    return ",".join(tokens)
