"""Replace common Unicode punctuation with ASCII; flag any remaining non-ASCII.

Run as a pre-commit hook. Files are rewritten in place when replacements are
applied; the hook then fails so the user re-stages. If any non-ASCII characters
remain after replacement, the hook fails with the offending lines.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Lossless ASCII equivalents for characters we routinely paste in by accident.
REPLACEMENTS = {
    "‘": "'",  # left single quote
    "’": "'",  # right single quote
    "“": '"',  # left double quote
    "”": '"',  # right double quote
    "–": "--",  # en dash
    "—": "--",  # em dash
    "…": "...",  # horizontal ellipsis
    " ": " ",  # non-breaking space
    "→": "->",  # rightwards arrow
    "←": "<-",  # leftwards arrow
    "⇒": "=>",  # rightwards double arrow
    "·": "*",  # middle dot
    "•": "*",  # bullet
    "×": "x",  # multiplication sign
    "−": "-",  # minus sign
    "§": "section ",  # section sign
    "©": "(c)",  # copyright sign
    "≤": "<=",  # less-than or equal
    "≥": ">=",  # greater-than or equal
    "≠": "!=",  # not equal
}


def process(path: Path) -> tuple[bool, list[str]]:
    """Rewrite ``path`` in place. Return ``(changed, leftover_diagnostics)``."""
    original = path.read_text(encoding="utf-8")
    replaced = original
    for src, dst in REPLACEMENTS.items():
        replaced = replaced.replace(src, dst)

    leftovers: list[str] = []
    for lineno, line in enumerate(replaced.splitlines(), start=1):
        for col, ch in enumerate(line, start=1):
            if ord(ch) > 127:
                leftovers.append(f"{path}:{lineno}:{col}: U+{ord(ch):04X} {ch!r}")

    changed = replaced != original
    if changed:
        path.write_text(replaced, encoding="utf-8")
    return changed, leftovers


def main(argv: list[str]) -> int:
    """Entry point. ``argv`` is the list of file paths from pre-commit."""
    any_changed = False
    all_leftovers: list[str] = []
    for arg in argv:
        path = Path(arg)
        if not path.is_file():
            continue
        try:
            changed, leftovers = process(path)
        except UnicodeDecodeError:
            print(f"skip (not utf-8): {path}", file=sys.stderr)
            continue
        any_changed = any_changed or changed
        all_leftovers.extend(leftovers)

    if all_leftovers:
        print("Non-ASCII characters remain (no ASCII equivalent applied):", file=sys.stderr)
        for line in all_leftovers:
            print(f"  {line}", file=sys.stderr)
        return 1
    if any_changed:
        print("Replaced Unicode punctuation with ASCII; re-stage the files.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
