# Job Agent

Daily job scraper/API for a given company list with filters for location, title, keywords, recent posts, and optional resume-derived keywords.

## What This MVP Includes

- `FastAPI` backend
- Daily scheduler with built-in `asyncio`
- Source adapters for:
  - `Greenhouse`
  - `Lever`
- Homepage to careers-page discovery from company website URLs
- Excel upload support for company website lists
- File-based run storage in `result/runs`
- Resume keyword extraction for `pdf`, `docx`, and `txt`
- Saved searches that can run manually or automatically once per day

## Company Inputs Supported

You can now use either:

- `companies`: source-specific slugs
- `company_websites`: company homepages like `https://www.adobe.com`
- Excel upload with `Company Name` and `Website Link` columns
- optional `company_limit`: only scrape the first `N` companies

If you use `companies`, they should be the source-specific company slug:

- Greenhouse example: `stripe`, `airtable`, `notion`
- Lever example: `netflix`, `figma`, `coinbase`

If you use `company_websites`, the app will:

1. open the homepage
2. look for careers/jobs links
3. follow the careers page
4. detect whether it is a supported platform
5. scrape from supported platforms like `Greenhouse` and `Lever`

If a company uses a custom careers site or Workday, you would add another adapter in `app/sources/`.

## Setup

Recommended runtime: `Python 3.14.3`

```powershell
cd D:\personal\job-agent
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy env.example .env
uvicorn app.main:app --reload
```

Open the API docs at `http://127.0.0.1:8000/docs`.

## How To Run

### First time

```powershell
cd D:\personal\job-agent
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy env.example .env
uvicorn app.main:app --reload
```

### Next time

```powershell
cd D:\personal\job-agent
.venv\Scripts\activate
uvicorn app.main:app --reload
```

## How To Use

### Use from Excel

1. Open `http://127.0.0.1:8000/docs`
2. Open `POST /search/run-from-excel`
3. Click `Try it out`
4. Upload the Excel file
5. Fill:
   - `sources` as `greenhouse,lever`
   - `location`
   - `job_title`
   - `keywords` as comma-separated values
   - `days_recent` as `1` or `2`
   - `company_limit` for how many companies to process
   - optional `resume`
6. Click `Execute`

### Use from website links

1. Open `POST /search/run`
2. Click `Try it out`
3. Paste JSON like:

```json
{
  "companies": [],
  "company_websites": ["https://www.adobe.com", "https://stripe.com"],
  "sources": ["greenhouse", "lever"],
  "location": "Bangalore",
  "job_title": "Software Engineer",
  "keywords": ["python", "fastapi", "sql"],
  "days_recent": 2,
  "company_limit": 10,
  "resume_keywords": []
}
```

4. Click `Execute`

### Use resume keyword extraction

1. Open `POST /resume/keywords`
2. Upload a `pdf`, `docx`, or text resume
3. Click `Execute`
4. Use the returned keywords in your search

### Use saved searches

1. Open `POST /saved-searches`
2. Save your search configuration with `is_active: true`
3. The app will run it daily based on:
   - `DAILY_RUN_HOUR`
   - `DAILY_RUN_MINUTE`
   - `TIMEZONE`

### Where results are saved

- run files: `result/runs/`
- saved searches: `result/saved_searches.json`

## Main Endpoints

- `POST /resume/keywords`
  - Upload a resume and extract likely search keywords.
- `POST /search/run`
  - Run a job search using JSON input, including `company_websites`.
- `POST /search/run-with-resume`
  - Run a search with form input plus a resume file upload.
- `POST /search/run-from-excel`
  - Upload the Excel file and search from homepage URLs automatically.
  - You can pass `company_limit=10` to scrape only the first 10 companies from the sheet.
- `POST /saved-searches`
  - Save a daily search configuration.
- `POST /saved-searches/{id}/run`
  - Manually run a saved search.
- `GET /jobs`
  - See jobs aggregated from saved run files.

## Example Search Payload

```json
{
  "companies": [],
  "company_websites": ["https://stripe.com", "https://www.notion.so"],
  "sources": ["greenhouse", "lever"],
  "location": "Bangalore",
  "job_title": "Software Engineer",
  "keywords": ["python", "fastapi", "sql", "api"],
  "days_recent": 2,
  "company_limit": 10,
  "resume_keywords": ["docker", "aws"]
}
```

You can still use slug-based input:

```json
{
  "companies": ["stripe", "notion"],
  "company_websites": [],
  "sources": ["greenhouse", "lever"],
  "location": "Bangalore",
  "job_title": "Software Engineer",
  "keywords": ["python", "fastapi", "sql", "api"],
  "days_recent": 2,
  "company_limit": 10,
  "resume_keywords": []
}
```

## How Daily Scheduling Works

The app starts one scheduled run every day using:

- `DAILY_RUN_HOUR`
- `DAILY_RUN_MINUTE`
- `TIMEZONE`

It executes all active saved searches from `result/saved_searches.json`.

## File Storage

Each search run is saved as a JSON file:

```text
result/runs/2026-03-20-search-001.json
```

Storage is resolved from the project root, so results are always saved inside this `job-agent` project even if you start the app from another directory.

Each run file contains:

- search filters used
- discovered careers pages
- full matched jobs
- simple result items with:
  - `company_name`
  - `job_link`

## Suggested Next Improvements

- Add Playwright for sites that need browser automation
- Add notifications by email or Telegram
- Add Workday / Ashby / custom careers page adapters
- Add authentication and a frontend dashboard

