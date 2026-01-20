"""Pydantic schemas for authentication."""

from pydantic import BaseModel, EmailStr


class TokenRequest(BaseModel):
    """Request schema for generating auth token."""
    email: EmailStr


class TokenResponse(BaseModel):
    """Response schema for auth token."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # minutes
