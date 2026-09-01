# MEMORY PACK — FOR HANDOFF TO ANY AI AGENT (Claude Opus 4.8 or other)
## Project: MedGuard — Clinical RAG Hallucination Auditor & Abstention Engine
*Compiled 2026-08-31 from a full design conversation. Paste this entire file as the first message to the new AI.*

---

## 0. HOW TO USE THIS PACK (for the AI reading it)

You are taking over an ALREADY FULLY DESIGNED project at the "pre-build" stage. The human (call him "mate", beginner-friendly English, likes ELI5 explanations, wants byte-sized steps, keep everything free) has completed: idea selection, deep research, all architecture decisions, tool selection, and Groq API verification. **Build has NOT started.** Your job: implement the plan below step by step, explaining simply, following the exact locked decisions — do NOT relitigate decided items unless the human asks.

## 1. THE PROJECT IN ONE PARAGRAPH

MedGuard is **not** a medical chatbot. It is an **auditor / safety layer** for ANY medical RAG chatbot — "an AI BS-detector." Inputs: (1) clinical question, (2) retrieved guideline chunk (verbatim text from public WHO/CDC/NICE guidelines), (3) an AI-generated answer. Pipeline: extract atomic factual claims from the answer → verify each claim against the source text ONLY (outside medical knowledge forbidden) → label SUPPORTED / UNSUPPORTED / CONTRADICTION with verbatim evidence quotes → compute evidence coverage → issue a hard verdict: SAFE / WARNING / BLOCKED / UNVERIFIABLE. Any contradiction blocks the whole answer; missing source forces abstention. Plus a "What the source says" side-by-side panel (verbatim quotes only — the system NEVER generates medical advice) and an independent cross-check score.

## 2. THE EXAM ANALOGY (use this to explain to the human)

Textbook = clinical guideline (the medicine lives HERE). Student = the RAG bot. Examiner = MedGuard. The examiner doesn't need to be a doctor — he only checks "does the answer match the page?" The examiner is even forbidden from using his own medical opinions. One LLM plays two "hats": examiner (auditor) and, later in phase 2, student (demo bot).

## 3. ALL LOCKED DECISIONS (do not change without asking the human)

| # | Decision | Choice | Why (short) |
|---|---|---|---|
| D1 | Build the auditor, not a chatbot | Yes | Uniqueness; chatbots are common |
| D2 | Model-agnostic, source-agnostic | Yes | Audits any chatbot via question/sources/answer JSON |
| D3 | Missing source → UNVERIFIABLE | Yes | Abstention is a safety feature |
| D4 | MVP = manual paste-in (no RAG bot) | Yes | Prove the auditor first; bot is phase 2 |
| D5 | Judge LLM | **`openai/gpt-oss-120b`** via Groq free API | Originally planned llama-3.3-70b-versatile, but it was DEPRECATED from the user's Groq account (verified 2026-08-31 via models.list()). gpt-oss-120b is bigger (120B) and supports json_mode + structured_outputs + reasoning. NOTE: gpt-oss is a reasoning model — set `reasoning_effort="low"` and generous max_tokens |
| D6 | Fallback LLM (extraction only, NEVER verification) | `qwen/qwen3.6-27b` or `openai/gpt-oss-20b` | Verified present on user's account |
| D7 | Cross-checker #1 (MVP) | **HHEM-2.1-Open** (Vectara, ~600M, HuggingFace, free, CPU, no key) | Simplest integration; industry-famous |
| D8 | Cross-checker #2 (upgrade/dropdown) | **MiniCheck-FT5** (770M) | Beats HHEM ~4–10% on LLM-AggreFact; sentence-level = fits claim-level design; ship both as UI dropdown, load only selected |
| D9 | Rejected models | Lynx-70B (needs GPU/API), Cleanlab TLM / AIMon (paid), medical LLMs (BioMistral/OpenBioLLM — no free API, weaker at 7-8B scale, and medical priors are a LIABILITY for a grounding auditor) | Documented in README "considered & rejected" |
| D10 | UI | **Streamlit** (+ .streamlit/config.toml theme + custom CSS verdict cards/chips/evidence quotes; components from streamlit-extras; borrow pieces from GitHub MIT-licensed apps, credit in README) | Beginner speed; UI is a replaceable skin; FastAPI+React-on-Vercel documented as v2 roadmap only |
| D11 | Cloud hosting | **Hugging Face Spaces** (free cpu-basic: 2 vCPU, 16GB RAM) | Only free tier fitting the whole stack (Streamlit + MiniCheck/HHEM ~3GB). Vercel can't host the models (serverless RAM). App sleeps after 48h idle; load only the selected cross-checker |
| D12 | Secrets | Groq key in st.secrets / HF Spaces Secrets vault; `.gitignore` excludes `.streamlit/secrets.toml` — committed BEFORE any code. NEVER hardcode | User's key was accidentally pasted into a chat once and was revoked + regenerated — reinforce key hygiene |
| D13 | Verdict logic (DETERMINISTIC, no ambiguity) | any CONTRADICTION → BLOCKED, coverage 0 · all SUPPORTED → SAFE, coverage 100 · mix → WARNING, coverage = supported/total × 100 · no source OR empty answer OR zero claims → UNVERIFIABLE, 0 | Fixes the original memory pack's ambiguous "BLOCKED or WARNING" |
| D14 | Verification batching | ONE batched call for all claims using `claim_id`s (not N+1 calls) | Free-tier rate limits + latency; claim_ids prevent order scrambling |
| D15 | Temperature | 0 on all audit calls; deterministic auditor | Same input → same verdict |
| D16 | Repo name | `medguard-audit` | Avoids collision with existing "MedGuard" products |
| D17 | Golden test case | UTI-in-pregnancy case (see §7) | Expected: BLOCKED, coverage 0% |
| D18 | "Correct treatment" feature | NEVER generate medical advice. Only surface verbatim source quotes in a side-by-side "What the source says" panel | Who-audits-the-correction regress; keeps unique positioning; matches safety rules |
| D19 | Medical LLMs | NOT USED anywhere. The guideline text IS the medical knowledge, injected fresh per audit | Researched: general 70B beats medical fine-tunes (~80-86% vs ~54% MedQA); and grounding auditors must not use priors |
| D20 | Overfitting concern | N/A — nothing trains; guidelines are reference books, not training data. Phase-2 real risks: wrong-chunk retrieval, guideline conflicts, stale versions | Explained to human, accepted |

## 4. RESEARCH HIGHLIGHTS (with sources for the README)

- Medical AI hallucination rates: ~1.47% controlled clinical workflows (Nature npj Digital Medicine, s41746-025-01670-7); 8–20% clinical decision support; 15–52% general LLM medical tasks; 91.8% of clinicians encountered AI hallucinations, 84.7% believe it can harm patients (2026 surveys)
- Related work to cite & differentiate: RAGAS, DeepEval, TruLens (batch eval frameworks); RAGChecker, RefChecker, LettuceDetect, LongTracer (claim-level diagnostics — closest cousins, but no medical policy/verdict layer); MedHallu benchmark; ClinicBot (arXiv 2605.00846, chatbot-with-verification); awesome-medical-rag list
- HHEM powers Vectara's hallucination leaderboard (now commercial HHEM-2.3); MiniCheck (EMNLP 2024) GPT-4-level grounding on LLM-AggreFact; Lynx-70B beat GPT-4o 8.3% on HaluBench but needs GPU
- BioMistral-7B MedQA ~54% vs Llama-3-70B-class ~80-86%; Nature Digital Medicine s41746-025-01653-8: general 7-8B models beat MediTron/BioMistral-7B

## 5. ARCHITECTURE (final)

```
GUIDELINE chunk (public WHO/CDC/NICE text, e.g. NICE NG111 for golden case)
   ├── INJECTION #1: pasted into verifier PROMPT ("SOURCE TEXT: judge ONLY against this")
   └── INJECTION #2: passed as input argument to HHEM/MiniCheck (doc, answer) pair

AI answer ──► [1] extract_claims(): 1 Groq call, atomic claims with claim_ids, JSON mode
              [2] verify_claims(): 1 BATCHED Groq call, per claim {claim_id, status,
                  reasoning, evidence(exact quote|null)}; structured_outputs on gpt-oss-120b
              [3] crosscheck(source, answer): HHEM or MiniCheck → independent score
              [4] verdict(): pure Python deterministic table (D13) — no LLM
              [5] Streamlit UI: color card + per-claim chips + highlighted evidence
                  + "What the source says" panel + raw JSON expander + disclaimer
```

## 6. FILE STRUCTURE (E:\MedGuard\)

```
E:\MedGuard\
├── app.py                  # Streamlit UI (theme + custom CSS verdict cards)
├── requirements.txt        # streamlit, groq, (transformers+torch for crosscheck), pytest
├── .gitignore              # FIRST commit: .streamlit/secrets.toml, venv/, __pycache__/
├── .streamlit/secrets.toml.example
├── README.md               # pitch, diagram, demo, related work, rejected-alternatives, disclaimer
├── RESEARCH_AND_PLAN.md    # deep research summary (exists)
├── HANDOFF_MEMORY_PACK.md  # this file
├── medguard/
│   ├── __init__.py
│   ├── verdict.py          # deterministic brain — BUILD FIRST, 100% offline
│   ├── prompts.py          # extractor + verifier prompts
│   ├── audit.py            # Groq wiring: JSON mode/structured_outputs + fence-stripping
│   │                       #   + retry on parse error + temp=0 + batched verification +
│   │                       #   dropped-claim re-attachment (default UNSUPPORTED) + status normalization
│   └── crosscheck.py       # HHEM / MiniCheck plug-in slot (st.cache_resource load)
└── tests/
    ├── test_verdict.py     # offline pytest: golden labels→BLOCKED/0; all-supported→SAFE/100; empty→UNVERIFIABLE
    └── golden_case.json
```

## 7. GOLDEN TEST CASE

- **Question:** What is the first-line antibiotic for uncomplicated UTI in pregnant women?
- **Source:** "For uncomplicated cystitis in pregnant women, nitrofurantoin or cephalexin are recommended. Fluoroquinolones such as ciprofloxacin are contraindicated because of fetal cartilage risk."
- **Bad answer:** "The first-line treatment is ciprofloxacin 500 mg twice daily for 3 days. Amoxicillin is also safe."
- **Expected:** claim1 "ciprofloxacin is first-line" → CONTRADICTION (quote the contraindication sentence); claim2 dosage → UNSUPPORTED; claim3 "Amoxicillin is also safe" → UNSUPPORTED (source silent — NOTE: amoxicillin is actually true in the real world, which PROVES the auditor is source-grounded, not opinion-grounded — say this in the README). Verdict BLOCKED, coverage 0%.
- Also test: good answer (nitrofurantoin) → SAFE/100; empty source → UNVERIFIABLE.

## 8. BUILD ORDER (9 steps — sanity order: brain before plumbing before face)

| Step | What | Internet? | Status |
|---|---|---|---|
| 0 | venv in E:\MedGuard, pip install streamlit groq pytest (transformers torch later) | once | ⏸ HOLDING (user said don't start yet) |
| 1 | medguard/verdict.py (deterministic table + edge cases incl. divide-by-zero) | NO | pending |
| 2 | tests/test_verdict.py → pytest GREEN | NO | pending |
| 3 | medguard/prompts.py (atomic extraction w/ exact drugs+doses; source-only verifier w/ evidence quotes) | NO | pending |
| 4 | medguard/audit.py (Groq wiring per D5/D14/D15; JSON defense) | yes | pending |
| 5 | app.py UI (D10 + "What the source says" panel D18 + disclaimer) | yes | pending |
| 6 | Live golden test with real key | yes | pending |
| 7 | README + .gitignore first → GitHub repo medguard-audit | yes | pending |
| 8 | HF Spaces deploy → Spaces Secrets → public link; quota guard (BYO-key option) | yes | pending |
| 9 | Post-MVP: hand-labeled eval set 20–30 triplets → precision/recall (HHEM vs MiniCheck comparison table); phase-2 demo bot (same Groq key); FastAPI endpoint; calibration | — | roadmap |

**Debugging doctrine:** if live audit misbehaves, bug is in step 4 (plumbing), never step 1 (brain — proven offline first).

## 9. CURRENT PROJECT STATE (updated 2026-09-02 — END OF BUILD DAY)

- ✅ **BUILD COMPLETE AND VERIFIED.** All milestones M0–M8 done:
  - 27/27 offline pytest GREEN (verdict brain proven before any API use)
  - 5/5 live end-to-end tests GREEN (real Groq calls): golden bad answer → BLOCKED/0% with CONTRADICTION + verbatim quote; good answer → SAFE/100%; both abstention paths correct; evidence quotes verified verbatim
  - HHEM ensemble verified live: bad answer 0.0129 vs good answer higher (directional separation PASS)
  - Full pipeline latency ~22s (reasoning model + HHEM)
- ✅ Code pushed to GitHub: https://github.com/ambrishraj06/med_guard (single clean commit; `.hfcache`/`.nltk_data` git-ignored after an initial staging catch)
- ✅ Groq verified working with `openai/gpt-oss-120b` (key lives in E:\MedGuard\.streamlit\secrets.toml — user-created, never in chat/repo)
- ⚠️ SECURITY INCIDENTS HANDLED: (1) a leaked key in chat was revoked + regenerated; (2) GitHub push protection caught the OLD revoked key inside `.streamlit/secrets.toml.example` (user had pasted it there) — file restored to placeholder and git history rebuilt from scratch so no secret exists in any commit. Key lesson: push protection scans ALL commits; keep secrets files out of git entirely.
- ⏳ DEPLOYMENT STATUS:
  - Streamlit Community Cloud: user deployed (repo ambrishraj06/med_guard, app.py) + needs GROQ_API_KEY in app Secrets. Production verification (browser test of golden case on the live URL) NOT yet done — user was running the 8-test battery manually.
  - HF Spaces: BLOCKED BY POLICY, not by code — free tier no longer includes cpu-basic flavor for Streamlit Spaces (limit=0 on two separate accounts; SDK flip to streamlit via README frontmatter worked, build refused at quota). Spaces exist at ambrishrs06/med_guard and ambrishrs69/med_guard (can be deleted). Do NOT retry HF free tier.
- ⬜ NEXT STEPS (in order):
  1. Verify production: user pastes live URL → run golden case in browser → expect BLOCKED/0%
  2. User runs the 8-test battery (golden/Safe/Unverifiable/Warning/negation-flip/dose-error/invented-study/grounding-showcase) — full test battery is in chat history; dangerous answers must never return SAFE
  3. OPTIONAL UPGRADE: add tiny NLI cross-checker (cross-encoder/nli-deberta-v3-small ~140MB) as third dropdown entry — fits any host incl. 512MB tiers
  4. Phase 2 roadmap: mini demo RAG bot (same Groq key) so sources flow automatically; FastAPI endpoint; Oracle Cloud Always Free ARM VM (12-24GB RAM, always free) to unlock MiniCheck + 24/7; eval set with precision/recall
- ❗ Lessons: (a) Groq model IDs deprecate — model name is config; (b) never paste keys in chat; gpt-oss = reasoning model (reasoning_effort="low", generous max_tokens); (d) transformers MUST stay <5 for HHEM; (e) HF free tier 2026 = no free cpu-basic for Streamlit — use Streamlit Cloud or Oracle ARM.

## 10. WHAT THE NEXT AI SHOULD DO

1. Read §3 (decisions) and §8 (build order) carefully — do not deviate
2. Wait for the human's "go" — then execute Step 0→6 in order, explaining each step in simple ELI5 language with the exam analogy
3. Write clean beginner-readable code with comments explaining WHY for non-obvious choices
4. After step 2 (pytest green), show the human the passing tests before proceeding
5. Use the exact golden case (§7) as the prefilled demo
6. Before deploying (step 8), confirm the human has GitHub + HF accounts
7. Never put the API key in code, chat, or README — always secrets vaults

## 11. SAFETY DISCLAIMER (must appear in app + README)

> MedGuard is an AI evaluation tool for educational purposes. It does not provide medical advice and should not replace professional clinical judgment or official guidelines.
