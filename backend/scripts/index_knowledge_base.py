from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.rag_knowledge_loader import (  # noqa: E402
    knowledge_document_summary,
    load_rag_knowledge_documents,
)
from app.services.vector_store import (  # noqa: E402
    search_knowledge_documents,
    upsert_knowledge_documents,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Index role profiles, skill dictionary, JD samples and interview questions into knowledge vectors.",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Run a few sample searches after indexing.",
    )
    args = parser.parse_args()

    documents = [document.to_vector_payload() for document in load_rag_knowledge_documents()]
    result = upsert_knowledge_documents(documents)
    payload = {
        "summary": knowledge_document_summary(),
        "index_result": result,
    }

    if args.verify:
        payload["samples"] = {
            query: search_knowledge_documents(query, top_k=3)
            for query in ["后端开发", "Python FastAPI", "AI应用开发", "STAR"]
        }

    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
