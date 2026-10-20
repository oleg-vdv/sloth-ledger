"""A synthetic statement with known answers, so accuracy is measured, not felt.

Persona: Aigerim bakes cakes to order from home and gets paid by card
transfer. Her mother sends money every month, two flatmates pay their share of
rent on the same days, her brother sends something now and then, and a friend
lent her money once and was paid back. Over July–September 2026 she passes the
100/3/12 rule — which is exactly how a real notice starts.

Every name and number is generated; nothing comes from a real statement.
"""

from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

FIRST = ("Айгуль Алия Алтынай Асем Аружан Ботагоз Гаухар Гульмира Дана Динара "
         "Жанар Жанель Зарина Индира Камила Карина Лаура Мадина Малика Меруерт "
         "Наталья Нургуль Ольга Сабина Салтанат Сауле Светлана Томирис Улжан "
         "Эльмира Адиль Айдар Алмас Арман Асхат Бауыржан Ерлан Ержан Кайрат "
         "Марат Нурлан Руслан Самат Серик Тимур Данияр Дмитрий Ильяс").split()
INITIAL = "АБГДЕЖЗИКЛМНОРСТУШЫ"

NOTES = """Я пеку торты на заказ дома, клиенты платят переводом на карту.
Мама — Гульнара С., помогает каждый месяц.
Брат Ерлан С. иногда скидывает деньги.
Квартиру снимаю вместе с Динарой К. и Асель М., они переводят мне свою часть аренды и коммуналки, я плачу хозяйке.
В июле одолжила 300 000 у подруги Жанны Т., вернула в сентябре.
"""

OWNER = {"Гульнара С.": "family", "Ерлан С.": "family",
         "Динара К.": "shared", "Асель М.": "shared", "Жанна Т.": "loan"}


def _customers(rng: random.Random, n: int) -> list[str]:
    names: set[str] = set()
    while len(names) < n:
        name = f"{rng.choice(FIRST)} {rng.choice(INITIAL)}."
        if name not in OWNER:
            names.add(name)
    return sorted(names)


def generate(seed: int = 7) -> tuple[list[tuple[date, float, str, str]], dict[str, str]]:
    rng = random.Random(seed)
    ops: list[tuple[date, float, str, str]] = []
    truth = dict(OWNER)
    customers = _customers(rng, 230)
    regulars = customers[:25]                     # come back most months
    for name in customers:
        truth[name] = "customer"

    for month in (7, 8, 9):
        start = date(2026, month, 1)
        days = 31 if month in (7, 8) else 30
        pool = rng.sample(customers[25:], 95) + rng.sample(regulars, 18)
        for name in pool:
            for _ in range(1 if rng.random() < 0.8 else 2):
                day = start + timedelta(days=rng.randrange(days))
                amount = rng.choice((6500, 8000, 9500, 12000, 14500, 16000, 18000, 22000, 25000))
                ops.append((day, amount, "Переводы", name))
        ops.append((date(2026, month, 5), 50_000, "Переводы", "Гульнара С."))
        ops.append((date(2026, month, 2), 85_000, "Переводы", "Динара К."))
        ops.append((date(2026, month, 3), 85_000, "Переводы", "Асель М."))
        if month != 8:
            ops.append((date(2026, month, rng.randrange(10, 25)), rng.choice((20_000, 30_000)),
                        "Переводы", "Ерлан С."))
        # outgoing life, so the statement looks like one
        ops.append((date(2026, month, 4), -255_000, "Переводы", "Хозяйка квартиры Р."))
        for _ in range(40):
            ops.append((start + timedelta(days=rng.randrange(days)),
                        -float(rng.randrange(800, 26000, 100)),
                        "Покупки", rng.choice(("Magnum", "Small", "Arbuz.kz", "Wolt", "Meloman",
                                               "Леруа Мерлен", "Sulpak", "Яндекс Go"))))
    ops.append((date(2026, 7, 12), 300_000, "Переводы", "Жанна Т."))
    ops.append((date(2026, 9, 20), -300_000, "Переводы", "Жанна Т."))
    ops.sort(key=lambda o: o[0])
    return ops, {k: v for k, v in truth.items() if any(o[3] == k and o[1] > 0 for o in ops)}


def _money(amount: float) -> str:
    sign = "+" if amount > 0 else "-"
    whole, cents = f"{abs(amount):,.2f}".split(".")
    return f"{sign} {whole.replace(',', ' ')},{cents} ₸"


def as_text(ops) -> str:
    lines = ["ВЫПИСКА по Kaspi Gold за период с 01.07.26 по 30.09.26 (синтетические данные)",
             "Дата Сумма Операция Детали"]
    lines += [f"{d:%d.%m.%y} {_money(a)} {k} {who}" for d, a, k, who in ops]
    return "\n".join(lines) + "\n"


def as_pdf(ops, path: Path) -> None:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas

    pdfmetrics.registerFont(TTFont("Body", "C:/Windows/Fonts/arial.ttf"))
    page = canvas.Canvas(str(path), pagesize=A4)
    width, height = A4
    y = height - 50
    for line in as_text(ops).splitlines():
        if y < 40:
            page.showPage()
            y = height - 50
        page.setFont("Body", 9)
        page.drawString(40, y, line)
        y -= 13
    page.save()


def write(folder: Path, seed: int = 7) -> None:
    ops, truth = generate(seed)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "statement.txt").write_text(as_text(ops), encoding="utf-8")
    as_pdf(ops, folder / "statement.pdf")
    (folder / "notes.txt").write_text(NOTES, encoding="utf-8")
    (folder / "truth.json").write_text(json.dumps(truth, ensure_ascii=False, indent=1),
                                       encoding="utf-8")


if __name__ == "__main__":
    write(Path(__file__).resolve().parent.parent / "samples" / "aigerim")
