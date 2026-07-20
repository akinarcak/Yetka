"""Enable the source-backed risk detection page in the community UI bundle."""

from pathlib import Path


ASSET_DIR = Path("/opt/lina/assets/js")
LICENSE_GATED_RENDER = "disabled:!n.hasValidLicense"
ENABLED_RENDER = "disabled:!1"
COMMUNITY_BUNDLES = ("RiskDetect.*.js", "AccountChangeSecret.*.js")
WECHAT_FIELD = 't(y,{label:l.$t(`WeChat`)},{default:c(()=>[t(b,{modelValue:f.object.wechat,"onUpdate:modelValue":d[1]||=e=>f.object.wechat=e},null,8,[`modelValue`])]),_:1},8,[`label`]),'
WECHAT_PAYLOAD = 'wechat:this.object.wechat'


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

    for bundle in sorted(ASSET_DIR.glob("profile.*.js")):
        content = bundle.read_text(encoding="utf-8")
        updated = content.replace(WECHAT_FIELD, "").replace(WECHAT_PAYLOAD, "")
        if updated == content:
            print(f"Yetka profile already cleaned or changed: {bundle.name}")
            continue
        bundle.write_text(updated, encoding="utf-8")
        print(f"Removed WeChat from Yetka profile: {bundle.name}")


if __name__ == "__main__":
    main()
