from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import get_settings
from app.models.schemas import SearchRequest
from app.services.file_store import create_run_file, list_saved_searches
from app.services.job_service import run_search


async def run_active_saved_searches() -> None:
    searches = [search for search in list_saved_searches() if search.is_active]
    for saved_search in searches:
        request = SearchRequest(
            companies=saved_search.companies,
            company_websites=saved_search.company_websites,
            sources=saved_search.sources,
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


def create_scheduler() -> AsyncIOScheduler:
    settings = get_settings()
    scheduler = AsyncIOScheduler(timezone=settings.timezone)
    scheduler.add_job(
        run_active_saved_searches,
        trigger="cron",
        hour=settings.daily_run_hour,
        minute=settings.daily_run_minute,
        id="daily-saved-searches",
        replace_existing=True,
    )
    return scheduler

