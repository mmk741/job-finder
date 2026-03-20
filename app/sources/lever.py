from datetime import UTC, datetime

import httpx
from bs4 import BeautifulSoup

from app.config import get_settings
from app.sources.base import JobSource, RawJob


def _parse_lever_datetime(value: int | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromtimestamp(value / 1000, tz=UTC)


class LeverSource(JobSource):
    name = "lever"

    async def fetch_jobs(self, company: str, job_title: str = "", location: str = "") -> list[RawJob]:
        settings = get_settings()
        headers = {"User-Agent": settings.user_agent}
        url = f"https://api.lever.co/v0/postings/{company}"
        params = {"mode": "json"}

        async with httpx.AsyncClient(timeout=settings.request_timeout_seconds, headers=headers) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()

        results: list[RawJob] = []
        for job in payload:
            title = job.get("text", "")
            job_location = (job.get("categories") or {}).get("location", "")
            if job_title and job_title.lower() not in title.lower():
                continue
            if location and location.lower() not in job_location.lower():
                continue

            description_raw = job.get("descriptionPlain") or job.get("description") or ""
            description = BeautifulSoup(description_raw, "html.parser").get_text(" ", strip=True)
            results.append(
                RawJob(
                    source=self.name,
                    company=company,
                    external_id=str(job.get("id")),
                    title=title,
                    location=job_location,
                    posted_at=_parse_lever_datetime(job.get("createdAt")),
                    description=description,
                    url=job.get("hostedUrl") or job.get("applyUrl") or "",
                )
            )
        return results

