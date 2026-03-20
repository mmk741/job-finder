from contextlib import asynccontextmanager
from datetime import date

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import HTMLResponse

from app.config import get_settings
from app.models.schemas import (
    JobRead,
    ResumeKeywordsResponse,
    RunSearchResponse,
    SearchRequest,
)
from app.scheduler import create_scheduler
from app.services.excel_reader import extract_company_rows_from_excel
from app.services.file_store import (
    create_run_file,
    init_storage,
    list_jobs_from_runs,
)
from app.services.job_service import run_search_for_company_rows
from app.services.resume_parser import extract_keywords_from_upload

settings = get_settings()
scheduler = create_scheduler()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_storage()
    if settings.scheduler_enabled and not scheduler.running:
        scheduler.start()
    try:
        yield
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=False)


app = FastAPI(title=settings.app_name, lifespan=lifespan)


@app.get("/", response_class=HTMLResponse)
async def home() -> str:
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="utf-8">
        <title>Job Agent</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; line-height: 1.5; }
            h1, h2 { margin-bottom: 8px; }
            ul { padding-left: 20px; }
            a { color: #0b57d0; text-decoration: none; }
            a:hover { text-decoration: underline; }
            .card { margin-bottom: 24px; padding: 16px; border: 1px solid #ddd; border-radius: 8px; }
            code { background: #f4f4f4; padding: 2px 6px; border-radius: 4px; }
        </style>
    </head>
    <body>
        <h1>Job Agent</h1>
        <p>Use this page to quickly navigate to the main API areas.</p>

        <div class="card">
            <h2>Main Links</h2>
            <ul>
                <li><a href="/docs">Swagger API Docs</a></li>
                <li><a href="/health">Health Check</a></li>
                <li><a href="/jobs">All Saved Jobs</a></li>
            </ul>
        </div>

        <div class="card">
            <h2>Run Searches</h2>
            <ul>
                <li><a href="/docs#/default/run_search_now_search_run_post">Run Search</a></li>
                <li><a href="/docs#/default/resume_keywords_resume_keywords_post">Extract Resume Keywords</a></li>
            </ul>
        </div>

    </body>
    </html>
    """


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/resume/keywords", response_model=ResumeKeywordsResponse)
async def resume_keywords(file: UploadFile = File(...)) -> ResumeKeywordsResponse:
    keywords, preview = await extract_keywords_from_upload(file)
    return ResumeKeywordsResponse(keywords=keywords, preview=preview)


@app.post("/search/run", response_model=RunSearchResponse)
async def run_search_now(
    file: UploadFile = File(...),
    resume: UploadFile = File(...),
    company_names: list[str] | None = Form(None),
    location: str = Form(""),
    job_title: str = Form(""),
    keywords: list[str] | None = Form(None),
    days_recent: int = Form(2),
    company_limit: int | None = Form(None),
) -> RunSearchResponse:
    company_rows = await extract_company_rows_from_excel(file)
    if not company_rows:
        raise HTTPException(status_code=400, detail="Could not read company rows from the Excel file")

    resume_keywords, _ = await extract_keywords_from_upload(resume)
    request = SearchRequest(
        company_names=company_names or [],
        company_websites=[row["website_link"] for row in company_rows],
        location=location,
        job_title=job_title,
        keywords=keywords or [],
        days_recent=days_recent,
        company_limit=company_limit,
        resume_keywords=resume_keywords,
    )
    jobs, keywords_used, discovered_companies = await run_search_for_company_rows(request, company_rows)
    run_id = None
    run_file = None
    if jobs:
        run_id, run_file = create_run_file(
            jobs,
            request.model_dump(mode="json"),
            [company.model_dump(mode="json") for company in discovered_companies],
        )
    return RunSearchResponse(
        run_id=run_id,
        run_file=run_file,
        matched_count=len(jobs),
        persisted_count=len(jobs),
        keywords_used=keywords_used,
        discovered_companies=discovered_companies,
        jobs=jobs,
    )


@app.get("/jobs", response_model=list[JobRead])
async def list_jobs(result_date: date | None = Query(None, alias="date")) -> list[JobRead]:
    return list_jobs_from_runs(result_date=result_date)

