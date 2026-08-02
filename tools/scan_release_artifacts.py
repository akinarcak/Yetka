"""Reject forbidden enterprise paths in packaged Yetka release artifacts."""

import argparse
import re
import tarfile
from pathlib import Path, PurePosixPath


FORBIDDEN_PATH_PARTS = {"xpack", "enterprise", "ee"}
FORBIDDEN_NAMES = re.compile(r"(^|[-_.])(lion|chen|magnus|razor|nec)([-_.]|$)", re.I)


def violations(archive: Path) -> list[str]:
    findings = []
    with tarfile.open(archive, "r:*") as package:
        for member in package.getmembers():
            path = PurePosixPath(member.name)
            lowered_parts = {part.lower() for part in path.parts}
            if lowered_parts & FORBIDDEN_PATH_PARTS:
                findings.append(member.name)
            elif FORBIDDEN_NAMES.search(path.name):
                findings.append(member.name)
    return findings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("archives", nargs="+", type=Path)
    args = parser.parse_args()
    failed = False
    for archive in args.archives:
        findings = violations(archive)
        if findings:
            failed = True
            print(f"{archive}: forbidden content")
            for finding in findings:
                print(f"  {finding}")
        else:
            print(f"{archive}: clean")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
