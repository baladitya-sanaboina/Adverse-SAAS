"""Pure business rules for production management.

No database access lives here, so every rule can be unit-tested directly.
See docs/ProductionManagementPlan.md, sections 3 and 6.
"""

from calendar import monthrange
from collections.abc import Sequence
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
class CycleLine:
    """One row of a payment sheet. `amount` is signed: money in is positive, work is negative."""

    day: date
    kind: Literal["CARRIED", "PAYMENT", "ADJUSTMENT", "WORK"]
    label: str
    amount: Decimal
    balance: Decimal


@dataclass(frozen=True)
class BudgetCycle:
    """One payment sheet (owner decision 2026-11-14): opens on a payment (top-up) and closes the
    day before the next one. Whatever is left, plus or minus, is carried into the next sheet."""

    index: int
    start: date
    end: date | None
    amount: Decimal
    used: Decimal
    items: int
    carried_in: Decimal = Decimal("0.00")
    ran_out_on: date | None = None
    lines: tuple[CycleLine, ...] = ()

    @property
    def remaining(self) -> Decimal:
        return money(self.carried_in + self.amount - self.used)


PAYMENT_METHOD_TEXT = {
    "CASH": "Cash",
    "BANK_TRANSFER": "Bank transfer",
    "UPI": "UPI",
    "CHEQUE": "Cheque",
    "CARD": "Card",
    "OTHER": "Other",
}


def budget_cycles(
    entries: Sequence[tuple[date, str, Decimal] | tuple[date, str, Decimal, str]],
    deliveries: Sequence[
        tuple[date, Decimal] | tuple[date, Decimal, str] | tuple[date, Decimal, str, bool]
    ],
    *,
    open_without_payment: bool = False,
) -> list[BudgetCycle]:
    """Split the money into payment sheets, one per top-up date (several top-ups on one day
    merge). Work before the first payment counts in the first sheet; adjustments belong to the
    sheet they fall in. Each sheet starts with the previous sheet's balance carried in, records
    the day its money ran out, and lists its own lines with the running balance."""
    starts: dict[date, Decimal] = {}
    labels: dict[date, list[str]] = {}
    for day, kind, amount, *rest in entries:
        if kind in ("INITIAL", "TOP_UP") and Decimal(amount) > 0:
            starts[day] = starts.get(day, Decimal("0")) + Decimal(amount)
            labels.setdefault(day, []).append(str(rest[0]) if rest else "Payment")
    if not starts and open_without_payment and deliveries:
        # Work but no payment yet: one open sheet from the first piece of work, starting at zero.
        first = min(delivery[0] for delivery in deliveries)
        starts[first] = Decimal("0")
        labels[first] = []
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

    # (day, order, kind, label, signed amount, counts as an item); on one day money in counts
    # before work. A monthly package charge is used money but not a video (counts=False).
    events: list[
        list[tuple[date, int, Literal["PAYMENT", "ADJUSTMENT", "WORK"], str, Decimal, bool]]
    ] = [[] for _ in windows]
    for day, kind, amount, *_ in entries:
        if kind == "ADJUSTMENT":
            events[window_of(day)].append(
                (day, 0, "ADJUSTMENT", "Adjustment", Decimal(amount), False)
            )
    for delivery in deliveries:
        day, amount = delivery[0], delivery[1]
        extra: list[object] = list(delivery[2:])
        counts = bool(extra[1]) if len(extra) > 1 else True
        events[window_of(day)].append(
            (day, 1, "WORK", str(extra[0]) if extra else "", -Decimal(amount), counts)
        )

    first_day = min([ordered[0], *[delivery[0] for delivery in deliveries]])
    cycles: list[BudgetCycle] = []
    carried = Decimal("0")
    for index, (start, end) in enumerate(windows):
        lines: list[CycleLine] = []
        balance = carried
        if index > 0 and carried != 0:
            # Owner wording 2026-11-19: leftover money is "carried"; an overspend is "extra used",
            # taken from the new top-up.
            label = (
                f"Balance carried from sheet {index}"
                if carried > 0
                else f"Extra used in sheet {index} (taken from this top-up)"
            )
            lines.append(CycleLine(start, "CARRIED", label, money(carried), money(carried)))
        amount = Decimal("0")
        used = Decimal("0")
        items = 0
        ran_out_on: date | None = start if index > 0 and carried < 0 else None
        # The payment is a dated line too, so work done before the first payment shows first.
        names = labels[start]
        payment = names[0] if len(names) == 1 else f"{len(names)} payments"
        # The payment goes first so that, on the same day, it counts before that day's work.
        dated: list[
            tuple[date, int, Literal["PAYMENT", "ADJUSTMENT", "WORK"], str, Decimal, bool]
        ] = ([(start, 0, "PAYMENT", payment, starts[start], False)] if starts[start] > 0 else [])
        dated += events[index]
        for day, _, kind, label, signed, counts in sorted(dated, key=lambda item: item[:2]):
            balance += signed
            if kind == "WORK":
                used -= signed
                items += 1 if counts else 0
            else:
                amount += signed
            if ran_out_on is None and balance <= 0:
                ran_out_on = day
            elif balance > 0:
                ran_out_on = None
            lines.append(CycleLine(day, kind, label, money(signed), money(balance)))
        cycle = BudgetCycle(
            index=index + 1,
            start=first_day if index == 0 else start,
            end=end,
            amount=money(amount),
            used=money(used),
            items=items,
            carried_in=money(carried),
            ran_out_on=ran_out_on,
            lines=tuple(lines),
        )
        cycles.append(cycle)
        carried = cycle.remaining
    return cycles


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


# -- content calendar (Phase 13) -------------------------------------------------------------


def calendar_priority(due: date, today: date) -> Literal["LOW", "MEDIUM", "HIGH", "URGENT"]:
    """Priority of a ticket made from a calendar entry, from how soon the post date is
    (owner request 2026-11-14: tickets ranked by date)."""
    days = (due - today).days
    if days <= 2:
        return "URGENT"
    if days <= 5:
        return "HIGH"
    if days <= 14:
        return "MEDIUM"
    return "LOW"
