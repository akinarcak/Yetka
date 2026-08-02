from pathlib import Path
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[2]


class ContainerSecurityTests(TestCase):
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
