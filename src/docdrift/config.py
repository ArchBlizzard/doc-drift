"""Central configuration: model aliases, paths, caps, and tolerances.

Every tunable the spec or contracts reference lives here so REPRODUCE.md can
cite one file. Model aliases resolve through Claude Code auth (research R2);
resolved model IDs are recorded per run in the ledger.
"""

from pathlib import Path

# --- models (aliases per plan.md Technical Context) ---
MODEL_AGENT = "sonnet"        # extractor, synthesizer, reporter, baselines
MODEL_ABLATION = "haiku"      # T029 synthesizer ablation

# --- orchestration caps (Constitution IV) ---
LLM_RETRY_CAP = 2             # validated-output retries per judgment point
CLAIM_SEMAPHORE = 4           # concurrent per-claim pipelines

# --- executor sandbox (research R5) ---
EXECUTOR_TIMEOUT_S = 60
EXECUTOR_STDOUT_CAP = 4096    # bytes
EVIDENCE_ROWS_MAX = 5         # FR-006

# --- eval ---
MASTER_SEED = 20260829        # case generation + hard-case synthesis
FUZZY_TOLERANCE_PP = 2.0      # ±percentage points for "roughly X%" claims (spec edge case)
SPAN_IOU_THRESHOLD = 0.5      # primary alignment (research R3)
FUZZY_FALLBACK_RATIO = 85     # rapidfuzz token-set fallback, flagged in results

# --- paths (repo-relative) ---
ROOT = Path(__file__).resolve().parents[2]
DATA_SRC = ROOT / "data_src"
CARDS_DIR = DATA_SRC / "cards"
CASES_DIR = ROOT / "cases"
EVAL_DIR = ROOT / "eval"
SPECS_DIR = EVAL_DIR / "specs"
GOLD_DIR = EVAL_DIR / "gold"
RUNS_DIR = ROOT / "runs"
RESULTS_DIR = ROOT / "results"
LESSONS_FILE = ROOT / "lessons.md"
