"""JWT authentication utilities for API security.

Provides token generation, validation, and FastAPI dependency injection
for protecting API endpoints.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.config.settings import settings
from loguru import logger


# HTTP Bearer token scheme
security = HTTPBearer()


class AuthService:
    """Service for handling JWT authentication."""

    @staticmethod
    def create_access_token(
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create a new JWT access token.

        Args:
            data: Payload data to encode in the token
            expires_delta: Optional custom expiration time

        Returns:
            Encoded JWT token string
        """
        to_encode = data.copy()

        # Set expiration time
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(
                minutes=settings.jwt_access_token_expire_minutes
            )

        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow()
        })

        # Encode the token
        encoded_jwt = jwt.encode(
            to_encode,
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm
        )

        logger.debug(f"Created JWT token for: {data.get('sub', 'unknown')}")

        return encoded_jwt

    @staticmethod
    def verify_token(token: str) -> Dict[str, Any]:
        """Verify and decode a JWT token.

        Args:
            token: JWT token string

        Returns:
            Decoded token payload

        Raises:
            HTTPException: If token is invalid or expired
        """
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

        try:
            payload = jwt.decode(
                token,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm]
            )

            # Check if token has required fields
            if payload.get("sub") is None:
                logger.warning("Token missing 'sub' field")
                raise credentials_exception

            return payload

        except JWTError as e:
            logger.warning(f"JWT validation failed: {e}")
            raise credentials_exception

    @staticmethod
    def get_user_email_from_token(token: str) -> str:
        """Extract user email from JWT token.

        Args:
            token: JWT token string

        Returns:
            User email address

        Raises:
            HTTPException: If token is invalid
        """
        payload = AuthService.verify_token(token)
        return payload.get("sub")


# FastAPI Dependencies

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:
    """FastAPI dependency to get current authenticated user.

    Args:
        credentials: HTTP Bearer credentials from request

    Returns:
        User email from token

    Raises:
        HTTPException: If authentication fails
    """
    token = credentials.credentials
    user_email = AuthService.get_user_email_from_token(token)

    if not user_email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )

    return user_email


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    )
) -> Optional[str]:
    """FastAPI dependency to get current user if authenticated, None otherwise.

    Useful for endpoints that have optional authentication.

    Args:
        credentials: Optional HTTP Bearer credentials

    Returns:
        User email or None if not authenticated
    """
    if not credentials:
        return None

    try:
        return AuthService.get_user_email_from_token(credentials.credentials)
    except HTTPException:
        return None


# Utility functions

def generate_token_for_user(user_email: str) -> str:
    """Generate a JWT token for a user.

    Args:
        user_email: User's email address

    Returns:
        JWT token string
    """
    token_data = {"sub": user_email}
    return AuthService.create_access_token(token_data)


def generate_long_lived_token(
    user_email: str,
    days: int = 180
) -> str:
    """Generate a long-lived JWT token (e.g., for API keys).

    Args:
        user_email: User's email address
        days: Number of days until expiration

    Returns:
        JWT token string
    """
    token_data = {"sub": user_email, "type": "long_lived"}
    expires_delta = timedelta(days=days)
    return AuthService.create_access_token(token_data, expires_delta)
