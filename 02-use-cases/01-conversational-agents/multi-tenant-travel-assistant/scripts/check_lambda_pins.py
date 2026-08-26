#!/usr/bin/env python3
"""Assert `backend/requirements-lambda.txt` pins exactly what `backend/uv.lock` resolved.

**Why this exists as a gate rather than a comment asking people to remember.** The Lambda bundle
installs from the requirements file (`infra/lib/mock-tmc-api.ts`), while the test suite installs
from the lock. Those are two files describing one dependency set, so they drift — and the drift is
invisible: both halves keep working, the tests keep passing, and the only symptom is that the
deployed function runs a version nothing tested. A sample cannot rely on a pipeline noticing, so
`./test.sh` notices.

The other two bundles read their version out of a lock at synth time
(`infra/lib/locked-requirement.ts`) and need no check like this. This one cannot: `pip install -r`
is what makes the file readable to someone auditing what ships, and that is worth a check.

Run with no arguments. Needs no AWS account and no network — it reads two files.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REQUIREMENTS = REPO_ROOT / "backend" / "requirements-lambda.txt"
LOCK = REPO_ROOT / "backend" / "uv.lock"

# `name = "x"` on one line, `version = "y"` on the next, which is how `uv` writes every
# `[[package]]` table. Matching the pair rather than each key separately keeps a version from being
# attributed to the wrong package if the format ever gains a field between them.
LOCK_ENTRY = re.compile(r'name = "([^"]+)"\nversion = "([^"]+)"')


def main() -> int:
    locked = dict(LOCK_ENTRY.findall(LOCK.read_text()))
    if not locked:
        print(f"FAIL  could not parse any package out of {LOCK}", file=sys.stderr)
        return 1

    problems: list[str] = []
    checked = 0
    for line in REQUIREMENTS.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        if "==" not in line:
            problems.append(
                f"{line!r} is not an exact pin — the Lambda bundle must install the versions the "
                f"suite ran against, so ranges are a drift the deploy cannot see"
            )
            continue
        name, _, pinned = line.partition("==")
        name, pinned = name.strip(), pinned.strip()
        expected = locked.get(name)
        checked += 1
        if expected is None:
            problems.append(f"{name} is pinned here but absent from uv.lock")
        elif expected != pinned:
            problems.append(
                f"{name} is pinned to {pinned} but uv.lock resolved {expected} — run "
                f"`uv lock` and update backend/requirements-lambda.txt together"
            )

    if problems:
        for problem in problems:
            print(f"FAIL  {problem}", file=sys.stderr)
        return 1

    print(f"OK    {checked} Lambda pins match backend/uv.lock")
    return 0


if __name__ == "__main__":
    sys.exit(main())
