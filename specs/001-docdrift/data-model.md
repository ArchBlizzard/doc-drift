# Data Model: DocDrift

All entities are pydantic v2 models in `src/docdrift/schemas.py` unless noted. Serialized forms: run ledger = JSON Lines; verdicts/gold = JSON per `contracts/`.

## Enums

- **ClaimType:** `schema | row_count | range | null_rate | category_set | aggregate_stat | temporal_coverage | prose_unverifiable`
- **Verdict:** `holds | violated | unverifiable`
- **UnverifiableReason:** `prose | check_failed | execution_error`
- **CheckStatus:** `draft | gate_passed | gate_skipped | rejected_vacuous | rejected_error`
- **GateOutcome:** `gate_passed | gate_skipped | vacuous | error`

`gate_skipped` exists only for v1 ledgers (Phase 3, before the mutation gate lands in T022); the final product never emits it.

## Core entities

### Claim
| field | type | notes |
|---|---|---|
| id | str | `{case_id}-c{NN}`, stable within a run |
| case_id | str | |
| type | ClaimType | |
| quoted_span | str | exact substring of `datacard.md` |
| span_start / span_end | int | character offsets into the card; **invariant:** `card[span_start:span_end] == quoted_span` |
| params | dict | typed parameters, e.g. `{column: "coupon_id", stated_null_pct: 10, tolerance_pp: 2}` |

### Check
| field | type | notes |
|---|---|---|
| claim_id | str | |
| source_code | str | self-contained `def check(df) -> CheckOutput` pandas function. **Contract:** MUST first verify every referenced column exists and return `passed=False, computed="missing-column"` instead of raising — phantom-column claims score `violated`, never `execution_error`. |
| attempt | int | 1 or 2 (Constitution IV cap) |
| status | CheckStatus | |

### MutantResult (mutation gate)
| field | type | notes |
|---|---|---|
| claim_id / attempt | str / int | |
| clean_passed | bool | check passed the claim-satisfying fixture |
| mutant_failed | bool | check failed the claim-violating fixture |
| outcome | GateOutcome | `gate_passed` iff clean_passed AND mutant_failed |
| mutant_desc | str | human-readable description of the injected violation |

### ExecutionResult
| field | type | notes |
|---|---|---|
| claim_id | str | |
| passed | bool | claim satisfied by full dataset |
| computed | str | computed value(s), stringified for the report |
| evidence_rows | list[dict] | ≤5 rows (FR-006) |
| duration_ms | int | |
| error | str? | set on crash/timeout |

### VerdictRecord
| field | type | notes |
|---|---|---|
| claim_id | str | |
| verdict | Verdict | |
| reason | UnverifiableReason? | required iff verdict = unverifiable |
| claimed / computed | str? | both present iff verdict ∈ {holds, violated} (FR-004) |

**Validation rules:** `computed` present ⟺ verdict ≠ unverifiable; a VerdictRecord with verdict ∈ {holds, violated} MUST reference an executed check in the same ledger, and from v2 (T022) onward that check MUST be `gate_passed` — v1 ledgers record `gate_skipped` explicitly (the final-product invariant is gate_passed only).

### LedgerEntry / RunLedger (`runs/<case>/agent/ledger.jsonl`)
LedgerEntry = one settled claim: `{claim, check, mutant_results[], execution, verdict_record, model_id, tokens_in, tokens_out, wall_ms}`. Append-only.
RunLedger header line: `{case_id, data_fingerprint: sha256(data file), card_fingerprint, sdk_version, started}`.
Full model message streams (system prompt, user content, raw reply per call) are logged separately by `llm.py` to `runs/<case>/agent/messages.jsonl` — the ledger stays compact; trajectory curation (T035) draws on both.
**Resume rule (FR-008):** skip a claim iff an entry exists with the same `sha256(claim.quoted_span + claim.type)` AND matching data+card fingerprints.

### System output (shared by baseline and agent) — `verdicts.json`
See `contracts/verdicts.schema.json`. `{case_id, system, model_id, claims: [{quoted_span, span_start?, span_end?, verdict, reason?, claimed?, computed?}], usage: {input_tokens, output_tokens}, wall_s}`. Baselines emit no ledger; span offsets optional for baselines (fallback alignment then applies, flagged).

## Eval entities

### CaseSpec (`eval/specs/case_NN.yaml`)
`{case_id, dataset: data_src filename | "synthetic_transactions_1m", seed, corruptions: [{op: one-of-8, target: card|data, params}], kept_true_claims: int, kept_unverifiable_claims: int}`

### GoldClaim (`eval/gold/case_NN_gold.json`)
File wrapper: `{case_id, dataset, seed, gold_claims: [...]}` per `contracts/gold.schema.json`. Each gold claim: `{id, span_start, span_end, quoted_span, type, gold_verdict, corruption_op?, note?}` (no per-claim `case_id` — the file-level field scopes it) — emitted by `make_cases.py` by construction; same span invariant as Claim.

### ScoreRow (`results/`)
`{case, system, n_claims, holds_p, holds_r, violated_p, violated_r, unverif_p, unverif_r, macro_f1, violations_caught, fallback_matches, tokens, wall_s}` + per-claim appendix rows `{case, gold_id, quoted_span, gold, baseline, baseline_plus, agent, agent_computed}`.

## State transitions (Check lifecycle)

```
draft ──gate──▶ gate_passed ──execute──▶ ExecutionResult ──▶ VerdictRecord(holds|violated)
  │
  └─(vacuous|error)──▶ rewrite (attempt 2) ──gate──▶ gate_passed ─▶ …
                              │
                              └─(vacuous|error)──▶ VerdictRecord(unverifiable, check_failed)
```

Execution crash/timeout after a passed gate: retry once; second failure → `unverifiable(execution_error)` (spec edge case).
