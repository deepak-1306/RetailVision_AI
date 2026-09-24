from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.security import create_access_token, create_refresh_token, hash_password, verify_password
from app.models.user import User
from app.schemas.auth import TokenPair, UserRegister


def register_user(db: Session, payload: UserRegister) -> User:
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise ValueError("A user with this email already exists")

    user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        store_name=payload.store_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user


def build_token_pair(user: User) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
        user=user,
    )
