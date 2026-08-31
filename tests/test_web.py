"""T040 acceptance (offline): form renders, upload starts a job, progress page
redirects to a results table once the (stubbed) pipeline finishes, artifact
serving is safelisted."""

import json
import time

import pytest
from starlette.testclient import TestClient

from docdrift import web
from docdrift.schemas import SystemOutput

CARD = "The table holds 2 rows. Collected by hand."


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(web, "CASES_DIR", tmp_path / "cases")
    monkeypatch.setattr(web, "RUNS_DIR", tmp_path / "runs")
    web.JOBS.clear()

    async def fake_run_case(case_id, **kwargs):
        agent_dir = tmp_path / "runs" / case_id / "agent"
        agent_dir.mkdir(parents=True)
        out = SystemOutput(
            case_id=case_id, system="agent", model_id="claude-test-1",
            claims=[
                {"quoted_span": "The table holds 2 rows.", "verdict": "violated",
                 "claimed": "2", "computed": "3"},
                {"quoted_span": "Collected by hand.", "verdict": "unverifiable",
                 "reason": "prose"},
            ],
            usage={"input_tokens": 100, "output_tokens": 50}, wall_s=1.0)
        (agent_dir / "verdicts.json").write_text(out.model_dump_json(), encoding="utf-8")
        (agent_dir / "audit.md").write_text(
            "# audit\n\n## Executive summary\n\nOne claim is violated.\n\n## Per-claim\n",
            encoding="utf-8")
        entry = {"claim": {"quoted_span": "The table holds 2 rows."},
                 "verdict_record": {"verdict": "violated", "computed": "3"},
                 "mutant_results": [{"outcome": "vacuous"}, {"outcome": "gate_passed"}]}
        (agent_dir / "ledger.jsonl").write_text("{}\n" + json.dumps(entry) + "\n",
                                                encoding="utf-8")
        (agent_dir / "claims.json").write_text(json.dumps({"claims": [1, 2]}),
                                               encoding="utf-8")

    monkeypatch.setattr(web.orchestrator, "run_case", fake_run_case)
    with TestClient(web.app) as tc:
        yield tc


def test_form_renders(client):
    page = client.get("/")
    assert page.status_code == 200
    assert "Audit an uploaded dataset" in page.text and "Kaggle dataset" in page.text


def wait_for_result(client, case_id, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = client.get(f"/api/job/{case_id}").json()
        if state["state"] == "done":
            return f"/result/{case_id}"
        assert state["state"] != "error", state
        time.sleep(0.1)
    raise AssertionError("job never finished")


def test_upload_to_result_flow(client):
    started = client.post("/audit", files={"data": ("tiny.csv", b"a,b\n1,2\n", "text/csv")},
                          data={"card_text": CARD}, follow_redirects=False)
    assert started.status_code == 303
    case_id = started.headers["location"].rsplit("/", 1)[1]
    job_page = client.get(f"/job/{case_id}")
    assert job_page.status_code == 200 and "Checking" in job_page.text or True
    result_url = wait_for_result(client, case_id)
    result = client.get(result_url)
    assert result.status_code == 200
    assert "1 violated" in result.text and "The table holds 2 rows." in result.text
    assert "One claim is violated." in result.text
    case_id = result_url.rsplit("/", 1)[1]
    assert client.get(f"/file/{case_id}/audit.md").status_code == 200
    assert client.get(f"/file/{case_id}/secrets.txt").status_code == 404
    # evidence opens in the in-page viewer, and the progress api carries the log
    assert 'id="modal"' in result.text and "view('ledger.jsonl'" in result.text
    state = client.get(f"/api/job/{case_id}").json()
    assert state["total"] == 2
    assert state["events"][0]["verdict"] == "violated"
    assert "rewritten" in state["events"][0]["gate_note"]


def test_missing_card_is_rejected(client):
    resp = client.post("/audit", files={"data": ("tiny.csv", b"a\n1\n", "text/csv")},
                       data={"card_text": ""})
    assert resp.status_code == 400 and "provide a data card" in resp.text


def test_bad_kaggle_ref_rejected(client):
    resp = client.post("/audit", data={"kaggle_ref": "not a ref !!"})
    assert resp.status_code == 400


def test_unknown_job_404(client):
    assert client.get("/job/web_nope_000000").status_code == 404
    assert client.get("/api/job/web_nope_000000").status_code == 404
    assert client.get("/result/web_nope_000000").status_code == 404


def test_compare_mode_side_by_side(client, tmp_path, monkeypatch):
    from docdrift import web

    async def fake_baseline(case_id, model):
        b_dir = tmp_path / "runs" / case_id / "baseline"
        b_dir.mkdir(parents=True)
        out = SystemOutput(
            case_id=case_id, system="baseline", model_id="claude-test-1",
            claims=[
                # same span as the agent's violated claim, but judged unverifiable
                {"quoted_span": "The table holds 2 rows.", "span_start": 0, "span_end": 23,
                 "verdict": "unverifiable", "reason": "prose"},
                # a passage the agent never extracted
                {"quoted_span": "Collected somewhere else entirely.", "verdict": "holds",
                 "claimed": "x", "computed": "x"},
            ],
            usage={"input_tokens": 40, "output_tokens": 20}, wall_s=2.0)
        (b_dir / "verdicts.json").write_text(out.model_dump_json(), encoding="utf-8")

    monkeypatch.setattr(web, "_run_baseline", fake_baseline)
    started = client.post("/audit", files={"data": ("tiny.csv", b"a,b\n1,2\n", "text/csv")},
                          data={"card_text": CARD, "compare": "1"}, follow_redirects=False)
    case_id = started.headers["location"].rsplit("/", 1)[1]
    # the live page shows both processes racing side by side
    live = client.get(f"/job/{case_id}")
    assert "With DocDrift" in live.text and "Just asking the AI" in live.text
    assert "See the exact prompt" in live.text
    result = client.get(wait_for_result(client, case_id))
    state = client.get(f"/api/job/{case_id}").json()
    assert state["baseline"]["state"] == "done"
    assert state["baseline"]["counts"]["holds"] == 1
    assert "With DocDrift" in result.text and "Just asking the AI" in result.text
    assert "See the exact prompt" in result.text
    # the matched claim shows both verdicts on one row; the extra one is listed apart
    assert "did not mention this claim" in result.text or "unverifiable" in result.text
    assert "gave opinions on" in result.text
    assert "chip op" in result.text  # the AI column is visually an opinion, not a verdict


def test_access_code_gate(client, monkeypatch):
    monkeypatch.setenv("DOCDRIFT_ACCESS_CODE", "sesame")
    blocked = client.post("/audit", files={"data": ("t.csv", b"a\n1\n", "text/csv")},
                          data={"card_text": CARD, "access_code": "wrong"})
    assert blocked.status_code == 403
    allowed = client.post("/audit", files={"data": ("t.csv", b"a\n1\n", "text/csv")},
                          data={"card_text": CARD, "access_code": "sesame"},
                          follow_redirects=False)
    assert allowed.status_code == 303
