"""
MedGuard — audit.py
===================
The ONLY module that talks to the network. Wires the judge LLM
(openai/gpt-oss-120b via Groq free API) into the audit pipeline.

Defensive engineering rules implemented here (locked decisions D5, D14, D15, D20):
  - Model name lives in CONFIG, never scattered in code (Groq deprecates models).
  - temperature = 0 everywhere: an auditor must be deterministic.
  - JSON defense: request JSON mode, strip markdown fences if the model adds
    them anyway, validate the schema, retry up to 3 times on parse failure.
  - ONE batched verification call for all claims (claim_ids prevent scrambling).
  - Dropped claims are re-attached as UNSUPPORTED (safe default).
  - Unknown statuses are normalized; unrecognized ones default to UNSUPPORTED.
  - gpt-oss is a reasoning model: reasoning_effort="low", generous max_tokens,
    and an automatic retry with more tokens if content comes back empty.
  - The API key is read from the environment / Streamlit secrets — never stored.
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any

from medguard import prompts
from medguard.verdict import compute_verdict, normalize_status

# ---------------------------------------------------------------------------
# CONFIG — the only place model names live (decision D20)
# ---------------------------------------------------------------------------
DEFAULT_JUDGE_MODEL = "openai/gpt-oss-120b"
EXTRACTION_FALLBACK_MODEL = "openai/gpt-oss-20b"  # extraction ONLY (D6)

MAX_RETRIES = 3
BASE_MAX_TOKENS = 4096
MAX_CLAIMS = 15  # audit cap: beyond this the batched call risks token limits

# Retry-after backoff for rate limits (seconds) — Groq free tier 429s under bursts.
_BACKOFF_SECONDS = (2, 4, 8)
# Hard ceiling on a single API call; a hung call must fail, not spin forever.
_API_TIMEOUT_SECONDS = 60


class RateLimitError(Exception):
    """Groq free-tier rate limit hit (429). Raised after backoff retries fail."""


def _is_rate_limit(err: Exception) -> bool:
    text = str(err)
    return "429" in text or "rate limit" in text.lower() or "Rate limit reached" in text


# ---------------------------------------------------------------------------
# Client + key handling — the key NEVER lives in this file
# ---------------------------------------------------------------------------
def _resolve_api_key(api_key: str | None = None) -> str:
    """Priority: explicit arg -> Streamlit secrets -> environment variable."""
    if api_key:
        return api_key
    try:  # Streamlit context (works locally via secrets.toml and on HF Spaces)
        import streamlit as st

        if hasattr(st, "secrets") and "GROQ_API_KEY" in st.secrets:
            return str(st.secrets["GROQ_API_KEY"])
    except Exception:
        pass
    key = os.environ.get("GROQ_API_KEY")
    if key:
        return key
    raise RuntimeError(
        "No Groq API key found. Add GROQ_API_KEY to .streamlit/secrets.toml "
        "(copy secrets.toml.example) or set it as an environment variable."
    )


def _get_client(api_key: str | None = None):
    from groq import Groq

    # Timeout: a hung call raises instead of spinning the UI forever.
    return Groq(api_key=_resolve_api_key(api_key), timeout=_API_TIMEOUT_SECONDS)


# ---------------------------------------------------------------------------
# JSON defense helpers
# ---------------------------------------------------------------------------
_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)
_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def strip_fences(text: str) -> str:
    """Remove markdown code fences the model adds despite instructions."""
    if "```" in text:
        match = _FENCE_RE.search(text)
        if match:
            return match.group(1).strip()
    return text.strip()


def extract_json_object(text: str) -> dict[str, Any]:
    """Parse the first JSON object found in a string. Raises ValueError if none."""
    cleaned = strip_fences(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    # Last resort: grab the outermost {...} block
    match = _JSON_OBJECT_RE.search(cleaned)
    if match:
        return json.loads(match.group(0))
    raise ValueError("No valid JSON object found in model output.")


def _chat_json(
    client,
    model: str,
    messages: list[dict],
    *,
    max_tokens: int = BASE_MAX_TOKENS,
) -> dict[str, Any]:
    """One chat call that must return a JSON object. Handles:
    - structured_outputs/json_schema if supported, else plain json_object
    - reasoning_effort='low' for gpt-oss reasoning models (graceful fallback)
    - empty content from reasoning models -> retry with more tokens
    - retries on malformed JSON
    - 429 rate limits -> exponential backoff (2s/4s/8s) then a friendly error
    """
    last_error: Exception | None = None
    current_max_tokens = max_tokens

    for attempt in range(1, MAX_RETRIES + 1):
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": current_max_tokens,
            "response_format": {"type": "json_object"},
        }
        # gpt-oss reasoning models: try to cap thinking effort; if the SDK or
        # API rejects the parameter, silently fall back to a plain call.
        if "gpt-oss" in model:
            try:
                return _do_call(client, {**kwargs, "reasoning_effort": "low"})
            except RateLimitError:
                raise  # handled by the outer backoff below
            except Exception as err:  # TypeError (old SDK) or API 400 (param rejected)
                last_error = err
        try:
            return _do_call(client, kwargs)
        except RateLimitError:
            # Free-tier 429: wait politely and retry — do NOT give up early.
            if attempt < MAX_RETRIES:
                time.sleep(_BACKOFF_SECONDS[min(attempt - 1, len(_BACKOFF_SECONDS) - 1)])
                continue
            raise RateLimitError(
                "Groq's free tier hit its rate limit. Wait about a minute and "
                "try again — the audit itself is fine, the server just needs a breather."
            ) from None
        except (ValueError, json.JSONDecodeError) as err:
            # Malformed JSON: retry, giving the reasoning model more headroom
            last_error = err
            current_max_tokens = int(current_max_tokens * 1.5)
            continue
        except RuntimeError as err:
            # Empty content after unpacking reasoning -> more tokens, retry
            last_error = err
            current_max_tokens = int(current_max_tokens * 1.5)
            continue

    raise RuntimeError(
        f"LLM call failed after {MAX_RETRIES} attempts (model={model}). "
        f"Last error: {last_error}"
    )


def _do_call(client, kwargs: dict) -> dict[str, Any]:
    try:
        response = client.chat.completions.create(**kwargs)
    except Exception as err:
        if _is_rate_limit(err):
            raise RateLimitError(str(err)) from err
        raise
    choice = response.choices[0]
    content = (choice.message.content or "").strip()

    # Some reasoning models put text in `reasoning` and leave content empty
    if not content:
        raise RuntimeError("Empty content returned (reasoning exhausted the token budget).")

    return extract_json_object(content)


def _create_with_rate_retry(client, kwargs: dict, max_attempts: int = 3):
    """Plain-text completions call with free-tier 429 backoff (2s/4s/8s)."""
    for attempt in range(1, max_attempts + 1):
        try:
            return client.chat.completions.create(**kwargs)
        except Exception as err:
            if _is_rate_limit(err) and attempt < max_attempts:
                time.sleep(_BACKOFF_SECONDS[min(attempt - 1, len(_BACKOFF_SECONDS) - 1)])
                continue
            if _is_rate_limit(err):
                raise RateLimitError(
                    "Groq's free tier hit its rate limit. Wait about a minute and "
                    "try again — the audit itself is fine, the server just needs a breather."
                ) from err
            raise


# ---------------------------------------------------------------------------
# Step 1 — Claim extraction
# ---------------------------------------------------------------------------
def extract_claims(
    answer: str,
    *,
    model: str = DEFAULT_JUDGE_MODEL,
    api_key: str | None = None,
    question: str = "",
) -> list[dict]:
    """Split an AI answer into atomic claims (explicit + implicit safety claims),
    aware of the patient's question. Returns [{"claim_id": int, "claim": str}]."""
    client = _get_client(api_key)
    messages = prompts.build_extraction_messages(answer, question)
    data = _chat_json(client, model, messages)

    raw_claims = data.get("claims", [])
    claims: list[dict] = []
    for idx, item in enumerate(raw_claims, start=1):
        if isinstance(item, dict):
            text = str(item.get("claim", "")).strip()
            cid = item.get("claim_id", idx)
        elif isinstance(item, str):  # model returned plain strings — accept, renumber
            text = item.strip()
            cid = idx
        else:
            continue
        if text:
            try:
                cid = int(cid)
            except (TypeError, ValueError):
                cid = idx
            claims.append({"claim_id": cid, "claim": text})

    # Guarantee sequential, unique ids regardless of what the model returned
    for new_id, claim in enumerate(claims, start=1):
        claim["claim_id"] = new_id

    # Claim cap: very long answers can produce dozens of claims, which risks
    # blowing the verification call's token budget. Audit the first MAX_CLAIMS
    # and report the truncation honestly (the audit never hides what it skipped).
    if len(claims) > MAX_CLAIMS:
        claims = claims[:MAX_CLAIMS]
        claims.append(
            {
                "claim_id": MAX_CLAIMS,
                "claim": (
                    f"(This answer contained more claims than the audit limit of "
                    f"{MAX_CLAIMS} — the remaining ones were not checked.)"
                ),
                "truncated": True,
            }
        )
    return claims


# ---------------------------------------------------------------------------
# Step 2 — Claim verification (ONE batched call — decision D14)
# ---------------------------------------------------------------------------
def verify_claims(
    claims: list[dict],
    source: str,
    question: str = "",
    *,
    model: str = DEFAULT_JUDGE_MODEL,
    api_key: str | None = None,
) -> list[dict]:
    """Verify all claims against the source in one call.

    Returns [{"claim_id", "claim", "status", "reasoning", "evidence"}] with
    every input claim present exactly once (dropped ones default UNSUPPORTED).
    """
    if not claims:
        return []

    client = _get_client(api_key)
    messages = prompts.build_verification_messages(question, source, claims)
    data = _chat_json(client, model, messages)

    raw_results = data.get("results", data.get("claims", []))
    by_id: dict[int, dict] = {}
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        try:
            cid = int(item.get("claim_id"))
        except (TypeError, ValueError):
            continue
        status = normalize_status(item.get("status")) or "UNSUPPORTED"
        reasoning = str(item.get("reasoning", "")).strip()
        evidence = item.get("evidence")
        if not isinstance(evidence, str) or not evidence.strip():
            evidence = None
        # Evidence hygiene: it must be a verbatim source substring, else drop it
        if evidence and evidence.strip() not in source:
            evidence = None
        by_id[cid] = {
            "claim_id": cid,
            "claim": "",
            "status": status,
            "reasoning": reasoning,
            "evidence": evidence,
        }

    # Re-attach every input claim; missing ones default to UNSUPPORTED
    results: list[dict] = []
    for claim in claims:
        cid = claim["claim_id"]
        row = by_id.get(
            cid,
            {
                "claim_id": cid,
                "claim": claim["claim"],
                "status": "UNSUPPORTED",
                "reasoning": "The verifier did not return this claim; defaulted to UNSUPPORTED.",
                "evidence": None,
            },
        )
        row["claim"] = claim["claim"]  # trust OUR copy of the claim text, not the model's
        results.append(row)
    return results


# ---------------------------------------------------------------------------
# Step 3 — Optional independent cross-check (pluggable, decision D7/D8)
# ---------------------------------------------------------------------------
def run_crosscheck(source: str, answer: str, checker: str) -> float | None:
    """Returns a 0-1 consistency score, or None if unavailable.

    Kept as a thin indirection so the UI can pass "HHEM", "MiniCheck" or "none".
    Import happens inside the function: torch/transformers stay optional and
    the model loads only when actually selected (HF Spaces RAM budget, D11).
    """
    if checker.lower() == "none":
        return None
    if checker.lower() == "hhem":
        from medguard.crosscheck import hhem_score

        return hhem_score(source, answer)
    if checker.lower() == "minicheck":
        from medguard.crosscheck import minicheck_score

        return minicheck_score(source, answer)
    raise ValueError(f"Unknown cross-checker: {checker}")


# ---------------------------------------------------------------------------
# Step 0 — Grounded answer generation (Ask & Check mode: question in → answer out)
# ---------------------------------------------------------------------------
def generate_answer(
    question: str,
    source: str,
    *,
    model: str = DEFAULT_JUDGE_MODEL,
    api_key: str | None = None,
) -> str:
    """Generate an answer to `question` using ONLY `source` (same epistemology
    as the verifier). Plain-text call with the same retry/empty-content defense
    as the JSON path."""
    client = _get_client(api_key)
    messages = prompts.build_generation_messages(question, source)
    current_max_tokens = BASE_MAX_TOKENS
    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": current_max_tokens,
        }
        if "gpt-oss" in model:
            try:
                response = _create_with_rate_retry(client, {**kwargs, "reasoning_effort": "low"})
                content = (response.choices[0].message.content or "").strip()
                if content:
                    return content
                raise RuntimeError("Empty content from reasoning model.")
            except RateLimitError:
                raise
            except RuntimeError as err:
                last_error = err
                current_max_tokens = int(current_max_tokens * 1.5)
                continue
            except Exception as err:  # SDK/API rejected reasoning_effort — plain retry
                last_error = err
        try:
            response = _create_with_rate_retry(client, kwargs)
            content = (response.choices[0].message.content or "").strip()
            if content:
                return content
            raise RuntimeError("Empty content from reasoning model.")
        except RateLimitError:
            raise
        except RuntimeError as err:
            last_error = err
            current_max_tokens = int(current_max_tokens * 1.5)
            continue

    raise RuntimeError(
        f"Answer generation failed after {MAX_RETRIES} attempts (model={model}). "
        f"Last error: {last_error}"
    )


# ---------------------------------------------------------------------------
# Final holistic safety review (whole answer, patient context) — Upgrade 3
# ---------------------------------------------------------------------------
def holistic_check(
    question: str,
    source: str,
    answer: str,
    *,
    model: str = DEFAULT_JUDGE_MODEL,
    api_key: str | None = None,
) -> dict:
    """One last whole-answer review in the patient's context.
    Returns {"status": "OK"|"CONTRADICTION", "reasoning": str, "evidence": quote|None}.
    Never raises — on any failure it returns OK with a note (audit still stands
    on its claim-level results)."""
    try:
        client = _get_client(api_key)
        messages = prompts.build_holistic_messages(question, source, answer)
        data = _chat_json(client, model, messages)
        status = normalize_status(data.get("status"))
        if status not in ("SUPPORTED", "CONTRADICTION"):
            status = "SUPPORTED"  # unknown/unparseable -> neutral, never fabricate danger
        reasoning = str(data.get("reasoning", "")).strip()
        evidence = data.get("evidence")
        if not isinstance(evidence, str) or not evidence.strip():
            evidence = None
        if evidence and evidence.strip() not in source:
            evidence = None
        return {
            "status": "CONTRADICTION" if status == "CONTRADICTION" else "OK",
            "reasoning": reasoning,
            "evidence": evidence,
        }
    except Exception as err:
        return {
            "status": "OK",
            "reasoning": f"(holistic check skipped: {err})",
            "evidence": None,
        }


# ---------------------------------------------------------------------------
# Full pipeline — one function the UI calls
# ---------------------------------------------------------------------------
def run_audit(
    question: str,
    source: str,
    answer: str,
    *,
    model: str = DEFAULT_JUDGE_MODEL,
    crosschecker: str = "none",
    api_key: str | None = None,
) -> dict:
    """Orchestrate the full MedGuard audit and return the final result dict."""
    source = (source or "").strip()
    answer = (answer or "").strip()

    # Verdict edge cases that need no LLM at all (D3/D13)
    if not source:
        verdict = compute_verdict(None, has_source=False)
        return _assemble(question, source, answer, [], None, verdict)
    if not answer:
        verdict = compute_verdict(None, has_answer=False)
        return _assemble(question, source, answer, [], None, verdict)

    claims = extract_claims(answer, model=model, api_key=api_key, question=question)
    if not claims:
        verdict = compute_verdict([], has_answer=True)
        return _assemble(question, source, answer, [], None, verdict)

    # Split off the truncation marker (if any) — it is a note, not a claim to judge.
    truncation_note = None
    real_claims = []
    for c in claims:
        if c.get("truncated"):
            truncation_note = c["claim"]
        else:
            real_claims.append(c)
    claims = real_claims

    verified = verify_claims(claims, source, question, model=model, api_key=api_key)
    statuses = [v["status"] for v in verified]

    # Claim-level verdict first — the holistic call only runs when it can change
    # the outcome (SAFE/WARNING). An already-BLOCKED audit needs no third call.
    verdict = compute_verdict(statuses)

    # Final holistic safety review in the patient's context (Upgrade 3).
    # A CONTRADICTION here promotes the verdict to BLOCKED — this is what
    # catches e.g. drug-interaction dangers the claim loop can miss.
    holistic = {"status": "OK", "reasoning": "", "evidence": None}
    if verdict["verdict"] != "BLOCKED":
        holistic = holistic_check(question, source, answer, model=model, api_key=api_key)
    if holistic["status"] == "CONTRADICTION":
        statuses = statuses + ["CONTRADICTION"]
        verdict = compute_verdict(statuses)
        if verdict["verdict"] != "BLOCKED":
            verdict = dict(verdict, verdict="BLOCKED", coverage=0)
        plain = holistic.get("reasoning") or "the answer gives dangerous guidance for this patient"
        base_reason = verdict.get("reason", "")
        verdict = dict(verdict, reason=f"{plain} ({base_reason})" if base_reason else plain)

    if truncation_note:
        verdict = dict(verdict)
        verdict["reason"] = (
            f"{verdict['reason']} (Note: {truncation_note})"
        )

    crosscheck: tuple[str, float | None] | None = None
    if crosschecker and crosschecker.lower() != "none":
        try:
            # Per-claim cross-checking: HHEM scores each extracted claim
            # independently — a claim-level second opinion aligned with the
            # judge's claim-by-claim audit. Also detects judge/checker
            # disagreement, which is surfaced on the affected claims.
            if crosschecker.lower() == "hhem":
                from medguard.crosscheck import hhem_score_claims

                claim_scores = hhem_score_claims(
                    source, [v["claim"] for v in verified]
                )
                for v, cs in zip(verified, claim_scores):
                    v["crosscheck_score"] = round(cs, 4)
                    # Disagreement: judge says SUPPORTED but HHEM strongly refutes
                    if v["status"] == "SUPPORTED" and cs < 0.3:
                        v["disagreement"] = (
                            "The independent checker doubts this claim even though "
                            "the judge accepted it."
                        )
                    elif v["status"] == "UNSUPPORTED" and cs > 0.7:
                        v["disagreement"] = (
                            "The independent checker supports this claim even though "
                            "the judge did not."
                        )
                if claim_scores:
                    crosscheck = (crosschecker, sum(claim_scores) / len(claim_scores))
                else:
                    crosscheck = (crosschecker, None)
            else:
                score = run_crosscheck(source, answer, crosschecker)
                crosscheck = (crosschecker, score)
        except Exception as err:  # never let a cross-checker crash the audit
            crosscheck = (crosschecker, None)
            verdict = dict(verdict)
            verdict["reason"] += f" (Cross-checker unavailable: {err})"

    return _assemble(question, source, answer, verified, crosscheck, verdict)


def _assemble(
    question: str,
    source: str,
    answer: str,
    verified: list[dict],
    crosscheck: tuple[str, float | None] | None,
    verdict: dict,
) -> dict:
    checker_name, checker_score = crosscheck if crosscheck else (None, None)
    return {
        "question": question,
        "source": source,
        "answer": answer,
        "claims": verified,
        "crosscheck_checker": checker_name,
        "crosscheck_score": checker_score,
        "verdict": verdict["verdict"],
        "coverage": verdict["coverage"],
        "reason": verdict["reason"],
        "counts": verdict["counts"],
    }
