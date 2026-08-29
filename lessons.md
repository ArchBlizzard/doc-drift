# Check-writing lessons (memory across eval iterations — T026)

Injected verbatim into the synthesizer's system prompt. Each entry generalizes
an observed failure; evidence citations live in CHANGELOG.md.

1. Sentinel values are not nulls. `?`, `999.9`, `9999.9` and friends are
   real cell values encoding missingness; count NaN and sentinels separately
   and judge exactly what the claim asserts (v0 evidence: both baselines
   conflated `?` sentinels with empty cells on the census case).
2. Verify every referenced column exists FIRST and return
   `{"passed": False, "computed": "missing-column", "evidence_rows": []}` —
   never raise for a missing column.
3. Coerce before comparing: `pd.to_datetime(..., errors="coerce")` and
   `pd.to_numeric(..., errors="coerce")`; a dtype-mismatched comparison that
   can never be True is the classic vacuous check.
4. Claims about real-world meaning of string values (countries inferred from
   station names, "cancellation" semantics of a prefix) are not checkable
   structure — treat them as unverifiable prose rather than regex-guessing
   (v1 evidence: a name-pattern check judged a true NOAA claim violated).
5. "Each row is one X" states the file's granularity intent, not a uniqueness
   constraint — do not fail it on legitimately repeated keys (v1 evidence: a
   duplicate-pair check flagged a true retail claim).
6. Approximate quantities ("roughly/about X%"): the claim holds iff
   |computed − stated| ≤ tolerance_pp (from params; default 2 percentage
   points). Report the computed value either way.
7. Test the quantity the claim states, not a proxy: a range claim needs BOTH
   endpoints checked against min AND max; a count claim needs the EXACT count
   (`nunique() == n`, never `>=`) — a proxy check is how a mutant slips
   through the gate (v2 evidence: the 24-countries claim went vacuous twice).
8. A compound sentence is ONE claim: quote the full sentence and judge every
   part of it together; splitting it hands the audit two half-claims whose
   verdicts can diverge (v2 evidence: the census "no empty cells; unknowns
   are `?`" sentence split into a violated half and an abstaining half).
