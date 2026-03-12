"""
check_adr_gate.py — ADR-first gate enforcer.

Enforces the project mandate that any change to library source code must be
accompanied by a new ADR file.  Designed for use in CI (GitHub Actions) or
as a local pre-push check.

Exit codes:
  0  — gate passed (no guarded files changed, or ADR present, or skip flag)
  1  — gate failed (guarded files changed with no new ADR)

Usage:
  python tools/check_adr_gate.py \\
      --changed-files "library/my_package/module.py" \\
      --new-files     "docs/adr/ADR-0001-new-decision.md" \\
      --commit-message "feat: add new feature"

  git diff --name-only HEAD~1 | python tools/check_adr_gate.py \\
      --new-files "$(git diff --name-only --diff-filter=A HEAD~1)"
"""

import argparse
import fnmatch
import sys
from pathlib import PurePosixPath


# ---------------------------------------------------------------------------
# Configuration — edit these to match your project layout
# ---------------------------------------------------------------------------

GUARDED_PATTERNS = [
    "__LIBRARY_PATH__/__PACKAGE_NAME__/*.py",
    "__LIBRARY_PATH__/__PACKAGE_NAME__/**/*.py",
]

EXCLUSION_PATTERNS = [
    "*/__pycache__/*",
    "*.pyc",
]

ADR_PATTERN = "__ADR_PATH__/ADR-*.md"

SKIP_TOKEN = "[skip-adr]"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalise(path: str) -> str:
    """Return a forward-slash path string with no leading './' or '/'."""
    p = path.strip().replace("\\", "/").lstrip("./")
    return p


def _split_file_list(raw: str) -> list[str]:
    """Split a whitespace-or-newline-separated file list into individual paths."""
    parts = []
    for token in raw.replace("\n", " ").split(" "):
        token = token.strip()
        if token:
            parts.append(_normalise(token))
    return parts


def _is_excluded(path: str) -> bool:
    """Return True if the path matches any exclusion pattern."""
    return any(fnmatch.fnmatch(path, pat) for pat in EXCLUSION_PATTERNS)


def _is_guarded(path: str) -> bool:
    """Return True if the path is library source code that requires an ADR."""
    if _is_excluded(path):
        return False
    return any(fnmatch.fnmatch(path, pat) for pat in GUARDED_PATTERNS)


def _is_new_adr(path: str) -> bool:
    """Return True if the path looks like a new ADR document."""
    return fnmatch.fnmatch(path, ADR_PATTERN)


# ---------------------------------------------------------------------------
# Core gate logic
# ---------------------------------------------------------------------------

def run_gate(
    changed_files: list[str],
    new_files: list[str],
    commit_message: str,
    skip_flag: bool,
) -> int:
    """
    Evaluate the ADR gate.

    Returns 0 for pass, 1 for fail.
    """
    print("=" * 60)
    print("ADR GATE — checking library source changes")
    print("=" * 60)

    guarded_changed = [f for f in changed_files if _is_guarded(f)]

    print(f"\nChanged files checked : {len(changed_files)}")
    print(f"Guarded files changed : {len(guarded_changed)}")

    if not guarded_changed:
        print("\n[PASS] No library source files were changed. Gate open.")
        return 0

    print("\nGuarded files that changed:")
    for f in guarded_changed:
        print(f"  - {f}")

    if skip_flag:
        print("\n[WARN] --skip-adr flag detected. Gate bypassed. Use only for trivial fixes.")
        return 0

    if SKIP_TOKEN in (commit_message or ""):
        print(f"\n[WARN] '{SKIP_TOKEN}' found in commit message. Gate bypassed.")
        return 0

    new_adrs = [f for f in new_files if _is_new_adr(f)]

    print(f"\nNew ADR files in this commit : {len(new_adrs)}")
    for f in new_adrs:
        print(f"  - {f}")

    if new_adrs:
        print("\n[PASS] Library changes are accompanied by a new ADR. Gate open.")
        return 0

    changed_list = "\n".join(f"  - {f}" for f in guarded_changed)

    message = f"""
ADR-GATE FAILED: library source code was changed without a new ADR.

Changed library files:
{changed_list}

Required action:
  1. Write an ADR in __ADR_PATH__/ADR-NNNN-<decision-title>.md
  2. Document the design decision, alternatives considered, and rationale
  3. Include 'Implementation: __LIBRARY_PATH__/...' link in the ADR
  4. Then commit the code change together with the ADR

To bypass (trivial fixes only): add [skip-adr] to your commit message.
See __ADR_PATH__/index.md for ADR writing guidance.
""".strip()

    print("\n" + message)
    return 1


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="check_adr_gate",
        description=(
            "Enforce the ADR-first mandate: library source changes must be "
            "accompanied by a new ADR document."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--changed-files", metavar="FILES", default="")
    parser.add_argument("--new-files", metavar="FILES", default="")
    parser.add_argument("--commit-message", metavar="MSG", default="")
    parser.add_argument("--skip-adr", action="store_true", default=False)
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.changed_files.strip():
        changed_files = _split_file_list(args.changed_files)
    elif not sys.stdin.isatty():
        changed_files = _split_file_list(sys.stdin.read())
    else:
        changed_files = []

    new_files = _split_file_list(args.new_files) if args.new_files.strip() else []

    exit_code = run_gate(
        changed_files=changed_files,
        new_files=new_files,
        commit_message=args.commit_message,
        skip_flag=args.skip_adr,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
