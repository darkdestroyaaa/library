"""Shared in-memory catalog for Contention Forecast.

This module owns the seed inventory. Other packages should read `BOOKS`
(or `get_books()`) and must not rebuild commitments here.
"""

from __future__ import annotations

import copy
import datetime

# Demo year matches the current prototype calendar (Aug 2026).
_YEAR = 2026


def _commitment(start: datetime.date, end: datetime.date, type: str) -> dict:
    return {"start_date": start, "end_date": end, "type": type}


def _copy(copy_id: str, book_title: str, commitments: list[dict] | None = None) -> dict:
    return {
        "copy_id": copy_id,
        "book_title": book_title,
        "status": "available",
        "commitments": list(commitments or []),
    }


def _book(title: str, category: str, copies: list[dict]) -> dict:
    return {
        "title": title,
        "category": category,
        "total_copies": len(copies),
        "copies": copies,
    }


def build_seed_catalog() -> list[dict]:
    """Return a fresh 5-book catalog with the required seed commitments."""
    clean_code = "Clean Code"
    intro_algs = "Introduction to Algorithms"
    design_patterns = "Design Patterns"
    pragmatic = "The Pragmatic Programmer"
    c_lang = "The C Programming Language"

    issued_until_aug_4 = _commitment(
        datetime.date(_YEAR, 7, 22),
        datetime.date(_YEAR, 8, 4),
        "issued",
    )
    reserved_aug_4_8 = _commitment(
        datetime.date(_YEAR, 8, 4),
        datetime.date(_YEAR, 8, 8),
        "reserved",
    )

    return [
        _book(
            clean_code,
            "Software Engineering",
            [
                _copy("CC-1", clean_code, [issued_until_aug_4]),
                _copy("CC-2", clean_code),
            ],
        ),
        _book(
            intro_algs,
            "Algorithms",
            [
                _copy("IA-1", intro_algs, [reserved_aug_4_8]),
                _copy("IA-2", intro_algs),
                _copy("IA-3", intro_algs),
            ],
        ),
        _book(
            design_patterns,
            "Software Engineering",
            [
                _copy("DP-1", design_patterns),
                _copy("DP-2", design_patterns),
            ],
        ),
        _book(
            pragmatic,
            "Software Engineering",
            [_copy("PP-1", pragmatic)],
        ),
        _book(
            c_lang,
            "Programming",
            [
                _copy("CL-1", c_lang),
                _copy("CL-2", c_lang),
            ],
        ),
    ]


# Live shared state. P3 mutates copy.commitments in place; P5 only reads.
BOOKS: list[dict] = build_seed_catalog()
INVENTORY = BOOKS


def get_books() -> list[dict]:
    """Return the live shared catalog (same list P3 mutates)."""
    return BOOKS


def get_inventory() -> list[dict]:
    return BOOKS


def snapshot_books() -> list[dict]:
    """Deep copy for tests or reset flows. Does not alter live commitments."""
    return copy.deepcopy(BOOKS)


def _find_commitment(title: str, type: str) -> dict | None:
    for book in BOOKS:
        if book["title"] != title:
            continue
        for copy in book["copies"]:
            for commitment in copy["commitments"]:
                if commitment["type"] == type:
                    return commitment
    return None


if __name__ == "__main__":
    assert len(BOOKS) == 5, "seed must contain exactly 5 books"
    assert all(book["total_copies"] == len(book["copies"]) for book in BOOKS)
    copy_counts = {book["title"]: book["total_copies"] for book in BOOKS}
    assert copy_counts["Clean Code"] == 2
    assert copy_counts["Introduction to Algorithms"] == 3
    assert copy_counts["Design Patterns"] == 2
    assert copy_counts["The Pragmatic Programmer"] == 1
    assert copy_counts["The C Programming Language"] == 2

    issued = _find_commitment("Clean Code", "issued")
    assert issued is not None
    assert issued["end_date"] == datetime.date(_YEAR, 8, 4)
    assert isinstance(issued["start_date"], datetime.date)

    reserved = _find_commitment("Introduction to Algorithms", "reserved")
    assert reserved is not None
    assert reserved["start_date"] == datetime.date(_YEAR, 8, 4)
    assert reserved["end_date"] == datetime.date(_YEAR, 8, 8)

    print("seed_data integrity checks passed")
    print("copy counts:", copy_counts)
