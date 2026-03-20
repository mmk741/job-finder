import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from app.models.schemas import JobRead, SavedSearchCreate, SavedSearchRead

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESULT_DIR = PROJECT_ROOT / "result"
RUNS_DIR = RESULT_DIR / "runs"
SAVED_SEARCHES_FILE = RESULT_DIR / "saved_searches.json"


def init_storage() -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    if not SAVED_SEARCHES_FILE.exists():
        SAVED_SEARCHES_FILE.write_text("[]", encoding="utf-8")


def _read_json_file(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json_file(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


def _next_daily_run_number(run_date: str) -> int:
    pattern = f"{run_date}-search-"
    numbers: list[int] = []
    for file in RUNS_DIR.glob(f"{pattern}*.json"):
        suffix = file.stem.replace(pattern, "")
        try:
            numbers.append(int(suffix))
        except ValueError:
            continue
    return (max(numbers) + 1) if numbers else 1


def create_run_file(jobs: list[JobRead], search_payload: dict[str, Any], discovered_companies: list[dict[str, Any]]) -> tuple[str, str]:
    now = datetime.now(UTC)
    run_date = now.date().isoformat()
    run_number = _next_daily_run_number(run_date)
    run_id = f"{run_date}-search-{run_number:03d}"
    run_path = RUNS_DIR / f"{run_id}.json"

    payload = {
        "run_id": run_id,
        "created_at": now.isoformat(),
        "filters": search_payload,
        "discovered_companies": discovered_companies,
        "jobs": [job.model_dump(mode="json") for job in jobs],
        "results": [
            {
                "company_name": job.company,
                "job_link": job.url,
            }
            for job in jobs
        ],
    }
    _write_json_file(run_path, payload)
    return run_id, str(run_path)


def list_saved_searches() -> list[SavedSearchRead]:
    payload = _read_json_file(SAVED_SEARCHES_FILE, [])
    return [SavedSearchRead.model_validate(item) for item in payload]


def get_saved_search(search_id: int) -> SavedSearchRead | None:
    for search in list_saved_searches():
        if search.id == search_id:
            return search
    return None


def upsert_saved_search(payload: SavedSearchCreate) -> SavedSearchRead:
    searches = _read_json_file(SAVED_SEARCHES_FILE, [])
    now = datetime.now(UTC).isoformat()

    for index, search in enumerate(searches):
        if search["name"] == payload.name:
            updated = {
                **search,
                **payload.model_dump(),
                "updated_at": now,
            }
            searches[index] = updated
            _write_json_file(SAVED_SEARCHES_FILE, searches)
            return SavedSearchRead.model_validate(updated)

    next_id = max((item.get("id", 0) for item in searches), default=0) + 1
    created = {
        "id": next_id,
        **payload.model_dump(),
        "created_at": now,
        "updated_at": now,
    }
    searches.append(created)
    _write_json_file(SAVED_SEARCHES_FILE, searches)
    return SavedSearchRead.model_validate(created)


def list_jobs_from_runs(result_date: date | None = None) -> list[JobRead]:
    target_date = result_date or datetime.now(UTC).date()
    jobs: list[JobRead] = []
    for run_file in sorted(RUNS_DIR.glob("*.json"), reverse=True):
        payload = _read_json_file(run_file, {})
        created_at_raw = payload.get("created_at")
        if not created_at_raw:
            continue
        try:
            created_at = datetime.fromisoformat(created_at_raw.replace("Z", "+00:00")).date()
        except ValueError:
            continue
        if created_at != target_date:
            continue
        for job in payload.get("jobs", []):
            jobs.append(JobRead.model_validate(job))
    jobs.sort(key=lambda item: (item.score, item.created_at), reverse=True)
    return jobs

