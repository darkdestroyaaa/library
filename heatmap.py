"""P1 — read-only 14-day copy availability heatmap."""

from __future__ import annotations

import datetime
import html
from typing import Any, Iterable, Optional

WINDOW_DAYS = 14
DEFAULT_REFERENCE_DATE = datetime.date(2026, 8, 4)

COLOR_AVAILABLE = "#2ECC71"
COLOR_COMMITTED = "#E74C3C"
COLOR_UNAVAILABLE = "#95A5A6"

STATUS_AVAILABLE = "available"
STATUS_RESERVED = "reserved"
STATUS_ISSUED = "issued"
STATUS_UNAVAILABLE = "unavailable"

_TEST_INVENTORY: Optional[list] = None


def _as_date(value: Any) -> datetime.date:
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


def _get_inventory() -> list:
    """Read live catalog: test override → Streamlit session → seed_data. Never writes."""
    if _TEST_INVENTORY is not None:
        return _TEST_INVENTORY

    try:
        import streamlit as st

        session = getattr(st, "session_state", None)
        if session is not None and session.get("books"):
            return session["books"]
    except Exception:
        pass

    try:
        import seed_data

        books = getattr(seed_data, "BOOKS", None)
        if books:
            return books
        getter = getattr(seed_data, "get_books", None)
        if callable(getter):
            return getter() or []
    except ImportError:
        pass
    return []


def window_dates(start_reference_date: datetime.date | None = None) -> list[datetime.date]:
    start = _as_date(start_reference_date or DEFAULT_REFERENCE_DATE)
    return [start + datetime.timedelta(days=offset) for offset in range(WINDOW_DAYS)]


def _date_in_range(day: datetime.date, start: Any, end: Any) -> bool:
    return _as_date(start) <= day <= _as_date(end)


def status_for_copy_on_date(copy: Any, day: datetime.date) -> str:
    """Map a copy+day to available / reserved / issued / unavailable (read-only)."""
    copy_status = str(_field(copy, "status") or STATUS_AVAILABLE).lower()
    if copy_status in ("unavailable", "retired", "lost", "maintenance"):
        return STATUS_UNAVAILABLE

    matched: Optional[str] = None
    for commitment in _field(copy, "commitments", []) or []:
        if not _date_in_range(day, _field(commitment, "start_date"), _field(commitment, "end_date")):
            continue
        ctype = str(_field(commitment, "type") or STATUS_RESERVED).lower()
        if ctype == STATUS_ISSUED:
            return STATUS_ISSUED
        matched = STATUS_RESERVED if ctype != STATUS_AVAILABLE else matched
        if ctype in (STATUS_RESERVED, "committed", "booked"):
            matched = STATUS_RESERVED
        elif matched is None:
            matched = STATUS_RESERVED
    return matched or STATUS_AVAILABLE


def color_for_status(status: str) -> str:
    if status in (STATUS_RESERVED, STATUS_ISSUED):
        return COLOR_COMMITTED
    if status == STATUS_UNAVAILABLE:
        return COLOR_UNAVAILABLE
    return COLOR_AVAILABLE


def get_book_state(book_title: str) -> dict:
    """Return copy IDs and commitment ranges for a title. Does not mutate state."""
    inventory: Iterable[Any] = _get_inventory()
    selected = None
    for book in inventory or []:
        title = _field(book, "title")
        if title == book_title:
            selected = book
            break
    if selected is None:
        needle = (book_title or "").strip().lower()
        for book in inventory or []:
            if str(_field(book, "title") or "").strip().lower() == needle:
                selected = book
                break

    if selected is None:
        return {
            "found": False,
            "title": book_title,
            "category": None,
            "total_copies": 0,
            "copies": [],
        }

    copies = []
    for copy in _field(selected, "copies", []) or []:
        commitments = []
        for commitment in _field(copy, "commitments", []) or []:
            commitments.append(
                {
                    "start_date": _as_date(_field(commitment, "start_date")),
                    "end_date": _as_date(_field(commitment, "end_date")),
                    "type": _field(commitment, "type") or STATUS_RESERVED,
                }
            )
        copies.append(
            {
                "copy_id": _field(copy, "copy_id"),
                "status": _field(copy, "status") or STATUS_AVAILABLE,
                "commitments": commitments,
                "_raw": copy,
            }
        )

    return {
        "found": True,
        "title": _field(selected, "title"),
        "category": _field(selected, "category"),
        "total_copies": _field(selected, "total_copies", len(copies)),
        "copies": copies,
    }


def build_heatmap_matrix(
    book_title: str,
    start_reference_date: datetime.date | None = None,
) -> dict:
    """Pure matrix used by the UI and by standalone tests."""
    days = window_dates(start_reference_date)
    state = get_book_state(book_title)
    rows = []
    for index, copy in enumerate(state["copies"], start=1):
        cells = [status_for_copy_on_date(copy.get("_raw", copy), day) for day in days]
        rows.append(
            {
                "label": f"Copy {index}",
                "copy_id": copy["copy_id"],
                "statuses": cells,
            }
        )
    return {"found": state["found"], "title": state["title"], "days": days, "rows": rows}


def _legend_html() -> str:
    swatch = (
        '<span style="display:inline-block;width:12px;height:12px;'
        'border-radius:2px;margin-right:6px;vertical-align:middle;'
        'background:{color};"></span>'
    )
    items = [
        (COLOR_AVAILABLE, "Available"),
        (COLOR_COMMITTED, "Reserved / issued"),
        (COLOR_UNAVAILABLE, "Unavailable"),
    ]
    chips = " &nbsp;&nbsp; ".join(
        f'{swatch.format(color=color)}<span>{html.escape(label)}</span>' for color, label in items
    )
    return f'<div style="font-size:0.9rem;margin:0.4rem 0 0.75rem 0;">{chips}</div>'


def _grid_html(matrix: dict) -> str:
    header_cells = "".join(
        f'<th style="padding:6px 8px;border:1px solid #ddd;background:#f7f7f7;'
        f'font-weight:600;white-space:nowrap;">{html.escape(day.strftime("%b %d"))}</th>'
        for day in matrix["days"]
    )
    body_rows = []
    for row in matrix["rows"]:
        label = html.escape(f'{row["label"]} ({row["copy_id"]})')
        cells = [
            f'<td title="{html.escape(row["copy_id"])} {day.isoformat()} — {html.escape(status)}" '
            f'style="padding:8px;border:1px solid #fff;text-align:center;'
            f'background:{color_for_status(status)};color:#fff;font-size:0.75rem;'
            f'text-transform:capitalize;">{html.escape(status)}</td>'
            for day, status in zip(matrix["days"], row["statuses"])
        ]
        body_rows.append(
            f'<tr><th style="padding:6px 10px;border:1px solid #ddd;text-align:left;'
            f'white-space:nowrap;background:#fafafa;">{label}</th>{"".join(cells)}</tr>'
        )
    if not body_rows:
        body_rows.append(
            f'<tr><td colspan="{1 + WINDOW_DAYS}" style="padding:12px;text-align:center;'
            f'background:{COLOR_UNAVAILABLE};color:#fff;">No copies to display.</td></tr>'
        )
    return (
        '<div style="overflow-x:auto;">'
        '<table style="border-collapse:collapse;width:100%;font-family:sans-serif;">'
        f'<thead><tr><th style="padding:6px 10px;border:1px solid #ddd;background:#f7f7f7;">Copy</th>'
        f"{header_cells}</tr></thead>"
        f'<tbody>{"".join(body_rows)}</tbody></table></div>'
    )


def render_heatmap(book_title: str, start_reference_date: datetime.date = None) -> dict:
    """Render the 14-day copy grid in Streamlit. Safe to call on every rerun."""
    matrix = build_heatmap_matrix(book_title, start_reference_date)
    try:
        import streamlit as st
    except ImportError:
        return matrix

    start = matrix["days"][0] if matrix["days"] else DEFAULT_REFERENCE_DATE
    end = matrix["days"][-1] if matrix["days"] else start
    st.subheader(f"Availability heatmap — {matrix['title']}")
    st.caption(f"{WINDOW_DAYS}-day window: {start.isoformat()} to {end.isoformat()}")
    st.markdown(_legend_html(), unsafe_allow_html=True)
    if not matrix["found"]:
        st.warning(f'No book named "{book_title}" was found in the catalog.')
    st.markdown(_grid_html(matrix), unsafe_allow_html=True)
    return matrix


if __name__ == "__main__":
    import copy

    import seed_data

    snapshot = copy.deepcopy(seed_data.BOOKS)
    _TEST_INVENTORY = snapshot
    ref = DEFAULT_REFERENCE_DATE

    state = get_book_state("Clean Code")
    assert state["found"] is True
    assert [c["copy_id"] for c in state["copies"]] == ["CC-1", "CC-2"]
    cc1 = next(c for c in state["copies"] if c["copy_id"] == "CC-1")
    assert cc1["commitments"][0]["end_date"] == datetime.date(2026, 8, 4)
    assert cc1["commitments"][0]["type"] == "issued"

    matrix = build_heatmap_matrix("Clean Code", ref)
    assert len(matrix["days"]) == 14
    assert matrix["days"][0] == ref
    assert matrix["days"][-1] == ref + datetime.timedelta(days=13)
    cc1_row = next(r for r in matrix["rows"] if r["copy_id"] == "CC-1")
    cc2_row = next(r for r in matrix["rows"] if r["copy_id"] == "CC-2")
    assert cc1_row["statuses"][0] == STATUS_ISSUED
    assert cc1_row["statuses"][1] == STATUS_AVAILABLE
    assert all(status == STATUS_AVAILABLE for status in cc2_row["statuses"])
    assert color_for_status(STATUS_ISSUED) == COLOR_COMMITTED
    assert color_for_status(STATUS_AVAILABLE) == COLOR_AVAILABLE

    ia = build_heatmap_matrix("Introduction to Algorithms", ref)
    ia1 = next(r for r in ia["rows"] if r["copy_id"] == "IA-1")
    assert ia1["statuses"][:5] == [STATUS_RESERVED] * 5
    assert ia1["statuses"][5] == STATUS_AVAILABLE

    missing = get_book_state("Not A Real Book")
    assert missing["found"] is False
    assert missing["copies"] == []

    original = copy.deepcopy(seed_data.BOOKS)
    _ = build_heatmap_matrix("Clean Code", ref)
    assert seed_data.BOOKS == original, "heatmap must not mutate shared seed state"

    print("heatmap read-only tests passed")
    print("Clean Code CC-1 on window start:", cc1_row["statuses"][0])
    print("Intro to Algorithms IA-1 first 6 days:", ia1["statuses"][:6])
