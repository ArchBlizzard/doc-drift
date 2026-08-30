"""Local web UI (T040): upload a dataset + its data card, get the audit.

A thin Starlette app over the unchanged pipeline: uploads (or a Kaggle
`owner/slug` fetched with the user's own local credentials) become an ad-hoc
case directory, `orchestrator.run_case` runs as a background asyncio task,
and a progress page polls the ledger until the audit is ready.

Deliberately a LOCAL, single-user demo surface: binds 127.0.0.1, no auth, no
multi-tenancy; the analysis itself stays read-only with the same sandboxed
executor. Zero new dependencies — starlette, uvicorn, and python-multipart
already ship with the project's dependency tree.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import json
import os
import re
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from starlette.routing import Route

from docdrift import orchestrator
from docdrift.config import CASES_DIR, MODEL_AGENT, RUNS_DIR
from docdrift.schemas import SystemOutput

PAGE = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">{refresh}
<title>DocDrift</title><style>
body{{font-family:system-ui,sans-serif;max-width:880px;margin:2rem auto;padding:0 1rem;color:#1a1a1a;background:#fafaf8}}
h1{{font-size:1.5rem}} h1 a{{color:inherit;text-decoration:none}}
.card{{background:#fff;border:1px solid #ddd;border-radius:8px;padding:1.2rem;margin:1rem 0}}
label{{display:block;font-weight:600;margin:.8rem 0 .2rem}}
input,textarea{{width:100%;box-sizing:border-box;padding:.4rem;border:1px solid #bbb;border-radius:4px;font:inherit}}
textarea{{height:8rem;font-family:ui-monospace,monospace}}
button{{margin-top:1rem;padding:.5rem 1.4rem;font:inherit;font-weight:600;background:#1a1a1a;color:#fff;border:0;border-radius:6px;cursor:pointer}}
table{{border-collapse:collapse;width:100%;font-size:.85rem}} td,th{{border:1px solid #ddd;padding:.35rem .5rem;text-align:left;vertical-align:top}}
.violated{{background:#fde8e8}} .holds{{background:#e8f5e9}} .unverifiable{{background:#f5f5f5;color:#666}}
.muted{{color:#666;font-size:.85rem}} code{{background:#eee;padding:0 .2rem;border-radius:3px}}
.summary{{white-space:pre-wrap}}</style></head>
<body><h1><a href="/">DocDrift</a> <span class="muted">— does the data card tell the truth?</span></h1>
{body}</body></html>"""

FORM = """<div class="card"><h2>Audit an uploaded dataset</h2>
<form method="post" action="/audit" enctype="multipart/form-data">
<label>Data file (.csv or .parquet)</label><input type="file" name="data" required>
<label>Data card / README (.md or .txt file — or paste below)</label><input type="file" name="card">
<textarea name="card_text" placeholder="...or paste the documentation text here"></textarea>
<button>Run audit</button></form></div>
<div class="card"><h2>…or audit a Kaggle dataset</h2>
<form method="post" action="/audit">
<label>Kaggle dataset ref (owner/slug, e.g. <code>uciml/iris</code>)</label>
<input name="kaggle_ref" placeholder="owner/slug" required>
<p class="muted">Uses your local Kaggle credentials (~/.kaggle/kaggle.json). The dataset's own
description becomes the card; its first CSV becomes the data.</p>
<button>Fetch &amp; run audit</button></form></div>
<p class="muted">Runs the full gated pipeline locally: claim extraction → check synthesis →
mutation gate → full-file execution → audit. Typically 1–4 minutes.</p>"""


@dataclass
class Job:
    case_id: str
    error: str | None = None
    task: asyncio.Task | None = field(default=None, repr=False)


JOBS: dict[str, Job] = {}
SAFE_FILES = {"audit.md", "ledger.jsonl", "verdicts.json", "messages.jsonl"}


def _slug(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:24] or "dataset"
    return f"web_{base}_{hashlib.sha256(os.urandom(8)).hexdigest()[:6]}"


def _kaggle_fetch(ref: str, case_dir: Path) -> None:
    user, key = os.environ.get("KAGGLE_USERNAME"), os.environ.get("KAGGLE_KEY")
    cfg = Path.home() / ".kaggle" / "kaggle.json"
    if not (user and key) and cfg.is_file():
        data = json.loads(cfg.read_text(encoding="utf-8"))
        user, key = data.get("username"), data.get("key")
    if not (user and key):
        raise RuntimeError("no Kaggle credentials found (~/.kaggle/kaggle.json)")

    def get(url: str) -> bytes:
        req = urllib.request.Request(url, headers={
            "User-Agent": "docdrift-web/0.1",
            "Authorization": "Basic " + base64.b64encode(f"{user}:{key}".encode()).decode()})
        with urllib.request.urlopen(req, timeout=180) as r:
            return r.read()

    meta = json.loads(get(f"https://www.kaggle.com/api/v1/datasets/view/{ref}"))
    description = (meta.get("description") or "").strip()
    if not description:
        raise RuntimeError(f"Kaggle dataset {ref} has no description to audit")
    blob = get(f"https://www.kaggle.com/api/v1/datasets/download/{ref}")
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        csv_name = next((n for n in zf.namelist() if n.lower().endswith(".csv")), None)
        if csv_name is None:
            raise RuntimeError(f"{ref} contains no CSV file")
        (case_dir / "data.csv").write_bytes(zf.read(csv_name))
    (case_dir / "datacard.md").write_text(description, encoding="utf-8", newline="\n")


async def _run_job(job: Job) -> None:
    try:
        await orchestrator.run_case(job.case_id, model=MODEL_AGENT)
    except Exception as exc:  # surfaced on the progress page
        job.error = f"{type(exc).__name__}: {exc}"


async def index(request: Request) -> HTMLResponse:
    return HTMLResponse(PAGE.format(refresh="", body=FORM))


async def audit(request: Request) -> HTMLResponse | RedirectResponse:
    form = await request.form()
    kaggle_ref = (form.get("kaggle_ref") or "").strip()
    try:
        if kaggle_ref:
            if not re.fullmatch(r"[A-Za-z0-9._-]+/[A-Za-z0-9._-]+", kaggle_ref):
                raise RuntimeError("Kaggle ref must look like owner/slug")
            case_id = _slug(kaggle_ref.split("/")[1])
            case_dir = CASES_DIR / case_id
            case_dir.mkdir(parents=True, exist_ok=True)
            await asyncio.to_thread(_kaggle_fetch, kaggle_ref, case_dir)
        else:
            data = form.get("data")
            card_file = form.get("card")
            card_text = (form.get("card_text") or "").strip()
            if data is None or not getattr(data, "filename", ""):
                raise RuntimeError("a data file is required")
            suffix = Path(data.filename).suffix.lower()
            if suffix not in (".csv", ".parquet"):
                raise RuntimeError("data file must be .csv or .parquet")
            card_bytes = await card_file.read() if getattr(card_file, "filename", "") else b""
            card = card_bytes.decode("utf-8", errors="replace").strip() or card_text
            if not card:
                raise RuntimeError("provide a data card file or paste its text")
            case_id = _slug(Path(data.filename).stem)
            case_dir = CASES_DIR / case_id
            case_dir.mkdir(parents=True, exist_ok=True)
            (case_dir / f"data{suffix}").write_bytes(await data.read())
            (case_dir / "datacard.md").write_text(card, encoding="utf-8", newline="\n")
    except RuntimeError as exc:
        return HTMLResponse(PAGE.format(
            refresh="", body=f'<div class="card"><b>Cannot start:</b> {exc}</div>{FORM}'),
            status_code=400)

    job = Job(case_id=case_id)
    job.task = asyncio.get_running_loop().create_task(_run_job(job))
    JOBS[case_id] = job
    return RedirectResponse(f"/job/{case_id}", status_code=303)


def _progress(case_id: str) -> tuple[int, int | None]:
    agent_dir = RUNS_DIR / case_id / "agent"
    total = None
    claims_file = agent_dir / "claims.json"
    if claims_file.is_file():
        total = len(json.loads(claims_file.read_text(encoding="utf-8"))["claims"])
    ledger = agent_dir / "ledger.jsonl"
    settled = max(0, len(ledger.read_text(encoding="utf-8").splitlines()) - 1) if ledger.is_file() else 0
    return settled, total


async def job_page(request: Request) -> HTMLResponse:
    case_id = request.path_params["case_id"]
    job = JOBS.get(case_id)
    if job is None:
        return HTMLResponse(PAGE.format(refresh="", body="<div class='card'>Unknown job.</div>"),
                            status_code=404)
    if job.error:
        return HTMLResponse(PAGE.format(
            refresh="", body=f"<div class='card'><b>Audit failed:</b> {job.error}</div>{FORM}"))
    if (RUNS_DIR / case_id / "agent" / "verdicts.json").is_file() and job.task and job.task.done():
        return RedirectResponse(f"/result/{case_id}", status_code=303)
    settled, total = _progress(case_id)
    stage = ("extracting claims from the card…" if total is None
             else f"verifying claims: {settled}/{total} settled")
    return HTMLResponse(PAGE.format(
        refresh='<meta http-equiv="refresh" content="3">',
        body=f"<div class='card'><h2>Auditing…</h2><p>{stage}</p>"
             f"<p class='muted'>This page refreshes every 3 seconds. Each claim gets a check "
             f"that must survive its own mutation test before it is trusted.</p></div>"))


async def result_page(request: Request) -> HTMLResponse:
    case_id = request.path_params["case_id"]
    agent_dir = RUNS_DIR / case_id / "agent"
    verdicts_file = agent_dir / "verdicts.json"
    if case_id not in JOBS or not verdicts_file.is_file():
        return HTMLResponse(PAGE.format(refresh="", body="<div class='card'>No such result.</div>"),
                            status_code=404)
    out = SystemOutput.model_validate_json(verdicts_file.read_text(encoding="utf-8"))
    audit_md = (agent_dir / "audit.md").read_text(encoding="utf-8")
    summary = audit_md.split("## Executive summary", 1)[-1].split("## Per-claim", 1)[0].strip()

    rows = []
    for c in out.claims:
        cls = c.verdict.value
        verdict = cls + (f" ({c.reason.value})" if c.reason else "")
        rows.append(f"<tr class='{cls}'><td>{c.quoted_span}</td><td>{verdict}</td>"
                    f"<td><code>{c.computed or '—'}</code></td></tr>")
    counts = {v: sum(1 for c in out.claims if c.verdict.value == v)
              for v in ("violated", "holds", "unverifiable")}
    body = (f"<div class='card'><h2>Audit: {case_id}</h2>"
            f"<p><b>{counts['violated']} violated · {counts['holds']} hold · "
            f"{counts['unverifiable']} unverifiable</b> — model {out.model_id}, "
            f"{out.usage.input_tokens + out.usage.output_tokens} tokens, {out.wall_s:.0f}s</p>"
            f"<div class='summary muted'>{summary}</div></div>"
            f"<div class='card'><table><tr><th>claim (quoted from the card)</th>"
            f"<th>verdict</th><th>computed</th></tr>{''.join(rows)}</table>"
            f"<p class='muted'>Full artifacts: <a href='/file/{case_id}/audit.md'>audit.md</a> · "
            f"<a href='/file/{case_id}/ledger.jsonl'>ledger.jsonl</a> · "
            f"<a href='/file/{case_id}/verdicts.json'>verdicts.json</a></p></div>"
            f"<p><a href='/'>Audit another dataset</a></p>")
    return HTMLResponse(PAGE.format(refresh="", body=body))


async def serve_file(request: Request) -> PlainTextResponse:
    case_id, name = request.path_params["case_id"], request.path_params["name"]
    if case_id not in JOBS or name not in SAFE_FILES:
        return PlainTextResponse("not found", status_code=404)
    path = RUNS_DIR / case_id / "agent" / name
    if not path.is_file():
        return PlainTextResponse("not found", status_code=404)
    return PlainTextResponse(path.read_text(encoding="utf-8"))


app = Starlette(routes=[
    Route("/", index),
    Route("/audit", audit, methods=["POST"]),
    Route("/job/{case_id}", job_page),
    Route("/result/{case_id}", result_page),
    Route("/file/{case_id}/{name}", serve_file),
])
