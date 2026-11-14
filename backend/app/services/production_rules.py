"""Pure business rules for production management.

No database access lives here, so every rule can be unit-tested directly.
See docs/ProductionManagementPlan.md, sections 3 and 6.
"""

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

TaskStatus = Literal[
    "PENDING",
    "ASSIGNED",
    "IN_PROGRESS",
    "SUBMITTED",
    "REVIEW",
    "APPROVED",
    "COMPLETED",
    "CANCELLED",
]
TaskActorRole = Literal["ADMIN", "ASSIGNEE", "MONITOR"]
ReportPeriod = Literal["all", "today", "this_week", "this_month", "previous_month", "custom"]

ALL_STATUSES: tuple[TaskStatus, ...] = (
    "PENDING",
    "ASSIGNED",
    "IN_PROGRESS",
    "SUBMITTED",
    "REVIEW",
    "APPROVED",
    "COMPLETED",
    "CANCELLED",
)
# Approval makes a task billable: it counts as client revenue, budget use and manager commission.
BILLABLE_STATUSES: frozenset[str] = frozenset({"APPROVED", "COMPLETED"})
CLOSED_STATUSES: frozenset[str] = BILLABLE_STATUSES | {"CANCELLED"}
# Statuses that need someone assigned to the task.
ASSIGNED_STATUSES: frozenset[str] = frozenset(
    {"ASSIGNED", "IN_PROGRESS", "SUBMITTED", "REVIEW", "APPROVED", "COMPLETED"}
)

# Assignees move their own work forward up to Submitted (and can withdraw a submission).
_ASSIGNEE_TRANSITIONS: dict[str, frozenset[str]] = {
    "ASSIGNED": frozenset({"IN_PROGRESS"}),
    "IN_PROGRESS": frozenset({"SUBMITTED"}),
    "SUBMITTED": frozenset({"IN_PROGRESS"}),
}
# A monitoring manager may only change status, never past Review. Review -> In Progress
# is the "changes requested" path.
_MONITOR_TRANSITIONS: dict[str, frozenset[str]] = {
    "ASSIGNED": frozenset({"IN_PROGRESS"}),
    "IN_PROGRESS": frozenset({"ASSIGNED", "SUBMITTED"}),
    "SUBMITTED": frozenset({"IN_PROGRESS", "REVIEW"}),
    "REVIEW": frozenset({"IN_PROGRESS"}),
}

CENT = Decimal("0.01")


def money(value: Decimal | int | str | None) -> Decimal:
    """Normalize a money value to two decimal places."""
    if value is None:
        return Decimal("0.00")
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def is_billable(status: str) -> bool:
    return status in BILLABLE_STATUSES


def allowed_transitions(role: TaskActorRole, current: str, has_assignee: bool) -> list[str]:
    """Statuses the given actor may move a task to from its current status."""
    if role == "ADMIN":
        options: list[str] = []
        for status in ALL_STATUSES:
            if status == current:
                continue
            if status in ASSIGNED_STATUSES and not has_assignee:
                continue
            if status == "PENDING" and has_assignee:
                continue
            options.append(status)
        return options
    table = _ASSIGNEE_TRANSITIONS if role == "ASSIGNEE" else _MONITOR_TRANSITIONS
    return sorted(table.get(current, frozenset()), key=ALL_STATUSES.index)


def can_transition(role: TaskActorRole, current: str, target: str, has_assignee: bool) -> bool:
    return target in allowed_transitions(role, current, has_assignee)


def status_timestamp_updates(
    target: str,
    now: datetime,
    *,
    assigned_at: datetime | None,
    started_at: datetime | None,
    approved_at: datetime | None,
) -> dict[str, datetime | None]:
    """Timestamp columns to write when a task moves to ``target``.

    Moving a task out of Approved/Completed clears its approval, so it stops being billable.
    """
    updates: dict[str, datetime | None] = {}
    if target in ASSIGNED_STATUSES and assigned_at is None:
        updates["assigned_at"] = now
    if target == "IN_PROGRESS" and started_at is None:
        updates["started_at"] = now
    if target == "SUBMITTED":
        updates["submitted_at"] = now
    if target == "APPROVED":
        updates["approved_at"] = approved_at or now
        updates["completed_at"] = None
        updates["cancelled_at"] = None
    elif target == "COMPLETED":
        updates["approved_at"] = approved_at or now
        updates["completed_at"] = now
        updates["cancelled_at"] = None
    elif target == "CANCELLED":
        updates["approved_at"] = None
        updates["completed_at"] = None
        updates["cancelled_at"] = now
    else:
        updates["approved_at"] = None
        updates["completed_at"] = None
        updates["cancelled_at"] = None
    return updates


def task_margin(client_price: Decimal, commission: Decimal | None) -> Decimal:
    """Per-task margin. Salaried employees have no per-task cost."""
    return money(client_price) - money(commission)


def is_overdue(status: str, due_date: date | None, today: date) -> bool:
    return due_date is not None and due_date < today and status not in CLOSED_STATUSES


@dataclass(frozen=True)
class BudgetPosition:
    has_budget: bool
    total: Decimal
    used: Decimal
    committed: Decimal
    remaining: Decimal
    overage: Decimal
    projected_used: Decimal
    projected_overage: Decimal
    exceeds_with_new_task: bool


def budget_position(
    total: Decimal,
    used: Decimal,
    committed: Decimal,
    new_task_amount: Decimal | None = None,
) -> BudgetPosition:
    """One-time client budget: used = approved work, committed = assigned but not yet approved.

    ``new_task_amount`` is a task about to be created, assigned or re-priced. The owner chose
    "warn but allow", so this only reports whether the budget would be exceeded.
    """
    total, used, committed = money(total), money(used), money(committed)
    has_budget = total > 0
    remaining = max(total - used, Decimal("0.00"))
    overage = max(used - total, Decimal("0.00")) if has_budget else Decimal("0.00")
    projected = used + committed + money(new_task_amount)
    projected_overage = max(projected - total, Decimal("0.00")) if has_budget else Decimal("0.00")
    return BudgetPosition(
        has_budget=has_budget,
        total=total,
        used=used,
        committed=committed,
        remaining=remaining,
        overage=overage,
        projected_used=projected,
        projected_overage=projected_overage,
        exceeds_with_new_task=has_budget and new_task_amount is not None and projected_overage > 0,
    )


def resolve_period(
    period: ReportPeriod,
    today: date,
    start: date | None = None,
    end: date | None = None,
) -> tuple[date | None, date | None]:
    """Inclusive date range for a report filter. ``all`` means no limit."""
    if period == "all":
        return None, None
    if period == "today":
        return today, today
    if period == "this_week":
        monday = today - timedelta(days=today.weekday())
        return monday, monday + timedelta(days=6)
    if period == "this_month":
        return today.replace(day=1), today.replace(day=monthrange(today.year, today.month)[1])
    if period == "previous_month":
        last_of_previous = today.replace(day=1) - timedelta(days=1)
        return last_of_previous.replace(day=1), last_of_previous
    if start is None or end is None:
        raise ValueError("A custom period needs both a start and an end date.")
    if end < start:
        raise ValueError("The end date must be on or after the start date.")
    return start, end


@dataclass(frozen=True)
class SalaryRate:
    monthly_amount: Decimal
    effective_from: date
    effective_to: date | None  # exclusive


def _month_start(value: date) -> date:
    return value.replace(day=1)


def _month_end(value: date) -> date:
    return value.replace(day=monthrange(value.year, value.month)[1])


def _next_month(value: date) -> date:
    return (_month_end(value) + timedelta(days=1)).replace(day=1)


def _rate_on(rates: list[SalaryRate], day: date) -> SalaryRate | None:
    covering = [
        rate
        for rate in rates
        if rate.effective_from <= day and (rate.effective_to is None or rate.effective_to > day)
    ]
    return max(covering, key=lambda rate: rate.effective_from) if covering else None


def salary_due_by_month(rates: list[SalaryRate], as_of: date) -> list[tuple[date, Decimal]]:
    """Salary owed per month, from the first salary month up to and including ``as_of``'s month.

    Each month uses the salary in effect at the end of that month (or on ``as_of`` for the
    current month). Months with no salary in effect are skipped.
    """
    if not rates:
        return []
    month = _month_start(min(rate.effective_from for rate in rates))
    last_month = _month_start(as_of)
    due: list[tuple[date, Decimal]] = []
    while month <= last_month:
        reference_day = min(_month_end(month), as_of)
        rate = _rate_on(rates, reference_day)
        if rate is not None:
            due.append((month, money(rate.monthly_amount)))
        month = _next_month(month)
    return due


def salary_cost_in_range(rates: list[SalaryRate], start: date, end: date) -> Decimal:
    """Salary cost of a date range, prorated by days so short ranges are not overcharged."""
    total = Decimal("0")
    day = start
    while day <= end:
        rate = _rate_on(rates, day)
        if rate is not None:
            days_in_month = monthrange(day.year, day.month)[1]
            total += Decimal(rate.monthly_amount) / days_in_month
        day += timedelta(days=1)
    return money(total)


def last_month_starts(today: date, count: int) -> list[date]:
    """First day of each of the last `count` months, oldest first, ending with today's month."""
    months = []
    year, month = today.year, today.month
    for _ in range(count):
        months.append(date(year, month, 1))
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    return list(reversed(months))


def monthly_totals(
    deliveries: list[tuple[date, Decimal]], month_starts: list[date]
) -> list[tuple[date, int, Decimal]]:
    """(month start, item count, amount) for each month, including empty months."""
    counts = {start: 0 for start in month_starts}
    amounts = {start: Decimal("0") for start in month_starts}
    for delivered_on, amount in deliveries:
        key = date(delivered_on.year, delivered_on.month, 1)
        if key in counts:
            counts[key] += 1
            amounts[key] += Decimal(amount)
    return [(start, counts[start], money(amounts[start])) for start in month_starts]


# -- client billing ledger (Phase 11) ------------------------------------------------------


def running_budget_left(
    budget_entries: list[tuple[date, Decimal]], deliveries: list[tuple[date, Decimal]]
) -> list[Decimal]:
    """Budget left after each delivery, like the owner's sheets.

    `deliveries` must be in chronological order. A budget entry counts from its own date,
    before that day's deliveries. Negative results mean the budget is exceeded.
    """
    entries = sorted(budget_entries, key=lambda item: item[0])
    result: list[Decimal] = []
    budget = Decimal("0")
    used = Decimal("0")
    position = 0
    for delivered_on, amount in deliveries:
        while position < len(entries) and entries[position][0] <= delivered_on:
            budget += Decimal(entries[position][1])
            position += 1
        used += Decimal(amount)
        result.append(money(budget - used))
    return result


@dataclass(frozen=True)
class DaySummary:
    day: date
    items: int
    amount: Decimal
    budget_left: Decimal


def daily_summary(
    deliveries: list[tuple[date, Decimal]], budget_left_after: list[Decimal]
) -> list[DaySummary]:
    """One row per delivery day, newest first; budget left is after that day's last item."""
    days: dict[date, list[Decimal]] = {}
    left: dict[date, Decimal] = {}
    for (delivered_on, amount), balance in zip(deliveries, budget_left_after, strict=True):
        days.setdefault(delivered_on, []).append(Decimal(amount))
        left[delivered_on] = balance
    return [
        DaySummary(day, len(amounts), money(sum(amounts, Decimal("0"))), left[day])
        for day, amounts in sorted(days.items(), key=lambda item: item[0], reverse=True)
    ]


@dataclass(frozen=True)
class BudgetCycle:
    """One budget period: from a top-up (or the first budget) until the day before the next one."""

    index: int
    start: date
    end: date | None
    amount: Decimal
    used: Decimal
    items: int

    @property
    def remaining(self) -> Decimal:
        return money(self.amount - self.used)


def budget_cycles(
    entries: list[tuple[date, str, Decimal]], deliveries: list[tuple[date, Decimal]]
) -> list[BudgetCycle]:
    """Split the budget into top-up periods. Work before the first budget counts in the first
    period; adjustments belong to the period they fall in; several top-ups on one day merge."""
    starts: dict[date, Decimal] = {}
    for day, kind, amount in entries:
        if kind in ("INITIAL", "TOP_UP") and Decimal(amount) > 0:
            starts[day] = starts.get(day, Decimal("0")) + Decimal(amount)
    if not starts:
        return []
    ordered = sorted(starts)
    windows: list[tuple[date, date | None]] = []
    for index, start in enumerate(ordered):
        end = ordered[index + 1] - timedelta(days=1) if index + 1 < len(ordered) else None
        windows.append((start, end))

    def window_of(day: date) -> int:
        for index, (start, end) in enumerate(windows):
            if (index == 0 or day >= start) and (end is None or day <= end):
                return index
        return len(windows) - 1

    amounts = [starts[start] for start in ordered]
    for day, kind, amount in entries:
        if kind == "ADJUSTMENT":
            amounts[window_of(day)] += Decimal(amount)
    used = [Decimal("0")] * len(windows)
    items = [0] * len(windows)
    for day, amount in deliveries:
        index = window_of(day)
        used[index] += Decimal(amount)
        items[index] += 1
    first_day = min([ordered[0], *[day for day, _ in deliveries]])
    return [
        BudgetCycle(
            index=index + 1,
            start=first_day if index == 0 else start,
            end=end,
            amount=money(amounts[index]),
            used=money(used[index]),
            items=items[index],
        )
        for index, (start, end) in enumerate(windows)
    ]


# -- manager advances (Phase 12) ------------------------------------------------------------


@dataclass(frozen=True)
class WalletEvent:
    day: date
    kind: Literal["TOP_UP", "COMMISSION"]
    title: str
    amount: Decimal
    balance: Decimal


def wallet_timeline(
    top_ups: list[tuple[date, str, Decimal]], commissions: list[tuple[date, str, Decimal]]
) -> list[WalletEvent]:
    """Advance balance after every top-up and every approved commission, oldest first.

    On the same day a top-up counts before that day's commission. A negative balance means the
    manager has earned more than they were advanced (the admin owes the difference)."""
    events: list[tuple[date, int, str, Decimal]] = [
        (day, 0, title, Decimal(amount)) for day, title, amount in top_ups
    ] + [(day, 1, title, Decimal(amount)) for day, title, amount in commissions]
    events.sort(key=lambda item: (item[0], item[1]))
    balance = Decimal("0")
    result: list[WalletEvent] = []
    for day, order, title, amount in events:
        balance += amount if order == 0 else -amount
        result.append(
            WalletEvent(
                day=day,
                kind="TOP_UP" if order == 0 else "COMMISSION",
                title=title,
                amount=money(amount),
                balance=money(balance),
            )
        )
    return result
