# Backend

FastAPI backend for authentication, job data auditing, resume review, matching, and mock interview workflows.

## Run

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Main Modules

- `api/v1/endpoints/auth.py`: login, registration, logout, current user
- `api/v1/endpoints/jobs.py`: job import, listing, audit, approved job query
- `api/v1/endpoints/resumes.py`: resume audit
- `api/v1/endpoints/matching.py`: resume-job matching
- `api/v1/endpoints/interviews.py`: mock interview workflow
- `services/`: business logic placeholders for each member

