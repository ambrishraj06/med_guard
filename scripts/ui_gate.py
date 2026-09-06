"""UI gate for the clinical revamp — run before every deploy.

Checks, in order:
  1. Static scan: app.py contains ZERO emoji codepoints (any block that can
     render as a colorful glyph) and no dark-theme color leftovers.
  2. AppTest boot: app starts, new labels present, no emoji in any rendered
     widget string.
  3. Real-API audit on the golden case -> must land BLOCKED ("AUDIT FAILED").
  4. Real-API classroom battle (warfarin case) -> both bots produce verdicts.

Uses the real Groq key from .streamlit/secrets.toml or GROQ_API_KEY (this is a
LIVE gate — it costs free-tier API calls on purpose; never claim it works
without running it). Rate-limited? Wait a minute and re-run.

Usage:  venv/Scripts/python scripts/ui_gate.py
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

EMOJI_RE = re.compile(
    "["
    "\U0001F000-\U0001FAFF"  # emoji pictographs (incl. flags)
    "\U00002600-\U000027BF"  # misc symbols + dingbats (incl. check marks)
    "\U00002300-\U000023FF"  # misc technical (hourglass/clock)
    "\U00002B00-\U00002BFF"  # stars/arrows-as-emoji
    "\U00002190-\U000021FF"  # arrows
    "\U000025A0-\U000025FF"  # geometric shapes
    "\U0000FE0F"             # emoji variation selector
    "\U000020E3"             # combining keycap
    "]"
)
LEGACY_RE = re.compile(
    r"Outfit|Inter|00D4AA|7BF1D9|0A0E1A|E2E8F0|8B95A9|AEB7C8|CFF5EC|FF8A93"
    r"|FFA502|2ED573|FF4757|linear-gradient|radial-gradient|backdrop-filter"
    r"|drop-shadow|translateY"
)

fails: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"{'PASS' if cond else 'FAIL'}  {name}{('  — ' + detail) if detail and not cond else ''}")
    if not cond:
        fails.append(name)


# ---------------------------------------------------------------------------
# 1. Static scans on app.py
# ---------------------------------------------------------------------------
src = (ROOT / "app.py").read_text(encoding="utf-8")
static_emoji = [f"line {src[:m.start()].count(chr(10)) + 1}: {m.group()!r}"
                for m in EMOJI_RE.finditer(src)]
check("static: zero emoji codepoints in app.py", not static_emoji, "; ".join(static_emoji[:5]))
legacy = [f"line {src[:m.start()].count(chr(10)) + 1}: {m.group()!r}"
          for m in LEGACY_RE.finditer(src)]
check("static: no dark-theme/gradient/blur leftovers", not legacy, "; ".join(legacy[:5]))

# ---------------------------------------------------------------------------
# 2. AppTest boot + label/emoji assertions
# ---------------------------------------------------------------------------
from streamlit.testing.v1 import AppTest  # noqa: E402

at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=300)
at.run()
check("boot: no exception", not at.exception,
      str(at.exception[0].value)[:300] if at.exception else "")

btn_labels = [b.label for b in at.button]
check("labels: audit button is 'Audit this answer'", "Audit this answer" in btn_labels)
check("labels: battle button is 'Run the classroom demo'",
      "Run the classroom demo" in btn_labels)

# Two radios now: [0]=Theme (Light/Dark), [1]=Audit depth.
check("labels: theme selector present",
      bool(at.radio) and "Light" in (at.radio[0].options or []) and "Dark" in (at.radio[0].options),
      str([r.options for r in at.radio]))
depth = at.radio[-1] if len(at.radio) > 1 else None
check("labels: audit-depth options de-emojified",
      depth is not None and list(depth.options) == ["Thorough (full audit)", "Fast (skip final review)"],
      str([r.options for r in at.radio]))

texts: list[str] = []
for md in at.markdown:
    texts.append(md.value or "")
for kind in ("caption", "info", "warning", "error", "title", "header"):
    for el in getattr(at, kind):
        texts.append(el.value or "")
for el in at.button:
    texts.append(el.label or "")
for el in at.selectbox:
    texts.append((el.label or "") + " | " + " | ".join(str(o) for o in (el.options or [])))
for el in at.radio:
    texts.append((el.label or "") + " | " + " | ".join(str(o) for o in (el.options or [])))
for el in at.text_area:
    texts.append(el.label or "")
for el in at.text_input:
    texts.append(el.label or "")
ui_emoji = sorted({m.group() for t in texts for m in EMOJI_RE.finditer(t)})
check("boot UI: zero emoji in any rendered string", not ui_emoji, str(ui_emoji))

check("boot UI: golden case prefilled",
      sum(1 for ta in at.text_area if ta.value and ta.value.strip()) == 3)

# ---------------------------------------------------------------------------
# 2b. Theme modes — selector switches the palette tokens, no exceptions
# ---------------------------------------------------------------------------
theme_radio = at.radio[0] if (at.radio and "Dark" in (at.radio[0].options or [])) else None
if theme_radio is not None:
    theme_radio.set_value("Dark")
    at.run()
    css_dark = "\n".join((m.value or "") for m in at.markdown)
    check("theme: Dark mode injects dark palette",
          "--bg: #0d131a" in css_dark and "--surface: #151e29" in css_dark)
    check("theme: no exception in Dark mode", not at.exception,
          str(at.exception[0].value)[:300] if at.exception else "")
    if at.radio and "Light" in (at.radio[0].options or []):
        at.radio[0].set_value("Light")
        at.run()
    css_light = "\n".join((m.value or "") for m in at.markdown)
    check("theme: Light mode restores light palette", "--bg: #fafbfc" in css_light)
    check("theme: no exception after switching back", not at.exception,
          str(at.exception[0].value)[:300] if at.exception else "")

# ---------------------------------------------------------------------------
# 3. Real audit on the golden case (checker=none for Cloud parity, Thorough)
# ---------------------------------------------------------------------------
sel_labels = [s.label for s in at.selectbox]
checker_idx = next((i for i, l in enumerate(sel_labels) if l == "Second opinion"), None)
if checker_idx is not None and "none" in (at.selectbox[checker_idx].options or []):
    at.selectbox[checker_idx].set_value("none")
    at.run()
check("audit: no exception after checker=none", not at.exception,
      str(at.exception[0].value)[:300] if at.exception else "")

audit_btn_idx = btn_labels.index("Audit this answer") if "Audit this answer" in btn_labels else 0
at.button[audit_btn_idx].click()
at.run()
check("audit: real run without exception", not at.exception,
      str(at.exception[0].value)[:400] if at.exception else "")
joined = "\n".join((md.value or "") for md in at.markdown)
check("audit: golden bad answer lands BLOCKED", "AUDIT FAILED" in joined)
check("audit: claims section rendered", "Audit findings" in joined)
check("audit: source panel rendered", "side by side" in joined)
check("audit: history captured", "Recent audits" in joined)

# ---------------------------------------------------------------------------
# 4. Real classroom battle (warfarin flagship case)
# ---------------------------------------------------------------------------
demo_idx = next((i for i, l in enumerate(sel_labels) if l == "Demo question"), None)
check("battle: demo selectbox present", demo_idx is not None)
if demo_idx is not None:
    at.selectbox[demo_idx].set_value("Warfarin + thrush (the hidden interaction)")
    at.run()
    check("battle: no exception after case pick", not at.exception)
    battle_btn_idx = next(
        (i for i, b in enumerate(at.button) if b.label == "Run the classroom demo"), None)
    at.button[battle_btn_idx].click()
    at.run()
    joined2 = "\n".join((md.value or "") for md in at.markdown)
    if at.exception:
        check("battle: real run without exception", False,
              str(at.exception[0].value)[:400])
    else:
        check("battle: real run without exception", True)
        check("battle: textbook card rendered", "Textbook page used to grade both students" in joined2)
        check("battle: naive bot verdict rendered",
              any("AUDIT" in (md.value or "") or "DECLINED" in (md.value or "") for md in at.markdown))
        warned = any("rate limit" in (w.value or "").lower() for w in at.warning)
        if warned:
            print("NOTE: battle hit a free-tier rate limit — verify manually after a minute")

# ---------------------------------------------------------------------------
print()
if fails:
    print(f"UI GATE: FAIL — {len(fails)} check(s) failed: {fails}")
    sys.exit(1)
print("UI GATE: ALL CHECKS PASSED")
