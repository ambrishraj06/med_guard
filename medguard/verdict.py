"""
MedGuard — verdict.py
=====================
The deterministic "brain" of MedGuard. PURE PYTHON — no LLM, no network.

It takes the per-claim statuses produced by the verifier and rolls them up
into the final verdict + evidence coverage score, using ONE fixed rule table.
An auditor must never be random, so this file has no randomness, no API,
and no ambiguity.

Rule table (locked decision D13):
    any CONTRADICTION            -> BLOCKED,      coverage = 0
    all SUPPORTED                -> SAFE,         coverage = 100
    mix of SUPPORTED/UNSUPPORTED -> WARNING,      coverage = supported/total * 100
    no source / empty answer / zero claims -> UNVERIFIABLE, coverage = 0
"""

from __future__ import annotations

# The only three statuses the verifier is allowed to produce.
CANONICAL_STATUSES = ("SUPPORTED", "UNSUPPORTED", "CONTRADICTION")

# Verdicts MedGuard can output.
VERDICTS = ("SAFE", "WARNING", "BLOCKED", "UNVERIFIABLE")

# Statuses commonly seen from LLMs, mapped to our canonical three.
_STATUS_ALIASES = {
    "supported": "SUPPORTED",
    "support": "SUPPORTED",
    "yes": "SUPPORTED",
    "true": "SUPPORTED",
    "entailed": "SUPPORTED",
    "unsupported": "UNSUPPORTED",
    "not_supported": "UNSUPPORTED",
    "not supported": "UNSUPPORTED",
    "unverifiable_claim": "UNSUPPORTED",
    "no_evidence": "UNSUPPORTED",
    "insufficient": "UNSUPPORTED",
    "contradiction": "CONTRADICTION",
    "contradicted": "CONTRADICTION",
    "contradicts": "CONTRADICTION",
    "refuted": "CONTRADICTION",
    "false": "CONTRADICTION",
    "unsafe": "CONTRADICTION",
}


def normalize_status(raw: str | None) -> str | None:
    """Map any LLM status variant to one of the three canonical statuses.

    Returns None if the value cannot be understood (caller decides what to do —
    the audit engine defaults unknown/dropped claims to UNSUPPORTED, which is
    the safe direction for a medical auditor).
    """
    if raw is None:
        return None
    key = str(raw).strip().lower().replace("-", " ").replace("_", " ")
    key = " ".join(key.split())  # collapse whitespace
    if key in _STATUS_ALIASES:
        return _STATUS_ALIASES[key]
    squeezed = key.replace(" ", "")
    if squeezed in _STATUS_ALIASES:
        return _STATUS_ALIASES[squeezed]
    return None


def compute_verdict(
    statuses: list[str] | None,
    *,
    has_source: bool = True,
    has_answer: bool = True,
) -> dict:
    """Roll per-claim statuses up into the final audit decision.

    Parameters
    ----------
    statuses : list of raw status strings (already validated upstream, but we
               normalize defensively here too — trust nothing from an LLM).
    has_source : True if the user/chatbot supplied guideline text.
    has_answer : True if there was an answer to audit at all.

    Returns a dict:
        verdict   : SAFE | WARNING | BLOCKED | UNVERIFIABLE
        coverage  : int 0..100  (evidence coverage, NOT calibrated confidence)
        reason    : human-readable one-liner for the UI
        counts    : {"supported": n, "unsupported": n, "contradiction": n, "total": n}
    """
    counts = {"supported": 0, "unsupported": 0, "contradiction": 0, "total": 0}

    # --- Edge case: no source to check against → abstain (decision D3) -------
    if not has_source:
        return {
            "verdict": "UNVERIFIABLE",
            "coverage": 0,
            "reason": "No source text provided. MedGuard cannot verify grounding without evidence.",
            "counts": counts,
        }

    # --- Edge case: nothing to audit -----------------------------------------
    if not has_answer:
        return {
            "verdict": "UNVERIFIABLE",
            "coverage": 0,
            "reason": "The answer is empty — there is nothing to audit.",
            "counts": counts,
        }

    # --- Normalize statuses, counting only what we understand ----------------
    for raw in statuses or []:
        norm = normalize_status(raw)
        if norm is None:
            # Unknown status from the LLM: treat as unsupported (safe default)
            counts["unsupported"] += 1
        else:
            counts[norm.lower()] += 1
        counts["total"] += 1

    # --- Edge case: answer existed but zero claims came out of it ------------
    if counts["total"] == 0:
        return {
            "verdict": "UNVERIFIABLE",
            "coverage": 0,
            "reason": "No verifiable factual claims were found in the answer.",
            "counts": counts,
        }

    total = counts["total"]

    # --- Core rule table (locked decision D13) --------------------------------
    if counts["contradiction"] > 0:
        return {
            "verdict": "BLOCKED",
            "coverage": 0,
            "reason": (
                f"Contradiction detected in {counts['contradiction']} of {total} claims. "
                "The answer goes against the source guideline."
            ),
            "counts": counts,
        }

    if counts["supported"] == total:
        return {
            "verdict": "SAFE",
            "coverage": 100,
            "reason": f"All {total} claims are supported by the source text.",
            "counts": counts,
        }

    coverage = round(100 * counts["supported"] / total)  # total >= 1 here, no div-by-zero
    return {
        "verdict": "WARNING",
        "coverage": coverage,
        "reason": (
            f"{counts['supported']} of {total} claims supported; "
            f"{counts['unsupported']} unsupported by the source text."
        ),
        "counts": counts,
    }
