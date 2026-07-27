from typing import Dict, Iterable, List


def normalize_import_batch(raw_jobs: Iterable[Dict]) -> List[Dict]:
    return [dict(item) for item in raw_jobs]

