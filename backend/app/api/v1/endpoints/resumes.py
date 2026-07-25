import json
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.exceptions import AppException
from app.db.session import get_db
from app.models.resume import Resume, ResumeAuditReport, ResumeVersion
from app.models.user import User
from app.schemas.common import ApiResponse, success_response
from app.schemas.resume import ResumeAuditRequest, ResumeAuditResult
from app.services.resume_audit import audit_resume_text

router = APIRouter()

ALLOWED_RESUME_SUFFIXES = {".pdf", ".doc", ".docx", ".txt", ".md"}
MAX_RESUME_BYTES = 5 * 1024 * 1024
UPLOAD_ROOT = Path("data/uploads/resumes")


def _latest_version(resume: Resume) -> ResumeVersion | None:
    return resume.versions[-1] if resume.versions else None


def _resume_summary(resume: Resume) -> dict:
    latest = _latest_version(resume)
    latest_report = resume.audit_reports[-1] if resume.audit_reports else None
    return {
        "id": resume.id,
        "filename": latest.file_name if latest else resume.title,
        "version": resume.current_version_number,
        "status": "approved" if latest_report else "pending",
        "review_comment": "已生成审核报告" if latest_report else "已保存，等待审核",
        "created_at": resume.created_at,
    }


def _decode_uploaded_text(content: bytes, filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix in {".txt", ".md"}:
        return content.decode("utf-8", errors="ignore")
    return "已上传文件：%s。文件解析将在后续简历解析模块接入。" % filename


@router.get("", response_model=ApiResponse[List[dict]])
def list_resumes(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[List[dict]]:
    resumes = db.scalars(
        select(Resume)
        .where(Resume.user_id == current_user.id)
        .order_by(Resume.updated_at.desc(), Resume.id.desc())
    ).all()
    return success_response([_resume_summary(resume) for resume in resumes])


@router.post("/upload", response_model=ApiResponse[dict])
async def upload_resume(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_RESUME_SUFFIXES:
        raise AppException(422, 42202, "only PDF, DOC, DOCX, TXT or MD resumes are supported")

    content = await file.read()
    if not content:
        raise AppException(422, 42203, "resume file cannot be empty")
    if len(content) > MAX_RESUME_BYTES:
        raise AppException(422, 42204, "resume file is too large")

    resume = Resume(
        user_id=current_user.id,
        title=file.filename or "resume",
        current_version_number=1,
    )
    db.add(resume)
    db.flush()

    target_dir = UPLOAD_ROOT / str(current_user.id)
    target_dir.mkdir(parents=True, exist_ok=True)
    safe_name = "resume_%s_v1%s" % (resume.id, suffix)
    target_path = target_dir / safe_name
    target_path.write_bytes(content)

    existing_version = db.scalars(
        select(ResumeVersion).where(
            ResumeVersion.resume_id == resume.id,
            ResumeVersion.version_number == 1,
        )
    ).first()
    if existing_version:
        existing_version.file_name = file.filename or safe_name
        existing_version.file_path = str(target_path)
        existing_version.content = _decode_uploaded_text(content, file.filename or safe_name)
    else:
        db.add(
            ResumeVersion(
                resume_id=resume.id,
                version_number=1,
                file_name=file.filename or safe_name,
                file_path=str(target_path),
                content=_decode_uploaded_text(content, file.filename or safe_name),
            )
        )
    db.commit()
    db.refresh(resume)
    return success_response(_resume_summary(resume), message="resume uploaded")


@router.get("/{resume_id}", response_model=ApiResponse[dict])
def resume_detail(
    resume_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    resume = db.get(Resume, resume_id)
    if resume is None or resume.user_id != current_user.id:
        raise AppException(404, 40403, "resume not found")
    return success_response(
        {
            **_resume_summary(resume),
            "versions": [
                {
                    "id": version.id,
                    "version": version.version_number,
                    "filename": version.file_name,
                    "content": version.content,
                    "created_at": version.created_at,
                }
                for version in resume.versions
            ],
        }
    )


@router.delete("/{resume_id}", response_model=ApiResponse[None])
def delete_resume(
    resume_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[None]:
    resume = db.get(Resume, resume_id)
    if resume is None or resume.user_id != current_user.id:
        raise AppException(404, 40403, "resume not found")
    files = [Path(version.file_path) for version in resume.versions if version.file_path]
    db.delete(resume)
    db.commit()
    for path in files:
        if path.exists() and UPLOAD_ROOT.resolve() in path.resolve().parents:
            path.unlink()
    return success_response(message="resume deleted")


@router.post("/audit", response_model=ApiResponse[ResumeAuditResult])
def audit_resume(
    payload: ResumeAuditRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[ResumeAuditResult]:
    resume_id = payload.resume_id
    if resume_id is not None:
        resume = db.get(Resume, resume_id)
        if resume is None or resume.user_id != current_user.id:
            raise AppException(404, 40403, "resume not found")

    result = audit_resume_text(payload.resume_text, payload.target_position)
    db.add(
        ResumeAuditReport(
            user_id=current_user.id,
            resume_id=resume_id,
            score=result["score"],
            risk_flags=json.dumps(result["risk_flags"], ensure_ascii=False),
            suggestions=json.dumps(result["suggestions"], ensure_ascii=False),
        )
    )
    db.commit()
    return success_response(ResumeAuditResult.model_validate(result))
