from dataclasses import dataclass
import logging
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.config import get_settings

logger = logging.getLogger(__name__)

CAREERS_KEYWORDS = (
    "careers",
    "career",
    "jobs",
    "job",
    "join-us",
    "joinus",
    "work-with-us",
    "workwithus",
    "opportunities",
)

COMMON_CAREERS_PATHS = (
    "/careers",
    "/career",
    "/jobs",
    "/join-us",
    "/company/careers",
)


@dataclass
class CompanyTarget:
    company_name: str
    homepage_url: str
    careers_url: str | None
    source: str | None
    identifier: str | None


def _normalize_url(url: str) -> str:
    if url.startswith(("http://", "https://")):
        return url.rstrip("/")
    return f"https://{url.rstrip('/')}"


def _same_host(url_a: str, url_b: str) -> bool:
    return urlparse(url_a).netloc.lower() == urlparse(url_b).netloc.lower()


def _score_link(link_text: str, url: str, homepage_url: str) -> int:
    text = f"{link_text} {url}".lower()
    score = 0
    for keyword in CAREERS_KEYWORDS:
        if keyword in text:
            score += 10
    if _same_host(homepage_url, url):
        score += 5
    return score


def _extract_links(html: str, base_url: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    links: list[tuple[str, str]] = []
    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href", "").strip()
        if not href or href.startswith(("mailto:", "tel:", "#", "javascript:")):
            continue
        links.append((anchor.get_text(" ", strip=True), urljoin(base_url, href)))
    return links


def _parse_greenhouse_identifier(url: str) -> str | None:
    parsed = urlparse(url)
    if "greenhouse.io" not in parsed.netloc.lower():
        return None
    parts = [part for part in parsed.path.split("/") if part]
    return parts[0] if parts else None


def _parse_lever_identifier(url: str) -> str | None:
    parsed = urlparse(url)
    if "lever.co" not in parsed.netloc.lower():
        return None
    parts = [part for part in parsed.path.split("/") if part]
    return parts[0] if parts else None


def detect_source_from_url(url: str) -> tuple[str | None, str | None]:
    greenhouse_id = _parse_greenhouse_identifier(url)
    if greenhouse_id:
        return "greenhouse", greenhouse_id

    lever_id = _parse_lever_identifier(url)
    if lever_id:
        return "lever", lever_id

    return None, None


async def _find_supported_board_url(client: httpx.AsyncClient, url: str) -> tuple[str | None, str | None, str | None]:
    logger.info("Trying careers candidate: %s", url)
    try:
        response = await client.get(url, follow_redirects=True)
        response.raise_for_status()
    except Exception as exc:
        logger.warning("Failed to open careers candidate %s: %s", url, exc)
        return None, None, None

    final_url = str(response.url)
    source, identifier = detect_source_from_url(final_url)
    if source and identifier:
        logger.info("Detected supported source %s (%s) at %s", source, identifier, final_url)
        return final_url, source, identifier

    for _, link_url in _extract_links(response.text, final_url):
        source, identifier = detect_source_from_url(link_url)
        if source and identifier:
            logger.info("Detected supported nested source %s (%s) at %s", source, identifier, link_url)
            return link_url, source, identifier

    logger.info("No supported source found at candidate %s (final url %s)", url, final_url)
    return final_url, None, None


async def discover_company_target(
    company_name: str,
    homepage_url: str,
    allowed_sources: list[str],
) -> CompanyTarget:
    settings = get_settings()
    normalized_homepage = _normalize_url(homepage_url)
    headers = {"User-Agent": settings.user_agent}
    logger.info("Checking company homepage for %s: %s", company_name, normalized_homepage)

    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds, headers=headers) as client:
        try:
            response = await client.get(normalized_homepage, follow_redirects=True)
            response.raise_for_status()
        except Exception as exc:
            logger.warning("Failed to open homepage for %s at %s: %s", company_name, normalized_homepage, exc)
            return CompanyTarget(company_name, normalized_homepage, None, None, None)

        homepage_final = str(response.url)
        logger.info("Opened homepage for %s -> %s", company_name, homepage_final)
        homepage_source, homepage_identifier = detect_source_from_url(homepage_final)
        if homepage_source in allowed_sources and homepage_identifier:
            logger.info(
                "Homepage for %s directly resolved to supported source %s (%s)",
                company_name,
                homepage_source,
                homepage_identifier,
            )
            return CompanyTarget(company_name, normalized_homepage, homepage_final, homepage_source, homepage_identifier)

        links = _extract_links(response.text, homepage_final)
        scored_links = [
            (link_url, _score_link(link_text, link_url, homepage_final))
            for link_text, link_url in links
        ]
        ranked_links = sorted(scored_links, key=lambda item: item[1], reverse=True)

        candidates = [link_url for link_url, score in ranked_links if score > 0]
        if not candidates:
            candidates = [urljoin(homepage_final, path) for path in COMMON_CAREERS_PATHS]
        logger.info("Generated %s careers candidate(s) for %s", len(candidates), company_name)

        seen: set[str] = set()
        for candidate in candidates[:10]:
            if candidate in seen:
                continue
            seen.add(candidate)
            careers_url, source, identifier = await _find_supported_board_url(client, candidate)
            if source in allowed_sources and identifier:
                logger.info("Found careers source for %s at %s", company_name, careers_url)
                return CompanyTarget(company_name, normalized_homepage, careers_url, source, identifier)
            if careers_url and any(keyword in careers_url.lower() for keyword in CAREERS_KEYWORDS):
                logger.info("Found careers-like URL for %s at %s without supported ATS", company_name, careers_url)
                return CompanyTarget(company_name, normalized_homepage, careers_url, source, identifier)

    logger.info("No careers page detected for %s from homepage %s", company_name, normalized_homepage)
    return CompanyTarget(company_name, normalized_homepage, None, None, None)


async def discover_company_targets(
    companies: list[dict[str, str]],
    allowed_sources: list[str],
) -> list[CompanyTarget]:
    targets: list[CompanyTarget] = []
    for company in companies:
        target = await discover_company_target(
            company_name=company.get("company_name", company.get("website_link", "")),
            homepage_url=company.get("website_link", ""),
            allowed_sources=allowed_sources,
        )
        targets.append(target)
    return targets

