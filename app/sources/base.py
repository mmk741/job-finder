from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class RawJob:
    source: str
    company: str
    external_id: str
    title: str
    location: str
    posted_at: datetime | None
    description: str
    url: str


class JobSource(ABC):
    name: str

    @abstractmethod
    async def fetch_jobs(self, company: str, job_title: str = "", location: str = "") -> list[RawJob]:
        raise NotImplementedError

