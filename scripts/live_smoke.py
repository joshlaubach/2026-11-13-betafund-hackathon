"""One live drafting call for power_rule level 2, to check the model path end to end.

Exits 3 with a message when no API key is set. Saves the run to replay/power_rule_L2.json
only when at least 3 drafts were accepted by the checker. Never prints the key.
Run as: python scripts/live_smoke.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv  # noqa: E402

from core.drafter import (  # noqa: E402
    DEFAULT_EFFORT,
    DEFAULT_MODEL,
    TOPIC,
    Draft,
    LiveSource,
    generate,
    save_run,
)

NO_KEY_EXIT = 3
LEVEL = 2
COUNT = 3
N_DRAFTS = 5
REPLAY_PATH = REPO_ROOT / "replay" / "power_rule_L2.json"


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    if not os.environ.get("ANTHROPIC_API_KEY", "").strip():
        print("no API key set (save .env)")
        return NO_KEY_EXIT
    source = LiveSource(
        os.environ.get("ANTHROPIC_MODEL", DEFAULT_MODEL),
        os.environ.get("ANTHROPIC_EFFORT", DEFAULT_EFFORT),
    )
    result = generate(TOPIC, LEVEL, source, count=COUNT, n_drafts=N_DRAFTS)
    print(f"source: {result['source']}")
    print(f"status: {result['status']}")
    print(
        f"drafted={result['drafted']} accepted={len(result['accepted'])} "
        f"rejected={len(result['rejected'])} duplicates={len(result['duplicates'])} "
        f"shortfall={result['shortfall']}"
    )
    print(f"tokens: {result['tokens']}")
    if result["status"] != "ok":
        print(f"error: {result['error']}")
        return 1
    if len(result["accepted"]) < COUNT:
        print(f"not saved: {len(result['accepted'])} accepted, need {COUNT}")
        return 0
    drafts = [Draft.model_validate(item) for item in result["drafts"]]
    save_run(REPLAY_PATH, TOPIC, LEVEL, drafts, source.source)
    print(f"saved run to {REPLAY_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
