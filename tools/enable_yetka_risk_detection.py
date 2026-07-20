"""Enable the source-backed risk detection page in the community UI bundle."""

from pathlib import Path
import re
import shutil


ASSET_DIR = Path("/opt/lina/assets/js")
LICENSE_GATED_RENDER = "disabled:!n.hasValidLicense"
ENABLED_RENDER = "disabled:!1"
COMMUNITY_BUNDLES = ("RiskDetect.*.js", "AccountChangeSecret.*.js")
WECHAT_FIELD = 't(y,{label:l.$t(`WeChat`)},{default:c(()=>[t(b,{modelValue:f.object.wechat,"onUpdate:modelValue":d[1]||=e=>f.object.wechat=e},null,8,[`modelValue`])]),_:1},8,[`label`]),'
WECHAT_PAYLOAD = 'wechat:this.object.wechat'
UPSTREAM_LICENSE_URL = 'https://github.com/jumpserver/jumpserver'
LICENSE_STORE_GATE = 't.XPACK_ENABLED&&(e.hasValidLicense=t.XPACK_LICENSE_IS_VALID)'
PAGE_DISABLED_OVERLAY = 'm.disabled?(i(),e(`div`,oe,'
NGINX_UI_LOCATION = '    location /ui/ {'
NGINX_UI_LOCATION_PATCH = '    location /ui/ {\n        add_header Cache-Control "no-store" always;'


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
        if bundle.name == "profile.Yetka.js":
            continue
        content = bundle.read_text(encoding="utf-8")
        updated = content.replace(WECHAT_FIELD, "").replace(WECHAT_PAYLOAD, "")
        if updated == content:
            print(f"Yetka profile already cleaned or changed: {bundle.name}")
            continue
        bundle.write_text(updated, encoding="utf-8")
        print(f"Removed WeChat from Yetka profile: {bundle.name}")

    profile_sources = [p for p in sorted(ASSET_DIR.glob("profile.*.js")) if p.name != "profile.Yetka.js"]
    if profile_sources:
        target = ASSET_DIR / "profile.Yetka.js"
        shutil.copyfile(profile_sources[0], target)
        print("Published cache-busted Yetka profile bundle: profile.Yetka.js")

    for bundle in sorted(ASSET_DIR.glob("License.*.js")):
        content = bundle.read_text(encoding="utf-8")
        updated = re.sub(
            r"quickActions:\[\{.*?\}\]\}\},computed",
            "quickActions:[]}},computed",
            content,
            count=1,
        )
        updated = updated.replace(
            "mounted(){this.quickActions[0].attrs.disabled=!this.publicSettings.XPACK_ENABLED,",
            "mounted(){",
        )
        updated = updated.replace(UPSTREAM_LICENSE_URL, "https://github.com/akinarcak/Yetka")
        updated = updated.replace("[` JumpServer `]", "[` Yetka `]")
        if updated == content:
            print(f"Yetka license page already cleaned or changed: {bundle.name}")
            continue
        bundle.write_text(updated, encoding="utf-8")
        print(f"Cleaned Yetka license page: {bundle.name}")

    for bundle in sorted(ASSET_DIR.glob("index.*.js")):
        content = bundle.read_text(encoding="utf-8")
        updated = content.replace(LICENSE_STORE_GATE, "e.hasValidLicense=!0")
        updated = re.sub(r"profile\.[A-Za-z0-9_-]+\.js", "profile.Yetka.js", updated)
        if updated == content:
            print(f"Yetka license state already patched or changed: {bundle.name}")
            continue
        bundle.write_text(updated, encoding="utf-8")
        print(f"Enabled GPL features without a license gate: {bundle.name}")

    for bundle in sorted(ASSET_DIR.glob("Page.*.js")):
        content = bundle.read_text(encoding="utf-8")
        updated = content.replace(PAGE_DISABLED_OVERLAY, "!1?(i(),e(`div`,oe,")
        if updated == content:
            print(f"Yetka enterprise overlay already disabled or changed: {bundle.name}")
            continue
        bundle.write_text(updated, encoding="utf-8")
        print(f"Disabled Yetka enterprise overlay: {bundle.name}")

    nginx_config = Path("/etc/nginx/conf.d/default.conf")
    if nginx_config.exists():
        content = nginx_config.read_text(encoding="utf-8")
        if NGINX_UI_LOCATION in content and NGINX_UI_LOCATION_PATCH not in content:
            nginx_config.write_text(
                content.replace(NGINX_UI_LOCATION, NGINX_UI_LOCATION_PATCH, 1),
                encoding="utf-8",
            )
            print("Disabled browser caching for Yetka UI assets")


if __name__ == "__main__":
    main()
