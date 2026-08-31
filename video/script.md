# Video script (target 4:30, hard cap 5:00)

Format: one screen recording of the web UI (http://127.0.0.1:8787, server
started with DOCDRIFT_MODEL=opus). The centerpiece is a LIVE Kaggle audit
from fetch to finish. The audit takes about 2 minutes, which gives you ~90
seconds of talking time while the progress log scrolls.

All six required elements are marked [E1]..[E6]:
problem, baseline, live run, final comparison, changelog highlight, removed
experiment.

## 0:00 to 0:25 — the problem [E1]

On screen: the DocDrift home page.

Say: "Every dataset ships with documentation that makes claims: no missing
values, twelve categories, scores from 0 to 10. That documentation is often
wrong, and nobody checks, because checking means half an hour of pandas per
dataset. Wrong docs cause silent bugs: filters that match zero rows, models
trained on categories nobody documented. I built DocDrift to check the docs
against the data, with proof."

## 0:25 to 0:45 — start the live race [E3 begins, E2 begins]

On screen: click "From Kaggle", type
`uciml/red-wine-quality-cortez-et-al-2009`, leave the comparison box checked,
press "Fetch and run the audit". The split view appears: DocDrift on the
left, "Just asking the AI" on the right. Unfold "See the exact prompt" for a
second so viewers see nothing is hidden.

Say: "This is a real, popular Kaggle dataset. Two things just started side by
side. On the right, the same model gets one plain prompt with the
documentation, the column types, and the first 50 rows; that is what asking
AI directly looks like, and the exact prompt is right there. On the left,
DocDrift starts reading the same documentation and checking every claim
against the full file, live."

## 0:45 to 2:15 — the 90 second explainer, while it runs

Keep the progress log visible. Speak over it; point at log lines when a
green "holds" or a rewrite note appears.

Say: "How it works: each claim becomes a small Python check. Here is the
trick that makes this trustworthy: before any check is trusted, DocDrift
builds two tiny fake datasets, one that satisfies the claim and one that
breaks it, and the check must pass the first and fail the second. A check
that cannot catch a violation is thrown out and rewritten. You can see those
rewrite notes in the log. Only trusted checks run against the full file, and
every verdict ships with the computed value as proof.

Why not just ask AI directly? I measured that. [E2] On my benchmark, twelve
datasets with 41 planted documentation lies, the plain ask-the-model approach
caught 11 and confidently 'verified' lies it could not see; one time it
verified a row count because it 'matches the known dataset size' while the
file had different data. The strongest single prompt I could build, with full
summary statistics in context, caught 38 but still handed out two false
certificates. [E4] DocDrift also caught 38, with zero false certificates:
where it cannot verify, it says so instead of guessing. On the hardest test,
a million-row file whose two violations hide after row 810,000 where no
sample or summary statistic can see them, DocDrift went nine for nine while
the strongest baseline missed both.

[E5] The change that mattered most, from my changelog: that mutation test of
the checks themselves. About one in thirteen first drafts would have returned
green while being unable to fail. Testing the verifier is the whole product.

[E6] And one experiment I removed: instead of running code, I tried stuffing
1,800 sampled rows into the prompt. It cost fifteen times the tokens, and it
certified whatever its samples happened to miss, eight false certificates.
Sampling turns blindness into confidence, so it went in the bin."

## 2:15 to 3:15 — the result [E3 ends, E4 on this dataset]

Note: around the 90 second mark the right panel finishes first, "Answered in
83s". Point at it briefly during the explainer: "opinions are fast." Then the
result page loads with the two panels and the claim by claim table.

Say: "Done. Both sides found exactly one violation each, but look closer,
because they are not the same violation and not the same kind of answer.

DocDrift's catch is the real one: the documentation calls wine quality a
10 point scale, but across all 1,599 rows only six values exist, 3 through
8. There is the computed proof, on the first row of the table. The direct
ask looked at the very same sentence and set it aside.

The direct ask's one violation is about packaging: the card mentions two
datasets and this download is one file. Fair observation, and DocDrift set
that one aside because no amount of reading this file proves what other
files exist.

Now the part that matters. The direct ask marked 15 claims as holding, but
scroll the right column: it verified the class imbalance claim from, quote,
'the 50 visible rows'. It verified the 0 to 10 range from four values it
happened to see. It even marked a line of tutorial advice as 'holds'. Every
one of DocDrift's 13 verified claims, in the left column, carries a value
computed over the full file by a check that first had to prove it could
catch a violation. Same model, same card: opinions on one side, an audit on
the other."

Optional 10 seconds: click "report" to show the rendered audit, or "check
ledger" for one entry with the check source and mutation test results.

## 3:15 to 3:45 — one more real catch, prerecorded or screenshot

On screen: trajectories/kaggle_kicker/audit.md, the telephone finding.

Say: "It finds real drift elsewhere too. On the 1994 German Credit dataset,
the documentation says telephone is yes or no; the data actually encodes
none or yes. Thirty years of users, and any filter on 'no' silently matches
zero rows. And when documentation is correct, like the iris dataset,
DocDrift certifies it with computed proof instead of finding fake problems."

## 3:45 to 4:15 — close, the hot take

On screen: results/final.md table.

Say: "The lesson I would give anyone building agents: a verifier you have
not tried to fool is just another generator. Mutation-test your agent's
checks. That one idea turned an LLM that writes pandas into an auditor whose
worst behavior is saying 'I could not verify this', and never 'verified'
when it should not. Everything here is reproducible from a clean machine
with one config file: the repo has the benchmark, the baselines, and every
agent trajectory. Thanks for watching."

## Recording checklist

- [ ] Server running with DOCDRIFT_MODEL=opus, page zoomed to ~125%.
- [ ] Comparison box CHECKED, so the split race view appears.
- [ ] Do one throwaway wine run first so you know the timing, then record the
      second run clean.
- [ ] Terminal not needed on screen; the UI carries the whole demo.
- [ ] Keep the log visible during the explainer; it proves the run is live.
- [ ] Reference numbers from the rehearsal run, in case a retake differs
      slightly: DocDrift 1 violated, 13 hold, 13 set aside, 111s; direct ask
      1 violated, 15 hold, 17 set aside, 83s. Speak to what is on screen.
- [ ] Two takes, keep the tighter one, confirm under 5:00.
