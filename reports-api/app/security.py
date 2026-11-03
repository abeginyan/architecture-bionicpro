"""JWT authentication and authorization for the Reports API.

Validates Keycloak access tokens offline:
  - signature via the realm JWKS (RS256),
  - issuer (external URL), audience (reports-api), expiry (with small leeway),
  - requires the realm role `prothetic_user`.

The identity used for data access comes ONLY from the token's `email` claim.
"""
from dataclasses import dataclass, field

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from .config import Settings, get_settings

bearer_scheme = HTTPBearer(auto_error=False)

_jwks_client: PyJWKClient | None = None


def get_jwk_client(settings: Settings = Depends(get_settings)) -> PyJWKClient:
    """Return a cached PyJWKClient. Overridden in tests with a local keypair."""
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(settings.jwks_uri)
    return _jwks_client


@dataclass
class CurrentUser:
    email: str
    username: str | None = None
    roles: list[str] = field(default_factory=list)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    jwk_client: PyJWKClient = Depends(get_jwk_client),
    settings: Settings = Depends(get_settings),
) -> CurrentUser:
    """Authenticate the request. 401 on any missing/invalid token problem."""
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        signing_key = jwk_client.get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            audience=settings.reports_api_audience,
            issuer=settings.keycloak_issuer,
            leeway=30,
            options={"require": ["exp", "iss", "aud"]},
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    email = claims.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is missing the email claim",
        )

    roles = claims.get("realm_access", {}).get("roles", []) or []
    return CurrentUser(email=email, username=claims.get("preferred_username"), roles=roles)


def require_prothetic_user(
    user: CurrentUser = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> CurrentUser:
    """Authorize: the token must carry the required realm role, else 403."""
    if settings.reports_required_role not in user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requires role '{settings.reports_required_role}'",
        )
    return user
