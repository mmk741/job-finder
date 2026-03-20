from datetime import UTC, datetime

from app.models.schemas import DiscoveredCompany, JobRead, SearchRequest
from app.services.company_discovery import CompanyTarget, discover_company_targets
from app.services.matcher import compute_score, is_recent, normalize_keywords
from app.sources.base import JobSource, RawJob
from app.sources.greenhouse import GreenhouseSource
from app.sources.lever import LeverSource


def _apply_company_limit(items: list, company_limit: int | None) -> list:
    if company_limit is None:
        return items
    return items[:company_limit]


def build_sources(source_names: list[str]) -> list[JobSource]:
    source_map: dict[str, JobSource] = {
        "greenhouse": GreenhouseSource(),
        "lever": LeverSource(),
    }
    return [source_map[name] for name in source_names if name in source_map]


async def collect_jobs(search: SearchRequest) -> list[RawJob]:
    jobs: list[RawJob] = []
    for source in build_sources(search.sources):
        for company in _apply_company_limit(search.companies, search.company_limit):
            try:
                jobs.extend(await source.fetch_jobs(company, search.job_title, search.location))
            except Exception:
                continue
    return jobs


async def collect_jobs_from_discovered_targets(
    search: SearchRequest,
    discovered_targets: list[CompanyTarget],
) -> list[RawJob]:
    jobs: list[RawJob] = []
    source_map = {source.name: source for source in build_sources(search.sources)}

    for target in _apply_company_limit(discovered_targets, search.company_limit):
        if not target.source or not target.identifier:
            continue
        source = source_map.get(target.source)
        if source is None:
            continue
        try:
            fetched_jobs = await source.fetch_jobs(target.identifier, search.job_title, search.location)
        except Exception:
            continue
        for job in fetched_jobs:
            job.company = target.company_name or job.company
        jobs.extend(fetched_jobs)

    return jobs


def _build_job_read(
    raw_jobs: list[RawJob],
    search: SearchRequest,
    merged_keywords: list[str],
) -> list[JobRead]:
    matched: list[JobRead] = []
    for raw_job in raw_jobs:
        if not is_recent(raw_job, search.days_recent):
            continue
        score, matched_keywords = compute_score(
            raw_job,
            search.job_title,
            search.location,
            merged_keywords,
            search.days_recent,
        )
        if score <= 0:
            continue
        now = datetime.now(UTC)
        matched.append(
            JobRead(
                id=abs(hash((raw_job.source, raw_job.external_id, raw_job.url))) % 10**9,
                source=raw_job.source,
                company=raw_job.company,
                external_id=raw_job.external_id,
                title=raw_job.title,
                location=raw_job.location,
                posted_at=raw_job.posted_at,
                description=raw_job.description,
                url=raw_job.url,
                matched_keywords=matched_keywords,
                score=score,
                created_at=now,
                updated_at=now,
            )
        )
    matched.sort(key=lambda item: item.score, reverse=True)
    return matched


async def run_search(search: SearchRequest) -> tuple[list[JobRead], list[str], list[DiscoveredCompany]]:
    merged_keywords = normalize_keywords(search.keywords + search.resume_keywords)
    normalized_search = search.model_copy(update={"keywords": merged_keywords})
    raw_jobs = await collect_jobs(normalized_search)

    discovered_targets: list[CompanyTarget] = []
    if search.company_websites:
        discovered_targets = await discover_company_targets(
            [{"company_name": website, "website_link": website} for website in search.company_websites],
            allowed_sources=search.sources,
        )
        raw_jobs.extend(await collect_jobs_from_discovered_targets(normalized_search, discovered_targets))

    matched = _build_job_read(raw_jobs, search, merged_keywords)
    discovered_companies = [
        DiscoveredCompany(
            company_name=target.company_name,
            homepage_url=target.homepage_url,
            careers_url=target.careers_url,
            source=target.source,
            identifier=target.identifier,
        )
        for target in _apply_company_limit(discovered_targets, search.company_limit)
    ]
    return matched, merged_keywords, discovered_companies


async def run_search_for_company_rows(
    search: SearchRequest,
    company_rows: list[dict[str, str]],
) -> tuple[list[JobRead], list[str], list[DiscoveredCompany]]:
    merged_keywords = normalize_keywords(search.keywords + search.resume_keywords)
    normalized_search = search.model_copy(update={"keywords": merged_keywords})
    selected_company_rows = _apply_company_limit(company_rows, search.company_limit)
    discovered_targets = await discover_company_targets(selected_company_rows, allowed_sources=search.sources)
    raw_jobs = await collect_jobs_from_discovered_targets(normalized_search, discovered_targets)
    matched = _build_job_read(raw_jobs, search, merged_keywords)
    discovered_companies = [
        DiscoveredCompany(
            company_name=target.company_name,
            homepage_url=target.homepage_url,
            careers_url=target.careers_url,
            source=target.source,
            identifier=target.identifier,
        )
        for target in discovered_targets
    ]
    return matched, merged_keywords, discovered_companies

