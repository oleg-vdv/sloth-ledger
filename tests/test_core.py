"""Parsing, the rule, the judge's guard rails and the letter — no network."""

import json
from datetime import date, timedelta

from sloth_ledger import judge, letter, rule, senders, statement, synth


def ops_for(month_senders: list[int], amount: float = 4000.0) -> list[statement.Operation]:
    """Three months, N distinct senders in each, one transfer apiece."""
    out = []
    for i, n in enumerate(month_senders):
        day = date(2026, 7 + i, 10)
        out += [statement.Operation(day, amount, "Переводы", f"Отправитель {k}.") for k in range(n)]
    return out


# --- statement --------------------------------------------------------------

def test_statement_line_is_parsed_with_spaces_and_comma():
    ops = statement.parse_text("12.07.26 + 1 250 000,50 ₸ Переводы Айгерим Б.\n"
                               "13.07.26 - 2 000,00 ₸ Покупки Magnum\n"
                               "Дата Сумма Операция Детали")
    assert len(ops) == 2
    assert ops[0].amount == 1_250_000.50 and ops[0].details == "Айгерим Б."
    assert ops[0].is_incoming_transfer and not ops[1].is_incoming_transfer


def test_outgoing_transfer_is_not_counted():
    op = statement.parse_text("20.09.26 - 300 000,00 ₸ Переводы Жанна Т.")[0]
    assert not op.is_incoming_transfer


def test_synthetic_pdf_and_text_parse_the_same(tmp_path):
    synth.write(tmp_path)
    from_pdf = statement.load(tmp_path / "statement.pdf")
    from_text = statement.load(tmp_path / "statement.txt")
    assert from_pdf == from_text and len(from_pdf) > 400


# --- rule -------------------------------------------------------------------

def test_rule_needs_100_senders_in_every_month():
    window = rule.worst(ops_for([150, 99, 150], amount=10_000))
    assert not window.senders_ok and not window.triggered


def test_rule_needs_total_strictly_above_12_wages():
    exactly = rule.worst(ops_for([100, 100, 100], amount=1_020_000 / 300))
    assert exactly.senders_ok and not exactly.total_ok
    above = rule.worst(ops_for([100, 100, 101], amount=1_020_000 / 300))
    assert above.triggered


def test_rule_months_must_be_consecutive():
    ops = ops_for([120, 120, 120], 5000)
    gap = [statement.Operation(o.day + timedelta(days=62) if o.day.month == 9 else o.day,
                               o.amount, o.kind, o.details) for o in ops]
    assert rule.windows(gap) == []


def test_synthetic_persona_triggers_the_rule():
    ops, _ = synth.generate()
    parsed = statement.parse_text(synth.as_text(ops))
    window = rule.worst(parsed)
    assert window.triggered and window.threshold == 1_020_000


# --- judge ------------------------------------------------------------------

def fake(rows):
    def transport(url, payload):
        assert payload["think"] is False and payload["options"]["temperature"] == 0
        return {"message": {"content": json.dumps({"senders": rows})}}
    return transport


def people(*names):
    return [senders.Sender(n, [1000.0], ["2026-07-01"]) for n in names]


def test_judge_drops_senders_it_invented():
    j = judge.Judge(transport=fake([
        {"name": "Мама", "category": "family", "confidence": "high", "reason": "x"},
        {"name": "Призрак Х.", "category": "customer", "confidence": "high", "reason": "x"}]))
    verdicts = j.classify("", people("Мама"))
    assert set(verdicts) == {"Мама"}


def test_silence_becomes_unclear_and_goes_to_the_human():
    verdicts = judge.Judge(transport=fake([])).classify("", people("Асель М."))
    assert verdicts["Асель М."].category == "unclear" and verdicts["Асель М."].needs_human


def test_unknown_category_becomes_unclear():
    verdicts = judge.Judge(transport=fake([
        {"name": "А Б.", "category": "salary", "confidence": "high", "reason": "x"}])
    ).classify("", people("А Б."))
    assert verdicts["А Б."].category == "unclear"


def test_broken_json_is_not_an_answer():
    def broken(url, payload):
        return {"message": {"content": "{not json"}}
    verdicts = judge.Judge(transport=broken).classify("", people("А Б."))
    assert verdicts["А Б."].needs_human


def test_low_confidence_goes_to_the_human():
    verdicts = judge.Judge(transport=fake([
        {"name": "А Б.", "category": "customer", "confidence": "low", "reason": "guess"}])
    ).classify("", people("А Б."))
    assert verdicts["А Б."].needs_human


# --- letter -----------------------------------------------------------------

def test_letter_numbers_come_from_the_statement():
    ops, truth = synth.generate()
    parsed = statement.parse_text(synth.as_text(ops))
    group = senders.group(parsed)
    verdicts = {s.name: judge.Verdict(s.name, truth[s.name], "high", "") for s in group}
    text = letter.draft(rule.worst(parsed), group, verdicts, "изготовлением тортов на заказ")

    customers = sum(s.total for s in group if truth[s.name] == "customer")
    assert letter.money(customers) in text
    assert "Гульнара С. — 150 000 ₸" in text
    assert "Динара К. — 255 000 ₸" in text
    assert "изготовлением тортов на заказ" in text
    assert "требует уточнения" not in text
    assert "За период с 01.07.2026 по 30.09.2026" in text
    assert "(отправителей: 200)" in text
    inner = text.split("[")[1:]
    assert all("]" in part and "[" not in part.split("]")[0] for part in inner), "no nested placeholders"


def test_letter_warns_when_someone_is_unclear():
    ops, truth = synth.generate()
    parsed = statement.parse_text(synth.as_text(ops))
    group = senders.group(parsed)
    verdicts = {s.name: judge.Verdict(s.name, "unclear", "low", "") for s in group}
    text = letter.draft(rule.worst(parsed), group, verdicts)
    assert f"(их {len(group)})" in text


# --- notes matching -----------------------------------------------------------

def test_notes_match_exact_person_through_case_endings():
    named = senders.mentioned("Снимаю с Динарой К. Одолжила у подруги Жанны Т.")
    assert senders.key("Динара К.") in named and senders.key("Жанна Т.") in named


def test_same_first_name_other_initial_is_not_named():
    named = senders.mentioned("Брат Ерлан С. Соседка Динара К.")
    assert senders.key("Ерлан Б.") not in named and senders.key("Динара Ш.") not in named


def test_profile_tells_the_model_who_is_named():
    named = senders.mentioned("Мама — Гульнара С.")
    assert senders.Sender("Гульнара С.", [1.0], ["2026-07-01"]).summary(named)["named_in_notes"]
    assert not senders.Sender("Гульнара Е.", [1.0], ["2026-07-01"]).summary(named)["named_in_notes"]


def test_one_transfer_is_not_called_a_repeating_amount():
    one = senders.Sender("А Б.", [22000.0], ["2026-07-01"]).summary()
    two = senders.Sender("А Б.", [22000.0, 22000.0], ["2026-07-01", "2026-08-01"]).summary()
    assert "same_amount_every_time" not in one and two["same_amount_every_time"] is True
