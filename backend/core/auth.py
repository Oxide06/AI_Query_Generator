from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.database import get_db
from backend.models.user import User, UserRole
from backend.schemas.user import TokenData

settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ---------- Password helpers ----------

def hash_password(plain: str) -> str:
    # bcrypt silently truncates at 72 bytes — enforce this explicitly
    if len(plain.encode("utf-8")) > 72:
        raise ValueError("Password exceeds 72-byte bcrypt limit")
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ---------- JWT helpers ----------

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> TokenData:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: int = payload.get("sub")
        username: str = payload.get("username")
        role: str = payload.get("role")
        if user_id is None:
            raise JWTError("Missing sub")
        return TokenData(user_id=int(user_id), username=username, role=UserRole(role))
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ---------- FastAPI dependencies ----------

def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    token_data = decode_token(token)
    user = db.query(User).filter(User.id == token_data.user_id).first()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    return user


def require_role(*roles: UserRole):
    """Dependency factory — restricts an endpoint to specific roles."""
    def _checker(current_user: Annotated[User, Depends(get_current_user)]) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role}' is not permitted to access this resource",
            )
        return current_user
    return _checker


# Convenience shortcuts
require_admin = require_role(UserRole.admin)
require_analyst_or_above = require_role(UserRole.admin, UserRole.analyst)
