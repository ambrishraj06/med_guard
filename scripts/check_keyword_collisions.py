"""
MedGuard — keyword collision checker
====================================
Flags keywords claimed by more than one library topic. Collisions are not
automatically bugs (the higher-scoring topic wins), but each one is a potential
misroute on edge phrasings — this script lists them so they can be disambiguated
with phrase keywords or removed.

Run from E:\\MedGuard:
    .\\venv\\Scripts\\python scripts\\check_keyword_collisions.py
"""

import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from medguard.library import LIBRARY  # noqa: E402


def main() -> int:
    owners = defaultdict(list)
    for entry in LIBRARY:
        for kw in entry.get("keywords", []):
            owners[kw].append(entry["topic"])

    dupes = {k: v for k, v in owners.items() if len(v) > 1}
    if not dupes:
        print("✅ No keyword collisions — every keyword is unique to one topic.")
        return 0

    print(f"⚠️  {len(dupes)} colliding keywords:\n")
    for kw, topics in sorted(dupes.items()):
        print(f"  {kw!r} -> {topics}")
    print(f"\n{len(dupes)} collisions across {len(LIBRARY)} topics.")
    print("Each is acceptable ONLY if the topics are true neighbors and the")
    print("scoring favors the right one on real phrasings — verify with tests.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
