# Revamp Research — UI resources deep-read (2026-09-05)

Every resource below was verified against OUR environment (Streamlit 1.62.0 pinned,
Python 3.12.10, Streamlit Cloud 1GB) — not marketing claims.

## Verified facts

1. **Our Streamlit 1.62 ALREADY HAS the new theming engine.** Checked in the installed
   source: `theme.fontFaces` (7 refs in config.py), `borderColor`, `linkColor`,
   `baseRadius`, `showWidgetBorder`, `headingFont`, `codeFont` — all supported.
   The jmedia65 themes repo was built on exactly this system (announced by the
   Streamlit co-founder). No version bump needed = zero deploy risk.
2. **st.context.theme works** in 1.62 (needed by extras for dark/light awareness).
   Native moderns available: `st.tabs`, `st.pills`, `st.segmented_control`,
   `st.container(border=...)`.
3. **awesome-streamlit-themes (jmedia65)**: 10 professional config.toml themes.
   Healthcare theme = clinical blue #0066cc, off-white #fafbfc, IBM Plex Sans
   (self-hosted .ttf via fontFaces — no Google Fonts CDN), accessibility-first.
   These are CONFIG-ONLY themes (plus optional CSS) — copy the palette, adapt.
4. **streamlit-extras v1.6.0**: pip package, requires streamlit>=1.54 + Python>=3.10
   (we have 3.12.10 ✓) + **plotly>=5.23 as a hard dependency** (heavy-ish, ~40MB).
   57 extras total. Notable for us: metric_cards (style_metric_cards), colored_header,
   stylable_container, keyboard shortcuts, tags, add_vertical_space, skeleton,
   stateful_button, pagination, app_logo, floating_button.
5. **streamlit-antd-components v0.3.2**: Ant Design + Mantine React components
   (menus, cards, buttons, tables). streamlit>=1.12 — compatible. Adds a React
   bundle dependency. Best single pick if we want richer components.
6. **streamlit-option-menu v0.4.0**: lightweight horizontal/vertical nav menu.
   streamlit>=1.36 ✓. Tiny. Good for top-nav.

## Verdict for MedGuard (de-slop mission)

ADOPT (config-level, zero new deps):
- Healthcare-inspired config.toml theme: clinical palette + IBM Plex via fontFaces,
  linkColor/borderColor/baseRadius. Light clinical mode suits a medical auditor;
  keep dark mode as-is (it is our identity) OR go clinical-light — user decides.
- Kill emoji-in-headline spam, let the theme do the talking (restraint = premium).

ADOPT (1 new dep, streamlit-extras): metric_cards for verdict stats, tags for
claim-chip palette, skeleton for loading shimmer, keyboard shortcut (⌘/Ctrl+Enter
to run audit). NOT the whole package if we want slim: the 4 functions are
copy-pasteable (they're plain Python + CSS) — copying avoids the plotly dep.

SKIP: antd components (React bundle for things our HTML already does), option-menu
(we have no multi-page nav need), pygwalker/hiplot (data-viz tools, not relevant),
webrtc/drawable-canvas/folium/nlu/stlite/AgGrid/ace (out of scope for an auditor UI),
authenticator (no login use case on free demo).

UNCHANGED: the FastAPI+custom-page plan for the FULL "normal website" revamp remains
the ceiling-breaker; this Streamlit polish is the quick win that ships this week.
