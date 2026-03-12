"""
check_adr_gate.py — ADR-first gate enforcer.

Enforces the project mandate that any change to library source code must be
accompanied by a new ADR file.  Designed for use in CI (GitHub Actions) or
as a local pre-push check.

Exit codes:
  0  — gate passed (no guarded files changed, or ADR present, or skip flag)
  1  — gate failed (guarded files changed with no new ADR)

Usage:
  python retro/tools/check_adr_gate.py \\
      --changed-files "library/keystone_nfc/monitor.py library/folder_lock.py" \\
      --new-files     "retro/docs/adr/ADR-0013-new-decision.md" \\
      --commit-message "feat: add new feature"

  git diff --name-only HEAD~1 | python retro/tools/check_adr_gate.py \\
      --new-files "$(git diff --name-only --diff-filter=A HEAD~1)"
"""

import argparse
import fnmatch
import sys
from pathlib import PurePosixPath


# ---------------------------------------------------------------------------
# Configuration — patterns that identify "guarded" library files
# ---------------------------------------------------------------------------

#: Glob patterns (relative to repo root, forward-slash separated) that mark a
#: file as library source code requiring an ADR when changed.
GUARDED_PATTERNS = [
    "library/keystone_nfc/*.py",
    "library/folder_lock.py",
]

#: Patterns that must NEVER match a guarded file (excludes build artefacts).
EXCLUSION_PATTERNS = [
    "*/__pycache__/*",
    "*.pyc",
]

#: Pattern for a valid new ADR file.
ADR_PATTERN = "retro/docs/adr/ADR-*.md"

#: Commit-message token that bypasses the gate for trivial fixes.
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
    # Support both space-separated (CLI) and newline-separated (stdin) input.
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

    Parameters
    ----------
    changed_files:
        All files that changed in this commit/push (modified + added + deleted).
    new_files:
        Subset of changed_files that are brand-new (diff-filter=A).
    commit_message:
        The commit message; checked for the [skip-adr] bypass token.
    skip_flag:
        True when --skip-adr is present on the command line.

    Returns
    -------
    int
        0 for pass, 1 for fail.
    """

    print("=" * 60)
    print("ADR GATE — checking library source changes")
    print("=" * 60)

    # --- 1. Identify guarded files that changed ----------------------------
    guarded_changed = [f for f in changed_files if _is_guarded(f)]

    print(f"\nChanged files checked : {len(changed_files)}")
    print(f"Guarded files changed : {len(guarded_changed)}")

    if not guarded_changed:
        print("\n[PASS] No library source files were changed. Gate open.")
        return 0

    print("\nGuarded files that changed:")
    for f in guarded_changed:
        print(f"  - {f}")

    # --- 2. Check bypass flags ---------------------------------------------
    if skip_flag:
        print(
            "\n[WARN] --skip-adr flag detected. "
            "Gate bypassed. Use only for trivial fixes."
        )
        return 0

    if SKIP_TOKEN in (commit_message or ""):
        print(
            f"\n[WARN] '{SKIP_TOKEN}' found in commit message. "
            "Gate bypassed. Use only for trivial fixes."
        )
        return 0

    # --- 3. Check for a new ADR in the commit ------------------------------
    new_adrs = [f for f in new_files if _is_new_adr(f)]

    print(f"\nNew ADR files in this commit : {len(new_adrs)}")
    for f in new_adrs:
        print(f"  - {f}")

    if new_adrs:
        print("\n[PASS] Library changes are accompanied by a new ADR. Gate open.")
        return 0

    # --- 4. Fail with a clear, actionable error ----------------------------
    changed_list = "\n".join(f"  - {f}" for f in guarded_changed)

    message = f"""
ADR-GATE FAILED: library source code was changed without a new ADR.

Changed library files:
{changed_list}

Required action:
  1. Write an ADR in retro/docs/adr/ADR-NNNN-<decision-title>.md
  2. Document the design decision, alternatives considered, and rationale
  3. Include 'Implementation: library/...' link in the ADR
  4. Then commit the code change together with the ADR

To bypass (trivial fixes only): add [skip-adr] to your commit message.
See retro/README.md for ADR writing guidance.
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
    parser.add_argument(
        "--changed-files",
        metavar="FILES",
        default="",
        help=(
            "Space- or newline-separated list of all changed files. "
            "If omitted, the script reads from stdin."
        ),
    )
    parser.add_argument(
        "--new-files",
        metavar="FILES",
        default="",
        help=(
            "Space- or newline-separated list of files that are NEW in this "
            "commit (i.e. added, not just modified). "
            "Used to identify newly created ADR documents."
        ),
    )
    parser.add_argument(
        "--commit-message",
        metavar="MSG",
        default="",
        help=(
            f"The commit message. If it contains '{SKIP_TOKEN}', "
            "the gate is bypassed with a warning."
        ),
    )
    parser.add_argument(
        "--skip-adr",
        action="store_true",
        default=False,
        help="Bypass the ADR gate unconditionally. Use for trivial fixes only.",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    # Collect changed files — CLI arg takes priority; fall back to stdin.
    if args.changed_files.strip():
        changed_files = _split_file_list(args.changed_files)
    elif not sys.stdin.isatty():
        raw_stdin = sys.stdin.read()
        changed_files = _split_file_list(raw_stdin)
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
