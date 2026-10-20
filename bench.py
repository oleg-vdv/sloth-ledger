"""Measure the judge against the synthetic statement's known answers.

    python bench.py gemma4:12b llama3.1:8b qwen2.5:7b

Writes docs/bench.json. Accuracy is reported three ways, because the overall
number is flattering: 200 of 205 senders are customers, so a model that calls
everyone a customer scores 97.6 %. What matters is the five people the owner
named, and how many senders get sent back to the human.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from sloth_ledger import judge, senders, statement

ROOT = Path(__file__).resolve().parent
SAMPLE = ROOT / "samples" / "aigerim"


def run(model: str) -> dict:
    ops = statement.load(SAMPLE / "statement.pdf")
    people = senders.group(ops)
    notes = (SAMPLE / "notes.txt").read_text(encoding="utf-8")
    truth = json.loads((SAMPLE / "truth.json").read_text(encoding="utf-8"))

    j = judge.Judge(model)
    started = time.monotonic()
    verdicts = j.classify(notes, people,
                          lambda done, total: print(f"  {model}: {done}/{total}", flush=True))
    wall = time.monotonic() - started

    right = [s.name for s in people if verdicts[s.name].category == truth[s.name]]
    named = [n for n, c in truth.items() if c != "customer"]
    flagged = [s.name for s in people if verdicts[s.name].needs_human]
    wrong_confident = [s.name for s in people
                       if verdicts[s.name].category != truth[s.name]
                       and not verdicts[s.name].needs_human]
    return {
        "model": model,
        "senders": len(people),
        "seconds": round(wall, 1),
        "accuracy": round(len(right) / len(people), 3),
        "named_right": sum(verdicts[n].category == truth[n] for n in named),
        "named_total": len(named),
        "sent_to_human": len(flagged),
        "wrong_and_confident": wrong_confident,
        "named": {n: [verdicts[n].category, verdicts[n].confidence, verdicts[n].reason]
                  for n in named},
    }


if __name__ == "__main__":
    out_path = ROOT / "docs" / "bench.json"
    results = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {}
    for model in sys.argv[1:] or [judge.DEFAULT_MODEL]:
        results[model] = run(model)
        print(json.dumps(results[model], ensure_ascii=False, indent=1), flush=True)
        out_path.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
