"""Eval sweep runner (T012), per contracts/cli-contracts.md.

`python eval/run_all.py [--systems ...] [--cases ...] [--force] [--no-score]`
runs the selected systems over the selected cases, skipping (case, system)
pairs whose verdicts.json already exists unless --force, then invokes the
deterministic scorer. Resumable by construction: a sweep interrupted by a
usage-window pause continues where it stopped on re-invocation.
"""

from __future__ import annotations

import argparse
import sys
import traceback
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # repo root: run_baseline/run_agent

from docdrift.config import CASES_DIR, GOLD_DIR, RESULTS_DIR, RUNS_DIR

DEFAULT_SYSTEMS = ["baseline", "baseline_plus", "agent"]
KNOWN_SYSTEMS = DEFAULT_SYSTEMS + ["baseline_stratified"]


def make_runner(system: str) -> Callable[[str, Path], None]:
    """Lazy imports so baselines run before the agent (or ablations) exist."""
    if system == "baseline":
        import anyio
        import run_baseline
        return lambda case, out: anyio.run(
            lambda: run_baseline.run_case(case, plus=False, out_root=out))
    if system == "baseline_plus":
        import anyio
        import run_baseline
        return lambda case, out: anyio.run(
            lambda: run_baseline.run_case(case, plus=True, out_root=out))
    if system == "agent":
        import run_agent
        return lambda case, out: run_agent.run_case_sync(case, out_root=out)
    if system == "baseline_stratified":
        import run_stratified
        return lambda case, out: run_stratified.run_case_sync(case, out_root=out)
    raise ValueError(f"unknown system {system!r} (known: {', '.join(KNOWN_SYSTEMS)})")


def pairs_to_run(cases: list[str], systems: list[str],
                 runs_dir: Path, force: bool) -> list[tuple[str, str]]:
    pairs = []
    for case in cases:
        for system in systems:
            if not force and (runs_dir / case / system / "verdicts.json").is_file():
                continue
            pairs.append((case, system))
    return pairs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--systems", default=",".join(DEFAULT_SYSTEMS))
    parser.add_argument("--cases", default="")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--no-score", action="store_true")
    parser.add_argument("--runs-dir", type=Path, default=RUNS_DIR)
    args = parser.parse_args(argv)

    systems = [s.strip() for s in args.systems.split(",") if s.strip()]
    for s in systems:
        if s not in KNOWN_SYSTEMS:
            print(f"unknown system {s!r}", file=sys.stderr)
            return 4

    if args.cases:
        cases = [c.strip() for c in args.cases.split(",") if c.strip()]
    else:
        cases = sorted(p.name for p in CASES_DIR.glob("case_*") if p.is_dir())
    if not cases:
        print("no cases found — run `make data` first", file=sys.stderr)
        return 3

    pairs = pairs_to_run(cases, systems, args.runs_dir, args.force)
    done = len(cases) * len(systems) - len(pairs)
    if done:
        print(f"skipping {done} already-completed (case, system) pairs (use --force to redo)")

    failures = 0
    for case, system in pairs:
        print(f"[{system}] {case} ...", flush=True)
        try:
            make_runner(system)(case, args.runs_dir)
        except KeyboardInterrupt:
            raise
        except SystemExit as exc:
            print(f"  FAILED (exit {exc.code})", flush=True)
            failures += 1
        except Exception as exc:
            print(f"  FAILED: {type(exc).__name__}: {exc}", flush=True)
            traceback.print_exc(limit=3)
            failures += 1

    if not args.no_score:
        import score
        score.score(args.runs_dir, GOLD_DIR, RESULTS_DIR)
        print(f"scored -> {RESULTS_DIR / 'results.md'}")

    if failures:
        print(f"{failures} run(s) failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
