"""Validate every example JSON file against the AnalyzeResponse schema.

Usage:  python examples/validate.py

Exits non-zero if any file fails. Used as a pre-commit gate so the examples
in this directory cannot drift from the Pydantic schema.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from pydantic import ValidationError

from app.schemas.responses import AnalyzeResponse


def main() -> int:
    examples_dir = Path(__file__).parent
    files = sorted(examples_dir.glob("*.json"))
    if not files:
        print("No JSON files found in examples/.", file=sys.stderr)
        return 1

    failed = 0
    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            AnalyzeResponse.model_validate(payload)
        except (json.JSONDecodeError, ValidationError) as e:
            failed += 1
            print(f"FAIL {path.name}: {type(e).__name__}: {e}", file=sys.stderr)
        else:
            print(f"OK   {path.name}")

    print(f"\n{len(files) - failed}/{len(files)} examples validate.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
