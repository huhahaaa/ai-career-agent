import argparse
from getpass import getpass

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.models.user import User
from app.schemas.auth import RegisterRequest


def create_reviewer(
    db: Session,
    username: str,
    email: str,
    password: str,
) -> User:
    payload = RegisterRequest(
        username=username,
        email=email,
        password=password,
    )
    existing_user = db.scalar(
        select(User).where(
            or_(
                User.username == payload.username,
                User.email == str(payload.email),
            )
        )
    )
    if existing_user:
        raise ValueError("username or email already exists")

    reviewer = User(
        username=payload.username,
        email=str(payload.email),
        hashed_password=hash_password(payload.password),
        role="reviewer",
    )
    db.add(reviewer)
    db.commit()
    db.refresh(reviewer)
    return reviewer


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a reviewer account")
    parser.add_argument("--username", required=True)
    parser.add_argument("--email", required=True)
    args = parser.parse_args()

    password = getpass("Password: ")
    password_confirmation = getpass("Confirm password: ")
    if password != password_confirmation:
        raise SystemExit("Passwords do not match")

    init_db()
    with SessionLocal() as db:
        try:
            reviewer = create_reviewer(
                db,
                username=args.username,
                email=args.email,
                password=password,
            )
        except ValueError as exc:
            raise SystemExit(str(exc))
    print("Created reviewer: %s" % reviewer.username)


if __name__ == "__main__":
    main()
