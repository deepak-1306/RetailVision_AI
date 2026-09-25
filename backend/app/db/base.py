"""
SQLAlchemy declarative base + engine/session factory.

Uses SQLite by default (zero-config for local/hackathon use) but works
unchanged against PostgreSQL when DATABASE_URL is set accordingly (as it is
in docker-compose.yml). Tables are created directly from the models via
`init_db()` at application startup -- the dedicated Alembic migration module
is intentionally out of scope for this build.
"""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(settings.DATABASE_URL, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    # Import models so they're registered on Base.metadata before create_all
    from app.models import (  # noqa: F401
        user, video, job, behaviour, prediction, recommendation, report
    )

    Base.metadata.create_all(bind=engine)

    # Ensure demo accounts exist out-of-the-box
    from app.core.security import hash_password
    from app.models.user import User

    with SessionLocal() as db:
        demo_accounts = [
            ("deepak@store.com", "admin123", "Deepak", "Flagship Store"),
            ("admin@retailvision.ai", "admin123", "Admin", "RetailVision HQ"),
            ("test@demo.com", "demo123", "Test User", "Demo Supermarket"),
        ]
        for email, pwd, name, store in demo_accounts:
            existing = db.query(User).filter(User.email == email).first()
            if not existing:
                db.add(User(
                    email=email,
                    hashed_password=hash_password(pwd),
                    full_name=name,
                    store_name=store,
                ))
        db.commit()
