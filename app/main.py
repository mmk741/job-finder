from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse

from app.config import get_settings
from app.models.schemas import (
    JobRead,
    ResumeKeywordsResponse,
    RunSearchResponse,
    SavedSearchCreate,
    SavedSearchRead,
    SearchRequest,
)
from app.scheduler import create_scheduler
from app.services.excel_reader import extract_company_rows_from_excel
from app.services.file_store import (
    create_run_file,
    get_saved_search,
    init_storage,
    list_jobs_from_runs,
    list_saved_searches as list_saved_search_records,
    upsert_saved_search,
)
from app.services.job_service import run_search, run_search_for_company_rows
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
                <li><a href="/saved-searches">Saved Searches</a></li>
            </ul>
        </div>

        <div class="card">
            <h2>Run Searches</h2>
            <ul>
                <li><a href="/docs#/default/run_search_now_search_run_post">Run Search from JSON</a></li>
                <li><a href="/docs#/default/run_search_with_resume_search_run_with_resume_post">Run Search with Resume</a></li>
                <li><a href="/docs#/default/run_search_from_excel_search_run_from_excel_post">Run Search from Excel</a></li>
                <li><a href="/docs#/default/resume_keywords_resume_keywords_post">Extract Resume Keywords</a></li>
            </ul>
        </div>

        <div class="card">
            <h2>Saved Search Actions</h2>
            <ul>
                <li><a href="/docs#/default/create_saved_search_saved_searches_post">Create or Update Saved Search</a></li>
                <li><a href="/saved-searches">View Saved Searches</a></li>
            </ul>
            <p>To manually run a saved search, open <code>/saved-searches</code>, note the ID, then use the matching action in <a href="/docs">Swagger Docs</a>.</p>
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
async def run_search_now(search: SearchRequest) -> RunSearchResponse:
    jobs, keywords_used, discovered_companies = await run_search(search)
    run_id, run_file = create_run_file(
        jobs,
        search.model_dump(mode="json"),
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


@app.post("/search/run-with-resume", response_model=RunSearchResponse)
async def run_search_with_resume(
    companies: str = Form(...),
    sources: str = Form("greenhouse,lever"),
    location: str = Form(""),
    job_title: str = Form(""),
    keywords: str = Form(""),
    days_recent: int = Form(2),
    company_limit: int | None = Form(None),
    resume: UploadFile = File(...),
) -> RunSearchResponse:
    resume_keywords, _ = await extract_keywords_from_upload(resume)
    request = SearchRequest(
        companies=[item.strip() for item in companies.split(",") if item.strip()],
        company_websites=[],
        sources=[item.strip() for item in sources.split(",") if item.strip()],
        location=location,
        job_title=job_title,
        keywords=[item.strip() for item in keywords.split(",") if item.strip()],
        days_recent=days_recent,
        company_limit=company_limit,
        resume_keywords=resume_keywords,
    )
    jobs, keywords_used, discovered_companies = await run_search(request)
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


@app.post("/search/run-from-excel", response_model=RunSearchResponse)
async def run_search_from_excel(
    file: UploadFile = File(...),
    sources: str = Form("greenhouse,lever"),
    location: str = Form(""),
    job_title: str = Form(""),
    keywords: str = Form(""),
    days_recent: int = Form(2),
    company_limit: int | None = Form(None),
    resume: UploadFile | None = File(None),
) -> RunSearchResponse:
    company_rows = await extract_company_rows_from_excel(file)
    if not company_rows:
        raise HTTPException(status_code=400, detail="Could not read company rows from the Excel file")

    resume_keywords: list[str] = []
    if resume is not None:
        resume_keywords, _ = await extract_keywords_from_upload(resume)

    request = SearchRequest(
        companies=[],
        company_websites=[row["website_link"] for row in company_rows],
        sources=[item.strip() for item in sources.split(",") if item.strip()],
        location=location,
        job_title=job_title,
        keywords=[item.strip() for item in keywords.split(",") if item.strip()],
        days_recent=days_recent,
        company_limit=company_limit,
        resume_keywords=resume_keywords,
    )
    jobs, keywords_used, discovered_companies = await run_search_for_company_rows(request, company_rows)
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
async def list_jobs() -> list[JobRead]:
    return list_jobs_from_runs()


@app.get("/saved-searches", response_model=list[SavedSearchRead])
async def list_saved_searches() -> list[SavedSearchRead]:
    return list_saved_search_records()


@app.post("/saved-searches", response_model=SavedSearchRead)
async def create_saved_search(payload: SavedSearchCreate) -> SavedSearchRead:
    return upsert_saved_search(payload)


@app.post("/saved-searches/{search_id}/run", response_model=RunSearchResponse)
async def run_saved_search(search_id: int) -> RunSearchResponse:
    saved_search = get_saved_search(search_id)
    if saved_search is None:
        raise HTTPException(status_code=404, detail="Saved search not found")
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
    jobs, keywords_used, discovered_companies = await run_search(request)
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

