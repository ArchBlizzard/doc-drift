"""Spike S1 (T004): verify claude-agent-sdk works on subscription auth alone.

Deliberately clears ANTHROPIC_API_KEY for this process so the SDK must fall
back to the stored Claude Code login (credential precedence rank per research
R2). Not part of the judge path.

Run: uv run python scripts/spike_auth.py
"""

from __future__ import annotations

import os
import time

import anyio

# Make the spike honest: no API key, no OAuth token env var.
os.environ.pop("ANTHROPIC_API_KEY", None)

from claude_agent_sdk import ClaudeAgentOptions, query  # noqa: E402


async def main() -> None:
    t0 = time.time()
    options = ClaudeAgentOptions(
        model="sonnet",
        max_turns=1,
        allowed_tools=[],
        system_prompt="Answer with exactly one word.",
    )
    model_id = None
    reply = None
    async for message in query(prompt="What is 2+2? One word.", options=options):
        kind = type(message).__name__
        model_id = getattr(message, "model", model_id)
        content = getattr(message, "content", None)
        if isinstance(content, list):
            for block in content:
                text = getattr(block, "text", None)
                if text:
                    reply = text
        print(f"  [{kind}] model={getattr(message, 'model', '-')}")
    dt = time.time() - t0
    print(f"\nRESULT: reply={reply!r} resolved_model={model_id!r} latency={dt:.1f}s")
    print("auth=subscription (ANTHROPIC_API_KEY cleared for this process)")


if __name__ == "__main__":
    anyio.run(main)
