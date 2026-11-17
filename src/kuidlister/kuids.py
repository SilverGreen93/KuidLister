"""The KUID listing logic, free of any GUI or terminal handling.

Port of the body of ``Button1_Click`` in frmMain.vb: find every kuid mention
in a chunk of text, drop the duplicates and join the survivors with commas --
optionally replacing each kuid by all of its asset versions from 0 up to a
chosen maximum.

Unlike the original, which split every kuid down to author and content id and
threw the version away, the plain listing keeps each token as it was written:
different versions of one asset stay separate entries and only exact repeats
collapse.  The author/id folding survives only where it belongs -- when a
version run is asked for (``upto``), so each asset expands exactly once.

The original ran over the whole text twice (once for the matches, once to
strip duplicates) and drove a progress bar with three passes; :func:`extract_kuids`
and :func:`list_kuids` keep those two stages apart so the GUI can report
progress between them, and each pass is a single ordered sweep instead of the
original's quadratic duplicate search.
"""

from __future__ import annotations

import re

__all__ = [
    "KUID_RE",
    "MAX_VERSION",
    "extract_kuids",
    "dedupe",
    "format_kuid",
    "format_token",
    "expand_versions",
    "list_kuids",
    "join",
]

# The same pattern as the VB.NET code: kuid or kuid2, an optional negative
# sign on each of the two numbers and an optional version number.  "KUID" in
# upper case matched too, so the pattern is case insensitive; the original's
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


def dedupe(kuids: list[str]) -> list[str]:
    """The kuids with exact repeats removed, keeping the first of each.

    Two mentions are the same when the whole token matches -- ``kuid2:A:C:3``
    and ``kuid2:A:C:4`` name two versions of an asset and stay separate entries,
    while a second ``kuid:A:C`` is dropped.  Keyed on the lower-cased token so
    ``KUID:7:8`` still folds onto ``kuid:7:8``, as it did in the VB.NET code;
    unlike there, the version written in a token is no longer discarded here --
    that folding now happens only for the version run, see :func:`list_kuids`.
    """

    unique: dict[str, str] = {}
    for token in kuids:
        unique.setdefault(token.lower(), token)
    return list(unique.values())


def format_kuid(author: int, content_id: int, version: int | None = None) -> str:
    """One kuid as it appears in the output list, brackets included.

    A version of zero is the first version of an asset and has no meaning of
    its own, so it is written as the plain ``<kuid:author:id>``; only versions
    from one up become ``<kuid2:author:id:version>``.  Trainz accepts either
    spelling for version zero, and the bare form is what a kuid copy normally
    shows.

    The VB.NET code had no such rule: it emitted ``<kuid2:author:id:0>`` for
    version zero, which is why this part of the output differs from 1.13.
    """
    if not version:
        return f"<kuid:{author}:{content_id}>"
    return f"<kuid2:{author}:{content_id}:{version}>"


def split_kuid(token: str) -> tuple[int, int]:
    """The author and content id of a kuid token as integers.

    ``token.split(":")[1]`` and ``[2]``, like the VB.NET code, but converted to
    numbers straight away: it compared the author against zero as a string, so
    only its negative sign was ever noticed.  Any version already written in
    the token is left out -- re-joining without it is what dropped it there.
    """
    parts = token.split(":")
    return int(parts[1]), int(parts[2])


def expand_versions(kuids: list[str], upto: int) -> list[str]:
    """Each kuid's asset versions from 0 to ``upto``, as formatted tokens.

    The assets are consecutive, so listing 0..n means n + 1 tokens with no
    repeats however many spellings of the same author/id pair the paste held
    (:func:`dedupe` folds them onto one first).  Version zero comes back as the
    plain kuid, see :func:`format_kuid`.

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

    Without ``upto`` (the checkbox off) every kuid is kept as it was written,
    version and all, with only exact repeats folded away -- so
    ``<kuid2:1234:12345:3> <kuid2:1234:12345:4>`` stays two entries.

    With ``upto`` set, each *asset* (author and content id) is replaced by one
    run of its versions from 0 to that number; every spelling of the same pair
    -- bare kuid or any versioned kuid2 -- folds onto that single run, so no
    author/id pair is expanded twice.

    An author/id pair is therefore listed once either way: as one token per
    distinct version when ``upto`` is off, or as one version run when it is on.
    """
    unique = dedupe(extract_kuids(text))
    if upto is None:
        return [format_token(token) for token in unique]
    pairs: dict[tuple[int, int], str] = {}
    for token in unique:
        pairs.setdefault(split_kuid(token), token)
    return expand_versions(list(pairs.values()), upto)


def format_token(token: str) -> str:
    """One extracted kuid token as it appears in the output list.

    The bare ``kuid:A:C`` becomes ``<kuid:A:C>``; a versioned ``kuid2:A:C:v``
    keeps its version verbatim, so ``<kuid2:A:C:0>`` stays spelled that way --
    "as written" wins over the zero rule here (that rule belongs to the version
    run, see :func:`format_kuid`).  Rebuilt from its parts so the odd casing of
    the original mention does not reach the output.
    """
    parts = token.split(":")
    if parts[0].lower() == "kuid2" and len(parts) > 3 and parts[3] != "":
        return f"<kuid2:{int(parts[1])}:{int(parts[2])}:{int(parts[3])}>"
    return format_kuid(int(parts[1]), int(parts[2]))


def join(tokens: list[str]) -> str:
    """The tokens separated by commas, no trailing comma.

    The VB.NET code appended a comma after every kuid and then cut the last
    one off the finished text.
    """
    return ",".join(tokens)
