"""Validate product-facing source text against the versioned policy."""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from pathlib import Path


def load_policy(path: Path) -> dict:
    policy = json.loads(path.read_text(encoding="utf-8"))
    if policy.get("version") != 1:
        raise ValueError(f"unsupported policy version: {policy.get('version')}")
    return policy


def is_allowed(relative: str, globs: list[str]) -> bool:
    return any(fnmatch.fnmatch(relative, pattern) for pattern in globs)


def violations(root: Path, policy: dict) -> list[str]:
    terms = [re.compile(re.escape(term), re.I) for term in policy["forbidden_terms"]]
    allowed_lines = [re.compile(pattern, re.I) for pattern in policy.get("allowed_line_patterns", [])]
    findings: list[str] = []
    ignored_dirs = {".git", "node_modules", "lina", "dist", "build"}
    for path in root.rglob("*"):
        if any(part in ignored_dirs for part in path.parts):
            continue
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if is_allowed(relative, policy["allowed_globs"]):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for line_no, line in enumerate(text.splitlines(), 1):
            if any(term.search(line) for term in terms) and not any(pattern.search(line) for pattern in allowed_lines):
                findings.append(f"{relative}:{line_no}:{line.strip()}")
    return findings


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("roots", nargs="+", type=Path)
    parser.add_argument("--policy", type=Path, default=Path("tools/forbidden-content-policy.json"))
    args = parser.parse_args()
    policy = load_policy(args.policy)
    findings = [finding for root in args.roots for finding in violations(root, policy)]
    if findings:
        print("Product-language policy violations (move technical references to an allowlisted path or rewrite UI text):")
        print("\n".join(f"  {finding}" for finding in findings))
        return 1
    print(f"product-language policy v{policy['version']}: clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
