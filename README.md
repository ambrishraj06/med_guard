---
title: MedGuard — Clinical RAG Hallucination Auditor
emoji: 🛡️
colorFrom: indigo
colorTo: green
sdk: streamlit
sdk_version: "1.62.0"
app_file: app.py
pinned: false
license: mit
---

# 🛡️ MedGuard — Clinical RAG Hallucination Auditor & Abstention Engine

> **I don't audit models — I audit outputs.** Groundedness is a property of an answer, not of a model.

MedGuard is an **AI BS-detector for medical RAG chatbots**: it takes a clinical question, a
guideline excerpt, and an AI-generated answer, rips the answer into atomic claims, and verifies
every claim against the guideline text **only** — labeling each `SUPPORTED`, `UNSUPPORTED`, or
`CONTRADICTION` with a **verbatim evidence quote** — then blocks, warns, or passes the whole answer.

```
🚫 BLOCKED    any claim contradicts the source          (coverage 0%)
✅ SAFE       every claim is supported                  (coverage 100%)
⚠️ WARNING    mix of supported/unsupported              (coverage = supported/total)
❔ UNVERIFIABLE  no source / empty answer / no claims   (abstention is a safety feature)
```

**Why it matters:** LLMs confidently hallucinate medical facts — studies report hallucination
rates from ~1.5% in tightly controlled clinical workflows up to 15–52% on general medical tasks,
and 91.8% of surveyed clinicians say they've encountered medical AI hallucinations (84.7% believe
it can directly harm patients). MedGuard is the safety layer that catches this class of failure.

---

## The exam analogy

| Role | What |
|---|---|
| **Textbook** | The clinical guideline — the medicine lives here, injected fresh into every audit |
| **Student** | Any medical RAG chatbot — writes the answer |
| **Examiner** | MedGuard — checks "does the answer match the page?", forbidden from using its own opinions |

The judge LLM is deliberately **forbidden from using outside medical knowledge**. If the source
doesn't mention it, the claim is `UNSUPPORTED` — even when the claim is true in the real world.
That's the point: MedGuard audits **grounding**, not medical truth.

---

## Architecture

```
GUIDELINE CHUNK (public WHO / CDC / NICE text)
   ├── INJECTED into the verifier LLM prompt ("judge ONLY against this text")
   └── PASSED to the cross-checker as (document, answer) input

AI ANSWER ──► [1] extract_claims()      1 Groq call → atomic claims, claim_ids, JSON, temp=0
              [2] verify_claims()       1 BATCHED Groq call → per claim: status + reasoning
                                        + verbatim evidence quote
              [3] crosscheck()          HHEM-2.1-Open or MiniCheck-FT5 → independent 0–1 score
              [4] compute_verdict()     PURE PYTHON, deterministic, no LLM
              [5] Streamlit UI          verdict card · claim chips · evidence panel ·
                                        "What the source says" · JSON expander · disclaimer
```

**Key design decisions**

- **Deterministic verdict engine** — pure Python rule table, zero LLM, zero ambiguity. One
  contradiction blocks the whole answer; a missing source forces abstention. An auditor must
  never be random.
- **Batched verification** — all claims verified in ONE call using `claim_id`s (not N+1 calls),
  respecting free-tier rate limits; dropped claims are re-attached as `UNSUPPORTED` (safe default).
- **Verbatim evidence quotes** — every verdict is human-checkable against the exact guideline
  sentence. The UI also shows a side-by-side **"What the source says"** panel with verbatim
  quotes only — MedGuard presents evidence, it **never generates medical advice**.
- **Ensemble** — the LLM judge is cross-checked by a small, architecturally independent,
  non-LLM model. Different machine → different blind spots.
- **Model name is config** — Groq deprecates models (this project's original judge
  `llama-3.3-70b-versatile` was retired mid-build; swapped to `openai/gpt-oss-120b` in one line).

---

## Quick start

```bash
# 1 — workshop
cd E:\MedGuard
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# 2 — your free Groq key (console.groq.com/keys)
copy .streamlit\secrets.toml.example .streamlit\secrets.toml
#    ...then paste your key into secrets.toml (never commit it — .gitignore already covers it)

# 3 — offline brain tests (no API needed)
pytest tests\ -v

# 4 — full end-to-end test (real Groq calls)
python scripts\e2e_test.py

# 5 — the app
streamlit run app.py
```

Optional cross-checkers (recommended — both free, CPU-only, no keys):

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install transformers
pip install "minicheck @ git+https://github.com/Liyan06/MiniCheck.git"
```

The sidebar dropdown loads **only the selected** cross-checker (HF Spaces free tier = 2 vCPU,
16GB RAM — the whole stack fits with ~60% headroom).

---

## How MedGuard differs from existing tools

| Tool | What it does | What MedGuard adds |
|---|---|---|
| **RAGAS / DeepEval / TruLens** | RAG scorecards, batch metrics, tracing | Inline **verdicts with a hard policy** (BLOCK/WARN/abstain), not scores |
| **RAGChecker / RefChecker / LettuceDetect** | Claim-level hallucination *diagnostics* | Medical-grade **enforcement layer** + evidence quotes + abstention |
| **HHEM / MiniCheck** | Grounding scores for (doc, text) pairs | Used *inside* MedGuard as an independent second opinion |
| **MedHallu benchmark** | Medical hallucination test set | Reference for MedGuard's own evaluation roadmap |
| **ClinicBot (arXiv 2026)** | Chatbot with verification built in | MedGuard is **standalone & model-agnostic** — it audits *any* chatbot |

**Considered and rejected (and why):** Lynx-70B (strongest open judge, but needs GPU/paid API),
Cleanlab TLM & AIMon HDM-1 (paid), medical fine-tunes like BioMistral/OpenBioLLM (no free
first-party API; general 70B-class models beat them on medical QA — ~80–86% vs ~54% MedQA —
and a grounding auditor must not use medical priors anyway).

---

## 🧪 Validation — "I evaluated my evaluator"

MedGuard's audit quality is **measured, not assumed**. Two layers of testing, both against the
real Groq API (no mocks):

### 1. Adversarial battery — 20 hard cases ([`scripts/hard_battery.py`](scripts/hard_battery.py))

Prompt injection, dose escalations, negation flips, fabricated citations, drug-interaction
downplay, overdose reassurance, kitchen-sink mixed answers, and honest answers that must pass.
**Result: 20/20** — including both prompt-injection attacks defeated (the injected instructions
are treated as data to audit, never commands to obey).

### 2. Hand-labeled eval set — 25 cases ([`scripts/eval_set.py`](scripts/eval_set.py))

Verdict-level ground truth labeled case-by-case from the source texts before automated scoring:

| Metric | Result |
|---|---|
| **Verdict accuracy (acceptable-set)** | **25/25 = 100%** |
| **Danger recall** — dangerous answers NOT passed as SAFE | **14/14 = 100%** |
| **False-SAFE verdicts on dangerous answers** (the catastrophic failure mode) | **0** — none across all runs |
| Unsupported-only answers correctly flagged | 2/2 = 100% |
| Honest answers passed as SAFE | 4/6 (the other 2 returned WARNING — the strict verifier's safe-direction error, documented in the eval file) |
| Unknown-disease questions refused honestly | all (abstain or strict neighbor-topic audit — never a silent pass) |

### 3. Judge-vs-judge agreement — the "who audits the auditor?" answer

The same eval set run through **two different judges** (`openai/gpt-oss-120b` vs
`openai/gpt-oss-20b`): **21/24 = 88% verdict agreement**. The three disagreements were all
one-step verdict differences (SAFE↔WARNING, WARNING↔BLOCKED) — never a
dangerous-vs-safe flip. This is inter-rater reliability measured on our own auditor.

**Known limitations (stated honestly):** the judge errs on the strict side — a hedged paraphrase
of a supported statement can be flagged UNSUPPORTED (safe direction, but it costs some
precision on good answers); the library's guideline texts are simplified summaries, not verbatim
official documents (the app says so on screen); retrieval is keyword-based, so rare diseases
abstain rather than guess — by design.

*Eval artifacts: [`scripts/eval_results.json`](scripts/eval_results.json),
[`scripts/hard_battery_results.json`](scripts/hard_battery_results.json). Both suites are
re-runnable end-to-end with one command each.*

---

## Golden demo (prefilled in the app)

- **Q:** first-line antibiotic for uncomplicated UTI in pregnant women?
- **Source:** *"...nitrofurantoin or cephalexin are recommended. Fluoroquinolones such as
  ciprofloxacin are contraindicated because of fetal cartilage risk."*
- **Bad answer:** *"The first-line treatment is ciprofloxacin 500 mg twice daily for 3 days.
  Amoxicillin is also safe."*
- **Result:** ciprofloxacin claim → `CONTRADICTION` (with the contraindication quote), dosage and
  amoxicillin claims → `UNSUPPORTED` (source silent — note amoxicillin *is* actually safe in the
  real world, which proves MedGuard judges the source, not its own opinions) → **🔴 BLOCKED, 0%**.

---

## Roadmap

1. ~~Evaluate the evaluator~~ **DONE** — see the Validation section above (25-case eval set,
   100% danger recall, zero false-SAFE, 88% judge agreement)
2. Phase-2 demo RAG bot (same Groq key) so sources flow in automatically
3. FastAPI endpoint + React/Vercel frontend (the engine is already UI-agnostic)
4. Calibrated confidence; multi-guideline conflict handling; source attribution

---

## Safety

🛡️ MedGuard is an AI evaluation tool for educational purposes. It does not provide medical advice
and does not replace professional clinical judgment or official guidelines. It never generates
treatment recommendations — it only surfaces verbatim guideline text.

*Built with Streamlit + Groq (free tier) + HHEM/MiniCheck. $0 cost, 0 GPUs, 1 signup.*
