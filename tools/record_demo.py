"""Make the demo video from real screenshots of a real run.

    python tools/record_demo.py http://localhost:8765 docs/demo.mp4

Browser screencasts tear while scrolling, so instead the script drives the
page with Playwright (installed Edge), takes sharp screenshots of each state —
including one every few seconds while the local model works — and assembles
the video itself: pans over full-page shots, the model run compressed and
labelled with its real duration. Needs `playwright`, `pillow`, `imageio-ffmpeg`.
"""

from __future__ import annotations

import io
import subprocess
import sys
import time
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

W, H, FPS = 1280, 720, 30
FONT = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 24)
INK = (74, 63, 166)


def shot(page, full: bool = False) -> Image.Image:
    return Image.open(io.BytesIO(page.screenshot(full_page=full))).convert("RGB")


def capture(url: str) -> dict:
    s: dict = {"run": []}
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge")
        page = browser.new_page(viewport={"width": W, "height": H})
        page.goto(url)
        page.wait_for_timeout(1500)
        s["landing"] = shot(page)
        page.click("#sample")
        page.wait_for_timeout(1200)
        s["sample"] = shot(page)
        page.click("#go")
        page.wait_for_selector("#meter:not([hidden])")
        meter_top = page.evaluate("document.querySelector('#meter').getBoundingClientRect().top + scrollY - 24")
        page.evaluate(f"window.scrollTo(0, {meter_top})")
        page.wait_for_timeout(1800)                    # bars rise, stamp lands
        started = time.monotonic()
        while page.is_hidden("#results"):
            s["run"].append((time.monotonic() - started, shot(page)))
            page.wait_for_timeout(4000)
        s["run_seconds"] = time.monotonic() - started
        page.wait_for_timeout(1200)
        s["results"] = shot(page, full=True)
        s["meter_top"] = meter_top
        s["results_top"] = page.evaluate("document.querySelector('#results').offsetTop - 24")
        s["people_top"] = page.evaluate("document.querySelector('#people').closest('section').offsetTop - 24")
        # correct one sender by hand; the letter is rebuilt with the same numbers
        flagged = page.query_selector("#people tr.flag select")
        if flagged:
            s["fixed"] = page.evaluate("el => el.closest('tr').cells[0].textContent", flagged)
            flagged.select_option("customer")
            page.wait_for_timeout(1500)
        s["after"] = shot(page, full=True)
        s["letter_top"] = page.evaluate("document.querySelector('#letter').closest('section').offsetTop - 24")
        browser.close()
    return s


def caption(frame: Image.Image, text: str) -> Image.Image:
    frame = frame.copy()
    draw = ImageDraw.Draw(frame)
    box = draw.textbbox((0, 0), text, font=FONT)
    w, h = box[2] - box[0], box[3] - box[1]
    draw.rectangle((20, H - h - 44, 44 + w, H - 20), fill=INK)
    draw.text((32, H - h - 34), text, font=FONT, fill="white")
    return frame


def hold(img, seconds, text=None):
    frame = caption(img, text) if text else img
    return [frame] * int(seconds * FPS)


def pan(page_img, y0, y1, seconds, text=None, hold_end=0.0):
    frames = []
    n = int(seconds * FPS)
    limit = page_img.height - H
    for i in range(n):
        t = i / max(n - 1, 1)
        eased = t * t * (3 - 2 * t)
        y = int(max(0, min(limit, y0 + (y1 - y0) * eased)))
        crop = page_img.crop((0, y, W, y + H))
        frames.append(caption(crop, text) if text else crop)
    return frames + [frames[-1]] * int(hold_end * FPS)


def assemble(s: dict, out: Path) -> None:
    real = s["run_seconds"]
    mins, secs = divmod(int(real), 60)
    run_text = f"Gemma on the local GPU, {mins} min {secs} s compressed into a few seconds"
    frames = []
    frames += hold(s["landing"], 3, "A notice came because of card transfers. Here's the statement.")
    frames += hold(s["sample"], 3.5, "Three sentences about who sends you money + the statement")
    for _, img in s["run"]:
        frames += hold(img, 0.35, run_text)
    frames += pan(s["results"], s["meter_top"], s["meter_top"], 3,
                  "Rule computed by code: 100+ senders, 3 months, > 12 minimum wages")
    frames += pan(s["results"], s["meter_top"], s["results_top"], 1.5)
    frames += hold(s["results"].crop((0, s["results_top"], W, s["results_top"] + H)), 5,
                   "You only check the senders the model wasn't sure about")
    frames += pan(s["results"], s["results_top"], s["people_top"], 1.5)
    frames += hold(s["results"].crop((0, s["people_top"], W, s["people_top"] + H)), 4,
                   "Every sender, a category and a reason")
    fixed = s.get("fixed")
    frames += hold(s["after"].crop((0, s["people_top"], W, s["people_top"] + H)), 2.5,
                   f"Fix one by hand ({fixed})" if fixed else "Fix any category by hand")
    frames += pan(s["after"], s["people_top"], s["letter_top"], 2)
    frames += pan(s["after"], s["letter_top"], s["letter_top"] + 520, 9,
                  "Draft reply: every number and name comes from the statement", hold_end=3)

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    out.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen([ffmpeg, "-y", "-loglevel", "error", "-f", "rawvideo",
                             "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                             "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                             "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)],
                            stdin=subprocess.PIPE)
    for frame in frames:
        proc.stdin.write(frame.tobytes())
    proc.stdin.close()
    proc.wait()
    print(f"{out}: {len(frames) / FPS:.0f} s video, model ran {real:.0f} s, "
          f"{len(s['run'])} screenshots during the run")


if __name__ == "__main__":
    assemble(capture(sys.argv[1]), Path(sys.argv[2]))
