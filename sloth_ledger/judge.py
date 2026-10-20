"""The open model's job: decide who each sender is, and say when it can't.

The model runs on a local Ollama server. A bank statement holds full names,
amounts and the shape of someone's life; it should not leave the machine to
answer a letter from the tax office. That is the whole reason this is built
on an open-weight model and not on a hosted API.

The model never computes the rule and never sees the raw ledger. It gets one
compact profile per sender plus the owner's own description of their life,
and returns a category, a confidence and a one-line reason. Anything it does
not return, or returns malformed, becomes "unclear" — the safe direction,
because "unclear" goes to the human.
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

from .senders import Sender, key, mentioned

CATEGORIES = {
    "customer": "pays for goods or services you sell — business income",
    "family": "relative sending personal money (gifts, support)",
    "shared": "flatmate/friend paying their share of rent, bills, a group purchase, or paying you back",
    "loan": "lending you money or repaying a personal loan",
    "unclear": "you cannot tell from the profile and the owner's notes",
}

PERSONAL = {"family", "shared", "loan"}   # categories that say "this is not income"

DEFAULT_HOST = os.environ.get("OLLAMA_HOST_URL", "http://127.0.0.1:11434")
DEFAULT_MODEL = os.environ.get("SLOTH_MODEL", "gemma4:12b")
BATCH = 12

SYSTEM = """You help a person in Kazakhstan explain incoming card transfers \
to the tax office. For each sender profile decide which category fits:
{categories}

Rules:
- named_in_notes says whether the owner wrote about this exact person. If it \
is true, the note decides the category. If it is false, the notes are not \
about this sender, even when the first name looks the same.
- Without a note, judge by the pattern: many people paying varied amounts \
once or twice look like customers; the same amount on the same days every \
month from a few people looks like shared rent or bills.
- If you are guessing, set confidence to "low". If nothing fits, use "unclear".
- Never invent facts about a sender. The reason must point at the note or \
the pattern you used, in one short sentence written in Russian.
Answer with JSON only."""

SCHEMA = {
    "type": "object",
    "properties": {
        "senders": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "category": {"type": "string", "enum": list(CATEGORIES)},
                    "confidence": {"type": "string", "enum": ["high", "low"]},
                    "reason": {"type": "string"},
                },
                "required": ["name", "category", "confidence", "reason"],
            },
        }
    },
    "required": ["senders"],
}


@dataclass
class Verdict:
    name: str
    category: str
    confidence: str
    reason: str

    @property
    def needs_human(self) -> bool:
        return self.category == "unclear" or self.confidence == "low"


Transport = Callable[[str, dict[str, Any]], dict[str, Any]]


def _http(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=600) as response:
        return json.loads(response.read().decode("utf-8"))


class Judge:
    def __init__(self, model: str = DEFAULT_MODEL, host: str = DEFAULT_HOST,
                 transport: Transport | None = None):
        self.model, self.host = model, host.rstrip("/")
        self._transport = transport or _http
        self.seconds = 0.0
        self.calls = 0

    def _ask(self, notes: str, batch: list[Sender]) -> list[dict[str, Any]]:
        categories = "\n".join(f"- {k}: {v}" for k, v in CATEGORIES.items())
        named = mentioned(notes)
        user = ("Owner's notes:\n" + (notes.strip() or "(none)") +
                "\n\nSender profiles:\n" +
                json.dumps([s.summary(named) for s in batch], ensure_ascii=False))
        payload = {
            "model": self.model,
            "stream": False,
            "think": False,       # thinking models otherwise reason for minutes
            "format": SCHEMA,
            "options": {"temperature": 0, "num_ctx": 8192},
            "messages": [
                {"role": "system", "content": SYSTEM.format(categories=categories)},
                {"role": "user", "content": user},
            ],
        }
        started = time.monotonic()
        reply = self._transport(f"{self.host}/api/chat", payload)
        self.seconds += time.monotonic() - started
        self.calls += 1
        try:
            return json.loads(reply["message"]["content"]).get("senders", [])
        except (KeyError, TypeError, ValueError):
            return []

    def classify(self, notes: str, senders: list[Sender],
                 progress: Callable[[int, int], None] | None = None) -> dict[str, Verdict]:
        out: dict[str, Verdict] = {}
        named = mentioned(notes)
        for start in range(0, len(senders), BATCH):
            batch = senders[start:start + BATCH]
            wanted = {s.name for s in batch}
            for row in self._ask(notes, batch):
                name = str(row.get("name", ""))
                if name not in wanted or name in out:
                    continue          # the model may not invent or repeat senders
                category = row.get("category")
                if category not in CATEGORIES:
                    category = "unclear"
                confidence = "high" if row.get("confidence") == "high" else "low"
                if category in PERSONAL and key(name) not in named:
                    # "not income" is the claim that matters to the tax office;
                    # without the owner's word for it, it's a guess for a human
                    confidence = "low"
                out[name] = Verdict(name, category, confidence,
                                    str(row.get("reason", "")).strip()[:200])
            for sender in batch:      # silence is not an answer
                out.setdefault(sender.name, Verdict(
                    sender.name, "unclear", "low", "the model returned nothing for this sender"))
            if progress:
                progress(min(start + BATCH, len(senders)), len(senders))
        return out
