"""Run the local release-hardening checks as one reproducible command."""

import argparse
import subprocess
import sys
from pathlib import Path


def run(label: str, command: list[str]) -> bool:
    print(f"== {label} ==")
    result = subprocess.run(command, check=False)
    if result.returncode:
        print(f"FAILED: {label}. Fix the command above before releasing.")
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lina", type=Path, help="Lina source root (compatibility alias)")
    parser.add_argument("--component", action="append", default=[], metavar="NAME=PATH", help="component source root to scan; repeatable")
    args = parser.parse_args()
    checks = [
        ("component lock", [sys.executable, "tools/validate_components_lock.py", "--lock", "components.lock.yml"]),
        ("provenance and security tests", [sys.executable, "-m", "unittest", "tools.tests.test_release_provenance", "tools.tests.test_product_language_policy"]),
    ]
    components = list(args.component)
    if args.lina:
        components.append(f"lina={args.lina}")
    for component in components:
        try:
            name, raw_path = component.split("=", 1)
        except ValueError:
            parser.error(f"invalid component '{component}', expected NAME=PATH")
        root = Path(raw_path)
        checks.append((f"{name} product language", [sys.executable, "tools/validate_product_language.py", str(root), "--policy", "tools/forbidden-content-policy.json"]))
    return 0 if all(run(label, command) for label, command in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
