from app.services.rag_knowledge_loader import (
    knowledge_document_summary,
    load_rag_knowledge_documents,
    load_role_profile_documents,
    load_skill_dictionary_documents,
)


def test_rag_knowledge_loader_builds_searchable_documents():
    documents = load_rag_knowledge_documents()
    summary = knowledge_document_summary()

    assert summary["total"] == len(documents)
    assert summary["role_profile"] >= 1
    assert summary["skill_definition"] >= 1
    assert summary["job_jd_sample"] >= 1
    assert summary["interview_question"] >= 1
    assert all(document.doc_id for document in documents)
    assert all(document.content.strip() for document in documents)


def test_role_profile_document_contains_core_and_bonus_skills():
    documents = load_role_profile_documents()
    backend_doc = next(document for document in documents if document.metadata.get("role") == "后端开发")

    assert "必备能力" in backend_doc.content
    assert "加分能力" in backend_doc.content
    assert "Python/Java/Go" in backend_doc.content


def test_skill_dictionary_document_contains_aliases():
    documents = load_skill_dictionary_documents()
    python_doc = next(document for document in documents if document.metadata.get("skill") == "Python")

    assert python_doc.doc_type == "skill_definition"
    assert "同义词" in python_doc.content
    assert "Python 开发" in python_doc.content
