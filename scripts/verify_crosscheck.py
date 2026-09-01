# scripts/verify_crosscheck.py
"""
M5 gate — verify the independent cross-checkers LOCALLY (no Groq needed).

Tests HHEM (and MiniCheck if installed) on the golden case:
  - bad answer  (ciprofloxacin contradiction) -> LOW consistency score
  - good answer (nitrofurantoin)              -> HIGH consistency score

Run from E:\\MedGuard:
    .\\venv\\Scripts\\python.exe scripts\\verify_crosscheck.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from medguard.crosscheck import available_checkers, hhem_score, minicheck_score  # noqa: E402

GOLDEN = json.loads((ROOT / "tests" / "golden_case.json").read_text(encoding="utf-8"))


def main() -> int:
    avail = available_checkers()
    print("Available cross-checkers:", avail)
    failed = 0

    if avail["hhem"]:
        print("\n--- HHEM-2.1-Open ---")
        bad = hhem_score(GOLDEN["source"], GOLDEN["bad_answer"])
        good = hhem_score(GOLDEN["source"], GOLDEN["good_answer"])
        print(f"bad answer consistency : {bad:.4f}  (expected LOW,  < 0.5)")
        print(f"good answer consistency: {good:.4f}  (expected HIGH, > 0.5)")
        if bad < 0.5 and good > 0.5 and good > bad:
            print("✅ HHEM separation verified")
        else:
            print("❌ HHEM did not separate the cases as expected")
            failed += 1
    else:
        print("\nℹ️  HHEM unavailable (install torch CPU + transformers)")

    if avail["minicheck"]:
        print("\n--- MiniCheck-Flan-T5-Large ---")
        bad = minicheck_score(GOLDEN["source"], GOLDEN["bad_answer"])
        good = minicheck_score(GOLDEN["source"], GOLDEN["good_answer"])
        print(f"bad answer support : {bad:.4f}  (expected LOW)")
        print(f"good answer support: {good:.4f}  (expected HIGH)")
        if bad < 0.5 and good > 0.5:
            print("✅ MiniCheck separation verified")
        else:
            print("❌ MiniCheck did not separate the cases as expected")
            failed += 1
    else:
        print("ℹ️  MiniCheck unavailable (pip install minicheck)")

    print("\nRESULT:", "FAILURES PRESENT" if failed else "ALL VERIFIED")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
