"""Generate `shared/generated/cards.ts` from `shared/cards.py`.

    python3 scripts/generate_card_types.py

**Why codegen rather than two hand-written files.** Cards cross a language boundary — Python tools
emit them, the TypeScript frontend renders one component per `card_type`. Two hand-maintained
definitions drift, and drift here is the worst kind: a card type the frontend does not recognise
renders as **nothing**, with no error anywhere. The user sees a missing tile and nobody sees a stack
trace.

So Python is the source of truth (the tools are what actually construct cards) and TypeScript is
derived. Run this after changing `cards.py`; CI should fail if the committed output is stale.

Deliberately emitted as **string-literal unions plus a discriminated union**, not classes: the
frontend needs exhaustiveness checking on `card_type` so that adding a card type produces a compile
error in the renderer's switch, rather than a silently unhandled case.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# Inlined rather than via a `REPO_ROOT` constant so that nothing but the `sys.path` idiom sits
# between the imports — `cards` is only importable after it.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from cards import ALLOWED_ACTIONS, REQUIRED_DATA, Action, CardType

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = REPO_ROOT / "shared/generated/cards.ts"

HEADER = """// AUTO-GENERATED from shared/cards.py by scripts/generate_card_types.py
// Do not edit by hand — run the script instead.
//
// Cards cross a language boundary: Python tools emit them, this file types the renderer. The
// generated `CardType` union is what makes the renderer's switch exhaustive, so adding a card type
// in Python produces a *compile error* here rather than a silently unrendered tile.
"""


def _ts_union(values: list[str]) -> str:
    return "\n  | ".join(f"'{value}'" for value in values)


def main() -> int:
    card_types = sorted(str(member) for member in CardType)
    actions = sorted(str(member) for member in Action)

    lines = [HEADER]
    lines.append("export type CardType =\n  | " + _ts_union(card_types) + ";\n")
    lines.append(
        "/** Closed registry: the frontend must refuse an action outside this union. */\n"
        "export type ActionId =\n  | " + _ts_union(actions) + ";\n"
    )
    lines.append(
        "export interface CardAction<P = Record<string, unknown>> {\n"
        "  id: ActionId;\n"
        "  label: string;\n"
        "  payload: P;\n"
        "}\n"
    )
    lines.append(
        "export interface Card<D = Record<string, unknown>> {\n"
        "  card_type: CardType;\n"
        "  /** Stable, referenceable — the model may cite it as `[card:<id>]`. */\n"
        "  id: string;\n"
        "  data: D;\n"
        "  actions?: CardAction[];\n"
        "}\n"
    )

    # Required keys per type, exported so the renderer can assert in dev builds rather than
    # discovering a missing field visually.
    required_entries = ",\n".join(
        (
            f"  {str(card_type)!r}: "
            f"[{', '.join(repr(key) for key in sorted(REQUIRED_DATA[card_type]))}]"
        ).replace("'", '"')
        for card_type in CardType
    )
    lines.append(
        "/** Required `data` keys per card type — a minimum, not a closed schema. */\n"
        "export const REQUIRED_DATA: Record<CardType, readonly string[]> = {\n"
        + required_entries
        + ",\n} as const;\n"
    )

    allowed_entries = ",\n".join(
        (
            f"  {str(card_type)!r}: "
            f"[{', '.join(repr(str(a)) for a in sorted(ALLOWED_ACTIONS[card_type], key=str))}]"
        ).replace("'", '"')
        for card_type in CardType
    )
    lines.append(
        "/** Which actions each card type may carry. */\n"
        "export const ALLOWED_ACTIONS: Record<CardType, readonly ActionId[]> = {\n"
        + allowed_entries
        + ",\n} as const;\n"
    )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines))
    print(f"wrote {OUT_PATH.relative_to(REPO_ROOT)}")
    print(f"  {len(card_types)} card types, {len(actions)} actions")

    # Format if prettier is available, so the committed file matches the frontend's style and a
    # regeneration does not produce a noisy diff. Best-effort: a missing prettier is not an error.
    try:
        subprocess.run(
            ["npx", "--no-install", "prettier", "--write", str(OUT_PATH)],
            check=True,
            capture_output=True,
        )
        print("  formatted with prettier")
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
