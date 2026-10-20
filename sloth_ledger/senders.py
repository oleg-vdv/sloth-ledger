"""One row per person who sent money: the unit a human actually reasons about.

Three months of a small baker's card is 400+ transfers but about 130 people.
Nobody explains transfers one by one; they explain people: "that's my mum",
"those are flatmates paying their share", "those are customers".
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from statistics import median

from .statement import Operation


@dataclass
class Sender:
    name: str
    amounts: list[float] = field(default_factory=list)
    days: list[str] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.amounts)

    @property
    def total(self) -> float:
        return sum(self.amounts)

    @property
    def months(self) -> int:
        return len({d[:7] for d in self.days})

    def summary(self) -> dict:
        """What the model sees. Rounded, compact, no raw ledger."""
        return {
            "name": self.name,
            "transfers": self.count,
            "months_active": self.months,
            "total_kzt": round(self.total),
            "median_kzt": round(median(self.amounts)),
            "min_kzt": round(min(self.amounts)),
            "max_kzt": round(max(self.amounts)),
            "same_amount_every_time": len({round(a) for a in self.amounts}) == 1,
            "days_of_month": sorted({int(d[8:10]) for d in self.days}),
        }


def group(operations: list[Operation]) -> list[Sender]:
    senders: dict[str, Sender] = defaultdict(lambda: Sender(""))
    for op in operations:
        if not op.is_incoming_transfer:
            continue
        sender = senders[op.details]
        sender.name = op.details
        sender.amounts.append(op.amount)
        sender.days.append(op.day.isoformat())
    return sorted(senders.values(), key=lambda s: -s.total)
