from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_ROOT = PROJECT_ROOT / "data"
ROLE_PROFILES_PATH = DATA_ROOT / "processed" / "role_profiles.json"
SKILL_DICTIONARY_PATH = DATA_ROOT / "processed" / "skill_dictionary.json"
JD_SAMPLES_PATH = DATA_ROOT / "audit_samples" / "job_jd_samples.jsonl"
INTERVIEW_QUESTIONS_PATH = DATA_ROOT / "audit_samples" / "interview_questions.jsonl"


@dataclass(frozen=True)
class KnowledgeDocument:
    doc_id: str
    doc_type: str
    title: str
    content: str
    metadata: Dict[str, str] = field(default_factory=dict)

    def to_vector_payload(self) -> Dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "content": self.content,
            "metadata": {
                "doc_type": self.doc_type,
                "title": self.title,
                **self.metadata,
            },
        }


def _read_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return rows
    for line in lines:
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _join(items: Iterable[Any]) -> str:
    return "、".join(str(item).strip() for item in items if str(item).strip())


def load_role_profile_documents() -> List[KnowledgeDocument]:
    profiles = _read_json(ROLE_PROFILES_PATH, [])
    if not isinstance(profiles, list):
        return []
    documents = []
    for profile in profiles:
        role = str(profile.get("role") or "未知岗位")
        doc_id = str(profile.get("profile_id") or f"role_{role}")
        content = (
            f"岗位角色：{role}\n"
            f"别名：{_join(profile.get('aliases', []) or [])}\n"
            f"必备能力：{_join(profile.get('must_have', []) or [])}\n"
            f"加分能力：{_join(profile.get('preferred', []) or [])}\n"
            f"证据信号：{_join(profile.get('evidence_signals', []) or [])}"
        )
        documents.append(
            KnowledgeDocument(
                doc_id=doc_id,
                doc_type="role_profile",
                title=f"{role}岗位能力画像",
                content=content,
                metadata={
                    "role": role,
                    "source_file": "role_profiles.json",
                    "profile_version": str(profile.get("profile_version") or ""),
                },
            )
        )
    return documents


def load_skill_dictionary_documents() -> List[KnowledgeDocument]:
    data = _read_json(SKILL_DICTIONARY_PATH, {})
    rules = data.get("normalization_rules", {}) if isinstance(data, dict) else {}
    if not isinstance(rules, dict):
        return []
    documents = []
    for skill, aliases in rules.items():
        alias_list = aliases if isinstance(aliases, list) else []
        documents.append(
            KnowledgeDocument(
                doc_id=f"skill_{skill}",
                doc_type="skill_definition",
                title=f"{skill}技能定义",
                content=f"标准技能：{skill}\n同义词：{_join(alias_list)}",
                metadata={
                    "skill": str(skill),
                    "source_file": "skill_dictionary.json",
                    "version": str(data.get("version") or ""),
                },
            )
        )
    return documents


def load_jd_sample_documents() -> List[KnowledgeDocument]:
    documents = []
    for item in _read_jsonl(JD_SAMPLES_PATH):
        jd_id = str(item.get("jd_id") or item.get("source_id") or item.get("title") or "")
        if not jd_id:
            continue
        title = str(item.get("title") or "岗位JD样例")
        content = (
            f"岗位：{title}\n"
            f"公司：{item.get('company', '')}\n"
            f"地点：{item.get('location', '')}\n"
            f"技能：{_join(item.get('skills', []) or [])}\n"
            f"要求：{_join(item.get('requirements', []) or [])}"
        )
        documents.append(
            KnowledgeDocument(
                doc_id=f"jd_{jd_id}",
                doc_type="job_jd_sample",
                title=title,
                content=content,
                metadata={
                    "source_file": "job_jd_samples.jsonl",
                    "source_id": str(item.get("source_id") or ""),
                    "source_link": str(item.get("source_link") or ""),
                },
            )
        )
    return documents


def load_interview_question_documents() -> List[KnowledgeDocument]:
    documents = []
    for item in _read_jsonl(INTERVIEW_QUESTIONS_PATH):
        question_id = str(item.get("question_id") or "")
        if not question_id:
            continue
        question = str(item.get("question") or "")
        content = (
            f"岗位：{item.get('role', '')}\n"
            f"类别：{item.get('category', '')}\n"
            f"难度：{item.get('difficulty', '')}\n"
            f"问题：{question}\n"
            f"期望要点：{_join(item.get('expected_points', []) or [])}\n"
            f"追问：{item.get('follow_up', '')}\n"
            f"评分标签：{_join(item.get('scoring_tags', []) or [])}"
        )
        documents.append(
            KnowledgeDocument(
                doc_id=f"question_{question_id}",
                doc_type="interview_question",
                title=question[:48] or question_id,
                content=content,
                metadata={
                    "role": str(item.get("role") or ""),
                    "category": str(item.get("category") or ""),
                    "source_file": "interview_questions.jsonl",
                },
            )
        )
    return documents


def load_rag_knowledge_documents() -> List[KnowledgeDocument]:
    return [
        *load_role_profile_documents(),
        *load_skill_dictionary_documents(),
        *load_jd_sample_documents(),
        *load_interview_question_documents(),
    ]


def knowledge_document_summary() -> Dict[str, int]:
    documents = load_rag_knowledge_documents()
    summary: Dict[str, int] = {}
    for document in documents:
        summary[document.doc_type] = summary.get(document.doc_type, 0) + 1
    summary["total"] = len(documents)
    return summary
