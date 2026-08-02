from pathlib import Path
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[2]


class ContainerSecurityTests(TestCase):
    def test_entrypoint_does_not_mutate_frontend_assets(self):
        entrypoint = (ROOT / "entrypoint.sh").read_text(encoding="utf-8")
        self.assertNotIn("enable_yetka_risk_detection.py", entrypoint)
        self.assertNotIn("inject_yetka_maintenance_alert.py", entrypoint)

    def test_container_build_uses_only_digest_pinned_official_python_base(self):
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        base = (ROOT / "Dockerfile-base").read_text(encoding="utf-8")
        for content in (dockerfile, base):
            self.assertIn("python:3.14-slim-trixie@sha256:", content)
            self.assertNotIn("jumpserver/core-base", content)
        self.assertNotIn("COPY --from=stage-build /opt /opt", dockerfile)

    def test_runtime_is_non_root_and_has_explicit_writable_paths(self):
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("USER 10001:10001", dockerfile)
        self.assertIn('VOLUME ["/opt/jumpserver/data"]', dockerfile)
        self.assertIn("ln -s /tmp/yetka /opt/jumpserver/tmp", dockerfile)
        runtime = dockerfile.split("FROM ${PYTHON_BASE_IMAGE} AS runtime", 1)[1]
        self.assertNotIn("cron", runtime)

    def test_production_dependency_groups_exclude_xpack_and_dev(self):
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn('default-groups = []', pyproject)
        self.assertIn("--no-dev --no-group xpack", dockerfile)

    def test_container_does_not_disable_ssh_host_key_verification(self):
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        forbidden = (
            "StrictHostKeyChecking no",
            "UserKnownHostsFile /dev/null",
            "Ciphers +aes128-cbc",
            "KexAlgorithms +diffie-hellman-group1-sha1",
            "HostKeyAlgorithms +ssh-rsa",
        )
        for directive in forbidden:
            with self.subTest(directive=directive):
                self.assertNotIn(directive, dockerfile)

    def test_base_build_does_not_download_unversioned_latest_binary(self):
        dockerfile = (ROOT / "Dockerfile-base").read_text(encoding="utf-8")
        self.assertNotIn("/releases/latest/", dockerfile)
