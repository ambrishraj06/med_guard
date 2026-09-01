# MedGuard — Deep Research Summary & A-to-Z Build Plan
**Clinical RAG Hallucination Auditor & Abstention Engine**
*Compiled 2026-08-31 · All decisions locked and research-validated*

---

## 1. WHAT WE ARE BUILDING (one paragraph)

MedGuard is **not a medical chatbot**. It is an **auditor that sits on top of any medical RAG chatbot** — an "AI BS-detector." It receives three inputs (clinical question, retrieved guideline text, AI-generated answer), splits the answer into atomic factual claims, verifies each claim against the guideline text ONLY (outside medical knowledge is forbidden), labels every claim SUPPORTED / UNSUPPORTED / CONTRADICTION with verbatim evidence quotes, computes an evidence-coverage score, and issues a hard verdict: **SAFE / WARNING / BLOCKED / UNVERIFIABLE** — where any contradiction blocks the whole answer and a missing source forces abstention.

---

## 2. WHY THIS MATTERS — RESEARCH-BACKED MOTIVATION

| Finding | Number | Source |
|---|---|---|
| Hallucination rate in tightly controlled clinical LLM workflows | ~1.47% (+3.45% omissions) | Nature npj Digital Medicine 2025 |
| Hallucination rate in clinical decision support AI (broader estimates) | 8–20% | industry analyses 2024–2026 |
| Hallucination rate of general-purpose LLMs on medical tasks | 15% → 52%+ | Othisis MedTech roundup |
| Clinicians who have personally encountered medical AI hallucinations | **91.8%** | 2026 clinician survey |
| Clinicians who believe hallucinations can directly harm patients | **84.7%** | same survey |

**The core insight:** LLMs do not signal when they are unsure. In medicine, a confident wrong answer (e.g., recommending a contraindicated drug) is worse than no answer. The safety literature converges on the exact safeguards MedGuard implements: grounding verification, evidence citation, uncertainty flagging, and **abstention**.

---

## 3. THE LANDSCAPE — WHAT ALREADY EXISTS (deep comparison)

### 3a. General RAG evaluation frameworks
| Tool | What it does | Why it is not MedGuard |
|---|---|---|
| **RAGAS** (Apache 2.0, actively maintained 2026) | Faithfulness / answer-relevancy / context metrics for RAG pipelines | Batch scorecard, no per-claim verdicts, no BLOCK policy, needs its own evaluator LLM, not medical |
| **DeepEval** (~50 metrics) | pytest-style LLM evaluation incl. hallucination metric | General-purpose; LLM-judge hidden inside; no medical policy layer |
| **TruLens** | Tracing + feedback functions for RAG debugging | Observability dashboard, not an enforcement gate |
| **RAGChecker** (Amazon Science) | Fine-grained claim-level RAG diagnostics | Closest general-purpose cousin — but diagnostic framework, not a medical safety gate with blocking/abstention |
| **RefChecker** (Amazon) | Fine-grained hallucination detection pipeline | General purpose, research-oriented |
| **LettuceDetect** | Lightweight encoder-based hallucinated-span flagger | Span flagging only; no verdicts, no medical tuning |
| **LongTracer** | RAG hallucination detection SDK (STS+NLI hybrid) | General purpose SDK |

### 3b. Hallucination-detection models (the "cross-checker" slot)
| Model | Type | Key fact | Fits our constraints (free, CPU, no key)? |
|---|---|---|---|
| **HHEM-2.1-Open** (Vectara) | ~600M cross-encoder | Powers the industry hallucination leaderboard; beat GPT-4 on Vectara's eval; leaderboard now runs commercial HHEM-2.3 | ✅ YES — our MVP pick |
| **MiniCheck-FT5** (770M) / Bespoke-MiniCheck-7B | Fact-checking models | GPT-4-level grounding accuracy on LLM-AggreFact, ~400x cheaper than GPT-4, beats HHEM by ~4–10%; **sentence-level = fits our claim-level design even better** | ✅ YES — planned upgrade / UI dropdown |
| **Lynx-70B** (Patronus AI) | 70B judge LLM | Beat GPT-4o by 8.3% on HaluBench | ❌ needs GPU/API — rejected, documented |
| **Cleanlab TLM / AIMon HDM-1** | Commercial APIs | Top precision/recall | ❌ paid — rejected, documented |

### 3c. Medical-specific research & benchmarks
- **MedHallu** — first comprehensive benchmark for medical LLM hallucination detection → our eval set should reference it
- **ClinicBot** (arXiv 2026) — guideline-grounded clinical CHATBOT with a verification pipeline → closest research cousin, but it is a chatbot-with-verification, not a standalone model-agnostic auditor
- **MedTrust-RAG** — evidence verification for biomedical QA
- **MIT Media Lab medical_hallucination** — impact research repo
- **awesome-medical-rag** (GitHub) — curated hub; confirms no dominant standalone medical auditor exists

### 3d. Medical LLMs (investigated and deliberately rejected)
| Model | MedQA (USMLE-style) | Verdict |
|---|---|---|
| BioMistral-7B (medical fine-tune) | ~54% | Weaker than general 70B; no free first-party API |
| OpenBioLLM-8B/70B | high (70B) | 70B = GPU/API; 8B too weak as judge |
| **Llama 3.3 70B (general)** | **~80–86%** | ✅ our pick — as auditor AND demo bot |
| Llama-3-8B / Mistral-7B (general) | outperform MediTron/BioMistral-7B per Nature Digital Medicine | confirms scale > medical fine-tuning |

**Key researched fact:** general Llama 3.3 70B's parametric medical knowledge BEATS specialized small medical models — and we deliberately forbid the auditor from using it (source-text-only rule), because a grounding auditor must judge against the page, not its priors. A RAG bot fed clinical guidelines IS a medical RAG bot; the medicine lives in the retrieval, not the weights.

---

## 4. WHAT IS UNIQUE ABOUT MEDGUARD (honest gap analysis)

1. **Standalone audit LAYER, not a chatbot and not a batch framework** — ClinicBot embeds verification inside one chatbot; RAGAS/RAGChecker/RefChecker are offline diagnostics. MedGuard is an inline, model-agnostic, source-agnostic gate that audits ANY chatbot's answer.
2. **Medical-grade enforcement policy** — hard BLOCK on any contradiction, WARNING on unsupported mix, UNVERIFIABLE abstention when no source. No general tool ships a policy layer; they ship scores.
3. **Claim-level with verbatim evidence quotes** — every verdict is human-checkable against the quoted guideline sentence.
4. **Ensemble design** — LLM judge (Llama 3.3 70B) + independent non-LLM cross-checker (HHEM/MiniCheck, swappable plug-in) + hand-labeled eval of the evaluator itself ("we evaluated our evaluator" — precision/recall, referenced to MedHallu/LLM-AggreFact).
5. **Free, GPU-less, one-API-key, deployable to a free public cloud link** — deliberately accessible without being a toy.
6. **Source-only epistemology** — the auditor is forbidden outside knowledge by design; it audits *grounding*, not medical truth. This is a defensible, articulable design position.

**Positioning line for the README/interviews:** *"I don't audit models — I audit outputs. Groundedness is a property of an answer, not of a model."*

---

## 5. FINAL LOCKED STACK (all decisions)

| Role | Choice | Runs on | Cost |
|---|---|---|---|
| Judge LLM (claim extraction + verification) | **GPT-OSS 120B** (`openai/gpt-oss-120b`) — UPDATE 2026-08-31: `llama-3.3-70b-versatile` was deprecated on the user's Groq account; account model list confirmed `openai/gpt-oss-120b` as the largest available judge (120B, json_mode + structured_outputs + reasoning, 131k context). Structured_outputs upgrades our per-claim schema enforcement. | Groq free API (cloud) | $0 |
| Fallback (extraction ONLY, never verification) | `qwen/qwen3.6-27b` or `openai/gpt-oss-20b` (account-confirmed IDs) | Groq | $0 |
| Bonus candidate noted | `openai/gpt-oss-safeguard-20b` (dedicated safety model on Groq) — potential future judge/cross-check experiment | Groq | $0 |
| Cross-checker (second opinion) | **HHEM-2.1-Open** first; **MiniCheck-FT5** as upgrade/dropdown | local / cloud CPU | $0 |
| UI | **Streamlit** | local then cloud | $0 |
| Cloud host | **Hugging Face Spaces** (free, 16GB RAM — fits MiniCheck/HHEM) | cloud | $0 |
| Secrets | `st.secrets` / Spaces Secrets vault; `.gitignore` first | — | — |
| Medical knowledge | Public guidelines (WHO / CDC / NICE, e.g. NICE NG111 for the golden case), pasted as chunks (MVP) or auto-retrieved (phase 2) | — | $0 |
| Repo name | `medguard-audit` (avoids name collisions) | — | — |

**Total signups: 1 (Groq). Total cost: $0. Total GPUs: 0.**

---

## 6. HOW IT WORKS — THE PIPELINE A TO Z (ELI5)

The exam analogy: the **textbook** = the clinical guideline; the **student** = the RAG bot; the **examiner** = MedGuard. The examiner doesn't need to be a doctor — the textbook already has the medicine. Their only job: "does the answer match the page?"

```
GUIDELINE (public PDF, e.g. NICE NG111)
   └─ chunk = one paragraph (~50-400 words)  ← the measuring stick
        ↓ INJECTION happens TWICE:
        ├──► Llama verifier PROMPT  ("judge ONLY against this text")
        └──► MiniCheck/HHEM INPUT   (doc, answer) pair — cannot run without it

AI ANSWER ──► [1] EXTRACT atomic claims (1 Groq call, temperature=0, JSON mode)
                   "one fact per claim; keep drugs/doses EXACT"
                   ↓
              [2] VERIFY all claims in ONE batched call (claim_ids, no N+1 calls)
                   per claim → SUPPORTED / UNSUPPORTED / CONTRADICTION
                            + reasoning + verbatim evidence quote
                   ↓
              [3] CROSS-CHECK (HHEM or MiniCheck): independent consistency score
                   ↓
              [4] VERDICT (pure code, deterministic):
                   any CONTRADICTION            → 🔴 BLOCKED, coverage 0
                   all SUPPORTED                → 🟢 SAFE, coverage 100
                   mix                          → 🟡 WARNING, supported/total × 100
                   no source / empty / 0 claims → ⚪ UNVERIFIABLE (abstain)
                   ↓
              [5] UI: color card + per-claim chips + highlighted evidence
                   + second-opinion score + raw JSON expander + disclaimer
```

**Golden test case (the demo):**
- Q: first-line antibiotic for uncomplicated UTI in pregnant women?
- Source: "…nitrofurantoin or cephalexin recommended. Fluoroquinolones such as ciprofloxacin are contraindicated…"
- Bad answer: "ciprofloxacin 500 mg twice daily for 3 days. Amoxicillin is also safe."
- Expected: claim 1 CONTRADICTION (quoted), claims 2–3 UNSUPPORTED (source silent — note amoxicillin is *actually* safe in real life, which proves the auditor is source-grounded, not opinion-grounded) → **BLOCKED, coverage 0%**.

---

## 7. IMPLEMENTATION PLAN — 9 STEPS (build order = safety order)

| Step | Deliverable | Needs internet? |
|---|---|---|
| 0 | Workshop: `E:\MedGuard`, venv, install streamlit/groq/pytest | yes, once |
| 1 | `medguard/verdict.py` — deterministic verdict table + edge cases (empty answer, zero claims, divide-by-zero) | **NO — offline** |
| 2 | `tests/test_verdict.py` — pytest green: golden labels → BLOCKED/0; all-supported → SAFE/100; empty → UNVERIFIABLE | **NO** |
| 3 | `medguard/prompts.py` — extractor (atomic, exact drugs/doses, claim_id JSON) + verifier (source-only, evidence quote, 3 statuses) | NO |
| 4 | `medguard/audit.py` — Groq wiring: JSON mode + fence-stripping + retry, temperature=0, batched verification with claim_ids, dropped-claim re-attachment (default UNSUPPORTED), status normalization | yes |
| 5 | `app.py` — Streamlit: secrets-first key handling, golden case prefilled, colored verdict card, evidence highlights, second-opinion score, JSON expander, medical disclaimer | yes |
| 6 | End-to-end test with real Groq key (golden case + good answer + no-source paths) | yes |
| 7 | README (pitch, diagram, screenshots, related-work incl. RAGAS/RAGChecker/RefChecker/LettuceDetect/MedHallu/ClinicBot + our differentiators, safety disclaimer, resume one-liner) + `.gitignore` BEFORE anything else → push to GitHub | yes |
| 8 | Deploy: HF Spaces → connect repo → key into Spaces Secrets → public link; MiniCheck/HHEM dropdown; quota guard (BYO-key option or daily counter) | yes |
| 9 | (Post-MVP roadmap) hand-labeled eval set 20–30 triplets → precision/recall vs hand labels, HHEM vs MiniCheck comparison; phase-2 demo bot (Llama+guideline chunks); REST API; calibration; multi-guideline conflict handling | yes |

**Debugging doctrine:** if the live audit misbehaves, the bug is in step 4 (plumbing), never step 1 (brain) — because the brain was proven offline first. Build order = sanity order.

---

## 8. FILE STRUCTURE

```
E:\MedGuard\
├── app.py                  # Streamlit UI (the face)
├── requirements.txt        # streamlit, groq, (pytest)
├── .gitignore              # .streamlit/secrets.toml, venv/, __pycache__/  ← FIRST commit
├── .streamlit/secrets.toml.example
├── README.md
├── RESEARCH_AND_PLAN.md    # this file
├── medguard/
│   ├── __init__.py
│   ├── verdict.py          # deterministic brain (offline)
│   ├── prompts.py          # extractor + verifier prompts
│   ├── audit.py            # Groq wiring + JSON defense + cross-checker plug-in slot
│   └── crosscheck.py       # HHEM / MiniCheck swappable second opinion
└── tests/
    ├── test_verdict.py     # offline pytest
    └── golden_case.json    # the UTI test case
```

---

## 9. RISKS & MITIGATIONS (research-honest)

| Risk | Mitigation |
|---|---|
| LLM judge hallucinating its verdicts | evidence-quote requirement (human-checkable), independent MiniCheck/HHEM cross-check, eval set |
| Same-model judge bias (player=referee) | MVP judges external answers; HHEM is architecturally independent; hand labels arbitrate |
| Groq model deprecation | verify model ID on console.groq.com at build time; model name is config, not hardcoded logic |
| JSON malformation | Groq JSON mode + fence stripping + retry + strict response validation |
| Public cloud app burning free quota | BYO-key option / daily counter |
| Retrieval fetches wrong chunk (phase 2) | show source attribution on every verdict; MVP uses manual chunks (perfect retrieval by definition) |
| Guideline conflicts/stale versions | keep current editions only; name the authority in the verdict (e.g. "verified against NICE NG111") |
| Overfitting/underfitting concerns | N/A — nothing trains; guidelines are reference books, not training data |

---

## 10. SOURCES (key references)

- Nature npj Digital Medicine — clinical LLM hallucination framework (1.47%/3.45%): nature.com/articles/s41746-025-01670-7
- Clinician survey (91.8% encountered / 84.7% harm belief): teledirectmd.com health guides 2026
- RAGAS vs DeepEval vs TruLens 2026: deepeval.com/blog/top-5-llm-evaluation-frameworks; genai.qa/blog/ragas-vs-trulens
- HHEM-2.1-Open: huggingface.co/vectara/hallucination_evaluation_model; Vectara HHEM 2.1 blog; leaderboard (now HHEM-2.3): github.com/vectara/hallucination-leaderboard
- MiniCheck (EMNLP 2024, LLM-AggreFact): aclanthology.org/2024.emnlp-main.499; github.com/Liyan06/MiniCheck; llm-aggrefact.github.io
- Lynx / HaluBench: arxiv.org/abs/2407.08488; patronus.ai blog
- Medical LLM landscape: BioMistral paper arxiv.org/html/2402.10373v1; Nature Digital Medicine s41746-025-01653-8 (general 7-8B beat MediTron/BioMistral); OpenBioLLM (Saama); HF Inference Providers docs
- Claim-level general auditors: github.com/amazon-science/RAGChecker; RefChecker; LettuceDetect; EdinburghNLP/awesome-hallucination-detection
- Medical benchmarks & kin: MedHallu (medhallu.github.io); ClinicBot arxiv.org/html/2605.00846v1; github.com/justin-marian/awesome-medical-rag; github.com/mitmedialab/medical_hallucination

---

*MEDGUARD IS AN EDUCATIONAL AI-EVALUATION TOOL. IT DOES NOT PROVIDE MEDICAL ADVICE AND DOES NOT REPLACE PROFESSIONAL CLINICAL JUDGMENT OR OFFICIAL GUIDELINES.*
