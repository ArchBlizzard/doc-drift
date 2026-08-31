"""Local web UI (T040, restyled in T042): upload a dataset and its data card,
get the audit.

A thin Starlette app over the unchanged pipeline: uploads (or a Kaggle
"owner/slug" fetched with the user's own local credentials) become a case
folder, orchestrator.run_case runs as a background task, and the progress
page polls a small JSON endpoint until the audit is ready.

Design follows Apple's Human Interface Guidelines: system font, quiet
background, rounded cards, one accent color, large touch targets, motion only
where it carries meaning, and full dark mode.

This stays a small demo surface: single process, no accounts. For a deployed
copy, set DOCDRIFT_ACCESS_CODE so only people you give the code to can start
audits (pages and results stay viewable). The analysis itself is read-only
and every check still runs in the sandboxed executor.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import json
import os
import re
import time
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
from starlette.routing import Route

from docdrift import orchestrator
from docdrift.config import CASES_DIR, MODEL_AGENT, RUNS_DIR
from docdrift.schemas import SystemOutput

SHELL = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>DocDrift</title><style>
:root{
  --bg:#f5f5f7; --card:#ffffff; --ink:#1d1d1f; --muted:#6e6e73;
  --line:#e8e8ed; --accent:#0071e3; --accent-ink:#ffffff;
  --ok:#e8f6ec; --ok-ink:#1d7a36; --bad:#fdecec; --bad-ink:#c22b2b;
  --gray:#f2f2f4; --gray-ink:#6e6e73; --shadow:0 6px 30px rgba(0,0,0,.06);
}
@media (prefers-color-scheme: dark){:root{
  --bg:#161617; --card:#1d1d1f; --ink:#f5f5f7; --muted:#a1a1a6;
  --line:#2d2d30; --accent:#0a84ff;
  --ok:#12351c; --ok-ink:#5bd77e; --bad:#3d1a1a; --bad-ink:#ff8080;
  --gray:#2a2a2c; --gray-ink:#a1a1a6; --shadow:0 6px 30px rgba(0,0,0,.4);
}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI",Roboto,sans-serif;
  -webkit-font-smoothing:antialiased;font-size:15px;line-height:1.5}
.wrap{max-width:820px;margin:0 auto;padding:2.5rem 1.2rem 4rem}
h1{font-size:2rem;font-weight:700;letter-spacing:-.02em;margin:0}
h1 a{color:inherit;text-decoration:none}
.tag{color:var(--muted);font-size:1rem;margin:.2rem 0 1.6rem}
h2{font-size:1.15rem;font-weight:600;margin:0 0 1rem}
.card{background:var(--card);border-radius:18px;padding:1.6rem;margin:1rem 0;
  box-shadow:var(--shadow);animation:rise .35s ease both}
@keyframes rise{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
.seg{display:flex;background:var(--gray);border-radius:12px;padding:3px;margin-bottom:1.4rem}
.seg button{flex:1;border:0;background:transparent;color:var(--muted);font:inherit;
  font-weight:600;padding:.55rem;border-radius:9px;cursor:pointer;transition:all .18s}
.seg button.on{background:var(--card);color:var(--ink);box-shadow:0 1px 6px rgba(0,0,0,.12)}
label{display:block;font-weight:600;font-size:.9rem;margin:1rem 0 .35rem}
input[type=text],input[type=password],textarea{width:100%;padding:.65rem .8rem;font:inherit;
  color:var(--ink);background:var(--bg);border:1px solid var(--line);border-radius:10px}
input:focus,textarea:focus{outline:none;border-color:var(--accent);
  box-shadow:0 0 0 3px color-mix(in srgb, var(--accent) 25%, transparent)}
textarea{height:9rem;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.85rem}
.drop{border:1.5px dashed var(--line);border-radius:14px;padding:1.6rem;text-align:center;
  color:var(--muted);cursor:pointer;transition:all .18s}
.drop.hot{border-color:var(--accent);background:color-mix(in srgb, var(--accent) 6%, transparent)}
.drop b{color:var(--accent)}
.drop .picked{color:var(--ink);font-weight:600}
.btn{display:inline-block;margin-top:1.3rem;padding:.65rem 1.8rem;font:inherit;font-weight:600;
  background:var(--accent);color:var(--accent-ink);border:0;border-radius:980px;cursor:pointer;
  transition:transform .12s, filter .15s}
.btn:hover{filter:brightness(1.08)} .btn:active{transform:scale(.97)}
.muted{color:var(--muted);font-size:.85rem}
.bar{height:6px;background:var(--gray);border-radius:3px;overflow:hidden;margin:1rem 0 .6rem}
.bar i{display:block;height:100%;width:0%;background:var(--accent);border-radius:3px;
  transition:width .6s ease}
.bar.wait i{width:30%;animation:slide 1.4s ease-in-out infinite alternate}
@keyframes slide{from{margin-left:0}to{margin-left:70%}}
table{border-collapse:collapse;width:100%;font-size:.86rem}
td,th{padding:.55rem .6rem;text-align:left;vertical-align:top;border-top:1px solid var(--line)}
th{color:var(--muted);font-weight:600;font-size:.78rem;text-transform:uppercase;
  letter-spacing:.04em;border-top:0}
tr{transition:background .15s}
tbody tr:hover{background:color-mix(in srgb, var(--accent) 5%, transparent)}
.chip{display:inline-block;padding:.15rem .6rem;border-radius:980px;font-weight:600;
  font-size:.78rem;white-space:nowrap}
.chip.violated{background:var(--bad);color:var(--bad-ink)}
.chip.holds{background:var(--ok);color:var(--ok-ink)}
.chip.unverifiable{background:var(--gray);color:var(--gray-ink)}
.stats{display:flex;gap:.6rem;flex-wrap:wrap;margin:.4rem 0 1rem}
.stat{background:var(--bg);border-radius:12px;padding:.6rem 1rem;text-align:center}
.stat b{display:block;font-size:1.3rem}
.stat span{font-size:.78rem;color:var(--muted)}
code{background:var(--gray);padding:.05rem .35rem;border-radius:5px;
  font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.82rem}
.summary{white-space:pre-wrap;color:var(--muted)}
a{color:var(--accent)}
.error{background:var(--bad);color:var(--bad-ink);border-radius:12px;padding:.8rem 1rem;
  margin-bottom:1rem;font-weight:600}
.scroll{overflow-x:auto}
.pct{font-variant-numeric:tabular-nums;font-weight:700;font-size:1.6rem}
.log{margin-top:1rem;max-height:16rem;overflow-y:auto;border-top:1px solid var(--line);
  padding-top:.6rem;font-size:.84rem}
.log div{padding:.22rem 0;color:var(--muted);animation:rise .3s ease both}
.log b{color:var(--ink);font-weight:600}
.log .v{color:var(--bad-ink)} .log .h{color:var(--ok-ink)}
.modal{position:fixed;inset:0;background:rgba(0,0,0,.45);display:none;
  align-items:center;justify-content:center;padding:1.2rem;z-index:50}
.modal.open{display:flex}
.sheet{background:var(--card);color:var(--ink);border-radius:18px;box-shadow:var(--shadow);
  width:min(860px,100%);max-height:86vh;display:flex;flex-direction:column;
  animation:rise .25s ease both}
.sheet header{display:flex;align-items:center;justify-content:space-between;
  padding:.9rem 1.2rem;border-bottom:1px solid var(--line)}
.sheet header b{font-size:.95rem}
.sheet .x{border:0;background:var(--gray);color:var(--ink);border-radius:980px;
  width:1.9rem;height:1.9rem;font-size:1rem;cursor:pointer}
.sheet pre{margin:0;padding:1rem 1.2rem;overflow:auto;white-space:pre-wrap;
  word-break:break-word;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
  font-size:.8rem;line-height:1.5}
.sheet footer{padding:.6rem 1.2rem;border-top:1px solid var(--line);font-size:.82rem}
.duel{display:grid;grid-template-columns:1fr 1fr;gap:.8rem;margin:.4rem 0 1rem}
@media (max-width:640px){.duel{grid-template-columns:1fr}}
.side{background:var(--bg);border-radius:14px;padding:.9rem 1rem}
.side h3{margin:0 0 .5rem;font-size:.95rem}
.side .nums{display:flex;gap:1rem;font-variant-numeric:tabular-nums}
.side .nums b{font-size:1.25rem;display:block}
.side .nums span{font-size:.75rem;color:var(--muted)}
details{margin-top:.6rem}
summary{cursor:pointer;color:var(--accent);font-size:.85rem}
details pre{background:var(--bg);border-radius:10px;padding:.8rem;overflow:auto;
  white-space:pre-wrap;font-size:.75rem;line-height:1.5;
  font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
.dim{color:var(--muted);font-style:italic;font-size:.8rem}
</style></head><body><div class="wrap">
<h1><a href="/">DocDrift</a></h1>
<p class="tag">Checks whether a dataset's documentation tells the truth.</p>
__BODY__
</div>__SCRIPT__</body></html>"""

FORM_BODY = """__ERROR__<div class="card">
<div class="seg" role="tablist">
  <button type="button" id="tab-up" class="on" onclick="pick('up')">Upload a file</button>
  <button type="button" id="tab-kg" onclick="pick('kg')">From Kaggle</button>
</div>
<form id="f-up" method="post" action="/audit" enctype="multipart/form-data">
  <h2>Audit an uploaded dataset</h2>
  <div class="drop" id="drop" onclick="document.getElementById('data').click()">
    <span id="drop-label"><b>Choose a file</b> or drag it here<br>
    <span class="muted">.csv or .parquet</span></span>
  </div>
  <input type="file" id="data" name="data" accept=".csv,.parquet" hidden>
  <label>Its documentation (paste the README text, or upload it)</label>
  <textarea name="card_text" placeholder="Paste the data card / README text here. Example: The file holds 150 rows. There are no missing values."></textarea>
  <input type="file" name="card" accept=".md,.txt" style="margin-top:.5rem">
  <label style="font-weight:400"><input type="checkbox" name="compare" value="1" checked
    style="width:auto;margin-right:.4rem"> Also ask the AI directly, for a side by side
    comparison</label>
  __CODE_FIELD__
  <button class="btn">Run the audit</button>
</form>
<form id="f-kg" method="post" action="/audit" hidden>
  <h2>Audit a Kaggle dataset</h2>
  <label>Dataset ref (owner/slug)</label>
  <input type="text" name="kaggle_ref" placeholder="uciml/iris">
  <p class="muted">Uses the Kaggle credentials on this machine. The dataset's own
  description becomes the card and its first CSV becomes the data.</p>
  <label style="font-weight:400"><input type="checkbox" name="compare" value="1" checked
    style="width:auto;margin-right:.4rem"> Also ask the AI directly, for a side by side
    comparison</label>
  __CODE_FIELD__
  <button class="btn">Fetch and run the audit</button>
</form>
</div>
<p class="muted">What happens next: every claim in the documentation becomes a small
Python check. Each check must first prove it can catch a fake violation before it is
trusted, then it runs against the full file. You get a report with evidence.
Takes about 1 to 4 minutes.</p>"""

FORM_SCRIPT = """<script>
function pick(which){
  const up = which === 'up';
  document.getElementById('f-up').hidden = !up;
  document.getElementById('f-kg').hidden = up;
  document.getElementById('tab-up').classList.toggle('on', up);
  document.getElementById('tab-kg').classList.toggle('on', !up);
}
const drop = document.getElementById('drop'), file = document.getElementById('data');
function show(name){ document.getElementById('drop-label').innerHTML =
  '<span class="picked">' + name + '</span><br><span class="muted">click to change</span>'; }
file.addEventListener('change', () => file.files[0] && show(file.files[0].name));
['dragover','dragenter'].forEach(ev => drop.addEventListener(ev, e => {
  e.preventDefault(); drop.classList.add('hot'); }));
['dragleave','drop'].forEach(ev => drop.addEventListener(ev, e => {
  e.preventDefault(); drop.classList.remove('hot'); }));
drop.addEventListener('drop', e => {
  if (e.dataTransfer.files.length){ file.files = e.dataTransfer.files; show(file.files[0].name); }});
</script>"""

DOCDRIFT_PANEL = """<div style="display:flex;align-items:baseline;justify-content:space-between">
  <h2 id="stage" style="margin:0">Reading the documentation…</h2>
  <span class="pct" id="pct"></span>
</div>
<div class="bar wait" id="bar"><i id="fill"></i></div>
<p class="muted" id="detail">Finding every claim the card makes about the data.</p>
<div class="log" id="log" hidden></div>"""

JOB_BODY = f'<div class="card">{DOCDRIFT_PANEL}</div>'

JOB_BODY_COMPARE = """<div class="duel" style="align-items:start">
<div class="card" style="margin:0"><h3 style="margin:0 0 .6rem">With DocDrift</h3>
__PANEL__
</div>
<div class="card" style="margin:0"><h3 style="margin:0 0 .6rem">Just asking the AI</h3>
<div class="bar wait" id="b-bar"><i id="b-fill"></i></div>
<p class="muted" id="b-detail">One message to the same model: the documentation, the
column types, and the first 50 rows. No code, no full-file access.</p>
<div class="log" id="b-log" hidden></div>
<details><summary>See the exact prompt it was given</summary>
<pre>__PROMPT__</pre></details>
</div></div>""".replace("__PANEL__", DOCDRIFT_PANEL)

JOB_SCRIPT = """<script>
const jobId = "__JOB_ID__";
let shown = 0, target = 0, shownPct = 0, announced = false, finished = false;
const STAGES = {
  fetching:  ['Fetching the dataset…', 'Downloading it and its documentation from Kaggle.'],
  extracting:['Reading the documentation…', 'Finding every claim the card makes about the data.'],
  checking:  ['Checking claims…', ''],
};
function addLog(html){
  const box = document.getElementById('log');
  box.hidden = false;
  const div = document.createElement('div');
  div.innerHTML = html;
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
}
// the bar glides toward its target and keeps a gentle forward creep, so it
// never freezes and never jumps
setInterval(() => {
  if (finished) return;
  shownPct = Math.min(target, shownPct + (target - shownPct) * 0.08 + 0.05);
  document.getElementById('fill').style.width = shownPct + '%';
  document.getElementById('pct').textContent = Math.floor(shownPct) + '%';
}, 120);
async function tick(){
  try{
    const r = await fetch('/api/job/' + jobId);
    const s = await r.json();
    if (s.state === 'error'){
      document.getElementById('stage').textContent = 'The audit failed';
      document.getElementById('detail').textContent = s.error;
      document.getElementById('bar').classList.remove('wait');
      return;
    }
    const [title, detail] = STAGES[s.stage] || STAGES.checking;
    document.getElementById('stage').textContent = title;
    if (s.stage === 'fetching'){
      target = Math.min(6, s.elapsed * 0.4);
      document.getElementById('detail').textContent = detail;
    } else if (s.stage === 'extracting'){
      target = Math.min(15, 6 + s.elapsed * 0.35);
      document.getElementById('detail').textContent = detail;
    } else if (s.total){
      target = 15 + 85 * (s.settled + 0.5 * s.inflight) / s.total;
      document.getElementById('detail').textContent =
        s.settled + ' of ' + s.total + ' claims settled'
        + (s.inflight ? ', ' + s.inflight + ' being checked now' : '');
      document.getElementById('bar').classList.remove('wait');
      if (!announced){
        announced = true;
        addLog('found <b>' + s.total + '</b> claims in the documentation');
        if (s.compare) addLog('also asking the AI directly in parallel, for the comparison');
      }
    }
    (s.events || []).slice(shown).forEach(e => {
      const cls = e.verdict === 'violated' ? 'v' : (e.verdict === 'holds' ? 'h' : '');
      let line = '<b class="' + cls + '">' + e.verdict + '</b> · ' + e.claim;
      if (e.computed) line += ' <b>(' + e.computed + ')</b>';
      if (e.gate_note) line = e.gate_note + '<br>' + line;
      addLog(line);
    });
    shown = (s.events || []).length;
    const b = s.baseline || {};
    const bBar = document.getElementById('b-bar');
    if (bBar && b.requested){
      const bDetail = document.getElementById('b-detail');
      const bLog = document.getElementById('b-log');
      if (b.state === 'waiting'){
        bDetail.textContent = 'Prompt sent. Waiting for the answer… ' + s.elapsed + 's';
      } else if (b.state === 'done' && !bBar.dataset.done){
        bBar.dataset.done = '1';
        bBar.classList.remove('wait');
        document.getElementById('b-fill').style.width = '100%';
        bDetail.textContent = 'Answered in ' + b.wall_s + 's. Waiting for DocDrift to finish.';
        bLog.hidden = false;
        bLog.innerHTML = '<div>judged <b>' + b.claims + '</b> claims from one prompt: '
          + '<b class="v">' + b.counts.violated + ' violated</b>, '
          + '<b class="h">' + b.counts.holds + ' hold</b>, '
          + b.counts.unverifiable + ' set aside</div>'
          + '<div class="dim">no checks were run; these are reading-based opinions</div>';
      } else if (b.state === 'failed'){
        bBar.classList.remove('wait');
        bDetail.textContent = 'The direct ask failed: ' + b.error;
      }
    }
    if (s.state === 'done'){
      finished = true;
      document.getElementById('pct').textContent = '100%';
      document.getElementById('fill').style.width = '100%';
      addLog('writing the report…');
      setTimeout(() => location.href = '/result/' + jobId, 800);
      return;
    }
  }catch(e){}
  setTimeout(tick, 1200);
}
tick();
</script>"""

VIEWER = """<div class="modal" id="modal" onclick="if(event.target===this)closeViewer()">
<div class="sheet"><header><b id="v-title"></b>
<button class="x" onclick="closeViewer()" aria-label="Close">✕</button></header>
<pre id="v-body">loading…</pre>
<footer><a id="v-raw" href="#" target="_blank">open the raw file</a></footer>
</div></div>
<script>
function closeViewer(){ document.getElementById('modal').classList.remove('open'); }
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeViewer(); });
async function view(name, title){
  const modal = document.getElementById('modal');
  document.getElementById('v-title').textContent = title;
  document.getElementById('v-raw').href = '/file/__CASE__/' + name;
  document.getElementById('v-body').textContent = 'loading…';
  modal.classList.add('open');
  const text = await (await fetch('/file/__CASE__/' + name)).text();
  let pretty = text;
  try{
    if (name.endsWith('.json')) pretty = JSON.stringify(JSON.parse(text), null, 2);
    else if (name.endsWith('.jsonl'))
      pretty = text.trim().split('\\n')
        .map(l => JSON.stringify(JSON.parse(l), null, 2))
        .join('\\n\\n────────────────────\\n\\n');
  }catch(e){}
  document.getElementById('v-body').textContent = pretty;
}
</script>"""


@dataclass
class Job:
    case_id: str
    error: str | None = None
    task: asyncio.Task | None = field(default=None, repr=False)
    fetching: bool = False      # Kaggle download still in progress
    compare: bool = False       # also run the ask-AI-directly baseline
    baseline_error: str | None = None
    kaggle_ref: str = ""
    started: float = 0.0


JOBS: dict[str, Job] = {}
SAFE_FILES = {"audit.md", "ledger.jsonl", "verdicts.json", "messages.jsonl"}


def _access_code() -> str:
    return os.environ.get("DOCDRIFT_ACCESS_CODE", "")


def _form_html(error: str = "") -> str:
    code_field = ""
    if _access_code():
        code_field = ('<label>Access code</label>'
                      '<input type="password" name="access_code" placeholder="ask the owner">')
    body = (FORM_BODY.replace("__CODE_FIELD__", code_field)
            .replace("__ERROR__", f'<div class="error">{error}</div>' if error else ""))
    return SHELL.replace("__BODY__", body).replace("__SCRIPT__", FORM_SCRIPT)


def _page(body: str, script: str = "") -> str:
    return SHELL.replace("__BODY__", body).replace("__SCRIPT__", script)


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
        raise RuntimeError("no Kaggle credentials found on this machine (~/.kaggle/kaggle.json)")

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


def _model() -> str:
    """Pipeline model for web audits. Set DOCDRIFT_MODEL=opus for the highest
    quality (see results/ablation_opus.md); default follows the project's
    documented default."""
    return os.environ.get("DOCDRIFT_MODEL", MODEL_AGENT)


async def _run_baseline(case_id: str, model: str) -> None:
    """The 'without DocDrift' side: one message to the same model holding the
    documentation, the column types, and the first 50 rows. No tools, no
    code, no full-file access. Exact prompt: run_baseline.SYSTEM_PROMPT,
    shown verbatim on the result page."""
    import run_baseline
    await run_baseline.run_case(case_id, model=model)


async def _run_job(job: Job) -> None:
    try:
        if job.kaggle_ref:
            job.fetching = True
            case_dir = CASES_DIR / job.case_id
            case_dir.mkdir(parents=True, exist_ok=True)
            await asyncio.to_thread(_kaggle_fetch, job.kaggle_ref, case_dir)
            job.fetching = False
        work = [orchestrator.run_case(job.case_id, model=_model())]
        if job.compare:
            work.append(_run_baseline(job.case_id, _model()))
        results = await asyncio.gather(*work, return_exceptions=True)
        if job.compare and len(results) > 1 and isinstance(results[1], BaseException):
            # a failed comparison run never sinks the audit
            job.baseline_error = f"{type(results[1]).__name__}: {results[1]}"
        if isinstance(results[0], BaseException):
            raise results[0]
    except Exception as exc:  # shown on the progress page
        job.fetching = False
        job.error = f"{type(exc).__name__}: {exc}"


async def index(request: Request) -> HTMLResponse:
    return HTMLResponse(_form_html())


async def audit(request: Request) -> HTMLResponse | RedirectResponse:
    form = await request.form()
    if _access_code() and (form.get("access_code") or "") != _access_code():
        return HTMLResponse(_form_html("Wrong or missing access code."), status_code=403)
    kaggle_ref = (form.get("kaggle_ref") or "").strip()
    compare = bool(form.get("compare"))
    try:
        if kaggle_ref:
            if not re.fullmatch(r"[A-Za-z0-9._-]+/[A-Za-z0-9._-]+", kaggle_ref):
                raise RuntimeError("Kaggle ref must look like owner/slug")
            # the download happens inside the job so this click answers instantly
            case_id = _slug(kaggle_ref.split("/")[1])
        else:
            data = form.get("data")
            card_file = form.get("card")
            card_text = (form.get("card_text") or "").strip()
            if data is None or not getattr(data, "filename", ""):
                raise RuntimeError("a data file is required")
            suffix = Path(data.filename).suffix.lower()
            if suffix not in (".csv", ".parquet"):
                raise RuntimeError("the data file must be .csv or .parquet")
            card_bytes = await card_file.read() if getattr(card_file, "filename", "") else b""
            card = card_bytes.decode("utf-8", errors="replace").strip() or card_text
            if not card:
                raise RuntimeError("provide a data card: paste its text or upload the file")
            case_id = _slug(Path(data.filename).stem)
            case_dir = CASES_DIR / case_id
            case_dir.mkdir(parents=True, exist_ok=True)
            (case_dir / f"data{suffix}").write_bytes(await data.read())
            (case_dir / "datacard.md").write_text(card, encoding="utf-8", newline="\n")
    except RuntimeError as exc:
        return HTMLResponse(_form_html(str(exc)), status_code=400)

    job = Job(case_id=case_id, compare=compare, kaggle_ref=kaggle_ref,
              started=time.time())
    job.task = asyncio.get_running_loop().create_task(_run_job(job))
    JOBS[case_id] = job
    return RedirectResponse(f"/job/{case_id}", status_code=303)


def _progress(case_id: str) -> tuple[int, int | None, list[dict]]:
    """Settled count, total claims, and the important events so far.

    Events come straight from the run's own ledger, so the log never invents
    anything: one line per settled claim, plus a note when a check was
    rejected by its mutation test and had to be rewritten.
    """
    agent_dir = RUNS_DIR / case_id / "agent"
    total = None
    claims_file = agent_dir / "claims.json"
    if claims_file.is_file():
        total = len(json.loads(claims_file.read_text(encoding="utf-8"))["claims"])
    events: list[dict] = []
    ledger = agent_dir / "ledger.jsonl"
    if ledger.is_file():
        for line in ledger.read_text(encoding="utf-8").splitlines()[1:]:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue  # a line still being written
            v = entry["verdict_record"]
            claim_text = entry["claim"]["quoted_span"]
            if len(claim_text) > 80:
                claim_text = claim_text[:77] + "…"
            verdict = v["verdict"] + (f" ({v['reason']})" if v.get("reason") else "")
            computed = (v.get("computed") or "")
            if len(computed) > 60:
                computed = computed[:57] + "…"
            gate_note = ""
            rejected = [m for m in entry.get("mutant_results", [])
                        if m["outcome"] != "gate_passed"]
            if rejected:
                gate_note = ("a first check draft failed its mutation test and was rewritten"
                             if len(entry.get("mutant_results", [])) > len(rejected)
                             or v["verdict"] != "unverifiable"
                             else "both check drafts failed their mutation test, so this claim abstains")
            events.append({"claim": claim_text, "verdict": v["verdict"],
                           "verdict_full": verdict, "computed": computed,
                           "gate_note": gate_note})
    return len(events), total, events


def _inflight(case_id: str, settled_ids: set[str]) -> int:
    """Claims whose check synthesis has started but not settled, from the
    message log. Lets the bar move inside a batch instead of jumping."""
    log = RUNS_DIR / case_id / "agent" / "messages.jsonl"
    if not log.is_file():
        return 0
    started: set[str] = set()
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.search(r'"label":\s*"synthesize:([^"]+)"', line)
        if m:
            started.add(m.group(1))
    return len(started - settled_ids)


def _settled_ids(case_id: str) -> set[str]:
    ledger = RUNS_DIR / case_id / "agent" / "ledger.jsonl"
    ids: set[str] = set()
    if ledger.is_file():
        for line in ledger.read_text(encoding="utf-8").splitlines()[1:]:
            try:
                ids.add(json.loads(line)["claim"]["id"])
            except (json.JSONDecodeError, KeyError):
                continue
    return ids


async def job_api(request: Request) -> JSONResponse:
    case_id = request.path_params["case_id"]
    job = JOBS.get(case_id)
    if job is None:
        return JSONResponse({"state": "unknown"}, status_code=404)
    if job.error:
        return JSONResponse({"state": "error", "error": job.error})
    settled, total, events = _progress(case_id)
    done = (RUNS_DIR / case_id / "agent" / "verdicts.json").is_file() and job.task and job.task.done()
    stage = "checking"
    if job.fetching:
        stage = "fetching"
    elif total is None:
        stage = "extracting"
    return JSONResponse({
        "state": "done" if done else "running",
        "stage": stage,
        "settled": settled, "total": total,
        "inflight": _inflight(case_id, _settled_ids(case_id)) if total else 0,
        "elapsed": round(time.time() - job.started) if job.started else 0,
        "compare": job.compare,
        "baseline": _baseline_status(job),
        "events": events,
    })


def _baseline_status(job: Job) -> dict:
    if not job.compare:
        return {"requested": False}
    if job.baseline_error:
        return {"requested": True, "state": "failed", "error": job.baseline_error}
    verdicts = RUNS_DIR / job.case_id / "baseline" / "verdicts.json"
    if not verdicts.is_file():
        return {"requested": True, "state": "waiting"}
    out = json.loads(verdicts.read_text(encoding="utf-8"))
    counts = {v: sum(1 for c in out["claims"] if c["verdict"] == v)
              for v in ("violated", "holds", "unverifiable")}
    return {"requested": True, "state": "done", "wall_s": round(out["wall_s"]),
            "claims": len(out["claims"]), "counts": counts}


async def job_page(request: Request) -> HTMLResponse:
    case_id = request.path_params["case_id"]
    job = JOBS.get(case_id)
    if job is None:
        return HTMLResponse(_page("<div class='card'>Unknown job.</div>"), status_code=404)
    if job.compare:
        import run_baseline
        prompt = (run_baseline.SYSTEM_PROMPT.replace("&", "&amp;")
                  .replace("<", "&lt;").replace(">", "&gt;"))
        body = JOB_BODY_COMPARE.replace("__PROMPT__", prompt)
    else:
        body = JOB_BODY
    return HTMLResponse(_page(body, JOB_SCRIPT.replace("__JOB_ID__", case_id)))


def _overlap(a, b) -> float:
    if None in (a.span_start, a.span_end, b.span_start, b.span_end):
        return 1.0 if a.quoted_span.strip() == b.quoted_span.strip() else 0.0
    inter = max(0, min(a.span_end, b.span_end) - max(a.span_start, b.span_start))
    union = max(a.span_end, b.span_end) - min(a.span_start, b.span_start)
    return inter / union if union else 0.0


def _match_baseline(agent_claims, baseline_claims) -> tuple[dict[int, object], list]:
    """Pair each DocDrift claim with the direct-ask claim about the same card
    text (best span overlap, greedy). Returns {agent_idx: baseline_claim} and
    the direct-ask claims about text DocDrift did not extract."""
    pairs = sorted(
        ((_overlap(a, b), ai, bi)
         for ai, a in enumerate(agent_claims)
         for bi, b in enumerate(baseline_claims)),
        key=lambda t: -t[0])
    taken_a, taken_b, matched = set(), set(), {}
    for score, ai, bi in pairs:
        if score < 0.3 or ai in taken_a or bi in taken_b:
            continue
        taken_a.add(ai); taken_b.add(bi)
        matched[ai] = baseline_claims[bi]
    leftovers = [b for bi, b in enumerate(baseline_claims) if bi not in taken_b]
    return matched, leftovers


def _chip(verdict: str, reason: str | None = None) -> str:
    label = verdict + (f" ({reason})" if reason else "")
    return f"<span class='chip {verdict}'>{label}</span>"


async def result_page(request: Request) -> HTMLResponse:
    case_id = request.path_params["case_id"]
    agent_dir = RUNS_DIR / case_id / "agent"
    verdicts_file = agent_dir / "verdicts.json"
    if case_id not in JOBS or not verdicts_file.is_file():
        return HTMLResponse(_page("<div class='card'>No such result.</div>"), status_code=404)
    out = SystemOutput.model_validate_json(verdicts_file.read_text(encoding="utf-8"))
    audit_md = (agent_dir / "audit.md").read_text(encoding="utf-8")
    summary = audit_md.split("## Executive summary", 1)[-1].split("## Per-claim", 1)[0].strip()
    summary = re.sub(r"^\*\*.*?\*\*", "", summary, count=1, flags=re.DOTALL).strip()

    baseline = None
    baseline_file = RUNS_DIR / case_id / "baseline" / "verdicts.json"
    if baseline_file.is_file():
        baseline = SystemOutput.model_validate_json(baseline_file.read_text(encoding="utf-8"))

    counts = {v: sum(1 for c in out.claims if c.verdict.value == v)
              for v in ("violated", "holds", "unverifiable")}

    if baseline is not None:
        matched, leftovers = _match_baseline(out.claims, baseline.claims)
        b_counts = {v: sum(1 for c in baseline.claims if c.verdict.value == v)
                    for v in ("violated", "holds", "unverifiable")}
        import run_baseline
        prompt = (run_baseline.SYSTEM_PROMPT.replace("&", "&amp;")
                  .replace("<", "&lt;").replace(">", "&gt;"))
        duel = (
            f"<div class='duel'>"
            f"<div class='side'><h3>With DocDrift</h3>"
            f"<div class='nums'><div><b>{counts['violated']}</b><span>violated</span></div>"
            f"<div><b>{counts['holds']}</b><span>hold</span></div>"
            f"<div><b>{counts['unverifiable']}</b><span>set aside</span></div>"
            f"<div><b>{out.wall_s:.0f}s</b><span>time</span></div></div>"
            f"<p class='muted'>Every verdict is backed by a check that survived its own "
            f"mutation test and then ran on the full file.</p></div>"
            f"<div class='side'><h3>Just asking the AI</h3>"
            f"<div class='nums'><div><b>{b_counts['violated']}</b><span>violated</span></div>"
            f"<div><b>{b_counts['holds']}</b><span>hold</span></div>"
            f"<div><b>{b_counts['unverifiable']}</b><span>set aside</span></div>"
            f"<div><b>{baseline.wall_s:.0f}s</b><span>time</span></div></div>"
            f"<p class='muted'>Same model ({baseline.model_id}), one message containing the "
            f"documentation, the column types, and the first 50 rows. No code, no access to "
            f"the full file.</p>"
            f"<details><summary>See the exact prompt it was given</summary>"
            f"<pre>{prompt}</pre></details></div></div>")
        rows = []
        for i, c in enumerate(out.claims):
            b = matched.get(i)
            if b is None:
                b_cell = "<span class='dim'>did not mention this claim</span>"
            else:
                b_cell = _chip(b.verdict.value, b.reason.value if b.reason else None)
                if b.computed:
                    b_cell += f"<br><span class='muted'>{b.computed}</span>"
            rows.append(
                f"<tr><td>{c.quoted_span}</td>"
                f"<td>{_chip(c.verdict.value, c.reason.value if c.reason else None)}"
                f"<br><code>{c.computed or '-'}</code></td>"
                f"<td>{b_cell}</td></tr>")
        extra = ""
        if leftovers:
            items = "".join(
                f"<li>{b.quoted_span} {_chip(b.verdict.value, b.reason.value if b.reason else None)}</li>"
                for b in leftovers)
            extra = (f"<p class='muted'>The direct ask also commented on "
                     f"{len(leftovers)} passage(s) DocDrift set aside as not checkable "
                     f"against this file:</p><ul class='muted'>{items}</ul>")
        table_card = (
            f"<div class='card scroll'><h2>Claim by claim</h2>"
            f"<table><thead><tr><th>Claim from the card</th>"
            f"<th>With DocDrift</th><th>Just asking the AI</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>{extra}")
    else:
        duel = (
            f"<div class='stats'>"
            f"<div class='stat'><b>{counts['violated']}</b><span>violated</span></div>"
            f"<div class='stat'><b>{counts['holds']}</b><span>hold</span></div>"
            f"<div class='stat'><b>{counts['unverifiable']}</b><span>unverifiable</span></div>"
            f"<div class='stat'><b>{out.wall_s:.0f}s</b><span>run time</span></div>"
            f"</div>"
            f"<p class='muted'>{counts['violated']} violated, {counts['holds']} hold, "
            f"{counts['unverifiable']} unverifiable.</p>")
        rows = []
        for c in out.claims:
            rows.append(f"<tr><td>{c.quoted_span}</td>"
                        f"<td>{_chip(c.verdict.value, c.reason.value if c.reason else None)}</td>"
                        f"<td><code>{c.computed or '-'}</code></td></tr>")
        table_card = (
            f"<div class='card scroll'><table><thead><tr><th>Claim from the card</th>"
            f"<th>Verdict</th><th>What the data says</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>")

    body = (
        f"<div class='card'><h2>Audit result</h2>"
        f"{duel}"
        f"<p class='muted'>Model {out.model_id}, "
        f"{out.usage.input_tokens + out.usage.output_tokens} tokens.</p>"
        f"<div class='summary'>{summary}</div></div>"
        f"{table_card}"
        f"<p class='muted'>Full evidence: "
        f"<a href='/file/{case_id}/audit.md' "
        f"onclick=\"event.preventDefault();view('audit.md','Audit report')\">report</a> · "
        f"<a href='/file/{case_id}/ledger.jsonl' "
        f"onclick=\"event.preventDefault();view('ledger.jsonl','Check ledger: every claim, "
        f"its check, the mutation test, and the evidence')\">check ledger</a> · "
        f"<a href='/file/{case_id}/verdicts.json' "
        f"onclick=\"event.preventDefault();view('verdicts.json','Raw verdicts')\">raw verdicts</a>"
        f"</p></div>"
        f"<p><a href='/'>Audit another dataset</a></p>")
    return HTMLResponse(_page(body, VIEWER.replace("__CASE__", case_id)))


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
    Route("/api/job/{case_id}", job_api),
    Route("/result/{case_id}", result_page),
    Route("/file/{case_id}/{name}", serve_file),
])
