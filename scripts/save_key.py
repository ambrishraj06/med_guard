# scripts/save_key.py
"""
Safely write your Groq key into .streamlit/secrets.toml.

Run from E:\\MedGuard:
    venv\\Scripts\\python scripts\\save_key.py

The key is read as hidden input (nothing echoes on screen) and written ONLY to
the git-ignored secrets file. It is never printed, never stored anywhere else.
"""

import getpass
from pathlib import Path

TARGET = Path(__file__).resolve().parents[1] / ".streamlit" / "secrets.toml"


def main() -> None:
    print("MedGuard key setup")
    print("-" * 40)
    print("Paste your Groq key (from console.groq.com/keys) and press Enter.")
    print("Input is hidden while you paste.\n")
    key = getpass.getpass("Groq key: ").strip()

    if not key.startswith("gsk_"):
        print("\n⚠️  That doesn't look like a Groq key (they start with 'gsk_'). Nothing was saved.")
        raise SystemExit(1)
    if len(key) < 40:
        print("\n⚠️  That key looks too short — did the paste get cut off? Nothing was saved.")
        raise SystemExit(1)

    TARGET.write_text(f'GROQ_API_KEY = "{key}"\n', encoding="utf-8")
    print(f"\n✅ Saved to {TARGET}")
    print("   (This file is git-ignored — it will never be committed or uploaded.)")


if __name__ == "__main__":
    main()
