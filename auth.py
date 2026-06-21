"""Tiny shared API-key auth for the A2A Travel Concierge PoC.

The simplest *real* A2A auth scheme: a shared secret sent in an ``x-api-key``
header. Three pieces use this module:

  - servers add :class:`ApiKeyMiddleware` to enforce the key,
  - servers call :func:`api_key_security` to advertise the requirement on their
    Agent Card (so discovery shows it),
  - the client sends the key in the ``x-api-key`` header.

Discovery (the ``/.well-known`` Agent Card) stays public so a client can read
*what* auth is required before it has credentials. AuthZ (per-tenant scoping) is
intentionally out of scope for this PoC.
"""

import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from a2a.types import APIKeySecurityScheme, In, SecurityScheme

# Same key for both agents; override via env with zero code changes.
API_KEY = os.getenv("A2A_DEMO_KEY", "demo-secret-123")
API_KEY_HEADER = "x-api-key"
SECURITY_SCHEME_NAME = "ApiKeyAuth"


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """Reject any non-discovery request lacking a valid ``x-api-key`` header."""

    async def dispatch(self, request: Request, call_next):
        # Discovery must be public: clients read the card to learn the auth need.
        if request.url.path.startswith("/.well-known"):
            return await call_next(request)
        if request.headers.get(API_KEY_HEADER) != API_KEY:
            return JSONResponse(
                {"error": "unauthorized: missing or invalid x-api-key"},
                status_code=401,
            )
        return await call_next(request)


def api_key_security():
    """Return ``(security_schemes, security)`` to attach to an ``AgentCard``."""
    scheme = SecurityScheme(
        root=APIKeySecurityScheme(name=API_KEY_HEADER, in_=In.header)
    )
    security_schemes = {SECURITY_SCHEME_NAME: scheme}
    security = [{SECURITY_SCHEME_NAME: []}]
    return security_schemes, security
