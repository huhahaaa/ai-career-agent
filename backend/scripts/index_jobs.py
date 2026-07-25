import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Iterable


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.matching import index_approved_jobs  # noqa: E402


def read_jsonl(path: Path) -> Iterable[Dict]:
    with path.open("r", encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    "invalid JSON at %s:%s" % (path, line_number)
                ) from exc


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Index approved jobs from a JSONL file into Chroma.",
    )
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=PROJECT_DIR / "data" / "processed" / "jobs_clean.jsonl",
    )
    args = parser.parse_args()
    path = args.path.expanduser().resolve()
    if not path.is_file():
        raise SystemExit("job data file not found: %s" % path)

    result = index_approved_jobs(read_jsonl(path))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
