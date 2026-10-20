"""The 100/3/12 rule, computed — never asked of a model.

Since 1 January 2026 Kazakh banks report a personal (non-business) account to
the State Revenue Committee when, in each of three consecutive months, it
received transfers from 100 or more different people, and the total over
those three months exceeds 12 minimum monthly wages (МЗП). Order of the
Minister of Finance No. 698 of 12 November 2025; Tax Code art. 55 p. 2
sub. 24.

Meeting the rule is a reporting trigger, not a tax or a fine: the bank passes
the data on and the person gets a notice asking where the money came from.

МЗП in 2026 is 85 000 ₸, so the threshold is 1 020 000 ₸.
"""

from __future__ import annotations

import calendar
from collections import defaultdict
from dataclasses import dataclass, field

from .statement import Operation

MIN_WAGE = {2025: 85_000, 2026: 85_000}
SENDERS_PER_MONTH = 100
MONTHS = 3
WAGES = 12


@dataclass
class Month:
    month: str
    senders: set[str] = field(default_factory=set)
    total: float = 0.0

    @property
    def sender_count(self) -> int:
        return len(self.senders)


@dataclass
class Window:
    months: list[Month]
    threshold: float

    @property
    def total(self) -> float:
        return sum(m.total for m in self.months)

    @property
    def senders_ok(self) -> bool:
        return all(m.sender_count >= SENDERS_PER_MONTH for m in self.months)

    @property
    def total_ok(self) -> bool:
        return self.total > self.threshold

    @property
    def triggered(self) -> bool:
        return self.senders_ok and self.total_ok

    @property
    def label(self) -> str:
        return f"{self.months[0].month} – {self.months[-1].month}"

    @property
    def dates(self) -> str:
        """The window as the letter states it: с 01.07.2026 по 30.09.2026."""
        fy, fm = map(int, self.months[0].month.split("-"))
        ly, lm = map(int, self.months[-1].month.split("-"))
        last = calendar.monthrange(ly, lm)[1]
        return f"с 01.{fm:02d}.{fy} по {last:02d}.{lm:02d}.{ly}"


def by_month(operations: list[Operation]) -> list[Month]:
    months: dict[str, Month] = defaultdict(lambda: Month(""))
    for op in operations:
        if not op.is_incoming_transfer:
            continue
        month = months[op.month]
        month.month = op.month
        month.senders.add(op.details)
        month.total += op.amount
    return [months[k] for k in sorted(months)]


def _consecutive(a: str, b: str) -> bool:
    ya, ma = map(int, a.split("-"))
    yb, mb = map(int, b.split("-"))
    return (yb * 12 + mb) - (ya * 12 + ma) == 1


def windows(operations: list[Operation]) -> list[Window]:
    """Every run of three consecutive calendar months present in the statement."""
    months = by_month(operations)
    out = []
    for i in range(len(months) - MONTHS + 1):
        run = months[i:i + MONTHS]
        if all(_consecutive(run[j].month, run[j + 1].month) for j in range(MONTHS - 1)):
            year = int(run[-1].month[:4])
            wage = MIN_WAGE.get(year, MIN_WAGE[max(MIN_WAGE)])
            out.append(Window(run, WAGES * wage))
    return out


def worst(operations: list[Operation]) -> Window | None:
    """The window closest to (or furthest past) the rule — what the bank sees."""
    found = windows(operations)
    if not found:
        return None
    return max(found, key=lambda w: (w.triggered,
                                     min(m.sender_count for m in w.months),
                                     w.total))
