"""
Offline tests for MedGuard's deterministic verdict brain (medguard/verdict.py).

These run with NO network and NO API key — proving the safety logic is
trustworthy before anything touches Groq. Run:  pytest tests/ -v
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from medguard.verdict import compute_verdict, normalize_status  # noqa: E402

TESTS_DIR = Path(__file__).resolve().parent
GOLDEN = json.loads((TESTS_DIR / "golden_case.json").read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# The golden case: labels produced by the verifier for the bad answer
# --------------------------------------------------------------------------
GOLDEN_BAD_STATUSES = ["CONTRADICTION", "UNSUPPORTED", "UNSUPPORTED"]
GOLDEN_GOOD_STATUSES = ["SUPPORTED", "SUPPORTED"]


def test_golden_case_blocked():
    """Golden bad answer: 1 contradiction + 2 unsupported → BLOCKED, 0%."""
    result = compute_verdict(GOLDEN_BAD_STATUSES)
    assert result["verdict"] == GOLDEN["expected_bad_verdict"] == "BLOCKED"
    assert result["coverage"] == 0
    assert result["counts"]["total"] == 3
    assert "contradiction" in result["reason"].lower()


def test_golden_case_safe():
    """Good answer: everything supported → SAFE, 100%."""
    result = compute_verdict(GOLDEN_GOOD_STATUSES)
    assert result["verdict"] == GOLDEN["expected_good_verdict"] == "SAFE"
    assert result["coverage"] == 100


def test_single_contradiction_among_supported_still_blocks():
    """One contradiction poisons the whole answer — medical safety, decision D13."""
    result = compute_verdict(["SUPPORTED", "SUPPORTED", "CONTRADICTION", "SUPPORTED"])
    assert result["verdict"] == "BLOCKED"
    assert result["coverage"] == 0


def test_mixed_warning_coverage_math():
    """2 of 4 supported, no contradiction → WARNING with 50% coverage."""
    result = compute_verdict(["SUPPORTED", "UNSUPPORTED", "SUPPORTED", "UNSUPPORTED"])
    assert result["verdict"] == "WARNING"
    assert result["coverage"] == 50


def test_warning_coverage_rounds():
    """1 of 3 supported → 33% (rounded, integer)."""
    result = compute_verdict(["SUPPORTED", "UNSUPPORTED", "UNSUPPORTED"])
    assert result["verdict"] == "WARNING"
    assert result["coverage"] == 33


def test_empty_source_is_unverifiable():
    """No source → we refuse to judge. Abstention is a safety feature (D3)."""
    result = compute_verdict(["SUPPORTED"], has_source=False)
    assert result["verdict"] == "UNVERIFIABLE"
    assert result["coverage"] == 0
    assert result["counts"]["total"] == 0


def test_empty_answer_is_unverifiable():
    result = compute_verdict([], has_answer=False)
    assert result["verdict"] == "UNVERIFIABLE"
    assert result["coverage"] == 0


def test_zero_claims_is_unverifiable():
    """Answer existed but the extractor found no factual claims."""
    result = compute_verdict([], has_answer=True)
    assert result["verdict"] == "UNVERIFIABLE"
    assert result["coverage"] == 0
    assert "no verifiable factual claims" in result["reason"].lower()


def test_none_input_is_unverifiable():
    result = compute_verdict(None)
    assert result["verdict"] == "UNVERIFIABLE"


def test_unknown_status_defaults_to_unsupported():
    """LLM invents a weird status → safe default (UNSUPPORTED), never a crash."""
    result = compute_verdict(["SUPPORTED", "KIND_OF_TRUE-ish"])
    assert result["verdict"] == "WARNING"
    assert result["counts"]["unsupported"] == 1
    assert result["counts"]["total"] == 2


def test_none_status_defaults_to_unsupported():
    result = compute_verdict([None, "SUPPORTED"])
    assert result["verdict"] == "WARNING"
    assert result["counts"]["unsupported"] == 1


# --------------------------------------------------------------------------
# Status normalization (LLM output is messy; we are strict)
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("SUPPORTED", "SUPPORTED"),
        ("supported", "SUPPORTED"),
        ("  Supported  ", "SUPPORTED"),
        ("UNSUPPORTED", "UNSUPPORTED"),
        ("not supported", "UNSUPPORTED"),
        ("not-supported", "UNSUPPORTED"),
        ("NOT_SUPPORTED", "UNSUPPORTED"),
        ("CONTRADICTION", "CONTRADICTION"),
        ("contradicted", "CONTRADICTION"),
        ("refuted", "CONTRADICTION"),
        ("entailed", "SUPPORTED"),
        ("yes", "SUPPORTED"),
        ("completely made up status", None),
        ("", None),
        (None, None),
    ],
)
def test_normalize_status(raw, expected):
    assert normalize_status(raw) == expected


def test_verdict_never_divides_by_zero():
    """Explicitly hammer the divide-by-zero corner: unsupported-only with total>0 is fine,
    and total==0 already returns UNVERIFIABLE before any division."""
    result = compute_verdict(["UNSUPPORTED", "UNSUPPORTED"])
    assert result["verdict"] == "WARNING"
    assert result["coverage"] == 0
