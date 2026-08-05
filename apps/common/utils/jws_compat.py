# -*- coding: utf-8 -*-
"""JWS reader and writer compatible with itsdangerous 1.1.0.

itsdangerous 2.0 removed `JSONWebSignatureSerializer` and
`TimedJSONWebSignatureSerializer`. `Signer` in `common.utils.encode` is built on
both, and `signer.unsign` is not only used for fresh tokens: `common.db.utils`
calls it to read values written before the crypto migration, and
`terminal.migrations.0003` reads values written by a much older release. Those
bytes are on disk. Swapping to a 2.x serializer would not fail loudly -- it
would quietly stop being able to read them.

So the format is reproduced here rather than replaced. Everything below matches
what itsdangerous 1.1.0 emits, verified against the installed library in
`common.jws_compat_tests` for as long as a 1.x is present.

The format, for the record:

    base64url(header) . base64url(payload) . base64url(signature)

with padding stripped, where header is `{"alg": <name>}` for the untimed
serializer and `{"alg": <name>, "iat": <int>, "exp": <int>}` for the timed one,
payload is the JSON-encoded value, and the signature is an HMAC over
`header.payload`. JSON is written with `ensure_ascii=False` and
`(",", ":")` separators, so non-ASCII values are stored as UTF-8 rather than
escaped -- getting that wrong changes the bytes for any non-ASCII secret.

One detail worth stating because it looks like an omission: itsdangerous uses
`key_derivation='none'` for JWS, so the HMAC key is the secret key itself with
no salt applied. That is the library's behaviour, not a simplification.
"""
import hashlib
import hmac
import json
import time

DEFAULT_ALGORITHM = 'HS256'

_DIGESTS = {
    'HS256': hashlib.sha256,
    'HS384': hashlib.sha384,
    'HS512': hashlib.sha512,
}


class BadSignature(Exception):
    """The token is malformed, or its signature does not match."""

    def __init__(self, message, payload=None):
        super().__init__(message)
        self.payload = payload


class BadHeader(BadSignature):
    """The header is not usable -- unknown algorithm, or a bad expiry."""


class SignatureExpired(BadSignature):
    """The signature was valid but its expiry has passed."""


def _want_bytes(value):
    return value.encode('utf-8') if isinstance(value, str) else value


def _b64_encode(raw):
    import base64
    return base64.urlsafe_b64encode(raw).rstrip(b'=')


def _b64_decode(raw):
    import base64
    return base64.urlsafe_b64decode(raw + b'=' * (-len(raw) % 4))


def _json_dumps(obj):
    # ensure_ascii=False and compact separators, matching itsdangerous'
    # _CompactJSON. Both matter for byte compatibility.
    return json.dumps(obj, ensure_ascii=False, separators=(',', ':'))


def _signature(key, signing_input, algorithm):
    try:
        digest = _DIGESTS[algorithm]
    except KeyError:
        raise BadHeader('Algorithm not supported: %s' % algorithm)
    return hmac.new(_want_bytes(key), signing_input, digest).digest()


def _split(token):
    token = _want_bytes(token)
    parts = token.rsplit(b'.', 1)
    if len(parts) != 2:
        raise BadSignature('No "." found in value')
    signing_input, signature = parts
    if signing_input.count(b'.') != 1:
        raise BadSignature('Malformed token')
    return signing_input, signature


def dumps(value, key, algorithm=DEFAULT_ALGORITHM, header_fields=None):
    """Serialize `value` exactly as itsdangerous 1.1.0 would."""
    if algorithm not in _DIGESTS:
        raise BadHeader('Algorithm not supported: %s' % algorithm)
    # `alg` is written first and the extra fields follow, because that is the
    # order itsdangerous builds the dict in and JSON preserves it. Reversing it
    # produces a valid token that is not the same bytes.
    header = {'alg': algorithm}
    if header_fields:
        header.update(header_fields)

    encoded_header = _b64_encode(_want_bytes(_json_dumps(header)))
    encoded_payload = _b64_encode(_want_bytes(_json_dumps(value)))
    signing_input = encoded_header + b'.' + encoded_payload
    signature = _signature(key, signing_input, algorithm)
    return signing_input + b'.' + _b64_encode(signature)


def loads(token, key, return_header=False):
    """Verify and decode a token written by itsdangerous 1.1.0 or by `dumps`."""
    signing_input, signature = _split(token)
    encoded_header, encoded_payload = signing_input.split(b'.', 1)

    try:
        header = json.loads(_b64_decode(encoded_header).decode('utf-8'))
    except Exception:
        raise BadHeader('Could not read header')
    if not isinstance(header, dict):
        raise BadHeader('Header is not a JSON object')

    algorithm = header.get('alg')
    if algorithm not in _DIGESTS:
        raise BadHeader('Algorithm not supported: %s' % algorithm)

    expected = _signature(key, signing_input, algorithm)
    try:
        provided = _b64_decode(signature)
    except Exception:
        raise BadSignature('Could not read signature')
    # Constant time, so a wrong signature cannot be narrowed down by timing.
    if not hmac.compare_digest(expected, provided):
        raise BadSignature('Signature does not match')

    try:
        payload = json.loads(_b64_decode(encoded_payload).decode('utf-8'))
    except Exception:
        raise BadSignature('Could not read payload')

    if return_header:
        return payload, header
    return payload


def dumps_timed(value, key, expires_in, algorithm='HS512', now=None):
    """Serialize with `iat`/`exp` in the header, as the timed serializer does.

    The timed serializer defaults to HS512 while the untimed one defaults to
    HS256. That asymmetry is itsdangerous', and is kept because changing it
    would change the bytes.
    """
    issued_at = int(time.time()) if now is None else int(now)
    return dumps(
        value,
        key,
        algorithm=algorithm,
        # Insertion order is alg, iat, exp -- the order the bytes are written in.
        header_fields={'iat': issued_at, 'exp': issued_at + int(expires_in)},
    )


def loads_timed(token, key, now=None):
    """Verify, then enforce the expiry the way the timed serializer does."""
    payload, header = loads(token, key, return_header=True)

    if 'exp' not in header:
        raise BadSignature('Missing expiry date', payload=payload)

    try:
        expires_at = int(header['exp'])
    except (TypeError, ValueError):
        raise BadHeader('Expiry date is not an IntDate', payload=payload)
    if expires_at < 0:
        raise BadHeader('Expiry date is not an IntDate', payload=payload)

    current = int(time.time()) if now is None else int(now)
    if expires_at < current:
        raise SignatureExpired('Signature expired', payload=payload)

    return payload
