"""P3 — booking confirmation and in-memory state mutation."""

from __future__ import annotations

import datetime
from typing import Any, Iterable, Optional

# Optional override used by the standalone tests at the bottom of this file.
_TEST_INVENTORY: Optional[list] = None

FLASH_SUCCESS_KEY = "p3_booking_success"
INVENTORY_REVISION_KEY = "inventory_revision"


def _as_date(value: Any) -> datetime.date:
    """Normalize date-like values to datetime.date (app-wide contract)."""
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    if isinstance(value, str):
        return datetime.date.fromisoformat(value[:10])
    date_fn = getattr(value, "date", None)
    if callable(date_fn):
        converted = date_fn()
        if isinstance(converted, datetime.date):
            return converted
    raise TypeError(f"Cannot convert {value!r} to datetime.date")


def _field(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _iter_copies(inventory: Iterable[Any]) -> Iterable[Any]:
    for book in inventory or []:
        copies = _field(book, "copies", []) or []
        for copy in copies:
            yield copy


def _get_inventory() -> list:
    """Resolve the live catalog: test override → Streamlit session → seed_data."""
    if _TEST_INVENTORY is not None:
        return _TEST_INVENTORY

    try:
        import streamlit as st

        session = getattr(st, "session_state", None)
        if session is not None:
            for key in ("books", "inventory", "catalog"):
                if key in session and session[key]:
                    return session[key]
    except Exception:
        pass

    try:
        import seed_data
    except ImportError:
        return []

    for name in ("BOOKS", "INVENTORY", "books", "inventory", "catalog"):
        value = getattr(seed_data, name, None)
        if value:
            return value

    for name in ("get_books", "get_inventory", "load_seed_data", "get_catalog"):
        loader = getattr(seed_data, name, None)
        if callable(loader):
            value = loader()
            if value:
                return value

    return []


def _parse_availability(result: Any) -> tuple[bool, Optional[str]]:
    if result is None:
        return False, None
    if isinstance(result, tuple) and len(result) >= 1:
        success = bool(result[0])
        copy_id = result[1] if len(result) > 1 else None
        return success, copy_id
    if isinstance(result, dict):
        success = bool(result.get("success", result.get("available", False)))
        copy_id = result.get("copy_id") or result.get("assigned_copy_id")
        return success, copy_id
    success = bool(getattr(result, "success", getattr(result, "available", False)))
    copy_id = getattr(result, "copy_id", None) or getattr(result, "assigned_copy_id", None)
    return success, copy_id


def _append_commitment(copy: Any, commitment: dict) -> None:
    existing = _field(copy, "commitments", None)
    if existing is None:
        if isinstance(copy, dict):
            copy["commitments"] = [commitment]
        else:
            copy.commitments = [commitment]
        return
    existing.append(commitment)


def commit_copy(
    copy_id: str,
    start_date: datetime.date,
    end_date: datetime.date,
    type: str = "reserved",
) -> bool:
    """Append a commitment to the matching copy. Returns False if copy_id is unknown."""
    if not copy_id:
        return False

    start = _as_date(start_date)
    end = _as_date(end_date)
    commitment = {"start_date": start, "end_date": end, "type": type}

    for copy in _iter_copies(_get_inventory()):
        if _field(copy, "copy_id") == copy_id:
            _append_commitment(copy, commitment)
            return True
    return False


def _delegate_to_p4(result: Any, book_title: str, start_date: datetime.date, end_date: datetime.date) -> Any:
    """Hand an unsuccessful availability check to P4 without mutating inventory."""
    try:
        import rejection
    except ImportError:
        return result

    for name in ("handle_rejection", "handle_unavailable", "show_rejection"):
        handler = getattr(rejection, name, None)
        if callable(handler):
            try:
                return handler(result, book_title, start_date, end_date)
            except TypeError:
                try:
                    return handler(result)
                except TypeError:
                    continue
    return result


def _bump_heatmap_revision() -> None:
    """Signal P1 that inventory changed so the heatmap re-renders on rerun."""
    try:
        import streamlit as st

        session = getattr(st, "session_state", None)
        if session is None:
            return
        session[INVENTORY_REVISION_KEY] = int(session.get(INVENTORY_REVISION_KEY, 0) or 0) + 1
        inventory = _get_inventory()
        if inventory and "books" not in session:
            session["books"] = inventory
    except Exception:
        pass


def handle_booking_submission(
    book_title: str,
    start_date: datetime.date,
    end_date: datetime.date,
) -> Any:
    """Validate via P2, commit via P3 on success, otherwise return/delegate to P4."""
    from validation import check_availability

    start = _as_date(start_date)
    end = _as_date(end_date)
    result = check_availability(book_title, start, end)
    success, copy_id = _parse_availability(result)

    if not success:
        return _delegate_to_p4(result, book_title, start, end)

    if not copy_id or not commit_copy(copy_id, start, end):
        return _delegate_to_p4(result, book_title, start, end)

    message = f"Successfully booked copy {copy_id} from {start} to {end}!"
    try:
        import streamlit as st

        st.session_state[FLASH_SUCCESS_KEY] = message
        _bump_heatmap_revision()
        st.success(message)
        if hasattr(st, "rerun"):
            st.rerun()
        elif hasattr(st, "experimental_rerun"):
            st.experimental_rerun()
    except Exception:
        pass
    return True


if __name__ == "__main__":
    inventory = [
        {
            "title": "Test Book",
            "category": "Fiction",
            "total_copies": 2,
            "copies": [
                {
                    "copy_id": "TB-1",
                    "book_title": "Test Book",
                    "status": "available",
                    "commitments": [],
                },
                {
                    "copy_id": "TB-2",
                    "book_title": "Test Book",
                    "status": "available",
                    "commitments": [
                        {
                            "start_date": datetime.date(2026, 1, 1),
                            "end_date": datetime.date(2026, 1, 5),
                            "type": "reserved",
                        }
                    ],
                },
            ],
        }
    ]
    _TEST_INVENTORY = inventory

    start = datetime.date(2026, 3, 10)
    end = datetime.date(2026, 3, 12)

    ok = commit_copy("TB-1", start, end)
    assert ok is True, "expected True for a valid copy_id"
    commitments = inventory[0]["copies"][0]["commitments"]
    assert len(commitments) == 1, "commitment should be appended"
    assert commitments[0] == {"start_date": start, "end_date": end, "type": "reserved"}
    assert isinstance(commitments[0]["start_date"], datetime.date)
    assert isinstance(commitments[0]["end_date"], datetime.date)

    ok = commit_copy("TB-1", "2026-04-01", datetime.datetime(2026, 4, 3, 9, 0, 0), type="reserved")
    assert ok is True
    assert commitments[1]["start_date"] == datetime.date(2026, 4, 1)
    assert commitments[1]["end_date"] == datetime.date(2026, 4, 3)

    assert commit_copy("DOES-NOT-EXIST", start, end) is False
    assert len(inventory[0]["copies"][1]["commitments"]) == 1, "other copies must be untouched"

    print("commit_copy tests passed")
    print("TB-1 commitments:", commitments)
