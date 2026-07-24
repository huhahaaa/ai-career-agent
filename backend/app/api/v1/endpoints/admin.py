from fastapi import APIRouter

router = APIRouter()


@router.get("/metrics")
def metrics():
    return {
        "jobs_pending": 0,
        "jobs_approved": 0,
        "resume_audits": 0,
        "interview_sessions": 0,
    }

