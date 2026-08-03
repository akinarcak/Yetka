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
    parser.add_argument("--lina", type=Path, help="Lina source root for product-language scanning")
    args = parser.parse_args()
    checks = [
        ("component lock", [sys.executable, "tools/validate_components_lock.py", "--lock", "components.lock.yml"]),
        ("provenance and security tests", [sys.executable, "-m", "unittest", "tools.tests.test_release_provenance", "tools.tests.test_product_language_policy"]),
    ]
    if args.lina:
        checks.append(("Lina product language", [sys.executable, "tools/validate_product_language.py", str(args.lina / "src" / "views"), str(args.lina / "src" / "layout"), str(args.lina / "src" / "i18n"), "--policy", "tools/forbidden-content-policy.json"]))
    return 0 if all(run(label, command) for label, command in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
