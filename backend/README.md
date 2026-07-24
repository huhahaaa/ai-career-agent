# Backend

FastAPI backend for authentication, job data auditing, resume review, matching, and mock interview workflows.

## Run

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

The application creates `career_agent.db` and all core tables on first startup.
Set a private `SECRET_KEY` before sharing or deploying the service; the available
environment variables are listed in the repository `.env.example` file.

## Reviewer Account

Public registration always creates a `student` account. Create an account with
job-review permission from the `backend` directory:

```bash
python -m app.commands.create_reviewer --username reviewer --email reviewer@example.com
```

The command prompts for the password without writing it to the shell history.

## Test

```bash
pytest -q
```

## Main Modules

- `api/v1/endpoints/auth.py`: login, registration, logout, current user
- `api/v1/endpoints/jobs.py`: job import, listing, audit, approved job query
- `api/v1/endpoints/resumes.py`: resume audit
- `api/v1/endpoints/matching.py`: resume-job matching
- `api/v1/endpoints/interviews.py`: mock interview workflow
- `services/`: business logic placeholders for each member

All `/api/v1` responses use the following envelope:

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```
