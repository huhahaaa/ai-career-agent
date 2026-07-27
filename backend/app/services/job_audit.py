from typing import Dict


def apply_job_audit(job: Dict, audit: Dict) -> Dict:
    updated = dict(job)
    updated["status"] = audit["status"]
    updated["audit_comment"] = audit.get("comment", "")
    updated["reviewer"] = audit.get("reviewer", "")
    updated["updated_at"] = "2026-07-24"
    return updated

