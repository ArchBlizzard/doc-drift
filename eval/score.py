"""Deterministic span-anchored scorer (T009). Pure — no model imports.

Alignment (research R3): for each gold claim, the best-matching output claim by
span IoU >= 0.5 wins; outputs without usable spans fall back to rapidfuzz
token_set_ratio >= 85 on the quoted text, and every fallback match is FLAGGED
in per_claim.csv so a skeptical judge can inspect all of them. Each output
claim matches at most one gold claim (greedy, best score first). An unmatched
gold claim is a MISS: it costs recall for its gold class and is recorded as
verdict "missed".

Primary metric: macro-F1 over {holds, violated, unverifiable} per system
across all scored cases. Also reported: violation recall ("violations caught"),
false alarms, fallback-match count, tokens and wall time.

Exit codes: 0 ok; 4 gold missing/invalid (cli-contracts.md).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from rapidfuzz import fuzz

from docdrift.config import FUZZY_FALLBACK_RATIO, GOLD_DIR, RESULTS_DIR, RUNS_DIR, SPAN_IOU_THRESHOLD
from docdrift.schemas import GoldFile, SystemOutput

CLASSES = ("holds", "violated", "unverifiable")


def span_iou(a: tuple[int, int], b: tuple[int, int]) -> float:
    inter = max(0, min(a[1], b[1]) - max(a[0], b[0]))
    union = max(a[1], b[1]) - min(a[0], b[0])
    return inter / union if union > 0 else 0.0


@dataclass
class Match:
    gold_id: str
    gold_verdict: str
    predicted: str            # holds | violated | unverifiable | missed
    via: str                  # span | fuzzy | none
    computed: str | None = None


@dataclass
class SystemScore:
    system: str
    matches: list[Match] = field(default_factory=list)
    tokens: int = 0
    wall_s: float = 0.0
    cases: int = 0

    def confusion(self) -> dict[str, dict[str, int]]:
        conf: dict[str, dict[str, int]] = {c: {} for c in CLASSES}
        for m in self.matches:
            row = conf[m.gold_verdict]
            row[m.predicted] = row.get(m.predicted, 0) + 1
        return conf

    def per_class(self) -> dict[str, tuple[float, float, float]]:
        conf = self.confusion()
        out = {}
        for cls in CLASSES:
            tp = conf[cls].get(cls, 0)
            fn = sum(n for pred, n in conf[cls].items() if pred != cls)
            fp = sum(conf[g].get(cls, 0) for g in CLASSES if g != cls)
            p = tp / (tp + fp) if tp + fp else 0.0
            r = tp / (tp + fn) if tp + fn else 0.0
            f1 = 2 * p * r / (p + r) if p + r else 0.0
            out[cls] = (p, r, f1)
        return out

    def macro_f1(self) -> float:
        per = self.per_class()
        return sum(f1 for _, _, f1 in per.values()) / len(CLASSES)

    def violations_caught(self) -> tuple[int, int]:
        gold_v = [m for m in self.matches if m.gold_verdict == "violated"]
        return sum(m.predicted == "violated" for m in gold_v), len(gold_v)

    def fallbacks(self) -> int:
        return sum(m.via == "fuzzy" for m in self.matches)


def align_case(gold: GoldFile, out: SystemOutput) -> list[Match]:
    candidates = []  # (score, is_span, gold_idx, out_idx)
    for gi, g in enumerate(gold.gold_claims):
        for oi, o in enumerate(out.claims):
            if o.span_start is not None and o.span_end is not None and o.span_end > o.span_start:
                iou = span_iou((g.span_start, g.span_end), (o.span_start, o.span_end))
                if iou >= SPAN_IOU_THRESHOLD:
                    candidates.append((iou + 1.0, True, gi, oi))  # span matches always beat fuzzy
                    continue
            ratio = fuzz.token_set_ratio(g.quoted_span, o.quoted_span)
            if ratio >= FUZZY_FALLBACK_RATIO:
                candidates.append((ratio / 100.0, False, gi, oi))
    candidates.sort(key=lambda c: (-c[0], c[2], c[3]))  # deterministic greedy

    taken_gold: set[int] = set()
    taken_out: set[int] = set()
    matches: dict[int, Match] = {}
    for score, is_span, gi, oi in candidates:
        if gi in taken_gold or oi in taken_out:
            continue
        taken_gold.add(gi)
        taken_out.add(oi)
        g, o = gold.gold_claims[gi], out.claims[oi]
        matches[gi] = Match(g.id, g.gold_verdict.value, o.verdict.value,
                            "span" if is_span else "fuzzy", o.computed)
    return [
        matches.get(gi, Match(g.id, g.gold_verdict.value, "missed", "none"))
        for gi, g in enumerate(gold.gold_claims)
    ]


def load_gold(gold_dir: Path) -> dict[str, GoldFile]:
    files = sorted(gold_dir.glob("case_*_gold.json"))
    if not files:
        print(f"no gold files under {gold_dir}", file=sys.stderr)
        sys.exit(4)
    out = {}
    for f in files:
        try:
            g = GoldFile.model_validate_json(f.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"invalid gold file {f.name}: {exc}", file=sys.stderr)
            sys.exit(4)
        out[g.case_id] = g
    return out


def score(runs_dir: Path, gold_dir: Path, out_dir: Path) -> dict[str, SystemScore]:
    gold = load_gold(gold_dir)
    systems: dict[str, SystemScore] = {}
    rows: list[dict[str, str]] = []

    for case_id in sorted(gold):
        case_dir = runs_dir / case_id
        if not case_dir.is_dir():
            continue
        for sys_dir in sorted(p for p in case_dir.iterdir() if p.is_dir()):
            verdicts = sys_dir / "verdicts.json"
            if not verdicts.is_file():
                continue
            out = SystemOutput.model_validate_json(verdicts.read_text(encoding="utf-8"))
            s = systems.setdefault(out.system.value, SystemScore(out.system.value))
            matches = align_case(gold[case_id], out)
            s.matches.extend(matches)
            s.tokens += out.usage.input_tokens + out.usage.output_tokens
            s.wall_s += out.wall_s
            s.cases += 1
            for m in matches:
                rows.append({
                    "case": case_id, "system": out.system.value, "gold_id": m.gold_id,
                    "gold": m.gold_verdict, "predicted": m.predicted, "via": m.via,
                    "computed": m.computed or "",
                })

    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "per_claim.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["case", "system", "gold_id", "gold",
                                                "predicted", "via", "computed"])
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# Results",
        "",
        "| system | cases | claims | holds P/R | violated P/R | unverif P/R | macro-F1 "
        "| violations caught | fallback matches | tokens | wall s |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for name in sorted(systems):
        s = systems[name]
        per = s.per_class()
        caught, total_v = s.violations_caught()
        fmt = lambda cls: f"{per[cls][0]:.2f}/{per[cls][1]:.2f}"
        lines.append(
            f"| {name} | {s.cases} | {len(s.matches)} | {fmt('holds')} | {fmt('violated')} "
            f"| {fmt('unverifiable')} | **{s.macro_f1():.3f}** | {caught}/{total_v} "
            f"| {s.fallbacks()} | {s.tokens} | {s.wall_s:.0f} |"
        )
    lines += ["", "Full per-claim detail (including every flagged fuzzy-fallback match): `per_claim.csv`.", ""]
    (out_dir / "results.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return systems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs-dir", type=Path, default=RUNS_DIR)
    parser.add_argument("--gold-dir", type=Path, default=GOLD_DIR)
    parser.add_argument("--out", type=Path, default=RESULTS_DIR)
    args = parser.parse_args()
    systems = score(args.runs_dir, args.gold_dir, args.out)
    if not systems:
        print("no verdicts.json found to score (run baselines/agent first)")
        return 0
    for name in sorted(systems):
        s = systems[name]
        caught, total = s.violations_caught()
        print(f"{name}: macro-F1={s.macro_f1():.3f} violations={caught}/{total} "
              f"fallbacks={s.fallbacks()} cases={s.cases}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
