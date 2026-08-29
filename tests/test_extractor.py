"""T016 acceptance (offline): span location + repair pass + claimless card.
Live extraction quality is exercised in the T020 sweep."""

import json

import anyio

from docdrift.agents.extractor import extract_claims
from docdrift.llm import RawReply

CARD = "# T\n\nThe table holds 3 rows. Prices range from 1 to 9. Collected by hand.\n"


def transport_for(replies):
    calls = []

    async def transport(system_prompt, user_prompt, model):
        calls.append(user_prompt)
        return RawReply(json.dumps(replies[len(calls) - 1]), "claude-test-1", 10, 5)

    transport.calls = calls
    return transport


def test_extracts_and_orders_claims_by_span():
    reply = {"claims": [
        {"type": "range", "quoted_span": "Prices range from 1 to 9.", "params": {"column": "price"}},
        {"type": "row_count", "quoted_span": "The table holds 3 rows.", "params": {}},
        {"type": "prose_unverifiable", "quoted_span": "Collected by hand.", "params": {}},
    ]}
    claims, metas, warnings = anyio.run(lambda: extract_claims(
        "case_77", CARD, "profile", transport=transport_for([reply])))
    assert [c.type.value for c in claims] == ["row_count", "range", "prose_unverifiable"]
    assert claims[0].id == "case_77-c01"
    for c in claims:
        c.validate_against_card(CARD)  # exact spans
    assert not warnings and len(metas) == 1


def test_repair_pass_fixes_bad_quotes():
    first = {"claims": [
        {"type": "row_count", "quoted_span": "The table holds three rows.", "params": {}},  # bad
        {"type": "range", "quoted_span": "Prices range from 1 to 9.", "params": {"column": "price"}},
    ]}
    second = {"claims": [
        {"type": "row_count", "quoted_span": "The table holds 3 rows.", "params": {}},  # fixed
    ]}
    transport = transport_for([first, second])
    claims, metas, warnings = anyio.run(lambda: extract_claims(
        "case_77", CARD, "profile", transport=transport))
    assert len(metas) == 2
    assert "NOT exact substrings" in transport.calls[1]
    assert {c.type.value for c in claims} == {"row_count", "range"}
    assert not warnings


def test_unrepairable_quote_dropped_with_warning():
    bad = {"claims": [{"type": "row_count", "quoted_span": "nope nope", "params": {}}]}
    claims, metas, warnings = anyio.run(lambda: extract_claims(
        "case_77", CARD, "profile", transport=transport_for([bad, bad])))
    assert claims == []
    assert any("dropped unlocatable" in w for w in warnings)
    assert any("zero extractable" in w for w in warnings)


def test_claimless_card_is_valid():
    claims, metas, warnings = anyio.run(lambda: extract_claims(
        "case_77", CARD, "profile", transport=transport_for([{"claims": []}])))
    assert claims == [] and len(metas) == 1
    assert any("zero extractable" in w for w in warnings)
