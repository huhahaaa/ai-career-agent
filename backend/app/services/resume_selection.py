from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.models.resume import (
    RESUME_SOURCE_FORMAL,
    Resume,
    ResumeVersion,
)
from app.models.user import User


def latest_resume_version(resume: Resume) -> Optional[ResumeVersion]:
    return resume.versions[-1] if resume.versions else None


def current_resume_version(resume: Resume) -> Optional[ResumeVersion]:
    if not resume.versions:
        return None
    current = next(
        (
            version
            for version in resume.versions
            if version.version_number == resume.current_version_number
        ),
        None,
    )
    return current or latest_resume_version(resume)


def resume_current_text(resume: Resume) -> str:
    version = current_resume_version(resume)
    return (version.content or "") if version else ""


def formal_resume_query(user_id: int):
    return (
        select(Resume)
        .where(
            Resume.user_id == user_id,
            Resume.source_type == RESUME_SOURCE_FORMAL,
        )
    )


def get_user_formal_resume(db: Session, user: User, resume_id: int) -> Resume:
    resume = db.get(Resume, resume_id)
    if (
        resume is None
        or resume.user_id != user.id
        or resume.source_type != RESUME_SOURCE_FORMAL
    ):
        raise AppException(404, 40403, "resume not found")
    return resume


def get_default_resume(db: Session, user: User) -> Optional[Resume]:
    default_resume = db.scalar(
        formal_resume_query(user.id)
        .where(Resume.is_default.is_(True))
        .order_by(Resume.updated_at.desc(), Resume.id.desc())
    )
    if default_resume is not None:
        return default_resume
    return db.scalar(
        formal_resume_query(user.id).order_by(Resume.updated_at.desc(), Resume.id.desc())
    )


def user_has_default_resume(db: Session, user_id: int) -> bool:
    return bool(
        db.scalar(
            select(Resume.id)
            .where(
                Resume.user_id == user_id,
                Resume.source_type == RESUME_SOURCE_FORMAL,
                Resume.is_default.is_(True),
            )
            .limit(1)
        )
    )


def make_default_resume(db: Session, user: User, resume: Resume) -> None:
    if resume.user_id != user.id or resume.source_type != RESUME_SOURCE_FORMAL:
        raise AppException(404, 40403, "resume not found")
    resumes = db.scalars(formal_resume_query(user.id)).all()
    for item in resumes:
        item.is_default = item.id == resume.id


def ensure_default_resume(db: Session, user_id: int) -> None:
    if user_has_default_resume(db, user_id):
        return
    fallback = db.scalar(
        formal_resume_query(user_id).order_by(Resume.updated_at.desc(), Resume.id.desc())
    )
    if fallback is not None:
        fallback.is_default = True


def create_resume_snapshot(
    db: Session,
    user: User,
    *,
    title: str,
    file_name: str,
    content: str,
    source_type: str,
) -> Resume:
    resume = Resume(
        user_id=user.id,
        title=title,
        current_version_number=1,
        source_type=source_type,
        is_default=False,
    )
    db.add(resume)
    db.flush()
    db.add(
        ResumeVersion(
            resume_id=resume.id,
            version_number=1,
            file_name=file_name,
            file_path="",
            content=content,
        )
    )
    return resume
