# Solution video script (≤5:00) — SR-003's six elements in order

Recording plan: single 1080p screen capture, terminal + editor, two takes,
cut to <5 min. Element timings below sum to ~4:40 leaving buffer.

## 1. The problem (0:00–0:30)

- On screen: `cases/case_04/datacard.md` (retail card) side-by-side with a
  pandas prompt.
- Script: "Every dataset ships with a README that makes claims — no missing
  IDs, dates end on the 21st, 24 countries. Documentation drifts from data
  constantly, and checking is half an hour of ad-hoc pandas nobody does. The
  danger isn't missing documentation — it's documentation that lies."

## 2. The baseline moment (0:30–1:10)

- On screen: `results/final_per_claim.csv` filtered to
  `case_03,baseline,w_rows` and `case_01,baseline,a_nulls`.
- Script: "The obvious fix — paste it into an LLM — makes it worse. Our
  measured baseline 'verified' this wine dataset's row count because it
  *matches the known UCI dataset size* — the file actually has 1,611 rows.
  And it confirmed 'no empty cells' from a 50-row sample while 17 nulls sat
  below it. Confident, cited, wrong."

## 3. Live run on the hard case (1:10–2:30)

- On screen: `uv run python run_agent.py case_12 --fresh` live; then
  `runs/case_12/agent/audit.md`.
- Script: "DocDrift extracts every claim, writes a pandas check per claim,
  and — the core — refuses to trust any check until it passes a fixture that
  satisfies the claim and FAILS a mutant that violates it. Then the gated
  check runs against the full million-row file. Watch it catch 173 malformed
  coupon codes that first appear after row 810,000 — invisible to any sample
  or summary statistic — and compute the real coupon-express share: 14.2%
  against the documented 'roughly 10%'." Point at the evidence rows
  (order_id 811033…) in the audit.

## 4. The final comparison (2:30–3:20)

- On screen: `results/final.md` table; highlight three cells.
- Script: "Across 12 cases and 41 planted violations: the agent catches 38
  with ZERO false confirmations. The strongest single-prompt baseline —
  full summary statistics in context — ties on count but hands out two false
  certificates, including confirming the corrupted pattern claim on the hard
  case. Where we miss, we say 'could not verify'; where it misses, it says
  'verified'. That asymmetry is the product."

## 5. Changelog highlight (3:20–3:55)

- On screen: `CHANGELOG.md` v2 entry; `results/v2.md` gate stats.
- Script: "The change that contributed most: the mutation gate. 7.5% of
  first-draft checks were rejected by their own mutants — green because they
  couldn't fail. Four came back correct after a rewrite carrying the mutant
  diff; four claims abstained rather than trust an unverifiable verifier.
  Verification of the verifier, measured."

## 6. Removed experiment + real-world kicker + hot take (3:55–4:40)

- On screen: `results/removed_stratified.md`, then
  `trajectories/kaggle_kicker/audit.md` (telephone finding highlighted).
- Script: "We also tried the obvious alternative — stuffing three stratified
  samples into context instead of executing code. Removed: seven of twelve
  runs collapsed into thousands of tokens of narrated hand-arithmetic, it cost
  fifteen times the agent's tokens — and it handed out EIGHT false
  certificates, confirming whatever its samples happened to miss (macro-F1
  0.886, 31 of 41 violations). And on a real, unmodified 1994 data card nobody
  prepared for us, DocDrift found the documentation says Telephone yes/no —
  the data says none/yes. Thirty years of users, silent zero-row filters.
  Hot take: a verifier you haven't tried to fool is just another generator —
  mutation-test your agent's checks."

## Recording checklist

- [ ] Terminal font ≥16pt, dark theme, window 1600×900.
- [ ] Pre-warm: `make data` run, case_12 ledger deleted so the run is live.
- [x] Stratified numbers filled from results/removed_stratified.md.
- [ ] Two takes; keep the tighter one; verify ≤5:00.
