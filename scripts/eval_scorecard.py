"""
MedGuard — EVAL SCORECARD (Session 2: "The Proof")
==================================================
Runs the 25-case hand-labeled eval set through the FULL audit pipeline
(real Groq API) and computes:

  - Verdict accuracy (exact + acceptable-set)
  - Safety-critical directional metrics:
      * danger recall    — dangerous answers that were NOT passed as SAFE
                           (a danger marked SAFE = the worst failure)
      * good precision   — honest answers passed as SAFE (not over-blocked)
      * abstention recall— unknown-topic questions that correctly refused
  - Confusion summary

Also supports judge-vs-judge mode: run with --judge2 to re-run every case on
the fallback model and report agreement between the two judges.

Run from E:\\MedGuard:
    .\\venv\\Scripts\\python scripts\\eval_scorecard.py           # full eval, primary judge
    .\\venv\\Scripts\\python scripts\\eval_scorecard.py --judge2  # + agreement with gpt-oss-20b
"""

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from medguard.audit import DEFAULT_JUDGE_MODEL, run_audit  # noqa: E402
from medguard.library import match_source  # noqa: E402
from scripts.eval_set import EVAL_CASES  # noqa: E402

FALLBACK_JUDGE = "openai/gpt-oss-20b"


def run_case(case, model=None):
    """Run one eval case through the app-equivalent flow (auto-pick on empty source)."""
    _id, q, source, answer, expected_set, category, note = case
    if not source.strip():
        match, _score = match_source(q)
        source = match["text"] if match else ""
    kwargs = {"model": model} if model else {}
    return run_audit(q, source, answer, **kwargs)


def is_pass(actual, expected_set):
    return actual in expected_set


def main() -> int:
    judge2 = "--judge2" in sys.argv
    print("=" * 78)
    print("MEDGUARD EVAL SCORECARD — 25 hand-labeled cases, real Groq API")
    print(f"primary judge: {DEFAULT_JUDGE_MODEL}")
    if judge2:
        print(f"agreement judge: {FALLBACK_JUDGE}")
    print("=" * 78)

    rows = []
    for case in EVAL_CASES:
        _id, q, source, answer, expected_set, category, note = case
        t0 = time.time()
        try:
            r = run_case(case)
            actual = r["verdict"]
            ok = is_pass(actual, expected_set)
            rows.append({
                "id": _id, "category": category, "note": note,
                "expected": sorted(expected_set), "actual": actual,
                "pass": ok, "latency_s": round(time.time() - t0, 1),
            })
            print(f"{'✅' if ok else '❌'} {_id} [{category:10s}] expected={'/'.join(sorted(expected_set)):28s} actual={actual:12s} ({rows[-1]['latency_s']}s) {note}")
        except Exception as err:
            rows.append({
                "id": _id, "category": category, "note": note,
                "expected": sorted(expected_set), "actual": "EXCEPTION",
                "pass": False, "latency_s": round(time.time() - t0, 1), "error": str(err)[:200],
            })
            print(f"❌ {_id} [{category:10s}] EXCEPTION: {str(err)[:100]}")

    # ---------------- metrics ----------------
    total = len(rows)
    passed = sum(1 for r in rows if r["pass"])

    dangers = [r for r in rows if r["category"] == "danger"]
    goods = [r for r in rows if r["category"] == "good"]
    abstains = [r for r in rows if r["category"] == "abstain"]
    unsups = [r for r in rows if r["category"] == "unsupported"]

    # Danger recall: a danger passes only if verdict is in expected set.
    # The catastrophic failure is actual == SAFE on a danger case.
    danger_caught = sum(1 for r in dangers if r["pass"])
    danger_false_safe = [r["id"] for r in dangers if r["actual"] == "SAFE"]

    good_passed = sum(1 for r in goods if r["actual"] == "SAFE")
    abstain_honored = sum(1 for r in abstains if r["pass"])
    unsup_correct = sum(1 for r in unsups if r["pass"])

    print()
    print("=" * 78)
    print("SCORECARD")
    print("=" * 78)
    print(f"Verdict accuracy (acceptable-set):   {passed}/{total} = {100*passed/total:.0f}%")
    if dangers:
        print(f"Danger recall (danger not passed):    {danger_caught}/{len(dangers)} = {100*danger_caught/len(dangers):.0f}%")
    if danger_false_safe:
        print(f"  ⚠️ FALSE-SAFE verdicts (worst failure): {danger_false_safe}")
    else:
        print(f"  ✅ ZERO false-SAFE verdicts on dangerous answers")
    if goods:
        print(f"Good answers passed as SAFE:          {good_passed}/{len(goods)} = {100*good_passed/len(goods):.0f}%")
    if unsups:
        print(f"Unsupported-only correctly flagged:   {unsup_correct}/{len(unsups)} = {100*unsup_correct/len(unsups):.0f}%")
    if abstains:
        print(f"Abstention honored (refused unknown): {abstain_honored}/{len(abstains)} = {100*abstain_honored/len(abstains):.0f}%")

    # ---------------- judge agreement (optional) ----------------
    if judge2:
        print()
        print("=" * 78)
        print(f"JUDGE-vs-JUDGE AGREEMENT — {DEFAULT_JUDGE_MODEL} vs {FALLBACK_JUDGE}")
        print("=" * 78)
        agree = disagree = 0
        diffs = []
        for case in EVAL_CASES:
            _id = case[0]
            primary_row = next(r for r in rows if r["id"] == _id)
            if primary_row["actual"] == "EXCEPTION":
                continue
            try:
                r2 = run_case(case, model=FALLBACK_JUDGE)
                a2 = r2["verdict"]
                if a2 == primary_row["actual"]:
                    agree += 1
                else:
                    disagree += 1
                    diffs.append((_id, primary_row["actual"], a2))
                time.sleep(2)
            except Exception as err:
                diffs.append((_id, primary_row["actual"], f"ERROR {str(err)[:60]}"))
        total_j = agree + disagree
        if total_j:
            print(f"Verdict agreement: {agree}/{total_j} = {100*agree/total_j:.0f}%")
        for d in diffs:
            print(f"  {d[0]}: primary={d[1]} vs fallback={d[2]}")

    out = ROOT / "scripts" / "eval_results.json"
    out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"\nresults saved: {out}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
