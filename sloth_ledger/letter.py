"""The reply to the notice. A template, filled by code.

The model sorts people; it does not write the letter. Every number below comes
from the parsed statement and every name from the sender table, so nothing in
the reply can be a model's invention. What the person still has to supply is
marked [в квадратных скобках].

This is a draft explanation, not legal advice: what to declare is the
person's decision, and the letter says only what the transfers were.
"""

from __future__ import annotations

from collections import defaultdict

from .judge import Verdict
from .rule import Window
from .senders import Sender

LABELS = {
    "customer": "оплата за товары/услуги (доход от деятельности)",
    "family": "переводы от родственников",
    "shared": "возмещение общих расходов (аренда, коммунальные услуги)",
    "loan": "заёмные средства / возврат займа",
    "unclear": "требует уточнения",
}


def money(value: float) -> str:
    return f"{round(value):,}".replace(",", " ") + " ₸"


def totals(senders: list[Sender], verdicts: dict[str, Verdict]) -> dict[str, tuple[int, float]]:
    out: dict[str, list[float]] = defaultdict(lambda: [0, 0.0])
    for sender in senders:
        row = out[verdicts[sender.name].category]
        row[0] += 1
        row[1] += sender.total
    return {k: (int(v[0]), v[1]) for k, v in out.items()}


def draft(window: Window, senders: list[Sender], verdicts: dict[str, Verdict],
          activity: str = "[вид деятельности]") -> str:
    sums = totals(senders, verdicts)
    named = defaultdict(list)
    for sender in senders:
        category = verdicts[sender.name].category
        if category in ("family", "shared", "loan"):
            named[category].append(f"{sender.name} — {money(sender.total)}")

    lines = [
        "В Управление государственных доходов по [району / городу]",
        "от [ФИО], ИИН [ИИН]",
        "",
        "ПОЯСНЕНИЕ",
        "к уведомлению № [номер] от [дата]",
        "",
        f"За период {window.dates} на мой текущий счёт поступили переводы от физических лиц "
        f"на общую сумму {money(window.total)}. По их характеру они распределяются так:",
        "",
    ]
    for category in ("customer", "family", "shared", "loan", "unclear"):
        if category in sums:
            count, total = sums[category]
            lines.append(f"— {LABELS[category]}: {money(total)} (отправителей: {count});")
    lines.append("")
    if named["family"]:
        lines.append("Переводы от родственников: " + "; ".join(named["family"]) + ".")
    if named["shared"]:
        lines.append("Возмещение общих расходов по совместной аренде жилья: "
                     + "; ".join(named["shared"]) + ". Эти средства перечислены "
                     "арендодателю и доходом не являются.")
    if named["loan"]:
        lines.append("Заёмные средства, возвращённые займодавцу: " + "; ".join(named["loan"]) + ".")
    if "customer" in sums:
        lines += ["",
                  f"Поступления на сумму {money(sums['customer'][1])} связаны с "
                  f"{activity}. [Выберите: «Зарегистрировался(-ась) в качестве ИП "
                  "и задекларирую этот доход в установленном порядке» или дайте "
                  "своё пояснение.]"]
    if "unclear" in sums:
        lines += ["", f"[Перед отправкой разберите отправителей с пометкой «требует "
                      f"уточнения» (их {sums['unclear'][0]}) — в письме их быть не должно.]"]
    lines += ["", "Приложение: выписка по счёту за указанный период.", "",
              "[Дата]                                   [Подпись]"]
    return "\n".join(lines)
