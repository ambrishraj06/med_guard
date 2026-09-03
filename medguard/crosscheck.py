"""
MedGuard — crosscheck.py
========================
Independent (non-LLM) second opinions for MedGuard's verdicts.

Two pluggable cross-checkers, both FREE, both CPU-friendly, no API keys:

  HHEM-2.1-Open  ("vectara/hallucination_evaluation_model")
      - ~600M cross-encoder; scores how well the ANSWER (hypothesis) is
        evidenced by the SOURCE (premise). Output: 0..1 consistency score.
      - Usage quirk: call model.predict(pairs), NOT model(pairs), and pass
        trust_remote_code=True (researched from the official model card).

  MiniCheck-Flan-T5-Large ("lytang/MiniCheck-Flan-T5-Large", 770M)
      - Sentence-level fact-checker: scorer.score(docs=[...], claims=[...])
        -> (labels, probabilities). We average claim probabilities.
      - Installed via: pip install "minicheck @ git+https://github.com/Liyan06/MiniCheck.git"

Both import lazily: torch/transformers are OPTIONAL dependencies and the model
loads only when its checker is actually selected (HF Spaces RAM budget, D11).
A singleton cache prevents reloading on every audit (M5 requirement).
"""

from __future__ import annotations

import os
from pathlib import Path

HHEM_MODEL_ID = "vectara/hallucination_evaluation_model"
MINICHECK_MODEL_NAME = "flan-t5-large"  # MiniCheck-FT5, 770M params

# Keep the multi-GB model cache on the project drive, never on C:.
# Must be set BEFORE transformers / nltk are imported anywhere.
os.environ.setdefault("HF_HOME", str(Path(__file__).resolve().parents[1] / ".hfcache"))
os.environ.setdefault("NLTK_DATA", str(Path(__file__).resolve().parents[1] / ".nltk_data"))

# Singletons — load once per process, reuse for every audit
_hhem_model = None
_minicheck_scorer = None


def _load_hhem():
    """Load HHEM once. Raises ImportError with a helpful message if torch/transformers
    are missing (they are optional dependencies)."""
    global _hhem_model
    if _hhem_model is not None:
        return _hhem_model
    try:
        from transformers import AutoModelForSequenceClassification
    except ImportError as err:
        raise ImportError(
            "HHEM requires torch + transformers. Install with: "
            'pip install torch --index-url https://download.pytorch.org/whl/cpu && pip install transformers'
        ) from err
    _hhem_model = AutoModelForSequenceClassification.from_pretrained(
        HHEM_MODEL_ID, trust_remote_code=True
    )
    _hhem_model.eval()
    return _hhem_model


def hhem_score(source: str, answer: str) -> float:
    """Consistency of ANSWER given SOURCE, as a float in [0, 1].

    Implementation note (empirically verified): HHEM is a cross-encoder trained
    on document->summary pairs. Scoring a WHOLE answer against a SHORT chunk in
    one pair is unreliable — a single pragmatically-inferred phrase can tank an
    otherwise-supported answer (e.g. adding "as first-line antibiotics" to a
    sentence whose source says "are recommended" scores 0.08 on a short premise
    but 0.92 on a long document). So we score EACH answer sentence separately
    against the source and average — the same shape MiniCheck is trained for.
    Even so, HHEM remains a STRICT, directional signal (see README).
    """
    model = _load_hhem()
    sentences = _split_sentences(answer)
    if not sentences:
        return 0.0
    pairs = [(source, s) for s in sentences]
    with __import__("torch").no_grad():
        scores = model.predict(pairs)
    return float(sum(scores) / len(scores))


def hhem_score_claims(source: str, claims: list[str]) -> list[float]:
    """HHEM consistency score for EACH claim against the source, in [0, 1].

    This is the claim-level second opinion: for every atomic claim the judge
    extracted, HHEM independently scores whether the source supports it.
    Returns one score per claim, same order as the input.
    """
    model = _load_hhem()
    if not claims:
        return []
    pairs = [(source, c) for c in claims]
    with __import__("torch").no_grad():
        scores = model.predict(pairs)
    return [float(s) for s in scores]


def _load_minicheck():
    global _minicheck_scorer
    if _minicheck_scorer is not None:
        return _minicheck_scorer
    try:
        from minicheck.minicheck import MiniCheck
    except ImportError as err:
        raise ImportError(
            "MiniCheck is not installed. Install with: "
            'pip install "minicheck @ git+https://github.com/Liyan06/MiniCheck.git"'
        ) from err
    _minicheck_scorer = MiniCheck(model_name=MINICHECK_MODEL_NAME, cache_dir="./ckpts")
    return _minicheck_scorer


def minicheck_score(source: str, answer: str) -> float:
    """Fraction of the answer's sentences MiniCheck deems supported, in [0, 1].

    MiniCheck works at sentence level, so we split the answer into sentences
    and average the raw support probabilities (raw_prob: 1 = supported).
    """
    scorer = _load_minicheck()
    sentences = _split_sentences(answer)
    if not sentences:
        return 0.0
    docs = [source] * len(sentences)
    _labels, probs, _, _ = scorer.score(docs=docs, claims=sentences)
    return float(sum(probs) / len(probs))


def _split_sentences(text: str) -> list[str]:
    """Lightweight sentence splitter (regex — no heavyweight NLP dependency)."""
    import re

    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def available_checkers() -> dict[str, bool]:
    """Report which cross-checkers can run in this environment (for the UI dropdown)."""
    status = {"none": True, "hhem": False, "minicheck": False}
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401

        status["hhem"] = True
    except ImportError:
        pass
    try:
        import minicheck  # noqa: F401

        status["minicheck"] = True
    except ImportError:
        pass
    return status
