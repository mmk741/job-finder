import asyncio
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.config import get_settings
from app.models.schemas import SearchRequest
from app.services.file_store import create_run_file, list_saved_searches
from app.services.job_service import run_search


async def run_active_saved_searches() -> None:
    searches = [search for search in list_saved_searches() if search.is_active]
    for saved_search in searches:
        request = SearchRequest(
            company_names=saved_search.company_names,
            company_websites=saved_search.company_websites,
            location=saved_search.location,
            job_title=saved_search.job_title,
            keywords=saved_search.keywords,
            days_recent=saved_search.days_recent,
            company_limit=saved_search.company_limit,
            resume_keywords=saved_search.resume_keywords,
        )
        jobs, _, discovered_companies = await run_search(request)
        create_run_file(
            jobs,
            request.model_dump(mode="json"),
            [company.model_dump(mode="json") for company in discovered_companies],
        )


def _seconds_until_next_run(hour: int, minute: int, timezone_name: str) -> float:
    timezone = ZoneInfo(timezone_name)
    now = datetime.now(timezone)
    next_run = datetime.combine(now.date(), time(hour=hour, minute=minute), tzinfo=timezone)
    if next_run <= now:
        next_run += timedelta(days=1)
    return max((next_run - now).total_seconds(), 1.0)


class DailyScheduler:
    def __init__(self, hour: int, minute: int, timezone_name: str):
        self.hour = hour
        self.minute = minute
        self.timezone_name = timezone_name
        self._task: asyncio.Task | None = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def _runner(self) -> None:
        while True:
            await asyncio.sleep(_seconds_until_next_run(self.hour, self.minute, self.timezone_name))
            try:
                await run_active_saved_searches()
            except Exception:
                # Keep the scheduler alive even if one daily run fails.
                await asyncio.sleep(1)

    def start(self) -> None:
        if self.running:
            return
        self._task = asyncio.create_task(self._runner(), name="daily-saved-searches")

    def shutdown(self, wait: bool = False) -> None:
        if not self.running:
            return
        assert self._task is not None
        self._task.cancel()


def create_scheduler() -> DailyScheduler:
    settings = get_settings()
    return DailyScheduler(
        hour=settings.daily_run_hour,
        minute=settings.daily_run_minute,
        timezone_name=settings.timezone,
    )

