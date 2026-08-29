"""T010 acceptance: stubbed-transport unit tests — validated output, retry cap,
message logging, credential precedence, auth-error classification."""

import json

import anyio
import pytest
from pydantic import BaseModel

from docdrift.config import LLM_RETRY_CAP
from docdrift.llm import (
    AuthError,
    LlmParseError,
    RawReply,
    call_json,
    extract_json,
    resolve_auth_mode,
)


class Reply(BaseModel):
    answer: int


def make_transport(replies):
    calls = []

    async def transport(system_prompt, user_prompt, model):
        calls.append({"system": system_prompt, "user": user_prompt, "model": model})
        text = replies[min(len(calls) - 1, len(replies) - 1)]
        if isinstance(text, Exception):
            raise text
        return RawReply(text, "claude-test-1", 10, 5)

    transport.calls = calls
    return transport


def run(coro):
    return anyio.from_thread.run_sync if False else anyio.run(lambda: coro)


def test_auth_precedence():
    assert resolve_auth_mode({"ANTHROPIC_API_KEY": "k", "CLAUDE_CODE_OAUTH_TOKEN": "t"}) == "api_key"
    assert resolve_auth_mode({"CLAUDE_CODE_OAUTH_TOKEN": "t"}) == "oauth_token"
    assert resolve_auth_mode({}) == "stored_login"


def test_extract_json_variants():
    assert extract_json('{"a": 1}') == {"a": 1}
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('Sure! Here it is: {"a": 1} hope that helps') == {"a": 1}
    with pytest.raises(json.JSONDecodeError):
        extract_json("no json at all")


def test_success_first_attempt(tmp_path):
    transport = make_transport(['{"answer": 4}'])
    log = tmp_path / "messages.jsonl"
    parsed, meta = run(call_json(Reply, "sys", "user", transport=transport, log_path=log, label="t"))
    assert parsed.answer == 4
    assert meta.attempts == 1
    assert meta.model_id == "claude-test-1"
    assert meta.input_tokens == 10 and meta.output_tokens == 5
    records = [json.loads(line) for line in log.read_text().splitlines()]
    assert len(records) == 1 and records[0]["parse_error"] is None
    assert records[0]["system_prompt"] == "sys" and records[0]["reply"] == '{"answer": 4}'


def test_retry_then_success(tmp_path):
    transport = make_transport(["not json at all", '{"answer": 7}'])
    log = tmp_path / "messages.jsonl"
    parsed, meta = run(call_json(Reply, "sys", "user", transport=transport, log_path=log))
    assert parsed.answer == 7
    assert meta.attempts == 2
    assert meta.input_tokens == 20  # summed across attempts
    records = [json.loads(line) for line in log.read_text().splitlines()]
    assert len(records) == 2
    assert records[0]["parse_error"] is not None
    assert "previous reply was not valid" in transport.calls[1]["user"]


def test_retry_cap_exhausted(tmp_path):
    transport = make_transport(["junk"])
    with pytest.raises(LlmParseError, match="never validated"):
        run(call_json(Reply, "sys", "user", transport=transport, log_path=tmp_path / "m.jsonl"))
    assert len(transport.calls) == LLM_RETRY_CAP + 1


def test_validation_error_also_retries(tmp_path):
    transport = make_transport(['{"answer": "not-an-int-value"}', '{"answer": 3}'])
    parsed, meta = run(call_json(Reply, "sys", "user", transport=transport))
    assert parsed.answer == 3 and meta.attempts == 2


def test_auth_error_propagates():
    transport = make_transport([AuthError("no credential found")])
    with pytest.raises(AuthError):
        run(call_json(Reply, "sys", "user", transport=transport))
