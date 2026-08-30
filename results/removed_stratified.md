# REMOVED experiment — stratified-sample context stuffing (T028)

The "maybe we don't need code execution" hypothesis: instead of synthesizing
and running checks, give one prompt the card, dtypes, and three seeded random
samples (600 rows each from the head, middle, and tail thirds of the file) —
the strongest sampling-based single prompt we could fit. Runner kept for
reproduction: `eval/run_all.py --systems baseline_stratified`
(`run_stratified.py`; the original 3×2,000-row design blew the context budget
on wide tables — shipped as 3×600, disclosed here).

## Numbers (12 cases, same gold, same scorer — [final.md](final.md))

| metric | stratified | DocDrift agent |
|---|---|---|
| macro-F1 | 0.886 | 0.928 |
| violations caught | 31/41 | 38/41 |
| **false confirmations of violated claims** | **8** | **0** |
| tokens | 817,664 | 55,063 (15× fewer) |
| wall clock | 113 min | 16 min (7× faster) |

## Why it was removed

1. **It certifies what its samples happen to miss.** Eight violated claims
   came back `holds` — injected categories, out-of-range values, and the
   hard case's row-810k pattern break simply weren't in the 1,800 sampled
   rows, so the model "verified" them (`final_per_claim.csv`,
   `system == baseline_stratified`). Sampling converts blindness into
   confident certificates — the exact failure DocDrift exists to kill.
2. **It fights the model's nature at enormous cost.** 7 of the first 12 runs
   collapsed: faced with 1,800 raw rows, the model narrated tens of thousands
   of tokens of hand-arithmetic before emitting JSON, blowing the turn cap
   (fixed only by raising it to 10 turns and demanding no narration). Final
   bill: 15× the agent's tokens for a worse result.
3. **What it taught us** (kept in the changelog): more in-context data raises
   confidence faster than correctness; the null hypothesis "context can
   replace execution" fails precisely on the violations that matter — the
   ones structurally invisible to any sample.
