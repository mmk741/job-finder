from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class SearchRequest(BaseModel):
    companies: list[str] = Field(default_factory=list)
    company_websites: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=lambda: ["greenhouse", "lever"])
    location: str = ""
    job_title: str = ""
    keywords: list[str] = Field(default_factory=list)
    days_recent: int = Field(default=2, ge=1, le=14)
    company_limit: int | None = Field(default=None, ge=1)
    resume_keywords: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_company_inputs(self) -> "SearchRequest":
        if not self.companies and not self.company_websites:
            raise ValueError("Provide at least one company slug or company website")
        return self


class SavedSearchCreate(SearchRequest):
    name: str = Field(..., min_length=1)
    is_active: bool = True


class DiscoveredCompany(BaseModel):
    company_name: str
    homepage_url: str
    careers_url: str | None = None
    source: str | None = None
    identifier: str | None = None


class SavedSearchRead(SavedSearchCreate):
    id: int
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class JobRead(BaseModel):
    id: int
    source: str
    company: str
    external_id: str
    title: str
    location: str
    posted_at: datetime | None = None
    description: str
    url: str
    matched_keywords: list[str]
    score: float
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class RunSearchResponse(BaseModel):
    run_id: str | None = None
    run_file: str | None = None
    matched_count: int
    persisted_count: int
    keywords_used: list[str]
    discovered_companies: list[DiscoveredCompany]
    jobs: list[JobRead]


class ResumeKeywordsResponse(BaseModel):
    keywords: list[str]
    preview: str

