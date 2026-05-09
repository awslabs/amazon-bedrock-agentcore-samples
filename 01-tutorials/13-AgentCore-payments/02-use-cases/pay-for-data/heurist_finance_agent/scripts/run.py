#!/usr/bin/env python3
"""Run the Heurist finance agent with a single prompt and record artifacts.

Usage:
    python -m heurist_finance_agent.scripts.run
    python -m heurist_finance_agent.scripts.run "Compare BTC and ETH momentum"
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

ARTIFACTS_DIR = Path(__file__).resolve().parents[1] / "artifacts"

DEFAULT_PROMPT = (
    "Use FredMacroAgent to fetch the latest US GDP growth rate and unemployment rate. "
    "Summarize the current macroeconomic environment in a brief markdown report."
)


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Heurist finance agent.")
    parser.add_argument("prompt", nargs="*", help="Custom prompt (defaults to built-in finance prompt).")
    args = parser.parse_args()

    prompt = " ".join(args.prompt).strip() or DEFAULT_PROMPT

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    before = {p.name for p in ARTIFACTS_DIR.glob("*") if p.is_file()}

    from heurist_finance_agent.agent import invoke_agent

    result = invoke_agent(prompt)

    after = {p.name for p in ARTIFACTS_DIR.glob("*") if p.is_file()}
    new_files = sorted(after - before)

    # Save transcript
    stamp = _utc_stamp()
    transcript_path = ARTIFACTS_DIR / f"run_{stamp}.txt"
    transcript_path.write_text(str(result))

    print(json.dumps({
        "artifact_dir": str(ARTIFACTS_DIR),
        "new_files": new_files,
        "transcript_path": str(transcript_path),
        "result_preview": str(result)[:4000],
    }, indent=2))


if __name__ == "__main__":
    main()
