"""Tests for kuidlister.kuids: finding kuids, filtering duplicates and
generating the asset versions up to a chosen number."""

from __future__ import annotations

import random

import pytest

from kuidlister.kuids import (
    MAX_VERSION,
    dedupe,
    expand_versions,
    extract_kuids,
    format_kuid,
    join,
    list_kuids,
    split_kuid,
)

# the two lines a Content Manager copy actually looks like
SAMPLE = """Unknown location: <kuid:1234:12345>
Modified: <kuid2:4321:54321:2>"""


# ---------------------------------------------------------------------------
# finding the kuid mentions
# ---------------------------------------------------------------------------

def test_finds_both_kinds_of_kuid():
    assert extract_kuids(SAMPLE) == ["kuid:1234:12345", "kuid2:4321:54321:2"]


def test_keeps_the_order_and_the_duplicates():
    text = "<kuid:2:2><kuid:1:1><kuid:2:2>"
    assert extract_kuids(text) == ["kuid:2:2", "kuid:1:1", "kuid:2:2"]


def test_ignores_text_that_is_not_a_kuid():
    assert extract_kuids("no kuids here, just a kuid-less sentence") == []


def test_uppercase_kuid_matches_too():
    assert extract_kuids("KUID:7:8 and Kuid2:9:10:3") == ["KUID:7:8", "Kuid2:9:10:3"]


def test_negative_numbers_match():
    assert extract_kuids("<kuid:-1:50>") == ["kuid:-1:50"]


def test_dedupe_keeps_the_first_of_each():
    assert dedupe(["kuid:1:1", "kuid:2:2", "kuid:1:1", "kuid:3:3", "kuid:2:2"]) == [
        "kuid:1:1",
        "kuid:2:2",
        "kuid:3:3",
    ]


def test_a_version_in_the_input_is_the_same_asset_as_the_bare_kuid():
    """The VB.NET code compared author and content id only.

    ``kuid2:1:2:7`` written after ``kuid:1:2`` is the same asset, so it is
    dropped and the first spelling is the one kept.
    """
    assert dedupe(["kuid:1:2", "kuid2:1:2:7"]) == ["kuid:1:2"]
    assert dedupe(["kuid2:1:2:7", "kuid:1:2"]) == ["kuid2:1:2:7"]


# ---------------------------------------------------------------------------
# splitting and formatting one kuid
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "token, author, content_id",
    [
        ("kuid:1234:12345", 1234, 12345),
        ("kuid2:4321:54321:2", 4321, 54321),
        ("kuid:-1:50", -1, 50),
    ],
)
def test_split_kuid_reads_author_and_content_id(token, author, content_id):
    assert split_kuid(token) == (author, content_id)


def test_format_kuid_with_and_without_a_version():
    assert format_kuid(1234, 12345) == "<kuid:1234:12345>"
    assert format_kuid(1234, 12345, 7) == "<kuid2:1234:12345:7>"


def test_version_zero_is_written_as_a_plain_kuid():
    """There is no ``<kuid:1:2:0>`` and no ``<kuid2:1:2:0>``.

    Version zero is the first version of an asset, so it carries nothing the
    bare kuid does not already say; every token for it comes back as
    ``<kuid:author:id>``.
    """
    assert format_kuid(1234, 12345, 0) == "<kuid:1234:12345>"
    assert format_kuid(-3, 4, 0) == "<kuid:-3:4>"


# ---------------------------------------------------------------------------
# negative author and content id numbers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "text, expected",
    [
        ("<kuid:-1234:-12345>", ["kuid:-1234:-12345"]),
        ("<kuid:-1234:12345>", ["kuid:-1234:12345"]),
        ("<kuid:1234:-12345>", ["kuid:1234:-12345"]),
        ("<kuid2:1234:-12345:2>", ["kuid2:1234:-12345:2"]),
    ],
)
def test_a_minus_sign_on_either_number_still_matches(text, expected):
    """All four spellings of a negative kuid are found.

    The pattern allows a sign on the author and on the content id separately;
    it never lets one carry over onto the other.
    """
    assert extract_kuids(text) == expected


def test_all_four_negative_spellings_are_listed():
    text = (
        "<kuid:-1234:-12345> <kuid:-1234:12345> "
        "<kuid:1234:-12345> <kuid2:1234:-12345:2>"
    )
    assert list_kuids(text) == [
        "<kuid:-1234:-12345>",
        "<kuid:-1234:12345>",
        "<kuid:1234:-12345>",
    ]


def test_negative_numbers_survive_the_split():
    assert split_kuid("kuid:-1234:-12345") == (-1234, -12345)
    assert split_kuid("kuid2:1234:-12345:2") == (1234, -12345)


def test_a_negative_content_id_still_gets_its_versions():
    """Only a negative *author* skips the version run; the id may be negative."""
    assert list_kuids("<kuid:1234:-12345>", upto=1) == [
        "<kuid:1234:-12345>",
        "<kuid2:1234:-12345:1>",
    ]


def test_negative_authors_are_listed_once_even_with_upto():
    """Built-in content below zero has no versions, in any spelling."""
    text = "<kuid:-1:50> <kuid2:-1:50:7>"
    assert list_kuids(text, upto=4) == ["<kuid:-1:50>"]


# ---------------------------------------------------------------------------
# the list without versions: checkbox off, no --upto
# ---------------------------------------------------------------------------

def test_lists_each_unique_kuid_once():
    assert list_kuids(SAMPLE) == ["<kuid:1234:12345>", "<kuid:4321:54321>"]


def test_a_repeat_is_listed_once():
    text = "<kuid:1234:12345> again <kuid:1234:12345>"
    assert list_kuids(text) == ["<kuid:1234:12345>"]


def test_a_version_written_in_the_input_is_dropped():
    """kuid2:4321:54321:2 becomes <kuid:4321:54321>.

    The VB.NET code split every kuid into author and content id and joined
    those two back together, so the version in the text never survived; the
    port re-joins them the same way.
    """
    assert list_kuids("<kuid2:4321:54321:2>") == ["<kuid:4321:54321>"]


def test_a_kuid2_repeat_of_a_kuid_adds_nothing():
    assert list_kuids("<kuid:1:2> and <kuid2:1:2:9>") == ["<kuid:1:2>"]


def test_two_versions_of_one_asset_fold_onto_a_single_kuid():
    """``:3`` and ``:4`` of the same author/id name one asset, not two.

    The VB.NET code keyed on author and content id only, so both spellings
    collapse to a single entry and the version written in the text is dropped;
    what they share is that pair, which is also why either one expands to the
    same 0..n run of versions.

    NOTE: this is VB-1.13 behaviour.  If ``:3`` and ``:4`` are meant to stay two
    separate tokens in the plain listing (see README / the open question), only
    the ``upto is None`` branch changes -- the version-run behaviour below stays.
    """
    text = "<kuid2:1234:12345:3> <kuid2:1234:12345:4>"
    assert list_kuids(text) == ["<kuid:1234:12345>"]
    assert len(list_kuids(text, upto=5)) == 6


def test_the_first_spelling_of_a_pair_is_the_one_kept():
    """A repeat never changes the order or brings back a version number."""
    assert list_kuids("<kuid:1:2> <kuid:1:2> <kuid:3:4>") == ["<kuid:1:2>", "<kuid:3:4>"]
    assert list_kuids("<kuid2:1:2:9> <kuid:1:2>") == ["<kuid:1:2>"]


def test_three_spelling_variants_of_one_pair_collapse_to_one():
    text = "<kuid:7:8> <kuid2:7:8:0> <kuid2:7:8:12> <KUID:7:8>"
    assert list_kuids(text) == ["<kuid:7:8>"]
    assert len(list_kuids(text, upto=3)) == 4


def test_nothing_in_gives_nothing_out():
    assert list_kuids("no kuids here") == []


# ---------------------------------------------------------------------------
# generating the versions up to a number: checkbox on, --upto N
# ---------------------------------------------------------------------------

def test_versions_run_from_zero_up_to_the_limit():
    assert list_kuids("<kuid:1234:12345>", upto=2) == [
        "<kuid:1234:12345>",
        "<kuid2:1234:12345:1>",
        "<kuid2:1234:12345:2>",
    ]


def test_upto_zero_lists_only_version_zero():
    assert list_kuids("<kuid:1234:12345>", upto=0) == ["<kuid:1234:12345>"]


def test_the_run_starts_with_a_plain_kuid_and_never_writes_a_zero_version():
    """``<kuid:a:c>``, ``<kuid2:a:c:1>``, ``<kuid2:a:c:2>`` ...

    Version zero is the bare kuid, so no token in the output ends in ``:0>``.
    """
    tokens = list_kuids("<kuid:1234:12345>", upto=3)
    assert tokens == [
        "<kuid:1234:12345>",
        "<kuid2:1234:12345:1>",
        "<kuid2:1234:12345:2>",
        "<kuid2:1234:12345:3>",
    ]
    assert not any(token.endswith(":0>") for token in tokens)


def test_versions_of_one_asset_are_never_duplicated():
    """One author/id pair gives one run of versions, however often it appears.

    The paste can name the same asset four times, in mixed spellings; with the
    version limit on it still produces a single 0..n sequence for it.
    """
    text = (
        "<kuid:1234:12345> <kuid2:1234:12345:3> <kuid:1234:12345> "
        "<kuid2:1234:12345:4>"
    )
    tokens = list_kuids(text, upto=2)
    assert tokens == [
        "<kuid:1234:12345>",
        "<kuid2:1234:12345:1>",
        "<kuid2:1234:12345:2>",
    ]
    assert len(tokens) == 3


def test_the_version_run_has_no_repeats_at_any_limit():
    for upto in (0, 1, 7, MAX_VERSION):
        tokens = list_kuids("<kuid:5:6> <kuid2:5:6:9>", upto=upto)
        assert len(tokens) == upto + 1
        assert len(set(tokens)) == len(tokens)


def test_each_kuid_gets_its_own_versions():
    assert list_kuids(SAMPLE, upto=1) == [
        "<kuid:1234:12345>",
        "<kuid2:1234:12345:1>",
        "<kuid:4321:54321>",
        "<kuid2:4321:54321:1>",
    ]


def test_versions_are_generated_after_filtering_duplicates():
    """The repeat is expanded once, not twice."""
    text = "<kuid:1234:12345> and <kuid:1234:12345>"
    assert len(list_kuids(text, upto=3)) == 4


def test_negative_author_has_no_versions():
    """Built-in content (author below zero) is listed as a plain kuid."""
    assert list_kuids("<kuid:-1:50>", upto=3) == ["<kuid:-1:50>"]


def test_the_limit_is_inclusive_and_counts_up_from_zero():
    for upto in (0, 1, 5, MAX_VERSION):
        assert len(list_kuids("<kuid:1234:12345>", upto=upto)) == upto + 1


# ---------------------------------------------------------------------------
# random kuids: generated here, checked against what was generated
# ---------------------------------------------------------------------------

def test_random_kuids_are_all_listed():
    """A handful of random kuids pasted as CM lines come back in full.

    Two of them are repeated as kuid2 with a version written in, which the
    list must fold back onto the same author/id pair: each pair appears once,
    in the order it was first seen.
    """
    rng = random.Random(20240601)
    kuids = [(rng.randint(1, 99999), rng.randint(1, 999999)) for _ in range(8)]
    repeats = [kuids[1], kuids[5]]

    lines = [f"Unknown location: <kuid:{a}:{c}>" for a, c in kuids]
    lines += [f"Modified: <kuid2:{a}:{c}:{rng.randint(0, 9)}>" for a, c in repeats]
    text = "\n".join(lines)

    expected = [f"<kuid:{a}:{c}>" for a, c in dict.fromkeys(kuids)]
    assert list_kuids(text) == expected


def test_random_kuids_are_expanded_to_the_limit():
    rng = random.Random(12345)
    kuids = [(rng.randint(1, 9999), rng.randint(1, 99999)) for _ in range(5)]
    upto = 4

    text = "\n".join(f"Unknown location: <kuid:{a}:{c}>" for a, c in kuids)
    tokens = list_kuids(text, upto=upto)

    assert len(tokens) == len(kuids) * (upto + 1)
    assert tokens == [
        format_kuid(a, c, version)
        for a, c in kuids
        for version in range(upto + 1)
    ]
    # and no explicit zero version anywhere in the run
    assert not any(token.endswith(":0>") for token in tokens)


# ---------------------------------------------------------------------------
# joining for display
# ---------------------------------------------------------------------------

def test_join_separates_with_commas_and_has_no_trailing_one():
    assert join(["<kuid:1:2>", "<kuid:3:4>"]) == "<kuid:1:2>,<kuid:3:4>"
    assert join([]) == ""


def test_expand_versions_takes_a_list_of_bare_tokens():
    assert expand_versions(["kuid:1:2", "kuid:-3:4"], 1) == [
        "<kuid:1:2>",
        "<kuid2:1:2:1>",
        "<kuid:-3:4>",
    ]
