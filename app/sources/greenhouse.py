from datetime import datetime

import httpx
from bs4 import BeautifulSoup

from app.config import get_settings
from app.sources.base import JobSource, RawJob


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class GreenhouseSource(JobSource):
    name = "greenhouse"

    async def fetch_jobs(self, company: str, job_title: str = "", location: str = "") -> list[RawJob]:
        settings = get_settings()
        headers = {"User-Agent": settings.user_agent}
        url = f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs"
        params = {"content": "true"}

        async with httpx.AsyncClient(timeout=settings.request_timeout_seconds, headers=headers) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()

        results: list[RawJob] = []
        for job in payload.get("jobs", []):
            title = job.get("title", "")
            job_location = (job.get("location") or {}).get("name", "")
            if job_title and job_title.lower() not in title.lower():
                continue
            if location and location.lower() not in job_location.lower():
                continue

            description_html = job.get("content", "")
            description = BeautifulSoup(description_html, "html.parser").get_text(" ", strip=True)
            results.append(
                RawJob(
                    source=self.name,
                    company=company,
                    external_id=str(job.get("id")),
                    title=title,
                    location=job_location,
                    posted_at=_parse_iso_datetime(job.get("updated_at")),
                    description=description,
                    url=job.get("absolute_url", ""),
                )
            )
        return results

