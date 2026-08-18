"""Authentication boundary for mock mode and future Supabase JWT validation."""
from __future__ import annotations

import os
from typing import Literal, Optional

from fastapi import Header, HTTPException
from pydantic import BaseModel


class CurrentUser(BaseModel):
    id: str = "demo-owner"
    email: str = "owner@demo.sda"
    role: Literal["owner", "admin", "member", "client_reviewer"] = "owner"
    organization_id: str = "org_demo"


def current_user(authorization: Optional[str] = Header(default=None)) -> CurrentUser:
    if os.getenv("MOCK_MODE", "true").lower() == "true":
        return CurrentUser()
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Authentication required")
    token = authorization.split(" ", 1)[1].strip()
    secret = os.getenv("SUPABASE_JWT_SECRET", "")
    if not secret:
        raise HTTPException(503, "SUPABASE_JWT_SECRET is not configured")
    try:
        import jwt

        options = {"require": ["sub", "exp"]}
        decode_kwargs = {"algorithms": ["HS256"], "options": options}
        issuer = os.getenv("SUPABASE_JWT_ISSUER")
        audience = os.getenv("SUPABASE_JWT_AUDIENCE")
        if issuer:
            decode_kwargs["issuer"] = issuer
        if audience:
            decode_kwargs["audience"] = audience
        payload = jwt.decode(token, secret, **decode_kwargs)
        metadata = payload.get("app_metadata") or payload.get("user_metadata") or {}
        role = metadata.get("role", "member")
        if role not in {"owner", "admin", "member", "client_reviewer"}:
            role = "member"
        organization_id = metadata.get("organization_id") or metadata.get("org_id")
        if not organization_id:
            raise ValueError("organization claim")
        return CurrentUser(id=str(payload["sub"]), email=str(payload.get("email", "")), role=role, organization_id=str(organization_id))
    except Exception as exc:
        raise HTTPException(401, "Invalid Supabase access token") from exc


def require_role(user: CurrentUser, *roles: str) -> CurrentUser:
    if user.role not in roles:
        raise HTTPException(403, "Insufficient role")
    return user
