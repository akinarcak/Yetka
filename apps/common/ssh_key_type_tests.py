# -*- coding: utf-8 -*-
"""Tests for which SSH key types this project accepts.

DSA was removed because paramiko 5.0.0 dropped DSSKey and there is no paramiko
that has both DSA and the current security fixes. What is worth asserting is
not only that DSA is gone, but that it is gone from *both* key paths.

This project parses keys two ways: `ssh_key_string_to_obj` uses paramiko, and
`validate_ssh_private_key` / `parse_ssh_private_key_str` use cryptography.
cryptography still supports DSA perfectly well. If only the paramiko side had
been changed, a DSA key would pass validation when an operator saved it and
then fail later, when something tried to connect with it -- moving the error
from the form to production. The last test here is the one that keeps those two
answers in agreement.
"""
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import dsa, ed25519, rsa
from django.test import SimpleTestCase

from common.utils.encode import (
    ssh_key_gen,
    ssh_key_string_to_obj,
    validate_ssh_private_key,
)


def _pem(private_key):
    # TraditionalOpenSSL, not PKCS8. paramiko reads "BEGIN RSA PRIVATE KEY"
    # and "BEGIN DSA PRIVATE KEY"; it does not read PKCS8. Using PKCS8 would
    # make the DSA test pass for the wrong reason -- rejected on format rather
    # than on key type -- and it would say nothing about DSA support.
    return private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ).decode()


def _openssh(private_key):
    return private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.OpenSSH,
        serialization.NoEncryption(),
    ).decode()


class SupportedKeyTypeTests(SimpleTestCase):
    def test_rsa_is_still_accepted_by_both_paths(self):
        key = _pem(rsa.generate_private_key(public_exponent=65537, key_size=2048))
        self.assertTrue(validate_ssh_private_key(key))
        self.assertIsNotNone(ssh_key_string_to_obj(key))

    def test_ed25519_is_still_accepted(self):
        key = _openssh(ed25519.Ed25519PrivateKey.generate())
        self.assertTrue(validate_ssh_private_key(key))
        self.assertIsNotNone(ssh_key_string_to_obj(key))

    def test_generated_key_round_trips(self):
        private_key, public_key = ssh_key_gen()
        self.assertTrue(validate_ssh_private_key(private_key))
        self.assertTrue(public_key.startswith('ssh-rsa '))


class DsaIsRejectedTests(SimpleTestCase):
    def setUp(self):
        self.dsa_key = _pem(dsa.generate_private_key(key_size=1024))

    def test_paramiko_path_rejects_dsa(self):
        with self.assertRaises(ValueError):
            ssh_key_string_to_obj(self.dsa_key)

    def test_generating_a_dsa_key_is_refused(self):
        with self.assertRaises(IOError):
            ssh_key_gen(type='dsa')

    def test_validation_rejects_dsa_too(self):
        # The point of the change: cryptography can still read this key, so
        # without an explicit check it would be accepted here and rejected by
        # the paramiko path later. Both paths must give the same answer.
        self.assertFalse(validate_ssh_private_key(self.dsa_key))
