"""Enable the source-backed risk detection page in the community UI bundle."""

from pathlib import Path


ASSET_DIR = Path("/opt/lina/assets/js")
LICENSE_GATED_RENDER = "disabled:!n.hasValidLicense"
ENABLED_RENDER = "disabled:!1"
COMMUNITY_BUNDLES = ("RiskDetect.*.js", "AccountChangeSecret.*.js")


def main() -> None:
    bundles = [
        bundle
        for pattern in COMMUNITY_BUNDLES
        for bundle in sorted(ASSET_DIR.glob(pattern))
    ]
    if not bundles:
        print("Yetka risk UI bundle not found; leaving the UI unchanged")
        return

    for bundle in bundles:
        content = bundle.read_text(encoding="utf-8")
        if LICENSE_GATED_RENDER not in content:
            print(f"Yetka risk UI already enabled or changed: {bundle.name}")
            continue
        bundle.write_text(
            content.replace(LICENSE_GATED_RENDER, ENABLED_RENDER),
            encoding="utf-8",
        )
        print(f"Enabled Yetka risk detection: {bundle.name}")


if __name__ == "__main__":
    main()
