"""Reading a bank statement into transactions.

Kazakh card statements (Kaspi Gold is the common one) come as PDF with one
operation per line:

    01.07.26   + 5 000,00 ₸   Переводы   Айгерим Б.
    02.07.26   - 1 200,00 ₸   Покупки    Magnum

Only incoming person-to-person transfers matter for the 100/3/12 rule, so
everything else is kept but marked. Parsing is plain regex over extracted
text: no model touches the numbers.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

LINE = re.compile(
    r"^\s*(?P<day>\d{2})\.(?P<month>\d{2})\.(?P<year>\d{2,4})\s+"
    r"(?P<sign>[+-])\s*(?P<amount>\d[\d\s ]*(?:[.,]\d{1,2})?)\s*₸?\s+"
    r"(?P<kind>\S+)\s*(?P<details>.*?)\s*$")

INCOMING_TRANSFER = {"переводы", "перевод", "аударымдар", "аударым"}


@dataclass(frozen=True)
class Operation:
    day: date
    amount: float          # positive for incoming, negative for outgoing
    kind: str
    details: str

    @property
    def is_incoming_transfer(self) -> bool:
        return self.amount > 0 and self.kind.lower() in INCOMING_TRANSFER

    @property
    def month(self) -> str:
        return f"{self.day.year:04d}-{self.day.month:02d}"


def _amount(raw: str) -> float:
    return float(raw.replace(" ", "").replace(" ", "").replace(",", "."))


def parse_text(text: str) -> list[Operation]:
    """Operations from statement text; lines that are not operations are skipped."""
    out = []
    for line in text.splitlines():
        found = LINE.match(line)
        if not found:
            continue
        year = int(found["year"])
        year += 2000 if year < 100 else 0
        amount = _amount(found["amount"])
        out.append(Operation(
            day=date(year, int(found["month"]), int(found["day"])),
            amount=amount if found["sign"] == "+" else -amount,
            kind=found["kind"],
            details=found["details"].strip()))
    return out


def parse_csv(text: str) -> list[Operation]:
    """CSV with columns date, amount, kind, details (amount signed)."""
    out = []
    for row in csv.DictReader(io.StringIO(text)):
        day, month, year = (int(x) for x in row["date"].split("."))
        year += 2000 if year < 100 else 0
        out.append(Operation(date(year, month, day), float(row["amount"]),
                             row["kind"].strip(), row["details"].strip()))
    return out


def pdf_text(data: bytes) -> str:
    from pypdf import PdfReader  # optional dependency, only for PDF input
    reader = PdfReader(io.BytesIO(data))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def load(path: str | Path) -> list[Operation]:
    path = Path(path)
    return read(path.read_bytes(), path.name)


def read(data: bytes, name: str) -> list[Operation]:
    lower = name.lower()
    if lower.endswith(".pdf"):
        return parse_text(pdf_text(data))
    text = data.decode("utf-8-sig")
    if lower.endswith(".csv"):
        return parse_csv(text)
    return parse_text(text)
