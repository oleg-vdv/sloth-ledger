"""Local web page: drop a statement, write three sentences, get a draft reply.

    python -m sloth_ledger --model gemma4:12b --ollama http://127.0.0.1:11434

Standard library only. The statement is read in memory and goes nowhere but
the Ollama server you point at. Nothing is written to disk.
"""

from __future__ import annotations

import base64
import json
import threading
import uuid
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from . import judge, letter, rule, senders, statement

HERE = Path(__file__).resolve().parent
SAMPLE = HERE.parent / "samples" / "aigerim"
JOBS: dict[str, dict[str, Any]] = {}
CONFIG = {"model": judge.DEFAULT_MODEL, "host": judge.DEFAULT_HOST}


def _window_json(window: rule.Window | None) -> dict[str, Any] | None:
    if window is None:
        return None
    return {"label": window.label, "total": window.total, "threshold": window.threshold,
            "triggered": window.triggered, "senders_ok": window.senders_ok,
            "total_ok": window.total_ok,
            "months": [{"month": m.month, "senders": m.sender_count, "total": m.total}
                       for m in window.months]}


def _run(job_id: str, data: bytes, name: str, notes: str, activity: str) -> None:
    job = JOBS[job_id]
    try:
        ops = statement.read(data, name)
        window = rule.worst(ops)
        people = senders.group(ops)
        job.update(stage="sorting", total=len(people), window=_window_json(window),
                   operations=len(ops))
        if not people:
            job.update(stage="error", error="В файле не нашлось входящих переводов. "
                       "Нужна выписка по карте за три месяца или больше.")
            return
        j = judge.Judge(CONFIG["model"], CONFIG["host"])
        verdicts = j.classify(notes, people, lambda done, _: job.update(done=done))
        job.update(_people=people, _verdicts=verdicts, _window=window)
        job.update(stage="done", seconds=round(j.seconds), activity=activity,
                   senders=[{**s.summary(), **asdict(verdicts[s.name])} for s in people])
        if window:
            job["letter"] = letter.draft(window, people, verdicts, activity or "[вид деятельности]")
    except Exception as exc:  # shown on the page, not swallowed
        job.update(stage="error", error=f"{type(exc).__name__}: {exc}")


def _relabel(job: dict[str, Any], changes: dict[str, str]) -> str:
    """The person corrects a category; the letter is rebuilt from the same numbers."""
    verdicts = job["_verdicts"]
    for name, category in changes.items():
        if name in verdicts and category in judge.CATEGORIES:
            verdicts[name] = judge.Verdict(name, category, "high", "изменено вручную")
    return letter.draft(job["_window"], job["_people"], verdicts,
                        job.get("activity") or "[вид деятельности]")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_: Any) -> None:
        pass

    def _send(self, status: int, body: bytes, kind: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload: Any, status: int = 200) -> None:
        self._send(status, json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8"),
                   "application/json; charset=utf-8")

    def do_GET(self) -> None:
        if self.path == "/":
            self._send(200, (HERE / "page.html").read_bytes(), "text/html; charset=utf-8")
        elif self.path.startswith("/fonts/") and "/" not in self.path[7:]:
            # fonts ship with the package: the page makes no request outside this server
            path = HERE / "fonts" / self.path[7:]
            kind = "text/css; charset=utf-8" if path.suffix == ".css" else "font/woff2"
            if path.is_file():
                self._send(200, path.read_bytes(), kind)
            else:
                self._json({"error": "нет такого файла"}, 404)
        elif self.path == "/config":
            self._json({"model": CONFIG["model"]})
        elif self.path == "/sample":
            self._json({"notes": (SAMPLE / "notes.txt").read_text(encoding="utf-8"),
                        "activity": "изготовлением тортов на заказ",
                        "name": "statement.pdf",
                        "data": base64.b64encode((SAMPLE / "statement.pdf").read_bytes()).decode()})
        elif self.path.startswith("/job/"):
            job = JOBS.get(self.path[5:])
            if job is None:
                self._json({"error": "нет такого разбора"}, 404)
            else:
                self._json({k: v for k, v in job.items() if not k.startswith("_")})
        else:
            self._json({"error": "нет такой страницы"}, 404)

    def do_POST(self) -> None:
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        if self.path == "/run":
            job_id = uuid.uuid4().hex[:8]
            JOBS[job_id] = {"stage": "reading", "done": 0, "total": 0, "model": CONFIG["model"]}
            threading.Thread(target=_run, daemon=True, args=(
                job_id, base64.b64decode(body.get("data", "")), body.get("name", "statement.txt"),
                body.get("notes", ""), body.get("activity", ""))).start()
            self._json({"job": job_id})
        elif self.path.startswith("/relabel/"):
            job = JOBS.get(self.path[9:])
            if not job or job.get("stage") != "done":
                self._json({"error": "разбор ещё не закончен"}, 409)
                return
            text = _relabel(job, body.get("changes", {}))
            job["letter"] = text
            self._json({"letter": text})
        else:
            self._json({"error": "нет такого действия"}, 404)


def serve(port: int = 8765, host: str = "127.0.0.1") -> None:
    print(f"sloth-ledger: http://localhost:{port}  (model {CONFIG['model']} at {CONFIG['host']})")
    ThreadingHTTPServer((host, port), Handler).serve_forever()
