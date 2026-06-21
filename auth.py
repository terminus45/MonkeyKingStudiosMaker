"""auth.py — FastAPI auth dependency for Phase 1.

Phase 1 ships a DEV verifier only. Real vendor JWT verification is stubbed below with
clear swap instructions. No vendor SDK is imported or required.

=== HOW TO SWAP TO A REAL AUTH VENDOR (Phase 2 / build time) ===

Option A — Clerk:
  1. pip install PyJWT[crypto]
  2. Set env: CLERK_JWKS_URL=https://<frontend-api>/.well-known/jwks.json
              CLERK_AUD=<your-clerk-publishable-key>
  3. Replace _verify_jwt_dev() with:

       from jwt import PyJWKClient
       import jwt as _jwt
       _JWKS = PyJWKClient(os.getenv("CLERK_JWKS_URL"))
       def _verify_jwt(token: str) -> tuple[str, str | None]:
           key = _JWKS.get_signing_key_from_jwt(token).key
           claims = _jwt.decode(token, key, algorithms=["RS256"],
                                audience=os.getenv("CLERK_AUD"),
                                options={"require": ["exp", "sub"]})
           return claims["sub"], claims.get("email")

Option B — Supabase Auth (HS256):
  1. pip install PyJWT
  2. Set env: SUPABASE_JWT_SECRET=<your-jwt-secret>
  3. Replace _verify_jwt_dev() with:

       import jwt as _jwt
       _SECRET = os.getenv("SUPABASE_JWT_SECRET")
       def _verify_jwt(token: str) -> tuple[str, str | None]:
           claims = _jwt.decode(token, _SECRET, algorithms=["HS256"],
                                options={"require": ["exp", "sub"]})
           return claims["sub"], claims.get("email")

In both cases:
  - Remove DEV_AUTH / dev-header logic from current_user().
  - The rest of this module (billing_db calls, HTTPException patterns) stays identical.
  - Update auth_client.js to use the vendor's SDK instead of the dev shim.
=== END SWAP INSTRUCTIONS ===
"""

import os
from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException, Request

# Lazily imported (only when BILLING_ENABLED). These are set by main.py at startup.
import billing_db

_DEV_AUTH: bool = os.getenv("DEV_AUTH", "true").lower() in ("1", "true", "yes")


@dataclass
class User:
    profile_id: str   # internal DB id (billing_db.profiles.id)
    auth_id: str      # external identity (provider 'sub' claim, or dev header value)
    email: Optional[str] = None


# ── DEV verifier (Phase 1 only) ──────────────────────────────────────────────

def _verify_jwt_dev(request: Request) -> tuple[str, Optional[str]]:
    """Accept either:
      Authorization: Bearer dev:<auth_id>
      X-Dev-User: <auth_id>

    Returns (auth_id, email=None). Raises HTTPException(401) if neither header present
    or the Bearer value does not start with 'dev:'.

    This shim is replaced by a real JWT verifier at Phase 2 build time (see module
    docstring for Clerk/Supabase swap instructions).
    """
    # Check X-Dev-User first (easier for manual curl testing)
    dev_user = request.headers.get("x-dev-user", "").strip()
    if dev_user:
        return dev_user, None

    auth_hdr = request.headers.get("authorization", "")
    if auth_hdr.startswith("Bearer dev:"):
        auth_id = auth_hdr[len("Bearer dev:"):].strip()
        if auth_id:
            return auth_id, None

    raise HTTPException(
        status_code=401,
        detail="Not authenticated. In DEV_AUTH mode, send X-Dev-User: <id> or Authorization: Bearer dev:<id>",
    )


# ── Stub for production JWT verification (NOT implemented in Phase 1) ─────────

def _verify_jwt_prod(token: str) -> tuple[str, Optional[str]]:  # noqa: ARG001
    """STUB — replace with real Clerk/Supabase JWT verification.

    Should return (auth_id, email_or_None) on success, raise ValueError on failure.
    See module docstring for implementation templates.
    """
    raise NotImplementedError(
        "Production JWT verification not implemented. "
        "Set DEV_AUTH=true and use the dev shim, or implement _verify_jwt_prod()."
    )


# ── FastAPI dependency ────────────────────────────────────────────────────────

async def current_user(request: Request) -> User:
    """FastAPI dependency: verify caller identity and return a User.

    Phase 1 (DEV_AUTH=true, default when BILLING_ENABLED):
      Reads X-Dev-User or Authorization: Bearer dev:<auth_id>.

    Phase 2 (DEV_AUTH=false, vendor JWT active):
      Reads Authorization: Bearer <jwt>, verifies with _verify_jwt_prod().

    Either way, lazily creates profile + wallet rows on first call (idempotent upsert).
    Returns a User dataclass. Raises HTTPException(401) on auth failure.
    """
    if _DEV_AUTH:
        try:
            auth_id, email = _verify_jwt_dev(request)
        except HTTPException:
            raise
    else:
        auth_hdr = request.headers.get("authorization", "")
        if not auth_hdr.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Not authenticated")
        token = auth_hdr[7:]
        try:
            auth_id, email = _verify_jwt_prod(token)
        except (ValueError, NotImplementedError, Exception) as exc:
            raise HTTPException(status_code=401, detail=f"Invalid token: {exc}") from exc

    # Lazily ensure profile + wallet exist (idempotent upsert)
    try:
        profile_id = billing_db.get_or_create_profile(auth_id, email)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database error: {exc}") from exc

    return User(profile_id=profile_id, auth_id=auth_id, email=email)
