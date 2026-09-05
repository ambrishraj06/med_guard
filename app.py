"""
MedGuard — app.py
=================
The Streamlit face of the clinical RAG hallucination auditor.

Design language (clinical revamp — flat light theme):
  - IBM Plex Sans/Mono, self-hosted; #0066cc medical-blue accent
  - Flat clinical surfaces: white cards + 1px #dee2e6 borders — no gradients,
    no blur, no glow, no transform hovers, and zero emoji anywhere
  - Verdict card (colored edge rule + status headline) + per-claim status
    chips + verbatim evidence blockquotes
  - "What the source says" side-by-side panel (verbatim quotes ONLY — never
    generated medical advice, decision D18)
  - Optional independent cross-check score (HHEM / MiniCheck / none)
  - Golden test case prefilled so the first click always demos perfectly
  - Medical disclaimer always visible

Run:  streamlit run app.py
"""

import hashlib
import json
import queue
import sys
import threading
import traceback
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Brand mark for the browser tab — the same flat navy shield as the header.
# A PIL image is the one page_icon form that works identically locally and on
# Streamlit Cloud (image_to_url embeds the bytes; no CDN, no emoji fallback).
try:
    from PIL import Image  # Pillow ships with Streamlit

    _FAVICON = Image.open(Path(__file__).resolve().parent / "static" / "favicon.png")
except Exception:
    _FAVICON = None

# Diagnostic trap: show the REAL import error on the page instead of
# Streamlit's redacted "ImportError" card, so failures are debuggable in prod.
try:
    from medguard.audit import DEFAULT_JUDGE_MODEL, generate_answer, run_audit  # noqa: E402
    from medguard.crosscheck import available_checkers  # noqa: E402
    from medguard.library import match_source  # noqa: E402
except Exception:
    st.set_page_config(page_title="MedGuard — startup error", page_icon=_FAVICON, layout="wide")
    st.error("MedGuard failed to import its engine. Real error below:")
    st.code(traceback.format_exc(), language="python")
    st.stop()

# ---------------------------------------------------------------------------
# Page + golden case
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="MedGuard — Clinical RAG Hallucination Auditor",
    page_icon=_FAVICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

GOLDEN = {
    "question": "What is the first-line antibiotic for uncomplicated UTI in pregnant women?",
    "source": (
        "For uncomplicated cystitis in pregnant women, nitrofurantoin or cephalexin "
        "are recommended. Fluoroquinolones such as ciprofloxacin are contraindicated "
        "because of fetal cartilage risk."
    ),
    "bad_answer": (
        "The first-line treatment is ciprofloxacin 500 mg twice daily for 3 days. "
        "Amoxicillin is also safe."
    ),
    "good_answer": (
        "For uncomplicated cystitis in pregnant women, nitrofurantoin or cephalexin "
        "are recommended as first-line antibiotics."
    ),
}

# Verdict wording. Status COLORS live in the CSS (flat design: colored edge
# rule on the card + status-colored headline — no icons, no emoji).
VERDICT_STYLES = {
    "BLOCKED": ("AUDIT FAILED — DON'T TRUST IT", "This answer goes against the medical guideline. Following it could be dangerous."),
    "SAFE": ("AUDIT PASSED — TRUSTED", "This answer matches the medical guideline."),
    "WARNING": ("AUDIT FLAGGED — PARTLY TRUSTED", "Some parts are fine, but the flagged parts below are NOT from the guideline."),
    "UNVERIFIABLE": ("CAN'T AUDIT — NO GUIDELINE FOUND", "We couldn't find a guideline for this. Paste a source (or try a common topic) and audit again."),
}

CHIP_STYLES = {
    "SUPPORTED": "BACKED BY THE GUIDELINE",
    "UNSUPPORTED": "NOT IN THE GUIDELINE",
    "CONTRADICTION": "GOES AGAINST THE GUIDELINE",
}

# One brand asset everywhere (tab icon, header, sidebar): the flat navy shield.
WORDMARK_IMG = (
    '<img class="mg-mark" src="app/static/favicon.png" alt="" width="30" height="30">'
)

# ---------------------------------------------------------------------------
# CSS — the clinical flat design layer (borders + typography, no effects)
# ---------------------------------------------------------------------------
st.markdown(
    """
<style>
  /* ---------- MedGuard clinical design system — flat light theme ----------
     Palette: #0066cc primary · #fafbfc app bg · #ffffff surfaces · #f4f6f8
     secondary · #2c3e50 text · #6b7a8d muted · #dee2e6 hairlines.
     Status: #c62828 fail · #1a7f37 pass · #b26a00 caution · #546e7a n/a.
     House rules: solid fills and 1px borders only — no gradients, no blur,
     no glow shadows, no transform hovers, no emoji. */
  #MainMenu, footer, header { visibility: hidden; }
  /* The collapsed-sidebar reopen arrow (stExpandSidebarButton) renders
     INSIDE that hidden header — without this rule the sidebar can be
     closed but never opened again. */
  header [data-testid="stExpandSidebarButton"],
  header [data-testid="stExpandSidebarButton"] * {
      visibility: visible !important; }
  header [data-testid="stExpandSidebarButton"] {
      background: #ffffff !important;
      border: 1px solid #dee2e6 !important;
      border-radius: 6px !important;
      box-shadow: none !important; }

  /* ---------- header ---------- */
  .mg-header { display:flex; align-items:center; gap:16px; padding: 16px 2px 0 2px; }
  .mg-logo { display:flex; align-items:center; gap:10px; font-size:1.65rem;
      font-weight:700; color:#2c3e50; letter-spacing:-.2px; }
  .mg-mark { display:block; }
  .mg-tag { color:#6b7a8d; font-size:.95rem; margin-top:4px; }
  .mg-rule { height:1px; margin:14px 0 18px 0; background:#dee2e6; }

  /* ---------- cards ---------- */
  .mg-card { background:#ffffff; border:1px solid #dee2e6;
      border-radius:6px; padding:18px 20px; }

  /* ---------- verdict card — status = colored edge rule + headline ---------- */
  .mg-verdict { background:#ffffff; border:1px solid #dee2e6;
      border-left:4px solid #546e7a; border-radius:6px; padding:22px 24px;
      animation: mgIn .4s ease both; }
  .mg-verdict .v-label { font-weight:700; font-size:1.5rem; letter-spacing:.5px;
      line-height:1.3; }
  .mg-verdict .v-sub { color:#2c3e50; margin-top:8px; font-size:1rem; }
  .mg-verdict .v-sub.advice { font-weight:600; }
  .mg-verdict-BLOCKED { border-left-color:#c62828; }
  .mg-verdict-BLOCKED .v-label, .mg-verdict-BLOCKED .v-sub.advice { color:#c62828; }
  .mg-verdict-SAFE { border-left-color:#1a7f37; }
  .mg-verdict-SAFE .v-label, .mg-verdict-SAFE .v-sub.advice { color:#1a7f37; }
  .mg-verdict-WARNING { border-left-color:#b26a00; }
  .mg-verdict-WARNING .v-label, .mg-verdict-WARNING .v-sub.advice { color:#b26a00; }
  .mg-verdict-UNVERIFIABLE { border-left-color:#546e7a; }
  .mg-verdict-UNVERIFIABLE .v-label, .mg-verdict-UNVERIFIABLE .v-sub.advice { color:#546e7a; }
  @keyframes mgIn { from { opacity:0; } to { opacity:1; } }

  /* ---------- claim chips + rows ---------- */
  .mg-chip { display:inline-flex; align-items:center; padding:3px 10px;
      border-radius:4px; font-size:.72rem; font-weight:700; letter-spacing:.6px;
      border:1px solid; }
  .mg-chip-SUPPORTED { color:#1a7f37; border-color:#a8cdb2; background:#f2f8f4; }
  .mg-chip-UNSUPPORTED { color:#b26a00; border-color:#dcbf94; background:#fbf6ec; }
  .mg-chip-CONTRADICTION { color:#c62828; border-color:#dba5a5; background:#fcf2f2; }
  .mg-claim { border-left:3px solid #dee2e6; padding:12px 14px; margin:10px 0;
      border-radius:0 6px 6px 0; background:#ffffff; }
  .mg-claim-CONTRADICTION { border-left-color:#c62828; }
  .mg-claim-UNSUPPORTED { border-left-color:#b26a00; }
  .mg-claim .c-text { color:#2c3e50; font-size:.98rem; }
  .mg-claim .c-why { color:#6b7a8d; font-size:.85rem; margin-top:5px; }
  .mg-quote { border-left:3px solid #0066cc; background:#f4f8fc;
      padding:10px 14px; border-radius:0 6px 6px 0; }
  .mg-quote, .mg-quote * { color:#2c3e50; font-style:italic; }

  /* ---------- side-by-side source panel ---------- */
  .mg-duo { display:grid; grid-template-columns: 1fr 1fr; gap:14px; }
  .mg-duo .head { font-weight:700; letter-spacing:.8px; font-size:.78rem;
      margin-bottom:8px; }
  .mg-duo .claimed { color:#c62828; }
  .mg-duo .sourced { color:#1a7f37; }

  /* ---------- footer ---------- */
  .mg-footer { color:#6b7a8d; font-size:.82rem; text-align:center;
      padding:22px 0 8px 0; border-top:1px solid #dee2e6; margin-top:26px; }

  /* ---------- mobile ---------- */
  @media (max-width: 760px) {
    .mg-duo { grid-template-columns: 1fr !important; }
    .mg-header { flex-direction: column; gap: 4px; }
    .mg-verdict { padding: 18px 16px; }
    .mg-verdict .v-label { font-size: 1.3rem; }
    .mg-card { padding: 14px 12px; }
  }
</style>
""",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Small render helpers
# ---------------------------------------------------------------------------
def render_header() -> None:
    st.markdown(
        f"""
        <div class="mg-header">
          <div>
            <div class="mg-logo">{WORDMARK_IMG} MedGuard</div>
            <div class="mg-tag">AI answers in. <b>Audit reports</b> out. Every medical claim checked against official guidelines.</div>
          </div>
        </div>
        <div class="mg-rule"></div>
        """,
        unsafe_allow_html=True,
    )


def compute_unverifiable() -> dict:
    """Plain abstention card shown when no guideline can be matched (no LLM call)."""
    return {
        "verdict": "UNVERIFIABLE",
        "coverage": 0,
        "reason": "No source text provided. MedGuard cannot verify grounding without evidence.",
    }


def render_verdict(verdict: str, coverage: int, reason: str) -> None:
    if verdict not in VERDICT_STYLES:
        verdict = "UNVERIFIABLE"
    label, advice = VERDICT_STYLES[verdict]
    st.markdown(
        f"""
        <div class="mg-verdict mg-verdict-{verdict}">
          <div class="v-label">{label}</div>
          <div class="v-sub advice">{advice}</div>
          <div class="v-sub" style="margin-top:10px;">{reason}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_claims(claims: list[dict]) -> None:
    """One card per claim, in ordinary words: what the answer said + plain verdict."""
    st.markdown("### Audit findings — every claim in the answer, checked")
    if not claims:
        st.markdown('<div class="mg-card">Nothing to check in this answer.</div>', unsafe_allow_html=True)
        return
    for c in claims:
        label = CHIP_STYLES.get(c["status"], CHIP_STYLES["UNSUPPORTED"])
        evidence_html = ""
        if c.get("evidence"):
            evidence_html = (
                f'<div class="mg-quote" style="margin-top:8px;"><b>From the guideline:</b> “{c["evidence"]}”</div>'
            )
        why = c.get("reasoning") or ""
        cc = c.get("crosscheck_score")
        cc_html = (
            f'<div class="c-why" style="margin-top:4px;">Independent checker: <b>{int(cc*100)}%</b> support</div>'
            if cc is not None else ""
        )
        disagree = c.get("disagreement")
        disagree_html = (
            f'<div class="c-why" style="margin-top:4px;color:#b26a00;">{disagree}</div>'
            if disagree else ""
        )
        st.markdown(
            f"""
            <div class="mg-claim">
              <span class="mg-chip mg-chip-{c['status']}">{label}</span>
              <div class="c-text" style="margin-top:7px;">“{c["claim"]}”</div>
              <div class="c-why">{why}</div>
              {cc_html}
              {disagree_html}
              {evidence_html}
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_source_panel(source: str, claims: list[dict], source_name: str | None = None) -> None:
    """Side-by-side: what the answer got wrong vs the guideline's own words."""
    failed = [c for c in claims if c["status"] in ("UNSUPPORTED", "CONTRADICTION")]
    st.markdown("### The answer vs the guideline, side by side")
    attribution = f" — Source: {source_name}" if source_name else ""
    st.caption(f"Real guideline text only{attribution}. MedGuard shows evidence, it never writes its own medical advice.")
    if not source.strip():
        st.markdown('<div class="mg-card">No guideline was provided.</div>', unsafe_allow_html=True)
        return
    if not failed:
        st.markdown(
            '<div class="mg-card">Everything in the answer traces back to the guideline.</div>',
            unsafe_allow_html=True,
        )
        return
    rows = ""
    for c in failed:
        quote = c.get("evidence") or _best_matching_sentence(source, c["claim"]) or "(nothing in the guideline talks about this — the answer made it up or brought it in from outside)"
        rows += f"""
        <div class="mg-duo mg-claim mg-claim-{c['status']}">
          <div>
            <div class="head claimed">WHAT THE ANSWER SAID</div>
            <div class="c-text">{c["claim"]}</div>
          </div>
          <div>
            <div class="head sourced">WHAT THE GUIDELINE SAYS{f" ({source_name})" if source_name else ""}</div>
            <div class="mg-quote">“{quote}”</div>
          </div>
        </div>"""
    st.markdown(rows, unsafe_allow_html=True)


def _best_matching_sentence(source: str, claim: str) -> str | None:
    """Naive lexical overlap match: which source sentence is most relevant to a claim?
    Used ONLY to surface verbatim guideline text next to a failed claim."""
    import re

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", source) if s.strip()]
    claim_words = {w for w in re.findall(r"[a-z0-9]+", claim.lower()) if len(w) > 3}
    best, best_overlap = None, 0
    for s in sentences:
        overlap = len(claim_words & {w for w in re.findall(r"[a-z0-9]+", s.lower())})
        if overlap > best_overlap:
            best, best_overlap = s, overlap
    return best


# ---------------------------------------------------------------------------
# Sidebar — guide, examples, advanced settings
# ---------------------------------------------------------------------------
checkers = available_checkers()

TEST_CASES = {
    "— Pick an example (fills the boxes) —": None,
    "Dangerous answer caught (UTI antibiotic)": {
        "q": "What is the first-line antibiotic for uncomplicated UTI in pregnant women?",
        "s": (
            "For uncomplicated cystitis in pregnant women, nitrofurantoin or cephalexin are "
            "recommended. Fluoroquinolones such as ciprofloxacin are contraindicated because of "
            "fetal cartilage risk."
        ),
        "a": "The first-line treatment is ciprofloxacin 500 mg twice daily for 3 days. Amoxicillin is also safe.",
    },
    "Honest answer passes": {
        "q": "What is the first-line antibiotic for uncomplicated UTI in pregnant women?",
        "s": (
            "For uncomplicated cystitis in pregnant women, nitrofurantoin or cephalexin are "
            "recommended. Fluoroquinolones such as ciprofloxacin are contraindicated because of "
            "fetal cartilage risk."
        ),
        "a": "For uncomplicated cystitis in pregnant women, nitrofurantoin or cephalexin are recommended as first-line antibiotics.",
    },
    "Dengue: wrong painkiller (WHO / ICMR)": {
        "q": "I have dengue fever with body aches. What painkiller should I take?",
        "s": (
            "Dengue is a mosquito-borne viral infection. There is no specific antiviral medicine; "
            "treatment is supportive — rest, plenty of fluids, and paracetamol for fever and pain. "
            "NSAIDs such as aspirin or ibuprofen must be avoided because they increase the risk of bleeding."
        ),
        "a": "Ibuprofen 400 mg three times a day is effective for dengue fever aches.",
    },
    "Warfarin: hidden drug interaction": {
        "q": "I take warfarin for my heart. I have a bad thrush infection — what medicine should I use?",
        "s": (
            "Fluconazole is an effective treatment for thrush. However, fluconazole must not be "
            "combined with warfarin — the combination causes a severe bleeding risk and is "
            "contraindicated. Miconazole gel is a safer alternative for patients taking warfarin."
        ),
        "a": "Fluconazole is a good option for treating your thrush.",
    },
    "Half-true answer (partly safe)": {
        "q": "What lifestyle changes are recommended for a patient with newly diagnosed high blood pressure?",
        "s": (
            "Adults with newly diagnosed hypertension should be advised to reduce salt intake to less "
            "than 5 g per day and to engage in at least 150 minutes of moderate-intensity aerobic exercise "
            "per week. Weight loss is recommended for patients who are overweight."
        ),
        "a": "Patients should reduce salt intake to less than 5 g per day and exercise for at least 150 minutes weekly. They should also take potassium supplements daily and completely avoid all fruits.",
    },
    "Invented study (classic AI lie)": {
        "q": "Does vitamin C prevent the common cold?",
        "s": (
            "Regular vitamin C supplementation has not been shown to prevent the common cold in the "
            "general population, though it may slightly reduce the duration of symptoms."
        ),
        "a": "Yes. According to the 2023 Harrison medical trial, taking 2000 mg of vitamin C daily prevents the common cold in 87% of people.",
    },
    "Unknown disease (honest CAN'T CHECK)": {
        "q": "What is the recommended management for Zellweger spectrum disorder?",
        "s": "",
        "a": "Zellweger spectrum disorder is managed by a team of specialists.",
    },
}

with st.sidebar:
    st.markdown(
        f"""
        <div style="padding:2px 2px 10px 2px;">
          <div class="mg-logo">{WORDMARK_IMG} MedGuard</div>
          <div class="mg-tag">Can you trust that AI health answer?</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("How to use this app"):
        st.markdown(
            """
            **3 simple steps:**

            1. Type the **question** someone asked the AI
            2. Paste the **AI's answer** you want checked
            3. Hit **“Audit this answer”**

            **About the guideline (source) box:**
            - Paste the official guideline for the most accurate check, **or**
            - Leave it empty — we auto-pick a matching topic from our built-in
              library of **69 medical guideline summaries** (WHO, CDC, NICE, ICMR
              and more) and tell you exactly which one we used.

            **If we don't have the topic:** the app will honestly say
            “CAN'T CHECK” instead of guessing — that's a safety feature.

            **What you get:** a clear trust verdict, each claim in the answer
            checked one-by-one, and the guideline's own words next to anything
            the answer got wrong.
            """
        )

    preset = st.selectbox(
        "Try an example",
        list(TEST_CASES.keys()),
    )

    st.markdown("**Audit depth**")
    audit_mode = st.radio(
        "Choose how deep the audit goes",
        ["Thorough (full audit)", "Fast (skip final review)"],
        index=0,
        label_visibility="collapsed",
        help="Thorough adds a third whole-answer safety review — best for demos and real checks. Fast skips it for speed.",
    )

    with st.expander("Advanced settings (for engineers)"):
        key_status = "Key loaded from secrets/env"
        try:
            import streamlit as st_secret_check  # noqa: PLC0415

            _ = st_secret_check.secrets["GROQ_API_KEY"]
        except Exception:
            key_status = (
                "No key found — paste one below "
                "(get a free key at console.groq.com/keys)"
            )
        st.markdown(f"**Groq API key**  \n{key_status}")
        manual_key = st.text_input(
            "Bring your own key (BYO)",
            type="password",
            help="Stored in memory for this session only — never written to disk.",
        )

        st.divider()
        st.markdown("**Judge model**")
        st.code(DEFAULT_JUDGE_MODEL, language=None)
        st.caption("Model name is config, not hardcoded logic — Groq deprecates models.")

        st.divider()
        st.markdown("**Independent cross-checker**")
        checker_options = [
            "none",
            "hhem" if checkers["hhem"] else "hhem (unavailable — install torch+transformers)",
            "minicheck" if checkers["minicheck"] else "minicheck (unavailable — pip install minicheck)",
        ]
        # HHEM is the default when it is available — the independent second
        # opinion runs automatically on every audit.
        default_idx = 1 if checkers["hhem"] else 0
        checker = st.selectbox("Second opinion", checker_options, index=default_idx)
        checker_clean = checker.split(" (")[0]
        st.caption(
            "HHEM / MiniCheck are small non-LLM models that independently score whether "
            "the answer is supported by the source. Loads only the selected model."
        )

# ---------------------------------------------------------------------------
# Main inputs
# ---------------------------------------------------------------------------
render_header()

# Sidebar preset fills the three boxes (canonical state path + rerun)
if TEST_CASES[preset] is not None and st.session_state.get("_loaded_preset") != preset:
    st.session_state["_loaded_preset"] = preset
    st.session_state["mg_question"] = TEST_CASES[preset]["q"]
    st.session_state["mg_source"] = TEST_CASES[preset]["s"]
    st.session_state["mg_answer"] = TEST_CASES[preset]["a"]
    st.rerun()
elif TEST_CASES[preset] is None:
    st.session_state["_loaded_preset"] = preset

# Canonical Streamlit pattern: set widget defaults ONCE in session_state,
# then create widgets with key= only. Passing value= together with key= is the
# known anti-pattern that reverts user edits on rerun.
if "mg_question" not in st.session_state:
    st.session_state["mg_question"] = GOLDEN["question"]
if "mg_source" not in st.session_state:
    st.session_state["mg_source"] = GOLDEN["source"]
if "mg_answer" not in st.session_state:
    st.session_state["mg_answer"] = GOLDEN["bad_answer"]

question = st.text_area(
    "The question that was asked",
    key="mg_question",
    height=68,
)
source = st.text_area(
    "Guideline text (optional — leave empty and we auto-pick from our library)",
    key="mg_source",
    height=110,
    help="Paste the official guideline here for the most accurate check. If you leave it empty, we'll try to find a matching topic in our built-in library of 69 medical guideline summaries.",
)
answer = st.text_area(
    "The AI answer you want checked",
    key="mg_answer",
    height=110,
    help="Paste the AI's answer here — MedGuard only checks answers, it never writes its own.",
)

if not source.strip():
    st.caption(
        "Paste the official guideline for better accuracy — otherwise we'll auto-pick "
        "a matching topic from our built-in library (WHO / CDC / NICE / ICMR and more)."
    )

run_clicked = st.button(
    "Audit this answer",
    use_container_width=True,
    type="primary",
)

# ---------------------------------------------------------------------------
# The classroom demo — "Bot vs Bot": one question, two AI students, both audited.
#   naive bot = answers from general knowledge, no guideline (typical chatbot)
#   RAG bot   = reads the retrieved guideline first, answers from the page
# The examiner (MedGuard) grades both against the same textbook page.
# Curated cases were chosen from REAL API runs — the naive/RAG divergence
# below was observed, not scripted.
# ---------------------------------------------------------------------------
from medguard.audit import generate_naive_answer  # noqa: E402

CLASSROOM_CASES = {
    "— Pick a classroom demo —": None,
    "Warfarin + thrush (the hidden interaction)": (
        "I take warfarin for my heart. I have a bad thrush infection — what medicine should I use?"
    ),
    "Dengue painkiller (true facts, unverified details)": (
        "I have dengue fever with body aches. What painkiller should I take?"
    ),
    "Vitamin C and the common cold": (
        "How much vitamin C should I take daily to prevent the common cold?"
    ),
}


def _run_bot_battle(question: str, api_key: str | None) -> dict:
    """Generate + audit BOTH students on the same question and textbook page.

    Returns {"topic", "source_name", "naive", "naive_result", "rag", "rag_result"}
    or raises. The textbook page always comes from the built-in library (the
    demo needs retrieval to make the RAG student grounded).

    Note: when the RAG student refuses (the source doesn't answer the question),
    the judge can legitimately flag the refusal sentence as a contradiction —
    "the source DOES talk about this". We surface that as an honest abstention
    note in the demo instead of a scary red card.
    """
    match, _score = match_source(question)
    if match is None:
        raise LookupError(
            "We couldn't find a guideline topic for this question in our built-in "
            "library — the classroom demo needs a textbook page to grade against. "
            "Try one of the demo questions or a more common medical topic."
        )
    src = match["text"]

    # naive student: answers from general knowledge
    naive = generate_naive_answer(question, api_key=api_key)
    naive_result = run_audit(
        question, src, naive, thorough=True, api_key=api_key
    )

    # RAG student: reads the guideline page first
    rag = generate_answer(question, src, api_key=api_key)
    rag_result = run_audit(
        question, src, rag, thorough=True, api_key=api_key
    )
    rag_abstained = "does not cover this question" in rag.lower()
    return {
        "topic": match["topic"],
        "source_name": match.get("source_name", "built-in library"),
        "naive": naive,
        "naive_result": naive_result,
        "rag": rag,
        "rag_result": rag_result,
        "rag_abstained": rag_abstained,
    }


# ---------------------------------------------------------------------------
# The classroom demo — Bot vs Bot (one question, two AI students, both graded)
# ---------------------------------------------------------------------------
with st.expander(
    "Classroom demo — watch two AI bots answer, then get graded (1 click)",
    expanded=False,
):
    st.markdown(
        "One question. Two AI students. **The naive bot** answers from general knowledge "
        "(like a typical health chatbot — confident, specific, no textbook). **The RAG bot** "
        "reads the matching guideline page from our library first. MedGuard then grades "
        "**both** answers against the same page. Same judge, same rules — the only difference "
        "is whether the student studied."
    )
    demo_sel = st.selectbox("Demo question", list(CLASSROOM_CASES.keys()), key="mg_demo_case")
    demo_q = CLASSROOM_CASES[demo_sel]
    if demo_q is None:
        custom_q = st.text_input(
            "…or type your own question (needs a topic our library covers)",
            key="mg_demo_custom_q",
        )
        demo_q = custom_q.strip() or None
    battle_clicked = st.button(
        "Run the classroom demo",
        use_container_width=True,
        disabled=demo_q is None,
        help="Generates both answers with the same Groq key, then audits both. Uses 6–8 free-tier API calls.",
    )

# ---------------------------------------------------------------------------
# Staged audit runner — live stage animation + Fast/Thorough toggle + memo
# ---------------------------------------------------------------------------
st.markdown(
    """
<style>
  /* ---------- stage rail (chips) — flat states: done / active / pending ---------- */
  .mg-progress { display:flex; gap:8px; flex-wrap:wrap; margin:6px 0 12px 0; }
  .mg-progress span { font-size:.78rem; color:#6b7a8d; padding:4px 12px;
      border-radius:4px; border:1px solid #dee2e6; background:#ffffff; }
  .mg-progress span.done { color:#1a7f37; border-color:#a8cdb2;
      background:#f2f8f4; }
  .mg-progress span.active { color:#0066cc; border-color:#0066cc;
      background:#f4f8fc; font-weight:700; }

  /* ---------- spinner — one flat ring ---------- */
  .mg-scan { position:relative; width:40px; height:40px; flex:none; }
  .mg-scan .ring { position:absolute; inset:0; border-radius:50%;
      border:3px solid #e4e9ee; border-top-color:#0066cc;
      animation: mgSpin .9s linear infinite; }
  @keyframes mgSpin { to { transform: rotate(360deg); } }

  /* ---------- current-stage line ---------- */
  .mg-stage-line { display:flex; align-items:center; gap:14px; margin:4px 0 10px 0; }
  .mg-stage-label { color:#2c3e50; font-weight:700; letter-spacing:.3px; }
  .mg-stage-sub { color:#6b7a8d; font-size:.82rem; margin-top:3px; }

  /* ---------- claim entrance ---------- */
  .mg-claim { animation: mgIn .4s ease both; }
  .mg-claim:nth-child(2) { animation-delay: .06s; }
  .mg-claim:nth-child(3) { animation-delay: .12s; }
  .mg-claim:nth-child(4) { animation-delay: .18s; }
  [data-testid="stTextArea"] textarea:focus {
      border-color: #0066cc !important;
      box-shadow: none !important; }
</style>
""",
    unsafe_allow_html=True,
)

_STAGE_KEYS = ["extract", "verify", "holistic", "crosscheck"]
_STAGE_INFO = {
    "extract": (
        "1 · Reading claims",
        "Finding every medical claim in the answer — including implied ones…",
    ),
    "verify": (
        "2 · Verifying against the guideline",
        "Checking each claim against the official source text…",
    ),
    "holistic": (
        "3 · Final safety review",
        "One last look at the whole answer in patient context…",
    ),
    "holistic-skip": (
        "3 · Final safety review — not needed",
        "The claim check already found a dangerous contradiction, so the third "
        "review cannot change the verdict. Skipping it keeps the audit fast.",
    ),
    "crosscheck": (
        "4 · Independent second opinion",
        "A separate checker scores how well each claim follows the guideline…",
    ),
    "done": (
        "Audit complete",
        "Building the report…",
    ),
}
_STAGE_CHIP_LABELS = {
    "extract": "1 · Reading claims",
    "verify": "2 · Verifying",
    "holistic": "3 · Safety review",
    "crosscheck": "4 · Second opinion",
}


def _stage_chips(active: str, visible: list[str]) -> str:
    """Chips for the stages this audit mode actually runs: everything before
    the active stage is done (green), the active stage is highlighted (blue),
    later stages stay muted. On 'done', all visible stages are done."""
    active = "holistic" if active == "holistic-skip" else active
    keys = [k for k in _STAGE_KEYS if k in visible]
    try:
        idx = keys.index(active)
    except ValueError:
        idx = len(keys)
    chips = []
    for i, key in enumerate(keys):
        cls = "done" if i < idx else ("active" if i == idx else "")
        chips.append(f'<span class="{cls}">{_STAGE_CHIP_LABELS[key]}</span>')
    return "".join(chips)


def _paint_stage(box, key: str, visible: list[str]) -> None:
    """Paint the audit-in-progress card (spinner + stage text + chips) into an
    st.empty() container — live-updating, so each stage lights up as it runs."""
    label, sub = _STAGE_INFO[key]
    if key == "done":
        spinner = ""
        label_html = f'<div class="mg-stage-label" style="color:#1a7f37;">{label}</div>'
    else:
        spinner = '<div class="mg-scan"><div class="ring"></div></div>'
        label_html = f'<div class="mg-stage-label">{label}</div>'
    box.markdown(
        f"""
<div class="mg-stage-line">{spinner}{label_html}</div>
<div class="mg-stage-sub" style="margin:-6px 0 10px 54px;">{sub}</div>
<div class="mg-progress">{_stage_chips(key, visible)}</div>
""",
        unsafe_allow_html=True,
    )


def _audit_cache_key(question: str, source: str, answer: str, checker: str,
                     thorough: bool, api_key: str | None) -> str:
    h = hashlib.sha1()
    for part in (question, source, answer, checker, str(thorough), api_key or ""):
        h.update(part.encode("utf-8", "ignore"))
        h.update(b"\x1f")
    return h.hexdigest()


def _run_staged_audit(question: str, source: str, answer: str, checker: str,
                      thorough: bool, api_key: str | None = None) -> dict:
    """Run the audit in a background thread while painting live stage updates.

    run_audit reports each pipeline phase as it starts (via the progress
    callback); those events flow through a queue to this thread, which repaints
    the stage card — so chips 1, 2, 3 genuinely light up as the work happens.
    Identical re-audits within the session hit the memo and cost ZERO API calls.
    """
    ck = _audit_cache_key(question, source, answer, checker, thorough, api_key)
    memo = st.session_state.setdefault("mg_audit_cache", {})
    if ck in memo:
        return memo[ck]

    # Only the stages this mode can actually run get a chip — Fast mode (or
    # checker "none") never pretends a step happened that was skipped.
    visible = ["extract", "verify"]
    if thorough:
        visible.append("holistic")
    if checker and checker.lower() != "none":
        visible.append("crosscheck")

    events: queue.Queue = queue.Queue()

    def worker() -> None:
        try:
            events.put(("stage", "extract"))
            result = run_audit(
                question=question, source=source, answer=answer,
                crosschecker=checker, thorough=thorough, api_key=api_key,
                progress=lambda key: events.put(("stage", key)),
            )
            events.put(("result", result))
        except Exception as err:  # noqa: BLE001 — surfaced to the UI thread
            events.put(("error", err))

    t = threading.Thread(target=worker, daemon=True)
    t.start()

    box = st.empty()
    active = "extract"
    _paint_stage(box, active, visible)
    result = None
    error = None
    while True:
        try:
            kind, payload = events.get(timeout=0.4)
            if kind == "stage":
                active = payload
                _paint_stage(box, active, visible)
            elif kind == "result":
                result = payload
                break
            else:  # "error"
                error = payload
                break
        except queue.Empty:
            if not t.is_alive():
                # Drain any final events the worker queued just before exiting.
                while True:
                    try:
                        kind, payload = events.get_nowait()
                    except queue.Empty:
                        break
                    if kind == "result":
                        result = payload
                    elif kind == "error":
                        error = payload
                break
            _paint_stage(box, active, visible)  # keep the animation alive between stages

    if error is not None:
        raise error
    if result is None:
        raise RuntimeError("The audit stopped before completing. Please press Audit again.")
    _paint_stage(box, "done", visible)

    if len(memo) >= 16:
        memo.pop(next(iter(memo)))  # drop the oldest entry
    memo[ck] = result
    return result




# ---------------------------------------------------------------------------
# Run + render
# ---------------------------------------------------------------------------
if run_clicked:
    if not question.strip() or not answer.strip():
        st.warning("Type the question and paste the AI answer you want audited.")
        st.stop()

    # --- Auto-pick the guideline from the built-in library if none provided ---
    used_source_name = None
    match = None
    if not source.strip():
        match, score = match_source(question)
        if match is None:
            st.warning(
                "We couldn't find a guideline for this topic in our built-in library, "
                "so we can't honestly audit this answer — guessing would be dangerous. "
                "Paste the official guideline text in the guideline box and try again."
            )
            verdict_preview = compute_unverifiable()
            render_verdict(verdict_preview["verdict"], verdict_preview["coverage"], verdict_preview["reason"])
            st.stop()
        source = match["text"]
        used_source_name = match.get("source_name", "our built-in guideline library")
        st.info(
            f"No guideline was pasted, so we used our built-in guideline on "
            f"**{match['topic']}** — *Source: {used_source_name}* "
            f"(a simplified public-health summary, not a verbatim official document)"
        )

    thorough_mode = audit_mode == "Thorough (full audit)"
    try:
        result = _run_staged_audit(
            question, source, answer, checker_clean, thorough_mode,
            api_key=manual_key or None,
        )
    except Exception as err:
        from medguard.audit import RateLimitError  # noqa: PLC0415

        if isinstance(err, RateLimitError):
            st.warning(
                "Groq's free tier needs a short breather (rate limit). "
                "Wait about a minute and press **Audit this answer** again — "
                "nothing is broken."
            )
        else:
            st.error(f"Audit failed: {err}")
        st.stop()

    # --- history (last 5 audits, viewable without re-running) ---
    hist = st.session_state.get("mg_history", [])
    hist.insert(0, {
        "q": question, "source": source, "answer": answer,
        "checker": checker_clean, "thorough": thorough_mode,
        "result": result, "source_name": used_source_name,
    })
    st.session_state["mg_history"] = hist[:5]

    render_verdict(result["verdict"], result["coverage"], result["reason"])
    st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)

    if used_source_name:
        st.markdown(
            f'<div class="mg-card" style="padding:10px 16px;">'
            f'Guideline used for this check: <b>{used_source_name}</b> — {match["topic"]}</div>',
            unsafe_allow_html=True,
        )

    left, right = st.columns([1.25, 1])
    with left:
        render_claims(result["claims"])
    with right:
        render_source_panel(result["source"], result["claims"], source_name=used_source_name)

    if result.get("crosscheck_score") is not None:
        pct = max(0.0, min(1.0, float(result["crosscheck_score"]))) * 100
        with st.expander("Second opinion (independent AI checker)"):
            st.markdown(
                f"""
                <div class="mg-card">
                  <div style="display:flex; justify-content:space-between; align-items:baseline;">
                    <div style="color:#6b7a8d;">{result["crosscheck_checker"].upper()} agreement score</div>
                    <div style="font-weight:700; font-size:1.5rem; color:#0066cc;">{pct:.0f}%</div>
                  </div>
                  <div class="v-sub" style="margin-top:8px;">A second, independent checker
                  (a different kind of AI — not the one that judged above) was also asked
                  whether the answer follows the guideline. Higher = more agreement.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    with st.expander("Technical details (for engineers)"):
        st.caption(f"Trust score: {result['coverage']}% of the answer's claims were backed by the guideline.")
        st.json(json.dumps(result, indent=2, ensure_ascii=False))

# ---------------------------------------------------------------------------
# Classroom demo — run + render (Bot vs Bot)
# ---------------------------------------------------------------------------
if battle_clicked and demo_q:
    with st.spinner("Running the classroom demo — both bots answer, then both get graded…"):
        try:
            battle = _run_bot_battle(demo_q, manual_key or None)
        except RateLimitError:
            st.warning(
                "Groq's free tier needs a short breather (rate limit). The demo uses several "
                "calls in a row — wait about a minute and press **Run the classroom demo** again."
            )
            battle = None
        except LookupError as err:
            st.warning(str(err))
            battle = None
        except Exception as err:  # noqa: BLE001
            st.error(f"Classroom demo failed: {err}")
            battle = None

    if battle:
        # log both students into history, labeled
        _bh = st.session_state.get("mg_history", [])
        for who, ans, res in (("naive bot", battle["naive"], battle["naive_result"]),
                              ("RAG bot", battle["rag"], battle["rag_result"])):
            _bh.insert(0, {
                "q": f"{who} · {demo_q}", "source": battle["naive_result"]["source"],
                "answer": ans, "checker": "none", "thorough": True,
                "result": res, "source_name": battle["source_name"],
            })
        st.session_state["mg_history"] = _bh[:5]

        st.markdown(
            f'<div class="mg-card" style="padding:10px 16px; margin-top:8px;">'
            f"Textbook page used to grade both students: <b>{battle['topic']}</b> — "
            f"{battle['source_name']}</div>",
            unsafe_allow_html=True,
        )
        naive_v = battle["naive_result"]
        rag_v = battle["rag_result"]
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### The naive bot — answered from memory")
            st.caption("No textbook. Typical health-chatbot behavior: confident and specific.")
            with st.expander("What it answered", expanded=True):
                st.markdown(f"> {battle['naive'][:800]}")
            render_verdict(naive_v["verdict"], naive_v["coverage"], naive_v["reason"])
        with col2:
            st.markdown("#### The RAG bot — answered from the guideline")
            st.caption(f"Read the '{battle['topic']}' page first, then answered using only it.")
            with st.expander("What it answered", expanded=True):
                st.markdown(f"> {battle['rag'][:800]}")
            if battle.get("rag_abstained"):
                st.markdown(
                    """
                    <div class="mg-card" style="padding:14px 18px;">
                      <div style="font-weight:700; font-size:1.05rem; color:#1a7f37;">
                        THE RAG BOT DECLINED TO ANSWER — the honest move</div>
                      <div style="color:#6b7a8d; margin-top:6px; font-size:.92rem;">
                        The guideline page doesn't answer this question, so the grounded bot
                        refused instead of guessing. (The judge technically flags the refusal
                        sentence — "the source does talk about this topic" — but refusing
                        beats inventing.) This is exactly why retrieval matters.</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                render_verdict(rag_v["verdict"], rag_v["coverage"], rag_v["reason"])

        st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)
        st.info(
            "**The lesson:** both students were graded by the same examiner against the same page. "
            "The naive bot's answer may even sound more helpful — it gives doses and details the "
            "guideline never states, which is exactly what the auditor flags: **unverified is not "
            "verified**, even when it happens to be true."
        )

# ---------------------------------------------------------------------------
# History — last 5 audits, viewable without re-running.
# NOTE: flat siblings only — expanders must never be nested inside another
# expander; newer Streamlit versions raise an exception on nesting.
# ---------------------------------------------------------------------------
hist = st.session_state.get("mg_history", [])
if hist:
    st.markdown(
        f'<div class="mg-card" style="padding:10px 16px; margin-top:8px;">'
        f"<b>Recent audits</b> ({len(hist)}) — click one to view it without re-running</div>",
        unsafe_allow_html=True,
    )
    for i, h in enumerate(hist):
        v = h["result"]["verdict"]
        label = (h["q"][:55] + "…") if len(h["q"]) > 55 else h["q"]
        with st.expander(f"{label} — {v}", expanded=(i == 0)):
            r = h["result"]
            st.markdown(f"**Verdict:** {v} · **Trust score:** {r['coverage']}%")
            st.caption(r["reason"][:300])
            st.caption(f"Audited with: {h['checker'] if h['checker'] != 'none' else 'judge only'} · "
                       f"{'Thorough' if h['thorough'] else 'Fast'} mode")
            for c in r["claims"][:4]:
                st.markdown(f"- **{c['status']}** — {c['claim'][:90]}")
# ---------------------------------------------------------------------------
# Empty state — before the first audit
# ---------------------------------------------------------------------------
if not run_clicked and not st.session_state.get("mg_history"):
    st.markdown(
        """
        <div class="mg-card" style="text-align:center; padding:34px 26px; margin-top:8px;">
          <div style="font-weight:700; font-size:1.25rem; color:#2c3e50; margin-top:6px;">
            Ready when you are
          </div>
          <div style="color:#6b7a8d; margin-top:8px; font-size:.95rem;">
            Paste a question + an AI answer above (or pick an example in the sidebar),
            then press <b style="color:#0066cc;">Audit this answer</b>.<br>
            Every claim gets checked against an official guideline — and you'll see
            exactly which guideline said what.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown(
    '<div class="mg-footer">MedGuard is an AI evaluation tool for educational purposes. '
    "It does not provide medical advice and does not replace professional clinical "
    "judgment or official guidelines.</div>",
    unsafe_allow_html=True,
)
