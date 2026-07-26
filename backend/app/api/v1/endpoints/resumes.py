import json
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.exceptions import AppException
from app.db.session import get_db
from app.models.resume import RESUME_SOURCE_FORMAL, Resume, ResumeAuditReport, ResumeVersion
from app.models.user import User
from app.schemas.common import ApiResponse, success_response
from app.schemas.resume import (
    ResumeAuditRequest,
    ResumeAuditResult,
    ResumeVersionCreateRequest,
)
from app.services.agent_logging import agent_operation_log
from app.services.resume_compare import compare_resume_versions
from app.services.resume_audit import audit_resume_text
from app.services.resume_parser import extract_resume_text
from app.services.resume_selection import (
    ensure_default_resume,
    formal_resume_query,
    get_user_formal_resume,
    latest_resume_version,
    make_default_resume,
    user_has_default_resume,
)

router = APIRouter()

ALLOWED_RESUME_SUFFIXES = {".pdf", ".doc", ".docx", ".txt", ".md"}
MAX_RESUME_BYTES = 5 * 1024 * 1024
UPLOAD_ROOT = Path("data/uploads/resumes")


def _latest_report(resume: Resume) -> ResumeAuditReport | None:
    if not resume.audit_reports:
        return None
    return max(resume.audit_reports, key=lambda report: report.id or 0)


def _load_json_list(value: str) -> list:
    if not value:
        return []
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError:
        return []
    return loaded if isinstance(loaded, list) else []


def _risk_level(score: int, risk_flags: list) -> str:
    if score < 60 or (score < 70 and len(risk_flags) >= 6):
        return "高"
    if score < 75 or len(risk_flags) >= 3:
        return "中"
    return "低"


def _audit_report_to_response(report: ResumeAuditReport) -> dict:
    risk_flags = _load_json_list(report.risk_flags)
    suggestions = _load_json_list(report.suggestions)
    return {
        "id": report.id,
        "score": report.score,
        "risk_flags": risk_flags,
        "suggestions": suggestions,
        "missing_keywords": _load_json_list(report.missing_keywords),
        "risk_level": _risk_level(report.score, risk_flags),
        "target_position": report.target_position or "",
        "resume_version": report.resume_version_number,
        "created_at": report.created_at,
    }


def _resume_summary(resume: Resume) -> dict:
    latest = latest_resume_version(resume)
    latest_report = _latest_report(resume)
    return {
        "id": resume.id,
        "filename": latest.file_name if latest else resume.title,
        "version": resume.current_version_number,
        "source_type": resume.source_type,
        "is_default": bool(resume.is_default),
        "status": "approved" if latest_report else "pending",
        "review_comment": (
            "已生成审核报告，综合评分 %s 分" % latest_report.score
            if latest_report
            else "已保存，等待审核"
        ),
        "created_at": resume.created_at,
    }


def _decode_uploaded_text(content: bytes, filename: str) -> str:
    try:
        text, _parser = extract_resume_text(content, filename)
        return text
    except Exception as exc:
        raise AppException(422, 42207, "resume text extraction failed: %s" % exc) from exc


def _version_payload(version: ResumeVersion) -> dict:
    return {
        "id": version.id,
        "version": version.version_number,
        "filename": version.file_name,
        "content": version.content,
        "content_length": len(version.content or ""),
        "created_at": version.created_at,
    }


def _resume_detail_payload(resume: Resume) -> dict:
    latest_report = _latest_report(resume)
    return {
        **_resume_summary(resume),
        "versions": [_version_payload(version) for version in resume.versions],
        "latest_report": (
            _audit_report_to_response(latest_report)
            if latest_report is not None
            else None
        ),
        "audit_reports": [
            _audit_report_to_response(report)
            for report in sorted(
                resume.audit_reports,
                key=lambda item: item.id or 0,
                reverse=True,
            )
        ],
    }


def _get_version_by_number(resume: Resume, version_number: int) -> ResumeVersion:
    for version in resume.versions:
        if version.version_number == version_number:
            return version
    raise AppException(404, 40404, "resume version not found")


@router.get("", response_model=ApiResponse[List[dict]])
def list_resumes(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[List[dict]]:
    resumes = db.scalars(
        formal_resume_query(current_user.id)
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
        source_type=RESUME_SOURCE_FORMAL,
        is_default=not user_has_default_resume(db, current_user.id),
    )
    db.add(resume)
    db.flush()

    target_dir = UPLOAD_ROOT / str(current_user.id)
    target_dir.mkdir(parents=True, exist_ok=True)
    safe_name = "resume_%s_v1%s" % (resume.id, suffix)
    target_path = target_dir / safe_name
    target_path.write_bytes(content)
    parsed_text = _decode_uploaded_text(content, file.filename or safe_name)

    db.add(
        ResumeVersion(
            resume_id=resume.id,
            version_number=1,
            file_name=file.filename or safe_name,
            file_path=str(target_path),
            content=parsed_text,
        )
    )
    db.commit()
    db.refresh(resume)
    return success_response(
        {
            **_resume_summary(resume),
            "parsed_text_length": len(parsed_text),
        },
        message="resume uploaded",
    )


@router.get("/{resume_id}", response_model=ApiResponse[dict])
def resume_detail(
    resume_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    resume = get_user_formal_resume(db, current_user, resume_id)
    return success_response(_resume_detail_payload(resume))


@router.post("/{resume_id}/versions", response_model=ApiResponse[dict])
def create_resume_version(
    resume_id: int,
    payload: ResumeVersionCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    resume = get_user_formal_resume(db, current_user, resume_id)
    next_version = max((version.version_number for version in resume.versions), default=0) + 1
    file_name = payload.file_name.strip() or "edited-resume.txt"
    db.add(
        ResumeVersion(
            resume_id=resume.id,
            version_number=next_version,
            file_name=file_name,
            file_path="",
            content=payload.content.strip(),
        )
    )
    resume.current_version_number = next_version
    db.commit()
    db.refresh(resume)
    return success_response(_resume_detail_payload(resume), message="resume version created")


@router.get("/{resume_id}/compare", response_model=ApiResponse[dict])
def compare_resume_version(
    resume_id: int,
    from_version: int = Query(..., ge=1),
    to_version: int = Query(..., ge=1),
    target_position: str = "",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    resume = get_user_formal_resume(db, current_user, resume_id)
    before = _get_version_by_number(resume, from_version)
    after = _get_version_by_number(resume, to_version)
    result = compare_resume_versions(
        before.content or "",
        after.content or "",
        target_position,
    )
    return success_response(
        {
            "resume_id": resume.id,
            "from_version": from_version,
            "to_version": to_version,
            "target_position": target_position,
            **result,
        }
    )


@router.delete("/{resume_id}", response_model=ApiResponse[None])
def delete_resume(
    resume_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[None]:
    resume = get_user_formal_resume(db, current_user, resume_id)
    files = [Path(version.file_path) for version in resume.versions if version.file_path]
    db.delete(resume)
    db.flush()
    ensure_default_resume(db, current_user.id)
    db.commit()
    for path in files:
        if path.exists() and UPLOAD_ROOT.resolve() in path.resolve().parents:
            path.unlink()
    return success_response(message="resume deleted")


@router.patch("/{resume_id}/default", response_model=ApiResponse[dict])
def set_default_resume(
    resume_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    resume = get_user_formal_resume(db, current_user, resume_id)
    make_default_resume(db, current_user, resume)
    db.commit()
    db.refresh(resume)
    return success_response(_resume_summary(resume), message="default resume updated")


@router.post("/audit", response_model=ApiResponse[ResumeAuditResult])
def audit_resume(
    payload: ResumeAuditRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[ResumeAuditResult]:
    resume_id = payload.resume_id
    if resume_id is not None:
        get_user_formal_resume(db, current_user, resume_id)

    with agent_operation_log(
        db,
        user_id=current_user.id,
        operation="resume.audit",
        request_summary={
            "resume_id": resume_id,
            "resume_version": payload.resume_version,
            "target_position": payload.target_position,
            "resume_chars": len(payload.resume_text),
        },
    ) as log_context:
        result = audit_resume_text(payload.resume_text, payload.target_position)
        log_context["response_summary"] = {
            "score": result.get("score"),
            "risk_level": result.get("risk_level"),
            "risk_count": len(result.get("risk_flags", [])),
            "target_position": payload.target_position,
            "resume_version": payload.resume_version,
        }
    db.add(
        ResumeAuditReport(
            user_id=current_user.id,
            resume_id=resume_id,
            score=result["score"],
            risk_flags=json.dumps(result["risk_flags"], ensure_ascii=False),
            suggestions=json.dumps(result["suggestions"], ensure_ascii=False),
            missing_keywords=json.dumps(
                result.get("missing_keywords", []),
                ensure_ascii=False,
            ),
            target_position=payload.target_position.strip(),
            resume_version_number=payload.resume_version,
        )
    )
    db.commit()
    return success_response(ResumeAuditResult.model_validate(result))
