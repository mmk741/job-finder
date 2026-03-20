import re
from datetime import UTC, datetime, timedelta

from app.sources.base import RawJob


def normalize_keywords(keywords: list[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for keyword in keywords:
        cleaned = keyword.strip().lower()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            normalized.append(cleaned)
    return normalized


def compute_score(job: RawJob, job_title: str, location: str, keywords: list[str], days_recent: int) -> tuple[float, list[str]]:
    score = 0.0
    matched_keywords: list[str] = []
    description = job.description.lower()
    title = job.title.lower()
    job_location = job.location.lower()

    if job_title and job_title.lower() in title:
        score += 30
    if location and location.lower() in job_location:
        score += 20

    for keyword in normalize_keywords(keywords):
        if keyword in description or keyword in title:
            matched_keywords.append(keyword)
            score += 10

    if job.posted_at:
        cutoff_24h = datetime.now(UTC) - timedelta(days=1)
        cutoff_recent = datetime.now(UTC) - timedelta(days=days_recent)
        posted_at = job.posted_at.astimezone(UTC)
        if posted_at >= cutoff_24h:
            score += 25
        elif posted_at >= cutoff_recent:
            score += 15
        else:
            score -= 100

    return score, matched_keywords


def is_recent(job: RawJob, days_recent: int) -> bool:
    if not job.posted_at:
        return True
    return job.posted_at.astimezone(UTC) >= datetime.now(UTC) - timedelta(days=days_recent)


def extract_terms_from_text(text: str, limit: int = 25) -> list[str]:
    stop_words = {
        "and",
        "the",
        "for",
        "with",
        "that",
        "this",
        "you",
        "your",
        "are",
        "our",
        "will",
        "from",
        "have",
        "has",
        "not",
        "but",
        "job",
        "role",
        "team",
        "work",
        "experience",
        "years",
        "skills",
    }
    counts: dict[str, int] = {}
    for token in re.findall(r"[A-Za-z][A-Za-z0-9+#\.-]{2,}", text.lower()):
        if token in stop_words:
            continue
        counts[token] = counts.get(token, 0) + 1
    return [word for word, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]]

