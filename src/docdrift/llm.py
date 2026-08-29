"""Model client wrapper (T010).

Every model call in DocDrift goes through `call_json`: a single-purpose,
no-tools query whose reply must validate against a pydantic model, with a hard
cap of LLM_RETRY_CAP retries (Constitution IV). Every attempt — system prompt,
user content, raw reply, resolved model id, usage — is appended to a
messages.jsonl file (SR-004 trajectories).

Auth (research R2, cli-contracts.md): the SDK resolves credentials itself in
the order ANTHROPIC_API_KEY > CLAUDE_CODE_OAUTH_TOKEN > stored Claude Code
login; `resolve_auth_mode` reports which source applies, and auth-shaped SDK
failures surface as AuthError (CLIs map it to exit 2).
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from docdrift.config import LLM_RETRY_CAP, MODEL_AGENT

M = TypeVar("M", bound=BaseModel)

AUTH_ERROR_MARKERS = ("api key", "apikey", "login", "auth", "credential", "oauth", "billing")


class AuthError(RuntimeError):
    """No usable credential / auth-shaped SDK failure. CLIs exit 2."""


class LlmParseError(RuntimeError):
    """Reply never validated within the retry cap."""


def resolve_auth_mode(env: Mapping[str, str] | None = None) -> str:
    """Which credential source the SDK will use (precedence per contract)."""
    env = os.environ if env is None else env
    if env.get("ANTHROPIC_API_KEY"):
        return "api_key"
    if env.get("CLAUDE_CODE_OAUTH_TOKEN"):
        return "oauth_token"
    return "stored_login"


@dataclass
class RawReply:
    text: str
    model_id: str
    input_tokens: int
    output_tokens: int


@dataclass
class CallMeta:
    model_id: str
    input_tokens: int
    output_tokens: int
    wall_ms: int
    attempts: int


Transport = Callable[[str, str, str], Awaitable[RawReply]]


def _neutral_cwd() -> Path:
    d = Path(tempfile.gettempdir()) / "docdrift_llm_cwd"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _usage_from(obj: object) -> tuple[int, int]:
    u = getattr(obj, "usage", None)
    if u is None:
        return 0, 0
    if isinstance(u, dict):
        inner = u.get("usage") if isinstance(u.get("usage"), dict) else u
        return int(inner.get("input_tokens") or 0), int(inner.get("output_tokens") or 0)
    return int(getattr(u, "input_tokens", 0) or 0), int(getattr(u, "output_tokens", 0) or 0)


async def sdk_transport(system_prompt: str, user_prompt: str, model: str,
                        max_turns: int = 3) -> RawReply:
    """Real transport: one no-tools Agent SDK query. `max_turns` bounds the
    CLI's output-continuation turns — huge prompts (the stratified removed
    experiment) need more room before the final JSON lands."""
    from claude_agent_sdk import ClaudeAgentOptions, query  # lazy: unit tests stay offline

    options = ClaudeAgentOptions(
        model=model, max_turns=max_turns, allowed_tools=[],
        system_prompt=system_prompt, cwd=str(_neutral_cwd()),
    )
    text_parts: list[str] = []
    model_id = "unknown"
    tokens = (0, 0)
    try:
        async for message in query(prompt=user_prompt, options=options):
            mid = getattr(message, "model", None)
            if mid:
                model_id = mid
            content = getattr(message, "content", None)
            if isinstance(content, list):
                for block in content:
                    t = getattr(block, "text", None)
                    if t:
                        text_parts.append(t)
            got = _usage_from(message)
            if got != (0, 0):
                tokens = got
    except Exception as exc:  # classify auth-shaped failures for exit 2
        if any(marker in str(exc).lower() for marker in AUTH_ERROR_MARKERS):
            raise AuthError(str(exc)) from exc
        # the CLI sometimes ends a plain reply with a turn-cap "error result";
        # if the text already arrived, that is a successful call
        if "maximum number of turns" in str(exc).lower() and text_parts:
            pass
        else:
            raise
    if not text_parts:
        raise LlmParseError("model returned no text blocks")
    return RawReply("".join(text_parts), model_id, tokens[0], tokens[1])


_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def extract_json(text: str) -> dict:
    """Parse a JSON object out of a model reply (fenced or bare)."""
    fenced = _FENCE.search(text)
    if fenced:
        text = fenced.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start:end + 1])
        raise


def _log(log_path: Path | None, record: dict) -> None:
    if log_path is None:
        return
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


async def call_json(
    reply_model: type[M],
    system_prompt: str,
    user_prompt: str,
    *,
    model: str = MODEL_AGENT,
    label: str = "call",
    log_path: Path | None = None,
    transport: Transport | None = None,
    max_turns: int = 3,
) -> tuple[M, CallMeta]:
    """One judgment point: validated JSON out, ≤LLM_RETRY_CAP retries, logged."""
    if transport is None:
        async def send(s: str, u: str, m: str) -> RawReply:
            return await sdk_transport(s, u, m, max_turns=max_turns)
    else:
        send = transport
    t0 = time.monotonic()
    total_in = total_out = 0
    model_id = "unknown"
    prompt = user_prompt
    last_err = "no attempts made"

    for attempt in range(1, LLM_RETRY_CAP + 2):
        try:
            raw = await send(system_prompt, prompt, model)
        except AuthError:
            raise
        except Exception as exc:  # transient transport failure: burn an attempt, retry
            last_err = f"transport failure: {type(exc).__name__}: {exc}"
            _log(log_path, {"ts": time.time(), "label": label, "attempt": attempt,
                            "model": model, "transport_error": last_err})
            continue
        total_in += raw.input_tokens
        total_out += raw.output_tokens
        model_id = raw.model_id
        error: str | None = None
        parsed: M | None = None
        try:
            parsed = reply_model.model_validate(extract_json(raw.text))
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            error = f"{type(exc).__name__}: {exc}"
        _log(log_path, {
            "ts": time.time(), "label": label, "attempt": attempt, "model": model,
            "model_id": raw.model_id, "system_prompt": system_prompt, "user_prompt": prompt,
            "reply": raw.text, "input_tokens": raw.input_tokens,
            "output_tokens": raw.output_tokens, "parse_error": error,
        })
        if parsed is not None:
            meta = CallMeta(model_id, total_in, total_out,
                            int((time.monotonic() - t0) * 1000), attempt)
            return parsed, meta
        last_err = error or "unknown parse failure"
        prompt = (
            f"{user_prompt}\n\nYour previous reply was not valid ({last_err}). "
            f"Reply again with ONLY the JSON object, no prose, matching the requested schema exactly."
        )

    raise LlmParseError(f"{label}: reply never validated after {LLM_RETRY_CAP + 1} attempts: {last_err}")
