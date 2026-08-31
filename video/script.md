# Video script (target 4:30, hard cap 5:00)

One screen recording of the web UI (http://127.0.0.1:8787, server started
with DOCDRIFT_MODEL=opus, comparison box checked). The centerpiece is a live
Kaggle audit racing a plain AI prompt, side by side. The audit takes about
2 minutes, which is the talking window.

Spoken lines are written in Anchit's voice per ~/.claude/anchit-voice.md:
task first, flat verdicts with one checked number each, "so" as connector,
before and after phrasing, close on what is left. Speak to what is on
screen; if a retake shows slightly different numbers, say those.

Required elements marked [E1]..[E6]: problem, baseline, live run, final
comparison, changelog highlight, removed experiment.

## 0:00 to 0:25 — the problem [E1]

On screen: the DocDrift home page.

Say: "So the problem I picked is simple. Every dataset comes with a README
that makes claims, like no missing values, or scores from 0 to 10. Nobody
checks those claims, because checking is half an hour of pandas per dataset.
And wrong docs cause silent bugs, like a filter that matches zero rows and
nobody notices. So I built DocDrift. It checks the docs against the actual
data, and it shows proof for every verdict."

## 0:25 to 0:45 — start the race [E2 and E3 begin]

On screen: click "From Kaggle", type
`uciml/red-wine-quality-cortez-et-al-2009`, comparison box stays checked,
press "Fetch and run the audit". The split view appears. Unfold "See the
exact prompt" on the right for a second.

Say: "So this is a real Kaggle dataset, the red wine one, and all I gave it
is the name. Two things just started side by side. The right side is just
asking the AI, one prompt with the docs, the column types and the first 50
rows, and the exact prompt is right here, nothing hidden. The left side is
DocDrift, and you can see it found the claims, the count is on screen. Now
it checks every one of them against the full file, live."

## 0:45 to 2:15 — the talking window, while both run

Keep the log visible. Around 90 seconds the right panel finishes first;
point at it when it does.

Say: "Now coming to the implementation. Every claim becomes a small Python
check. And the main thing is the mutation test on those checks. What
happened before was the AI would write a check that always passes, it looks
green but it can catch nothing. What happens now is DocDrift builds two tiny
fake tables, one that follows the claim and one that breaks it, and the
check has to pass the first and fail the second before anyone trusts it.
Fails that, it gets one rewrite, and you can see those rewrite notes in the
log. I measured it on my benchmark, 12 datasets where I planted 41 wrong
claims on purpose, and about 1 in 13 first drafts failed their own mutation
test, counted from the gate logs.

So, is this better than just asking AI. I tested that with the same claims
and the same scorer. Just asking caught 11 of the 41 planted lies, and it
also said verified on things it never computed. The strongest prompt I could
build caught 38, but it gave 2 false certificates. DocDrift also caught 38,
with zero false certificates, and that zero is the whole product. Where it
cannot verify, it says so instead of guessing. And on the hardest test, a
million row file where both violations hide after row 810,000, DocDrift
caught both, the strongest prompt caught neither.

One experiment I threw away: instead of running code I stuffed 1,800 sampled
rows into the prompt. It cost 15 times the tokens and handed out 8 false
certificates, so it went in the bin.

(when the right panel finishes) And see, the AI side is already done, took
around 80 seconds. Opinions are fast."

[E2, E4, E5, E6 all land in this block: the direct ask, the benchmark
comparison, the mutation gate as the change that mattered most, and the
removed sampling experiment.]

## 2:15 to 3:15 — the result [E3 ends, E4 on this dataset]

On screen: the result page with two panels and the claim by claim table.
The violated row sits on top.

Say: "Done. So both sides found exactly one violation, but not the same one,
and not the same kind of answer.

DocDrift's catch is the real one. The docs call wine quality a 10 point
scale. The check ran on all 1,599 rows and found only six values, 3 to 8.
The proof is right there in the first row. The AI read the same sentence and
set it aside.

The AI's one catch is about packaging, the docs mention two datasets and
this download is one file. Fair point, and DocDrift set that one aside on
purpose, because reading this file cannot prove what other files exist.

Now the part I want you to see. Scroll the right column. The AI marked 15
claims as holding, and in its own words it verified the class balance claim
from the 50 visible rows. Fifty rows out of 1,599. Every verdict on the left
has a value computed on the full file by a check that passed its own
mutation test first. Same model, same docs. One side is opinions, the other
side is an audit."

Optional 10 seconds: click "report" to show the rendered audit, or "check
ledger" for one entry with the check source and mutation results.

## 3:15 to 3:45 — one more real catch

On screen: trajectories/kaggle_kicker/audit.md, the telephone finding.

Say: "It finds real drift outside my benchmark too. On the 1994 German
credit dataset, the docs say telephone is yes or no, the data says none and
yes. I checked that by running the audit on the untouched docs, the trace is
in the repo. So any filter on no matches zero rows, and that doc has been
wrong for thirty years. And when docs are right, like the iris dataset, it
says so with proof, 50 samples per species, counted."

## 3:45 to 4:15 — close, on what is left

On screen: results/final.md table.

Say: "So the one thing I would tell anyone building agents: a checker you
have not tried to fool is just another guesser. Mutation test your agent's
checks. That single idea is why this tool's worst behavior is saying it
could not verify something, and never saying verified when it should not.
Everything runs from a clean machine, the repo has the benchmark, the
baselines and every trace. What is left: wiring this into CI so docs get
checked on every push, and putting the hosted version behind an access code.
Thanks."

## Recording checklist

- [ ] Server on with DOCDRIFT_MODEL=opus, comparison box checked, ~125% zoom.
- [ ] One throwaway wine run first for timing, record the second run clean.
- [ ] Keep the log visible during the talking window, it proves the run is live.
- [ ] Reference numbers from the rehearsal, speak to the screen if a retake
      differs: DocDrift 1 violated, 13 hold, 13 set aside, 111s; direct ask
      1 violated, 15 hold, 17 set aside, 83s.
- [ ] Two takes, keep the tighter one, confirm under 5:00.
