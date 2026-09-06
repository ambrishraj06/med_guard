# MedGuard

A hallucination auditor for medical AI answers. Give it a clinical question, a guideline
text, and any chatbot's answer. It breaks the answer into individual claims, checks each
claim against that guideline only, and returns one of four verdicts with the exact
guideline sentence to back it up.

**Try it live:** [medguardauidt.streamlit.app](https://medguardauidt.streamlit.app/)

The whole thing runs on free tiers. No GPU, no credit card, no paid API. A free Groq key
is the only signup you need.

---

## The problem, in one paragraph

Ask a medical chatbot a question and it will answer with total confidence, whether or
not it actually knows. The dangerous part is not that it can be wrong. The dangerous
part is that you cannot tell which sentence is the wrong one. MedGuard fixes that
narrow, concrete problem: it points at the exact sentence, pulls up the exact guideline
line, and says this one contradicts the source, this one is not in the source at all.

## A 30 second tour

You land on the app and the golden demo is already filled in. A question about
antibiotics in pregnancy, a guideline excerpt, and a bad answer that recommends a
contraindicated drug. Press one button and you watch the audit run stage by stage:

```
1. Reading claims      split the answer into atomic claims
2. Verifying           check every claim against the guideline text
3. Safety review       one pass over the whole answer in patient context
4. Second opinion      an independent non-LLM checker scores each claim
```

The result is a verdict card, then every claim with its own status chip, and next to
each flagged claim the guideline's own words. The bad answer in the demo gets blocked
because it recommends ciprofloxacin, which the guideline explicitly contraindicates in
pregnancy. The evidence quote is right there on the card. You do not have to trust
MedGuard. You can read the guideline yourself.

The verdicts:

| Verdict | Meaning |
|---------|---------|
| SAFE | Every claim traces back to the source |
| WARNING | Some claims supported, some not in the source |
| BLOCKED | At least one claim contradicts the source |
| UNVERIFIABLE | No usable source, so no honest audit is possible |

UNVERIFIABLE is a feature, not a failure mode. When MedGuard cannot find a guideline
for the topic, it says so and stops. An auditor that guesses is worse than no auditor.

## The classroom demo

There is a second mode built into the app: one question, two AI students, same
examiner. The naive bot answers from general knowledge, like any health chatbot would.
The RAG bot reads the matching guideline page first and answers from that page only.
Both answers then get audited against the same text, side by side.

The warfarin case is the flagship. The naive bot confidently recommends fluconazole
for a patient's thrush infection and gets blocked, because the guideline says
fluconazole plus warfarin is a severe bleeding risk. The RAG bot answers from the
page and passes. It is the whole argument for grounded generation, played out live
in one click.

## How it works

```
question + answer
      |
      v
[1] find the source      no guideline pasted? auto-pick from a 69 topic
                         built-in library, or abstain if nothing qualifies
      |
[2] extract claims       one API call, atomic claims with IDs, temperature 0,
                         capped at 15 claims with an honest note if truncated
      |
[3] verify claims        one batched API call for ALL claims (not one per claim),
                         each returns status + reasoning + verbatim evidence
      |
[4] safety review        whole-answer pass that catches things claim checks
                         miss, like a dangerous drug interaction stated in passing
      |
[5] second opinion      HHEM or MiniCheck, small non-LLM models, score each
                         claim independently; disagreements get flagged visibly
      |
[6] verdict              pure Python rule table, no LLM involved here
```

Two details matter more than the rest.

The verdict is computed by a deterministic rule table, not by the LLM. One
contradiction blocks the answer. A missing source forces abstention. The judge model
labels claims, but it never gets to decide the final verdict, because an auditor
that flip-flops between runs is not an auditor.

The judge is only allowed to use the pasted source text. The prompts are written so
the model checks the answer against the page in front of it and nothing else. A claim
that is medically true in the real world but absent from the source gets flagged
UNSUPPORTED. That is deliberate. MedGuard audits grounding, not world knowledge, and
those are different jobs.

### Engineering notes

- **Prompt injection defense.** User input is wrapped in explicit delimiters and
  every system prompt carries a rule: text inside the delimiters is data to examine,
  never instructions to follow. Both injection attacks in the adversarial battery were
  defeated.
- **Rate limit handling.** Free tier means 429s. The client retries with backoff
  (2s, 4s, 8s), validates every JSON response against a schema, and strips
  markdown fences before parsing. Re-auditing an identical case within a session
  costs zero API calls thanks to memoization.
- **Model name is config, not code.** Groq retired the original judge model
  mid-project. The swap to the current one was a one line change, which is exactly
  why it was built that way.
- **Everything runs in a worker thread.** The audit streams stage events through a
  queue to the UI, so the progress chips light up as each stage actually runs rather
  than animating on a timer.

## The built-in guideline library

Paste your own guideline for the most accurate audit, or leave the box empty. The app
then matches the question against a built-in library of 69 clinical topics, each
with a named public-health source: WHO, NICE, CDC, NHS, ICMR and others. The screen
always shows which topic and which source was used.

The matching is keyword based and deliberately strict. A topic only qualifies when
the question hits its keywords. An unknown disease never gets audited against a
nearby topic, because a wrong source produces a confident, wrong audit. A keyword
collision check script keeps the 69 topics from fighting over the same words.

One honest caveat, stated in the app too: the library texts are simplified
public-health summaries modeled on those guidelines, not verbatim official documents.
For real audits, paste the real guideline.

## Is it any good?

The evaluator got evaluated. All numbers below come from real API runs, no mocks,
and the result files are in `scripts/` so you can re-run them yourself.

| Suite | Result |
|-------|--------|
| Adversarial battery, 20 cases: injection attacks, 10x dose escalations, negation flips, fabricated citations | 20/20 |
| Hand-labeled eval set, 25 cases | 25/25 verdicts correct |
| Danger recall: dangerous answers that must never pass | 14/14 caught |
| False SAFE verdicts on dangerous answers | 0 across all runs |
| Judge agreement: same 25 cases, two different judge models | 88% (the disagreements were all one step, never danger passed as safe) |

The eval set was labeled by hand from the source texts before any automated scoring,
which is the only way the number means anything. The known failure mode is
documented rather than hidden: the judge is strict, so a hedged paraphrase of a
supported fact can get flagged UNSUPPORTED. That errs in the safe direction and costs
some precision on good answers. It is written down in the eval script alongside the
results.

## Repo layout

```
app.py                     the Streamlit app (audit UI, classroom demo, history)
medguard/
  audit.py                 pipeline: extract, verify, review, crosscheck
  prompts.py                the five judge prompts, injection delimiters included
  verdict.py               the deterministic verdict rule table
  library.py               69 topic guideline library with keyword matcher
  crosscheck.py            HHEM / MiniCheck second-opinion loaders
scripts/
  hard_battery.py          20-case adversarial suite (run it end to end)
  eval_set.py              25 hand-labeled cases
  eval_scorecard.py        scoring, plus judge-vs-judge agreement mode
  check_keyword_collisions.py   keeps the library keywords unique
  ui_gate.py               UI gate: static scans + AppTest + theme assertions
tests/                     27 offline tests, no API key needed
static/                    self-hosted fonts and the favicon
```

## Running it locally

```bash
git clone https://github.com/ambrishraj06/med_guard.git
cd med_guard
python -m venv venv
venv\Scripts\activate        # on mac or linux: source venv/bin/activate
pip install -r requirements.txt

# your free key from console.groq.com/keys
copy .streamlit\secrets.toml.example .streamlit\secrets.toml
# edit secrets.toml and paste the key

pytest tests -v               # offline tests, no key needed
streamlit run app.py          # the app
```

The app runs fully with just Streamlit and the Groq client, which is all that
`requirements.txt` installs. The cross-checker models are optional extras documented
in the requirements file; on a small host the dropdown simply lists them as
unavailable and the audit runs judge only.

## Stack and constraints

Streamlit for the interface, Groq's free tier for the LLM calls (gpt-oss-120b as the
judge), pure Python for the verdict, HHEM or MiniCheck as the independent second
opinion where RAM allows. Hosted free on Streamlit Community Cloud. Python 3.12.

The constraints were real and shaped the design: no budget, no GPU, no card on file
anywhere. Everything above runs inside those constraints.

## Safety

MedGuard is an evaluation tool for educational purposes. It does not provide medical
advice, it does not generate treatment recommendations, and it never replaces
clinical judgment or official guidelines. It only surfaces guideline text, verbatim.

MIT license, see [LICENSE](LICENSE).
