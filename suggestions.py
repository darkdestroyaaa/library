"""P5 — nearest available slot suggestions (read-only)."""

from __future__ import annotations

import datetime
from typing import Any, Callable, Optional

# Tests may inject a checker so interval math can run without Streamlit/P2.
_CHECK_AVAILABILITY: Optional[Callable[..., dict]] = None

SESSION_START_KEYS = ("start_date", "booking_start", "requested_start")
SESSION_END_KEYS = ("end_date", "booking_end", "requested_end")


def _as_date(value: Any) -> datetime.date:
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    if isinstance(value, str):
        return datetime.date.fromisoformat(value[:10])
    raise TypeError(f"Cannot convert {value!r} to datetime.date")


def _not_found() -> dict:
    return {"found": False, "suggested_start": None, "suggested_end": None}


def _check_availability(book_title: str, start_date: datetime.date, end_date: datetime.date) -> dict:
    checker = _CHECK_AVAILABILITY
    if checker is None:
        from validation import check_availability as checker
    result = checker(book_title, start_date, end_date)
    if not isinstance(result, dict):
        return {"success": False}
    return result


def find_nearest_available(
    book_title: str,
    requested_start: datetime.date,
    requested_end: datetime.date,
    search_window_days: int = 14,
) -> dict:
    """Find the nearest continuous slot of the requested duration within ±window days.

    Search order: original start, then ±1, ±2, … (forward before backward on ties).
    Read-only: availability is delegated to validation.check_availability.
    """
    requested_start = _as_date(requested_start)
    requested_end = _as_date(requested_end)
    duration = (requested_end - requested_start).days + 1
    if duration < 1 or search_window_days < 0:
        return _not_found()

    for distance in range(0, search_window_days + 1):
        deltas = (0,) if distance == 0 else (distance, -distance)
        for delta in deltas:
            suggested_start = requested_start + datetime.timedelta(days=delta)
            suggested_end = suggested_start + datetime.timedelta(days=duration - 1)
            result = _check_availability(book_title, suggested_start, suggested_end)
            if result.get("success") is True:
                return {
                    "found": True,
                    "suggested_start": suggested_start,
                    "suggested_end": suggested_end,
                }

    return _not_found()


def render_suggestions_panel(
    book_title: str,
    start_date: datetime.date,
    end_date: datetime.date,
) -> dict:
    """Show an alternate window (or a 14-day fallback) without mutating inventory."""
    import streamlit as st

    suggestion = find_nearest_available(book_title, start_date, end_date)
    if suggestion.get("found"):
        suggested_start = suggestion["suggested_start"]
        suggested_end = suggestion["suggested_end"]
        st.info(
            f"Nearest available window for **{book_title}**: "
            f"{suggested_start} to {suggested_end}."
        )
        if st.button("Use these dates", key=f"p5_apply_{book_title}_{suggested_start}"):
            for key in SESSION_START_KEYS:
                st.session_state[key] = suggested_start
            for key in SESSION_END_KEYS:
                st.session_state[key] = suggested_end
            if hasattr(st, "rerun"):
                st.rerun()
            elif hasattr(st, "experimental_rerun"):
                st.experimental_rerun()
    else:
        st.warning(
            "No alternative slots are open in the visible 14-day window."
        )
    return suggestion


if __name__ == "__main__":
    blocked_start = datetime.date(2026, 8, 4)
    blocked_end = datetime.date(2026, 8, 8)

    def fake_check(book_title: str, start: datetime.date, end: datetime.date) -> dict:
        overlaps = start <= blocked_end and end >= blocked_start
        return {"success": not overlaps}

    _CHECK_AVAILABILITY = fake_check

    # Inclusive duration: Aug 4–4 is 1 day.
    one_day = find_nearest_available(
        "Introduction to Algorithms",
        datetime.date(2026, 8, 4),
        datetime.date(2026, 8, 4),
    )
    assert one_day["found"] is True
    # |offset|=1 backward (Aug 3) is nearer than jumping to Aug 9.
    assert one_day["suggested_start"] == datetime.date(2026, 8, 3)
    assert one_day["suggested_end"] == datetime.date(2026, 8, 3)
    assert (one_day["suggested_end"] - one_day["suggested_start"]).days + 1 == 1

    # Five-day request overlapping the block: nearest 5-day gap is a 5-day shift.
    five_day = find_nearest_available(
        "Introduction to Algorithms",
        datetime.date(2026, 8, 4),
        datetime.date(2026, 8, 8),
    )
    assert five_day["found"] is True
    duration = (datetime.date(2026, 8, 8) - datetime.date(2026, 8, 4)).days + 1
    assert duration == 5
    assert (five_day["suggested_end"] - five_day["suggested_start"]).days + 1 == 5
    # Tie at ±5: prefer forward (Aug 9–13) over backward (Jul 30–Aug 3).
    assert five_day["suggested_start"] == datetime.date(2026, 8, 9)
    assert five_day["suggested_end"] == datetime.date(2026, 8, 13)

    def always_busy(*_args, **_kwargs) -> dict:
        return {"success": False}

    _CHECK_AVAILABILITY = always_busy
    none = find_nearest_available(
        "Clean Code",
        datetime.date(2026, 8, 4),
        datetime.date(2026, 8, 6),
        search_window_days=14,
    )
    assert none == {"found": False, "suggested_start": None, "suggested_end": None}

    print("find_nearest_available interval tests passed")
    print("1-day suggestion:", one_day)
    print("5-day suggestion:", five_day)
