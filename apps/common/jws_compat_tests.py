# -*- coding: utf-8 -*-
"""Tests for the in-repo JWS reader that replaces itsdangerous' removed one.

The point of `common.utils.jws_compat` is that tokens already on disk stay
readable. So the load-bearing test is not the round trip -- it is the
differential one: for the same inputs, does this produce the same bytes as
itsdangerous 1.1.0, and can it read what that library wrote?

Those differential tests run only while a 1.x itsdangerous is installed. Once
the dependency moves to 2.x the classes are gone and they skip themselves,
which is the intended end state: they exist to prove the replacement before the
swap, not to hold the old library in place forever.
"""
import time
import unittest

from django.test import SimpleTestCase

from common.utils import jws_compat

try:  # itsdangerous 1.x only
    from itsdangerous import (
        JSONWebSignatureSerializer,
        TimedJSONWebSignatureSerializer,
    )
    HAS_LEGACY_ITSDANGEROUS = True
except ImportError:  # pragma: no cover - taken once the dependency moves
    HAS_LEGACY_ITSDANGEROUS = False

KEY = 'a-secret-key-for-tests'

# Values chosen to cover what the signer is actually used for: passwords and
# encrypted field contents, which are arbitrary text, not identifiers.
VALUES = [
    'plain',
    '',
    'boşluklu değer',            # non-ASCII: ensure_ascii=False changes bytes
    'ünïcode ✓ 秘密',
    'a' * 500,
    'quote"and\\backslash',
    '{"looks": "like json"}',
]


class JwsRoundTripTests(SimpleTestCase):
    def test_round_trip_preserves_the_value(self):
        for value in VALUES:
            with self.subTest(value=value[:20]):
                token = jws_compat.dumps(value, KEY)
                self.assertEqual(jws_compat.loads(token, KEY), value)

    def test_a_different_key_does_not_verify(self):
        token = jws_compat.dumps('secret', KEY)
        with self.assertRaises(jws_compat.BadSignature):
            jws_compat.loads(token, 'another-key')

    def test_tampered_payload_does_not_verify(self):
        token = jws_compat.dumps('secret', KEY)
        header, payload, signature = token.split(b'.')
        tampered = b'.'.join([header, payload[:-1] + b'X', signature])
        with self.assertRaises(jws_compat.BadSignature):
            jws_compat.loads(tampered, KEY)

    def test_malformed_tokens_are_rejected(self):
        for bad in (b'', b'no-dots', b'only.two', b'a.b.c.d'):
            with self.subTest(token=bad):
                with self.assertRaises(jws_compat.BadSignature):
                    jws_compat.loads(bad, KEY)

    def test_unknown_algorithm_is_rejected(self):
        # 'none' is an algorithm itsdangerous accepted. Accepting it here would
        # mean an unsigned token verifies, so it must not be supported.
        token = jws_compat.dumps('secret', KEY)
        header = jws_compat._b64_encode(b'{"alg":"none"}')
        forged = header + b'.' + token.split(b'.')[1] + b'.'
        with self.assertRaises(jws_compat.BadSignature):
            jws_compat.loads(forged, KEY)


class TimedJwsTests(SimpleTestCase):
    def test_round_trip_within_the_window(self):
        token = jws_compat.dumps_timed('secret', KEY, expires_in=3600)
        self.assertEqual(jws_compat.loads_timed(token, KEY), 'secret')

    def test_expired_token_raises(self):
        issued = int(time.time()) - 7200
        token = jws_compat.dumps_timed('secret', KEY, expires_in=3600, now=issued)
        with self.assertRaises(jws_compat.SignatureExpired):
            jws_compat.loads_timed(token, KEY)

    def test_untimed_token_has_no_expiry_to_check(self):
        token = jws_compat.dumps('secret', KEY)
        with self.assertRaises(jws_compat.BadSignature):
            jws_compat.loads_timed(token, KEY)


@unittest.skipUnless(
    HAS_LEGACY_ITSDANGEROUS,
    'itsdangerous 1.x is not installed; the differential check no longer applies',
)
class DifferentialAgainstItsdangerousTests(SimpleTestCase):
    """The tests that actually justify the replacement."""

    def test_bytes_are_identical_for_the_untimed_serializer(self):
        reference = JSONWebSignatureSerializer(KEY, algorithm_name='HS256')
        for value in VALUES:
            with self.subTest(value=value[:20]):
                self.assertEqual(
                    jws_compat.dumps(value, KEY, algorithm='HS256'),
                    reference.dumps(value),
                )

    def test_can_read_what_itsdangerous_wrote(self):
        reference = JSONWebSignatureSerializer(KEY, algorithm_name='HS256')
        for value in VALUES:
            with self.subTest(value=value[:20]):
                self.assertEqual(
                    jws_compat.loads(reference.dumps(value), KEY), value
                )

    def test_itsdangerous_can_read_what_this_writes(self):
        # Both directions, so a deployment mid-upgrade stays consistent.
        reference = JSONWebSignatureSerializer(KEY, algorithm_name='HS256')
        for value in VALUES:
            with self.subTest(value=value[:20]):
                self.assertEqual(
                    reference.loads(jws_compat.dumps(value, KEY, algorithm='HS256')),
                    value,
                )

    def test_bytes_are_identical_for_the_timed_serializer(self):
        issued = 1785919988
        reference = TimedJSONWebSignatureSerializer(KEY, expires_in=3600)
        reference.now = lambda: issued
        for value in VALUES:
            with self.subTest(value=value[:20]):
                self.assertEqual(
                    jws_compat.dumps_timed(value, KEY, 3600, now=issued),
                    reference.dumps(value),
                )

    def test_can_read_what_the_timed_serializer_wrote(self):
        reference = TimedJSONWebSignatureSerializer(KEY, expires_in=3600)
        for value in VALUES:
            with self.subTest(value=value[:20]):
                self.assertEqual(
                    jws_compat.loads_timed(reference.dumps(value), KEY), value
                )

    def test_other_hmac_algorithms_match(self):
        for algorithm in ('HS256', 'HS384', 'HS512'):
            reference = JSONWebSignatureSerializer(KEY, algorithm_name=algorithm)
            with self.subTest(algorithm=algorithm):
                self.assertEqual(
                    jws_compat.dumps('value', KEY, algorithm=algorithm),
                    reference.dumps('value'),
                )


@unittest.skipUnless(
    HAS_LEGACY_ITSDANGEROUS,
    'itsdangerous 1.x is not installed; the differential check no longer applies',
)
class SignerReadsExistingDataTests(SimpleTestCase):
    """The property that data at rest depends on.

    `common.db.utils.decrypt` falls back to `signer.unsign` for rows written
    before the crypto migration, and a terminal data migration reads values
    written by a much older release. Those bytes were produced by itsdangerous.
    If `Signer` stops reading them the failure is silent -- `unsign` returns
    None on a bad signature, so the caller sees an empty value rather than an
    error.
    """

    def test_signer_reads_tokens_written_by_itsdangerous(self):
        from common.utils.encode import Signer

        secret = 'a-different-secret-for-the-signer'
        legacy = JSONWebSignatureSerializer(secret, algorithm_name='HS256')
        # Signer is a singleton, so constructing it does not necessarily apply
        # the key. Setting it explicitly is what makes this deterministic.
        signer = Signer(secret)
        signer.secret_key = secret

        for value in VALUES:
            with self.subTest(value=value[:20]):
                self.assertEqual(signer.unsign(legacy.dumps(value)), value)

    def test_signer_output_is_unchanged(self):
        from common.utils.encode import Signer

        secret = 'a-different-secret-for-the-signer'
        signer = Signer(secret)
        signer.secret_key = secret
        legacy = JSONWebSignatureSerializer(secret, algorithm_name='HS256')

        for value in VALUES:
            with self.subTest(value=value[:20]):
                self.assertEqual(signer.sign(value), legacy.dumps(value).decode())
