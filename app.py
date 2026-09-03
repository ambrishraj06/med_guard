"""
MedGuard — app.py
=================
The Streamlit face of the clinical RAG hallucination auditor.

Design language (locked decision D10):
  - Deep-navy dark theme, glassmorphism verdict cards, medical-teal accent
  - Verdict card + per-claim status chips + verbatim evidence blockquotes
  - "What the source says" side-by-side panel (verbatim quotes ONLY — never
    generated medical advice, decision D18)
  - Optional independent cross-check score (HHEM / MiniCheck / none)
  - Golden test case prefilled so the first click always demos perfectly
  - Medical disclaimer always visible

Run:  streamlit run app.py
"""

import json
import sys
import traceback
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Diagnostic trap: show the REAL import error on the page instead of
# Streamlit's redacted "ImportError" card, so failures are debuggable in prod.
try:
    from medguard.audit import DEFAULT_JUDGE_MODEL, run_audit  # noqa: E402
    from medguard.crosscheck import available_checkers  # noqa: E402
    from medguard.library import match_source  # noqa: E402
except Exception:
    st.set_page_config(page_title="MedGuard — startup error", page_icon="🛡️", layout="wide")
    st.error("MedGuard failed to import its engine. Real error below:")
    st.code(traceback.format_exc(), language="python")
    st.stop()

# ---------------------------------------------------------------------------
# Page + golden case
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="MedGuard — Clinical RAG Hallucination Auditor",
    page_icon="🛡️",
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

VERDICT_STYLES = {
    "BLOCKED": ("#FF4757", "🚫", "AUDIT FAILED — DON'T TRUST IT", "This answer goes against the medical guideline. Following it could be dangerous."),
    "SAFE": ("#2ED573", "✅", "AUDIT PASSED — TRUSTED", "This answer matches the medical guideline."),
    "WARNING": ("#FFA502", "⚠️", "AUDIT FLAGGED — PARTLY TRUSTED", "Some parts are fine, but the flagged parts below are NOT from the guideline."),
    "UNVERIFIABLE": ("#747D8C", "❔", "CAN'T AUDIT — NO GUIDELINE FOUND", "We couldn't find a guideline for this. Paste a source (or try a common topic) and audit again."),
}

CHIP_STYLES = {
    "SUPPORTED": ("#2ED573", "✅", "BACKED BY THE GUIDELINE"),
    "UNSUPPORTED": ("#FFA502", "❔", "NOT IN THE GUIDELINE"),
    "CONTRADICTION": ("#FF4757", "🚫", "GOES AGAINST THE GUIDELINE"),
}

# ---------------------------------------------------------------------------
# CSS — the "premium SaaS" layer (glassmorphism, animations, fonts)
# ---------------------------------------------------------------------------
st.markdown(
    """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&family=Outfit:wght@600;800&display=swap" rel="stylesheet">

<style>
  /* ---------- base ---------- */
  html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
  h1, h2, h3 { font-family: 'Outfit', 'Inter', sans-serif !important; letter-spacing: .3px; }
  #MainMenu, footer, header { visibility: hidden; }
  .stApp { background:
      radial-gradient(1100px 500px at 85% -10%, rgba(0,212,170,.10), transparent 60%),
      radial-gradient(900px 420px at -10% 110%, rgba(94,120,255,.08), transparent 60%),
      #0A0E1A; }

  /* ---------- header ---------- */
  .mg-header { display:flex; align-items:center; gap:16px; padding: 18px 6px 2px 6px; }
  .mg-logo { font-family:'Outfit'; font-size: 2.1rem; font-weight:800;
      background: linear-gradient(90deg, #E2E8F0, #00D4AA);
      -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; }
  .mg-logo .shield { filter: drop-shadow(0 0 12px rgba(0,212,170,.55)); }
  .mg-tag { color:#8B95A9; font-size:.95rem; margin-top:2px; }
  .mg-rule { height:1px; margin:14px 0 18px 0;
      background: linear-gradient(90deg, rgba(0,212,170,.7), rgba(0,212,170,.06), transparent); }

  /* ---------- glass card ---------- */
  .mg-card { background: rgba(20,27,45,.62); backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      border: 1px solid rgba(226,232,240,.08); border-radius: 18px;
      padding: 20px 22px; box-shadow: 0 8px 32px rgba(0,0,0,.25); }

  /* ---------- verdict card ---------- */
  .mg-verdict { animation: mgIn .55s ease both; border-radius: 20px; padding: 26px 28px;
      border: 1px solid rgba(226,232,240,.10); position: relative; overflow: hidden;
      background: rgba(20,27,45,.66); backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      box-shadow: 0 12px 40px rgba(0,0,0,.35); }
  .mg-verdict .v-label { font-family:'Outfit'; font-weight:800; font-size:2.3rem;
      letter-spacing:1px; display:flex; align-items:center; gap:14px; }
  .mg-verdict .v-sub { color:#AEB7C8; margin-top:8px; font-size:1.02rem; }
  .mg-verdict .v-glow { position:absolute; inset:auto -30% -70% -30%; height:140px;
      border-radius:50%; filter: blur(60px); opacity:.35; }
  .mg-pulse { animation: mgPulse 1.8s ease-in-out infinite; }
  @keyframes mgPulse { 0%,100% { opacity:.28 } 50% { opacity:.55 } }
  @keyframes mgIn { from { opacity:0; transform: translateY(14px); }
                    to   { opacity:1; transform: translateY(0); } }

  /* ---------- primary button premium ---------- */
  .stButton > button[kind="primary"] { border-radius: 14px !important;
      font-weight:700; letter-spacing:.3px;
      box-shadow: 0 4px 24px rgba(0,212,170,.35);
      transition: transform .15s ease, box-shadow .15s ease !important; }
  .stButton > button[kind="primary"]:hover { transform: translateY(-1px);
      box-shadow: 0 8px 32px rgba(0,212,170,.5) !important; }
  .mg-meter { height:10px; border-radius:6px; background:rgba(226,232,240,.08);
      overflow:hidden; margin-top:16px; }
  .mg-meter > div { height:100%; border-radius:6px;
      background: linear-gradient(90deg, #00D4AA, #7BF1D9); }

  /* ---------- claim chips + rows ---------- */
  .mg-chip { display:inline-flex; align-items:center; gap:7px; padding:4px 12px;
      border-radius:999px; font-size:.78rem; font-weight:700; letter-spacing:.6px;
      color:#0A0E1A; transition: transform .15s ease, box-shadow .15s ease; }
  .mg-chip:hover { transform: translateY(-1px); box-shadow: 0 4px 14px rgba(0,0,0,.35); }
  .mg-claim { border-left:3px solid rgba(226,232,240,.12); padding:10px 14px;
      margin:10px 0; border-radius:0 12px 12px 0; background:rgba(20,27,45,.5); }
  .mg-claim .c-text { color:#E2E8F0; font-size:.98rem; }
  .mg-claim .c-why { color:#9AA4B8; font-size:.85rem; margin-top:5px; }
  .mg-quote { border-left:3px solid #00D4AA; background:rgba(0,212,170,.06);
      padding:10px 14px; border-radius:0 10px 10px 0; }
  .mg-quote, .mg-quote * { color:#CFF5EC !important; font-style:italic; }

  /* ---------- side-by-side source panel ---------- */
  .mg-duo { display:grid; grid-template-columns: 1fr 1fr; gap:14px; }
  .mg-duo .head { font-family:'Outfit'; font-weight:700; letter-spacing:.8px;
      font-size:.85rem; margin-bottom:8px; }
  .mg-duo .claimed { color:#FF8A93; }
  .mg-duo .sourced { color:#7BF1D9; }

  /* ---------- footer ---------- */
  .mg-footer { color:#68738A; font-size:.82rem; text-align:center; padding:26px 0 10px 0; }

  /* ---------- mobile ---------- */
  @media (max-width: 760px) {
    .mg-duo { grid-template-columns: 1fr !important; }
    .mg-header { flex-direction: column; gap: 4px; }
    .mg-logo { font-size: 1.6rem; }
    .mg-verdict { padding: 20px 18px; }
    .mg-verdict .v-label { font-size: 1.6rem; }
    .mg-card { padding: 16px 14px; }
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
            <div class="mg-logo"><span class="shield">🛡️</span> MedGuard</div>
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
    color, icon, label, advice = VERDICT_STYLES.get(verdict, VERDICT_STYLES["UNVERIFIABLE"])
    pulse = "mg-pulse" if verdict == "BLOCKED" else ""
    st.markdown(
        f"""
        <div class="mg-verdict">
          <div class="v-glow {pulse}" style="background:{color};"></div>
          <div class="v-label" style="color:{color};">{icon} {label}</div>
          <div class="v-sub" style="color:{color}; font-weight:600;">{advice}</div>
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
        color, icon, label = CHIP_STYLES.get(c["status"], CHIP_STYLES["UNSUPPORTED"])
        evidence_html = ""
        if c.get("evidence"):
            evidence_html = (
                f'<div class="mg-quote" style="margin-top:8px;"><b>From the guideline:</b> “{c["evidence"]}”</div>'
            )
        why = c.get("reasoning") or ""
        cc = c.get("crosscheck_score")
        cc_html = (
            f'<div class="c-why" style="margin-top:4px;">🔬 Independent checker: <b>{int(cc*100)}%</b> support</div>'
            if cc is not None else ""
        )
        disagree = c.get("disagreement")
        disagree_html = (
            f'<div class="c-why" style="margin-top:4px;color:#FFA502;">⚖️ {disagree}</div>'
            if disagree else ""
        )
        st.markdown(
            f"""
            <div class="mg-claim">
              <span class="mg-chip" style="background:{color};">{icon} {label}</span>
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
            '<div class="mg-card">✅ Everything in the answer traces back to the guideline.</div>',
            unsafe_allow_html=True,
        )
        return
    rows = ""
    for c in failed:
        quote = c.get("evidence") or _best_matching_sentence(source, c["claim"]) or "(nothing in the guideline talks about this — the answer made it up or brought it in from outside)"
        rows += f"""
        <div class="mg-duo mg-claim" style="border-left-color:{VERDICT_STYLES['BLOCKED'][0] if c['status']=='CONTRADICTION' else VERDICT_STYLES['WARNING'][0]};">
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
    "🔴 Dangerous answer caught (UTI antibiotic)": {
        "q": "What is the first-line antibiotic for uncomplicated UTI in pregnant women?",
        "s": (
            "For uncomplicated cystitis in pregnant women, nitrofurantoin or cephalexin are "
            "recommended. Fluoroquinolones such as ciprofloxacin are contraindicated because of "
            "fetal cartilage risk."
        ),
        "a": "The first-line treatment is ciprofloxacin 500 mg twice daily for 3 days. Amoxicillin is also safe.",
    },
    "🟢 Honest answer passes": {
        "q": "What is the first-line antibiotic for uncomplicated UTI in pregnant women?",
        "s": (
            "For uncomplicated cystitis in pregnant women, nitrofurantoin or cephalexin are "
            "recommended. Fluoroquinolones such as ciprofloxacin are contraindicated because of "
            "fetal cartilage risk."
        ),
        "a": "For uncomplicated cystitis in pregnant women, nitrofurantoin or cephalexin are recommended as first-line antibiotics.",
    },
    "🔴 Dengue: wrong painkiller (WHO / ICMR)": {
        "q": "I have dengue fever with body aches. What painkiller should I take?",
        "s": (
            "Dengue is a mosquito-borne viral infection. There is no specific antiviral medicine; "
            "treatment is supportive — rest, plenty of fluids, and paracetamol for fever and pain. "
            "NSAIDs such as aspirin or ibuprofen must be avoided because they increase the risk of bleeding."
        ),
        "a": "Ibuprofen 400 mg three times a day is effective for dengue fever aches.",
    },
    "🔴 Warfarin: hidden drug interaction": {
        "q": "I take warfarin for my heart. I have a bad thrush infection — what medicine should I use?",
        "s": (
            "Fluconazole is an effective treatment for thrush. However, fluconazole must not be "
            "combined with warfarin — the combination causes a severe bleeding risk and is "
            "contraindicated. Miconazole gel is a safer alternative for patients taking warfarin."
        ),
        "a": "Fluconazole is a good option for treating your thrush.",
    },
    "🟡 Half-true answer (partly safe)": {
        "q": "What lifestyle changes are recommended for a patient with newly diagnosed high blood pressure?",
        "s": (
            "Adults with newly diagnosed hypertension should be advised to reduce salt intake to less "
            "than 5 g per day and to engage in at least 150 minutes of moderate-intensity aerobic exercise "
            "per week. Weight loss is recommended for patients who are overweight."
        ),
        "a": "Patients should reduce salt intake to less than 5 g per day and exercise for at least 150 minutes weekly. They should also take potassium supplements daily and completely avoid all fruits.",
    },
    "🔴 Invented study (classic AI lie)": {
        "q": "Does vitamin C prevent the common cold?",
        "s": (
            "Regular vitamin C supplementation has not been shown to prevent the common cold in the "
            "general population, though it may slightly reduce the duration of symptoms."
        ),
        "a": "Yes. According to the 2023 Harrison medical trial, taking 2000 mg of vitamin C daily prevents the common cold in 87% of people.",
    },
    "❓ Unknown disease (honest CAN'T CHECK)": {
        "q": "What is the recommended management for Zellweger spectrum disorder?",
        "s": "",
        "a": "Zellweger spectrum disorder is managed by a team of specialists.",
    },
}

with st.sidebar:
    st.markdown(
        """
        <div style="padding:2px 2px 10px 2px;">
          <div style="font-family:'Outfit';font-size:1.6rem;font-weight:800;color:#E2E8F0;">🛡️ MedGuard</div>
          <div style="color:#8B95A9;font-size:.85rem;margin-top:2px;">Can you trust that AI health answer?</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("❓ How to use this app"):
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
        "🧪 Try an example",
        list(TEST_CASES.keys()),
    )

    st.markdown("**Audit depth**")
    audit_mode = st.radio(
        "Choose how deep the audit goes",
        ["🔍 Thorough (full audit)", "⚡ Fast (skip final review)"],
        index=0,
        label_visibility="collapsed",
        help="Thorough adds a third whole-answer safety review — best for demos and real checks. Fast skips it for speed.",
    )

    with st.expander("⚙️ Advanced settings (for engineers)"):
        key_status = "🟢 key loaded from secrets/env"
        try:
            import streamlit as st_secret_check  # noqa: PLC0415

            _ = st_secret_check.secrets["GROQ_API_KEY"]
        except Exception:
            key_status = (
                "🟡 no key found — paste one below "
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

# Sidebar preset → fill the three boxes (canonical state path + rerun)
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
    "❓ The question that was asked",
    key="mg_question",
    height=68,
)
source = st.text_area(
    "📖 Guideline text (optional — leave empty and we auto-pick from our library)",
    key="mg_source",
    height=110,
    help="Paste the official guideline here for the most accurate check. If you leave it empty, we'll try to find a matching topic in our built-in library of 69 medical guideline summaries.",
)
answer = st.text_area(
    "🤖 The AI answer you want checked",
    key="mg_answer",
    height=110,
    help="Paste the AI's answer here — MedGuard only checks answers, it never writes its own.",
)

if not source.strip():
    st.caption(
        "💡 Paste the official guideline for better accuracy — otherwise we'll auto-pick "
        "a matching topic from our built-in library (WHO / CDC / NICE / ICMR and more)."
    )

run_clicked = st.button(
    "🛡️  Audit this answer",
    use_container_width=True,
    type="primary",
)

# ---------------------------------------------------------------------------
# Staged audit runner — staged progress + Fast/Thorough toggle + caching
# ---------------------------------------------------------------------------
st.markdown(
    """
<style>
  .mg-progress { display:flex; gap:8px; flex-wrap:wrap; margin:6px 0 10px 0; }
  .mg-progress span { font-size:.8rem; color:#8B95A9; padding:4px 10px;
      border-radius:999px; border:1px solid rgba(226,232,240,.15); }
  .mg-progress span.on { color:#0A0E1A; background:#00D4AA; border-color:#00D4AA; font-weight:700; }
</style>
""",
    unsafe_allow_html=True,
)


def _progress_stage(active: str) -> None:
    stages = ["1 · Reading claims", "2 · Verifying against guideline", "3 · Final safety review"]
    idx = stages.index(active) if active in stages else 0
    chips = "".join(
        f'<span class="{"on" if i <= idx else ""}">{s}</span>' for i, s in enumerate(stages)
    )
    st.markdown(f'<div class="mg-progress">{chips}</div>', unsafe_allow_html=True)


@st.cache_data(show_spinner=False, max_entries=64)
def _cached_audit(question: str, source: str, answer: str, checker: str, thorough: bool) -> dict:
    """Cache wrapper: identical re-audits cost ZERO API calls. The pipeline
    itself is the same run_audit — staging happens in _run_staged_audit below."""
    return run_audit(
        question=question, source=source, answer=answer,
        crosschecker=checker, thorough=thorough,
    )


def _run_staged_audit(question: str, source: str, answer: str, checker: str, thorough: bool) -> dict:
    """Runs the audit with visible stages. Calls the cached wrapper so an
    identical repeat returns instantly (demo-friendly)."""
    try:
        _progress_stage("1 · Reading claims")
        return _cached_audit(question, source, answer, checker, thorough)
    except Exception as err:
        raise err


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
                "Paste the official guideline text in the 📖 box and try again."
            )
            verdict_preview = compute_unverifiable()
            render_verdict(verdict_preview["verdict"], verdict_preview["coverage"], verdict_preview["reason"])
            st.stop()
        source = match["text"]
        used_source_name = match.get("source_name", "our built-in guideline library")
        st.info(
            f"📖 No guideline was pasted, so we used our built-in guideline on "
            f"**{match['topic']}** — *Source: {used_source_name}* "
            f"(a simplified public-health summary, not a verbatim official document)"
        )

    thorough_mode = audit_mode == "🔍 Thorough (full audit)"
    try:
        result = _run_staged_audit(
            question, source, answer, checker_clean, thorough_mode
        )
    except Exception as err:
        from medguard.audit import RateLimitError  # noqa: PLC0415

        if isinstance(err, RateLimitError):
            st.warning(
                "⏳ Groq's free tier needs a short breather (rate limit). "
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
            f'<div class="mg-card" style="padding:10px 16px;">📚 '
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
        with st.expander("🔬 Second opinion (independent AI checker)"):
            st.markdown(
                f"""
                <div class="mg-card">
                  <div style="display:flex; justify-content:space-between; align-items:baseline;">
                    <div style="color:#AEB7C8;">{result["crosscheck_checker"].upper()} agreement score</div>
                    <div style="font-family:'Outfit'; font-weight:800; font-size:1.5rem; color:#00D4AA;">{pct:.0f}%</div>
                  </div>
                  <div class="v-sub" style="margin-top:8px;">A second, independent checker
                  (a different kind of AI — not the one that judged above) was also asked
                  whether the answer follows the guideline. Higher = more agreement.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    with st.expander("🔧 Technical details (for engineers)"):
        st.caption(f"Trust score: {result['coverage']}% of the answer's claims were backed by the guideline.")
        st.json(json.dumps(result, indent=2, ensure_ascii=False))

# ---------------------------------------------------------------------------
# History — last 5 audits, viewable without re-running.
# NOTE: flat siblings only — expanders must never be nested inside another
# expander; newer Streamlit versions raise an exception on nesting.
# ---------------------------------------------------------------------------
hist = st.session_state.get("mg_history", [])
if hist:
    st.markdown(
        f'<div class="mg-card" style="padding:10px 16px; margin-top:8px;">🕘 '
        f"<b>Recent audits</b> ({len(hist)}) — click one to view it without re-running</div>",
        unsafe_allow_html=True,
    )
    for i, h in enumerate(hist):
        v = h["result"]["verdict"]
        icon = {"BLOCKED": "🔴", "SAFE": "🟢", "WARNING": "🟡", "UNVERIFIABLE": "⚪"}.get(v, "⚪")
        label = (h["q"][:55] + "…") if len(h["q"]) > 55 else h["q"]
        with st.expander(f"{icon} {label} — {v}", expanded=(i == 0)):
            r = h["result"]
            st.markdown(f"**Verdict:** {v} · **Trust score:** {r['coverage']}%")
            st.caption(r["reason"][:300])
            st.caption(f"Audited with: {h['checker'] if h['checker'] != 'none' else 'judge only'} · "
                       f"{'Thorough' if h['thorough'] else 'Fast'} mode")
            for c in r["claims"][:4]:
                st.markdown(f"- `{'✅' if c['status']=='SUPPORTED' else '❔' if c['status']=='UNSUPPORTED' else '🚫'}` {c['claim'][:90]}")
# ---------------------------------------------------------------------------
# Empty state — before the first audit
# ---------------------------------------------------------------------------
if not run_clicked and not st.session_state.get("mg_history"):
    st.markdown(
        """
        <div class="mg-card" style="text-align:center; padding:34px 26px; margin-top:8px;">
          <div style="font-size:2.4rem;">🛡️</div>
          <div style="font-family:'Outfit'; font-weight:800; font-size:1.25rem; color:#E2E8F0; margin-top:6px;">
            Ready when you are
          </div>
          <div style="color:#8B95A9; margin-top:8px; font-size:.95rem;">
            Paste a question + an AI answer above (or pick a 🧪 example in the sidebar),
            then press <b style="color:#00D4AA;">Audit this answer</b>.<br>
            Every claim gets checked against an official guideline — and you'll see
            exactly which guideline said what.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown(
    '<div class="mg-footer">🛡️ MedGuard is an AI evaluation tool for educational purposes. '
    "It does not provide medical advice and does not replace professional clinical "
    "judgment or official guidelines.</div>",
    unsafe_allow_html=True,
)
