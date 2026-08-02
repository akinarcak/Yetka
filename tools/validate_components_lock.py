"""Validate immutable component inputs and generate a release manifest."""

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path


SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
REQUIRED_FIELDS = {"repository", "commit", "version", "license", "artifact"}


def load_lock(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError("Unsupported component lock schema")
    components = data.get("components")
    if not isinstance(components, dict) or not components:
        raise ValueError("Component lock has no components")
    for name, component in components.items():
        missing = REQUIRED_FIELDS - set(component)
        if missing:
            raise ValueError(f"{name} is missing fields: {', '.join(sorted(missing))}")
        if not SHA_PATTERN.fullmatch(component["commit"]):
            raise ValueError(f"{name} commit is not an immutable SHA-1")
        if not component["repository"].startswith("https://github.com/akinarcak/"):
            raise ValueError(f"{name} repository is outside the approved Yetka organization")
        if component["license"] != "GPL-3.0-or-later":
            raise ValueError(f"{name} license metadata is not GPL-3.0-or-later")
    return data


def git_head(path: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(path), "rev-parse", "HEAD"], text=True
    ).strip()


def validate_checkouts(data: dict, checkout_root: Path) -> None:
    for name, component in data["components"].items():
        actual = git_head(checkout_root / name)
        if actual != component["commit"]:
            raise ValueError(
                f"{name} checkout mismatch: expected {component['commit']}, got {actual}"
            )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def release_manifest(data: dict, artifacts_dir: Path, release_tag: str, core_commit: str) -> dict:
    if not SHA_PATTERN.fullmatch(core_commit):
        raise ValueError("Core commit is not an immutable SHA-1")
    components = {
        "core": {
            "repository": "https://github.com/akinarcak/Yetka.git",
            "commit": core_commit,
            "version": release_tag,
            "license": "GPL-3.0-or-later",
        }
    }
    for name, locked in data["components"].items():
        artifact_name = locked["artifact"].format(release_tag=release_tag)
        artifact = artifacts_dir / artifact_name
        if not artifact.is_file():
            raise ValueError(f"Missing release artifact: {artifact_name}")
        components[name] = {
            "repository": locked["repository"],
            "commit": locked["commit"],
            "version": locked["version"],
            "license": locked["license"],
            "artifact": artifact_name,
            "sha256": sha256(artifact),
        }
    return {"schema_version": 1, "release": release_tag, "components": components}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lock", type=Path, default=Path("components.lock.yml"))
    parser.add_argument("--checkout-root", type=Path)
    parser.add_argument("--artifacts-dir", type=Path)
    parser.add_argument("--release-tag")
    parser.add_argument("--core-commit")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    data = load_lock(args.lock)
    if args.checkout_root:
        validate_checkouts(data, args.checkout_root)
    if args.output:
        if not all((args.artifacts_dir, args.release_tag, args.core_commit)):
            parser.error("manifest output requires artifacts-dir, release-tag and core-commit")
        manifest = release_manifest(
            data, args.artifacts_dir, args.release_tag, args.core_commit
        )
        args.output.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
