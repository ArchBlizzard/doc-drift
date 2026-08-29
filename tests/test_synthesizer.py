"""T017 acceptance (offline): source-contract validation, retry-on-bad-code,
lessons/feedback wiring. The 3-fixture-claim live check runs in scripts/smoke_synth.py
and the T020 sweep."""

import json

import anyio
import pytest

from docdrift.agents.synthesizer import SynthReply, synthesize_check, validate_check_source
from docdrift.llm import RawReply
from docdrift.schemas import Claim, ClaimType

GOOD = 'def check(df):\n    return {"passed": True, "computed": "ok", "evidence_rows": []}\n'


def make_claim():
    return Claim(id="case_77-c01", case_id="case_77", type=ClaimType.row_count,
                 quoted_span="holds 3 rows", span_start=0, span_end=12,
                 params={"expected": 3})


def transport_for(replies):
    calls = []

    async def transport(system_prompt, user_prompt, model):
        calls.append({"system": system_prompt, "user": user_prompt})
        return RawReply(json.dumps(replies[len(calls) - 1]), "claude-test-1", 10, 5)

    transport.calls = calls
    return transport


def test_validate_check_source_accepts_good():
    validate_check_source(GOOD)


@pytest.mark.parametrize("bad,msg", [
    ("x = 1", "must define check"),
    ("def check(df:\n  pass", "does not compile"),
    ("check = 42\ndef check_(df): pass\n", "must define check"),
])
def test_validate_check_source_rejects(bad, msg):
    with pytest.raises(ValueError, match=msg):
        validate_check_source(bad)


def test_pydantic_reply_enforces_contract():
    with pytest.raises(Exception):
        SynthReply(source_code="not code at(")
    assert SynthReply(source_code=GOOD).source_code == GOOD


def test_bad_source_retries_then_succeeds():
    transport = transport_for([
        {"source_code": "def check(df:\n  broken"},
        {"source_code": GOOD},
    ])
    source, meta = anyio.run(lambda: synthesize_check(
        make_claim(), "profile", transport=transport))
    assert source == GOOD and meta.attempts == 2


def test_lessons_and_feedback_reach_prompts():
    transport = transport_for([{"source_code": GOOD}])
    anyio.run(lambda: synthesize_check(
        make_claim(), "profile", lessons="never compare str to int",
        feedback="check passed its mutant", transport=transport))
    call = transport.calls[0]
    assert "never compare str to int" in call["system"]
    assert "REJECTED" in call["user"] and "passed its mutant" in call["user"]
