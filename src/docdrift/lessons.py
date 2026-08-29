"""Lessons memory (T026): check-writing pitfalls accumulated across eval
iterations, injected into the synthesizer's system prompt on every run.

lessons.md is curated by the builder: each entry generalizes an observed
failure (a gate rejection, a false alarm, a baseline confusion) and cites its
evidence in the changelog/results. Loading is code so every run — including a
judge's reproduction — picks up the same accumulated state.
"""

from __future__ import annotations

from docdrift.config import LESSONS_FILE


def load_lessons() -> str:
    if LESSONS_FILE.is_file():
        return LESSONS_FILE.read_text(encoding="utf-8").strip()
    return ""
