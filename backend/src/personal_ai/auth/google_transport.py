"""Bounded signing-key transport shared by user and service authentication."""

from contextlib import contextmanager
from time import monotonic

from google.auth.transport.requests import Request


class _BoundedGoogleAuthRequest(Request):
    def __init__(self, *, timeout_seconds=3.0, deadline=None):
        super().__init__()
        self.timeout_seconds = min(max(timeout_seconds, 0.1), 3.0)
        self.deadline = deadline

    def __call__(self, url, method="GET", body=None, headers=None, timeout=None, **kwargs):
        remaining = self.timeout_seconds
        if self.deadline is not None:
            remaining = min(remaining, self.deadline - monotonic())
        if remaining <= 0:
            raise TimeoutError
        requested_timeout = timeout if timeout is not None else self.timeout_seconds
        return super().__call__(
            url,
            method=method,
            body=body,
            headers=headers,
            timeout=min(requested_timeout, self.timeout_seconds, remaining),
            **kwargs,
        )


@contextmanager
def signing_key_request(*, timeout_seconds=3.0, deadline=None):
    """Close the HTTP session even when key retrieval or token validation fails."""
    request = _BoundedGoogleAuthRequest(
        timeout_seconds=timeout_seconds,
        deadline=deadline,
    )
    try:
        yield request
    finally:
        request.session.close()
