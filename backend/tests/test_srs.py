"""Step-ladder SRS — same semantics as Android N3 Sensei's SpacedRepetitionScheduler."""

from datetime import UTC, datetime

import pytest

from app.database.enums import ReviewRating as R
from app.database.enums import SrsState
from app.reviews.srs import (
    DEFAULT_LADDER,
    NEW_ITEM,
    Ladder,
    next_step,
    resolve_zone,
    schedule,
    state_for,
)

L = Ladder.parse(DEFAULT_LADDER)
VN = resolve_zone("Asia/Ho_Chi_Minh")
T0 = datetime(2026, 3, 10, 2, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("current", "rating", "expected"),
    [
        (None, R.AGAIN, 0), (None, R.HARD, 0), (None, R.GOOD, 1), (None, R.EASY, 2),
        (3, R.AGAIN, 0), (3, R.HARD, 3), (3, R.GOOD, 4), (3, R.EASY, 5),
        (6, R.GOOD, 6), (5, R.EASY, 6), (99, R.HARD, 6),
    ],
)  # fmt: skip
def test_rating_table_matches_android(current: int | None, rating: R, expected: int) -> None:
    assert next_step(current, rating, L) == expected


def test_states_follow_the_ladder() -> None:
    assert [state_for(s, L) for s in range(7)] == [SrsState.LEARNING] * 2 + [
        SrsState.REVIEW
    ] * 4 + [SrsState.MASTERED]


def test_schedule_is_deterministic_and_counts() -> None:
    a = schedule(NEW_ITEM, R.GOOD, T0, VN, L)
    b = schedule(NEW_ITEM, R.GOOD, T0, VN, L)
    assert a == b
    assert (a.state, a.step_index, a.interval_minutes, a.review_count) == (
        SrsState.LEARNING,
        1,
        60,
        1,
    )
    assert a.due_at == datetime(2026, 3, 10, 3, 0, tzinfo=UTC)


def test_lapse_only_from_long_term() -> None:
    s = NEW_ITEM
    for r in (R.GOOD, R.GOOD, R.GOOD):  # → step 3 (2 days, REVIEW)
        s = schedule(s, r, T0, VN, L)
    assert s.state == SrsState.REVIEW
    lapsed = schedule(s, R.AGAIN, T0, VN, L)
    assert (lapsed.step_index, lapsed.lapse_count, lapsed.state) == (0, 1, SrsState.LEARNING)
    again = schedule(lapsed, R.AGAIN, T0, VN, L)
    assert again.lapse_count == 1  # learning items do not lapse


def test_calendar_months_clamp_and_local_time() -> None:
    s = schedule(NEW_ITEM, R.GOOD, T0, VN, L)
    s = s.__class__(**{**s.__dict__, "step_index": 5, "state": SrsState.REVIEW})
    at = datetime(2026, 1, 31, 1, 0, tzinfo=UTC)  # 08:00 in Vietnam
    nxt = schedule(s, R.GOOD, at, VN, L)  # step 6 = 1 month
    assert nxt.due_at == datetime(2026, 2, 28, 1, 0, tzinfo=UTC)  # Feb has no 31st


def test_day_steps_keep_local_clock_across_dst() -> None:
    ny = resolve_zone("America/New_York")
    s = NEW_ITEM.__class__(SrsState.LEARNING, 1, 60, None, None, 1, 0)
    at = datetime(2026, 3, 7, 14, 0, tzinfo=UTC)  # 09:00 EST, DST starts 2026-03-08
    nxt = schedule(s, R.GOOD, at, ny, L)  # step 2 = 1 day
    assert nxt.due_at == datetime(2026, 3, 8, 13, 0, tzinfo=UTC)  # 09:00 EDT next day
    assert nxt.interval_minutes == 23 * 60


def test_bad_inputs() -> None:
    with pytest.raises(ValueError):
        Ladder.parse("20m,0h")
    with pytest.raises(ValueError):
        resolve_zone("Mars/Base")
    with pytest.raises(ValueError):
        schedule(NEW_ITEM, R.GOOD, datetime(2026, 1, 1), VN, L)
