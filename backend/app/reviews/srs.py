"""Spaced repetition: the step-ladder (Leitner-style) algorithm of Android N3 Sensei,
re-implemented so web and app agree on what a rating *means*:

| Rating | New item | Item on step s |
|--------|----------|----------------|
| again  | step 0   | step 0 (a lapse if it was in REVIEW/MASTERED) |
| hard   | step 0   | stays on s     |
| good   | step 1   | s + 1          |
| easy   | step 2   | s + 2          |

Steps are clamped to the ladder. Next due = ``ladder[step]`` added to the answer time:
minutes/hours as an exact duration; days/weeks/months on the calendar in the user's time
zone (keeps the local clock time, months clamp to the last day — like ``java.time``).
State: MASTERED on the last step, REVIEW from the first calendar step, else LEARNING.

Pure functions only: same input → same output (tested). Times are stored in UTC.
"""

import calendar
import re
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.database.enums import ReviewRating, SrsState

ALGORITHM_VERSION = "ladder-v1"
DEFAULT_LADDER = "20m,1h,1d,2d,1w,2w,1mo"  # = Android ReviewLadder.DEFAULT
_UNIT_ORDER = {"m": 0, "h": 1, "d": 2, "w": 3, "mo": 4}
_PATTERN = re.compile(r"^(\d{1,4})(mo|m|h|d|w)$")


@dataclass(frozen=True)
class Interval:
    amount: int
    unit: str  # m | h | d | w | mo

    @property
    def is_calendar(self) -> bool:
        return _UNIT_ORDER[self.unit] >= _UNIT_ORDER["d"]

    def add_to(self, moment: datetime, zone: ZoneInfo) -> datetime:
        if self.unit == "m":
            return moment + timedelta(minutes=self.amount)
        if self.unit == "h":
            return moment + timedelta(hours=self.amount)
        local = moment.astimezone(zone)
        if self.unit in {"d", "w"}:
            days = self.amount * (7 if self.unit == "w" else 1)
            shifted = local + timedelta(days=days)  # wall-clock arithmetic in `zone`
        else:
            month_index = local.month - 1 + self.amount
            year, month = local.year + month_index // 12, month_index % 12 + 1
            day = min(local.day, calendar.monthrange(year, month)[1])
            shifted = local.replace(year=year, month=month, day=day)
        return shifted.astimezone(UTC)

    def encode(self) -> str:
        return f"{self.amount}{self.unit}"


@dataclass(frozen=True)
class Ladder:
    intervals: tuple[Interval, ...]

    @classmethod
    def parse(cls, text: str) -> "Ladder":
        items = []
        for part in text.split(","):
            m = _PATTERN.match(part.strip())
            if not m or int(m.group(1)) <= 0:
                raise ValueError(f"invalid ladder step: {part!r}")
            items.append(Interval(int(m.group(1)), m.group(2)))
        if not items:
            raise ValueError("empty ladder")
        return cls(tuple(items))

    @property
    def last_index(self) -> int:
        return len(self.intervals) - 1

    @property
    def review_start_index(self) -> int:
        return next(
            (i for i, iv in enumerate(self.intervals) if iv.is_calendar), len(self.intervals)
        )

    def clamp(self, step: int) -> int:
        return max(0, min(step, self.last_index))

    def __getitem__(self, step: int) -> Interval:
        return self.intervals[self.clamp(step)]

    def encode(self) -> str:
        return ",".join(i.encode() for i in self.intervals)


@dataclass(frozen=True)
class SrsSnapshot:
    state: SrsState
    step_index: int | None
    interval_minutes: int
    due_at: datetime | None
    last_reviewed_at: datetime | None
    review_count: int
    lapse_count: int

    def as_json(self) -> dict[str, object]:
        data = asdict(self)
        data["state"] = self.state.value
        for key in ("due_at", "last_reviewed_at"):
            value = data[key]
            data[key] = value.astimezone(UTC).isoformat() if value else None
        return data


NEW_ITEM = SrsSnapshot(SrsState.NEW, None, 0, None, None, 0, 0)


def resolve_zone(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name) if name else ZoneInfo("UTC")
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError(f"unknown time zone: {name!r}") from None


def next_step(current_step: int | None, rating: ReviewRating, ladder: Ladder) -> int:
    if current_step is None:
        step = {
            ReviewRating.AGAIN: 0,
            ReviewRating.HARD: 0,
            ReviewRating.GOOD: 1,
            ReviewRating.EASY: 2,
        }[rating]
    else:
        s = ladder.clamp(current_step)
        step = {
            ReviewRating.AGAIN: 0,
            ReviewRating.HARD: s,
            ReviewRating.GOOD: s + 1,
            ReviewRating.EASY: s + 2,
        }[rating]
    return ladder.clamp(step)


def state_for(step: int, ladder: Ladder) -> SrsState:
    if step >= ladder.last_index:
        return SrsState.MASTERED
    if step >= ladder.review_start_index:
        return SrsState.REVIEW
    return SrsState.LEARNING


def schedule(
    current: SrsSnapshot, rating: ReviewRating, now: datetime, zone: ZoneInfo, ladder: Ladder
) -> SrsSnapshot:
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    now = now.astimezone(UTC)
    step = next_step(current.step_index, rating, ladder)
    due = ladder[step].add_to(now, zone)
    interval = int((due - now).total_seconds() // 60)
    long_term = current.state in {SrsState.REVIEW, SrsState.MASTERED}
    lapse = rating == ReviewRating.AGAIN and long_term
    return replace(
        current,
        state=state_for(step, ladder),
        step_index=step,
        interval_minutes=interval,
        due_at=due,
        last_reviewed_at=now,
        review_count=current.review_count + 1,
        lapse_count=current.lapse_count + (1 if lapse else 0),
    )


def preview(
    current: SrsSnapshot, now: datetime, zone: ZoneInfo, ladder: Ladder
) -> dict[str, datetime]:
    """Next due time per rating, to label the answer buttons."""
    return {r.value: schedule(current, r, now, zone, ladder).due_at for r in ReviewRating}  # type: ignore[misc]
