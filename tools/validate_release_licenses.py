"""Fail closed when release metadata or component license files are missing."""

import argparse
import tarfile
from pathlib import Path

from tools.validate_components_lock import load_lock

LICENSE_NAMES = {"license", "license.txt", "copying", "copying.txt"}


def archive_has_license(archive: Path) -> bool:
    with tarfile.open(archive, "r:*") as package:
        return any(Path(member.name).name.lower() in LICENSE_NAMES
                   for member in package.getmembers())


def validate(lock_path: Path, archives: list[Path]) -> None:
    lock = load_lock(lock_path)
    for component in lock["components"].values():
        if component["license"] != "GPL-3.0-or-later":
            raise ValueError("release contains a non-GPL component license")
    for archive in archives:
        if not archive_has_license(archive):
            raise ValueError(f"{archive} has no LICENSE/COPYING file")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("archives", nargs="+", type=Path)
    args = parser.parse_args()
    validate(args.lock, args.archives)


if __name__ == "__main__":
    main()
