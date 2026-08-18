"""Authentication and tenant context boundary.

Mock mode intentionally uses the deterministic demo principal. Production mode
validates Supabase access tokens with JWKS (RS256) when configured and only uses
the legacy shared secret as an explicit local compatibility fallback.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Callable, Literal, Optional

from fastapi import Header, HTTPException
from pydantic import BaseModel


class CurrentUser(BaseModel):
    id: str = "demo-owner"
    email: str = "owner@demo.sda"
    role: Literal["owner", "admin", "member", "client_reviewer"] = "owner"
    organization_id: str = "org_demo"
    session_id: Optional[str] = None


# Injected by the application bootstrap to avoid coupling token parsing to the
# persistence adapter. Returning None means the membership is absent.
_membership_validator: Optional[Callable[[str, str], Optional[str]]] = None


def set_membership_validator(validator: Optional[Callable[[str, str], Optional[str]]]) -> None:
    global _membership_validator
    _membership_validator = validator


@lru_cache(maxsize=4)
def _jwks_client(url: str):
    try:
        from jwt import PyJWKClient
    except ImportError as exc:  # pragma: no cover - dependency is pinned
        raise RuntimeError("PyJWT is required for Supabase JWKS validation") from exc
    return PyJWKClient(url)


def _decode_supabase_token(token: str) -> dict:
    try:
        import jwt

        issuer = os.getenv("SUPABASE_JWT_ISSUER") or (f"{os.getenv('SUPABASE_URL').rstrip('/')}/auth/v1" if os.getenv("SUPABASE_URL") else "")
        audience = os.getenv("SUPABASE_JWT_AUDIENCE", "authenticated")
        jwks_url = os.getenv("SUPABASE_JWKS_URL") or (f"{issuer}/.well-known/jwks.json" if issuer else "")
        if jwks_url:
            signing_key = _jwks_client(jwks_url).get_signing_key_from_jwt(token).key
            return jwt.decode(token, signing_key, algorithms=["RS256", "ES256"], issuer=issuer or None, audience=audience)

        # Compatibility fallback is deliberately opt-in and should only be used
        # for local Supabase installations that do not expose JWKS.
        secret = os.getenv("SUPABASE_JWT_SECRET", "")
        if not secret:
            raise ValueError("Supabase JWKS or SUPABASE_JWT_SECRET is required")
        return jwt.decode(token, secret, algorithms=["HS256"], issuer=issuer or None, audience=audience or None, options={"require": ["sub", "exp"]})
    except Exception as exc:
        raise HTTPException(401, "Invalid Supabase access token") from exc


def current_user(authorization: Optional[str] = Header(default=None)) -> CurrentUser:
    if os.getenv("MOCK_MODE", "true").lower() == "true":
        return CurrentUser()
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Authentication required")
    token = authorization.split(" ", 1)[1].strip()
    payload = _decode_supabase_token(token)
    claims = payload.get("app_metadata") or {}
    organization_claim = os.getenv("SUPABASE_ORGANIZATION_CLAIM", "organization_id")
    organization_id = payload.get(organization_claim) or claims.get(organization_claim) or payload.get("org_id")
    if not organization_id:
        raise HTTPException(403, "Authenticated user has no active organization context")
    # The database membership is authoritative. app_metadata is only used as a
    # compatibility fallback before the repository has been bootstrapped.
    role = claims.get("role", "member")
    if _membership_validator is not None:
        membership_role = _membership_validator(str(payload["sub"]), str(organization_id))
        if membership_role is None:
            raise HTTPException(403, "User is not a member of the active organization")
        role = membership_role
    if role not in {"owner", "admin", "member", "client_reviewer"}:
        role = "member"
    return CurrentUser(id=str(payload["sub"]), email=str(payload.get("email", "")), role=role, organization_id=str(organization_id), session_id=str(payload.get("session_id")) if payload.get("session_id") else None)


def require_role(user: CurrentUser, *roles: str) -> CurrentUser:
    if user.role not in roles:
        raise HTTPException(403, "Insufficient role")
    return user
