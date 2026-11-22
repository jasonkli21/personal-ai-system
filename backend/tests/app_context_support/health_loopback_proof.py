"""Test-only signed service requests, with no provider or deployed issuer."""

import hmac
from hashlib import sha256
from time import time
from uuid import uuid4

PROOF_HEADER = "x-fixture-health-service-proof"
TRANSACTION_HEADER = "x-fixture-health-transaction"


def _signature(key, audience, method, path, body, nonce, expires):
    statement = "\n".join((audience, method, path, sha256(body).hexdigest(), nonce, expires))
    return hmac.digest(key, statement.encode(), "sha256").hex()


def sign(key, audience, method, path, body, *, nonce=None):
    nonce = nonce or str(uuid4())
    expires = str(int(time()) + 5)
    return ".".join((nonce, expires, _signature(key, audience, method, path, body, nonce, expires)))


def verify(key, audience, method, path, body, proof):
    try:
        nonce, expires, received = proof.split(".")
        if len(nonce) != 36 or not int(time()) <= int(expires) <= int(time()) + 5:
            return None
        expected = _signature(key, audience, method, path, body, nonce, expires)
        return nonce if hmac.compare_digest(received, expected) else None
    except (AttributeError, TypeError, ValueError):
        return None
