"""Auth0 JWT validation."""

import json
import urllib.request

from jose import jwt, JWTError

from app.config import settings

_jwks_cache: dict | None = None


def _get_jwks() -> dict:
    """Fetch and cache Auth0 JWKS (JSON Web Key Set)."""
    global _jwks_cache
    if _jwks_cache is None:
        url = f"https://{settings.auth0_domain}/.well-known/jwks.json"
        with urllib.request.urlopen(url) as resp:
            _jwks_cache = json.loads(resp.read())
    return _jwks_cache


def decode_auth0_token(token: str) -> dict | None:
    """Decode and validate an Auth0 access token. Returns payload or None."""
    try:
        jwks = _get_jwks()
        unverified_header = jwt.get_unverified_header(token)

        rsa_key = {}
        for key in jwks["keys"]:
            if key["kid"] == unverified_header.get("kid"):
                rsa_key = {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"],
                }
                break

        if not rsa_key:
            return None

        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=settings.auth0_algorithms,
            audience=settings.auth0_audience,
            issuer=f"https://{settings.auth0_domain}/",
        )
        return payload
    except JWTError:
        return None
