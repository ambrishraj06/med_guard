# scripts/e2e_test.py
"""
MedGuard end-to-end test — the M7 gate.

Runs the FULL pipeline (real Groq API call with openai/gpt-oss-120b) on the
golden test case + edge cases, and prints a pass/fail table.

Prerequisite: put YOUR key in E:\\MedGuard\\.streamlit\\secrets.toml
    (copy .streamlit/secrets.toml.example and paste your key)
    ... or set the GROQ_API_KEY environment variable.

Run from E:\\MedGuard:
    .\\venv\\Scripts\\python.exe scripts\\e2e_test.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from medguard.audit import run_audit  # noqa: E402
from medguard.crosscheck import available_checkers  # noqa: E402

GOLDEN = json.loads((ROOT / "tests" / "golden_case.json").read_text(encoding="utf-8"))

results = []


def check(name: str, fn):
    try:
        ok, detail = fn()
    except Exception as err:
        ok, detail = False, f"EXCEPTION: {err}"
    results.append((name, ok, detail))
    print(f"{'✅ PASS' if ok else '❌ FAIL'}  {name}  —  {detail}")


def main() -> int:
    print("=" * 70)
    print("MedGuard end-to-end test (real Groq API)")
    print("=" * 70)

    # 1 — Golden case: dangerous answer must be BLOCKED with 0% coverage
    def golden_bad():
        r = run_audit(GOLDEN["question"], GOLDEN["source"], GOLDEN["bad_answer"])
        statuses = {c["status"] for c in r["claims"]}
        ok = (
            r["verdict"] == "BLOCKED"
            and r["coverage"] == 0
            and "CONTRADICTION" in statuses
        )
        return ok, (
            f"verdict={r['verdict']} coverage={r['coverage']}% "
            f"statuses={[c['status'] for c in r['claims']]}"
        )

    check("Golden case (bad answer) → BLOCKED / 0% / contradiction found", golden_bad)

    # 2 — Good answer must be SAFE with 100% coverage
    def golden_good():
        r = run_audit(GOLDEN["question"], GOLDEN["source"], GOLDEN["good_answer"])
        ok = r["verdict"] == "SAFE" and r["coverage"] == 100
        return ok, (
            f"verdict={r['verdict']} coverage={r['coverage']}% "
            f"statuses={[c['status'] for c in r['claims']]}"
        )

    check("Good answer → SAFE / 100%", golden_good)

    # 3 — No source must abstain WITHOUT calling the LLM
    def no_source():
        r = run_audit(GOLDEN["question"], "", GOLDEN["bad_answer"])
        ok = r["verdict"] == "UNVERIFIABLE" and r["coverage"] == 0 and r["claims"] == []
        return ok, f"verdict={r['verdict']} claims={len(r['claims'])}"

    check("Empty source → UNVERIFIABLE (no LLM call)", no_source)

    # 4 — Empty answer must abstain
    def empty_answer():
        r = run_audit(GOLDEN["question"], GOLDEN["source"], "")
        ok = r["verdict"] == "UNVERIFIABLE"
        return ok, f"verdict={r['verdict']}"

    check("Empty answer → UNVERIFIABLE", empty_answer)

    # 5 — Verbatim evidence hygiene: every evidence string must exist in the source
    def evidence_verbatim():
        r = run_audit(GOLDEN["question"], GOLDEN["source"], GOLDEN["bad_answer"])
        bad = [
            c["evidence"]
            for c in r["claims"]
            if c["evidence"] and c["evidence"] not in GOLDEN["source"]
        ]
        return len(bad) == 0, f"non-verbatim evidences: {len(bad)}"

    check("Evidence quotes are verbatim source substrings", evidence_verbatim)

    # 6 — Cross-checker availability report (informational)
    avail = available_checkers()
    print(
        f"\nℹ️  Cross-checker availability: hhem={avail['hhem']} minicheck={avail['minicheck']} "
        "(install torch CPU + transformers / minicheck to enable)"
    )

    failed = [name for name, ok, _ in results if not ok]
    print("\n" + "=" * 70)
    print(f"RESULT: {len(results) - len(failed)}/{len(results)} passed")
    if failed:
        print("FAILED:", ", ".join(failed))
        return 1
    print("ALL GREEN — MedGuard core pipeline verified end-to-end.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
