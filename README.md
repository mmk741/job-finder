# Job Agent

Daily job scraper/API for a given company list with filters for location, title, keywords, recent posts, and optional resume-derived keywords.

## What This MVP Includes

- `FastAPI` backend
- Daily scheduler with built-in `asyncio`
- Scrapes only from company career pages discovered from company websites
- Excel upload support for company website lists
- File-based run storage in `result/runs`
- Resume keyword extraction for `pdf`, `docx`, and `txt`

## Search Source

Primary input is the Excel file with:

- `Company Name`
- `Website Link`

Optional user input:

- `company_names`
  - a list of names like `Adobe`, `Stripe`
  - if provided, the app only processes those companies from the Excel file
- optional `company_limit`: only scrape the first `N` companies

The app will:

1. open the homepage
2. look for careers/jobs links
3. follow the careers page
4. detect whether it is a supported careers platform
5. scrape jobs only from that company's careers page flow

Currently supported careers platforms:

- `Greenhouse`
- `Lever`

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

There is one main search flow.

1. Open `http://127.0.0.1:8000/docs`
2. Open `POST /search/run`
3. Click `Try it out`
4. Provide either:
   - an Excel file, or
   - `company_urls` as a list
5. Upload the resume
6. Fill optional filters:
   - `company_names`
   - `company_urls`
   - `location`
   - `job_title`
   - `keywords`
   - `days_recent`
   - `company_limit`
7. Click `Execute`

Notes:

- provide either `file` or `company_urls`
- `resume` is mandatory
- `company_names` is optional and should be given as a list
- `company_urls` is optional and should be given as a list
- `keywords` is optional and should be given as a list
- if `company_names` is empty, the app checks all provided companies
- if `company_urls` is provided, the effective company count follows the number of URLs you passed
- the app matches only from company career pages
- homepage and careers-page attempts are logged in the server console

### Use resume keyword extraction

1. Open `POST /resume/keywords`
2. Upload a `pdf`, `docx`, or text resume
3. Click `Execute`
4. Use the returned keywords in your search

### Where results are saved

- run files: `result/runs/`

## Main Endpoints

- `POST /search/run`
  - Main search endpoint
  - Excel file optional
  - company URL list optional
  - at least one of them is required
  - Resume required
  - `company_names` optional list
  - `company_urls` optional list
  - `keywords` optional list
- `POST /resume/keywords`
  - Upload a resume and extract likely search keywords.
- `GET /jobs`
  - See jobs aggregated from saved run files.
  - By default it shows the current date's results.
  - Optional query: `date=YYYY-MM-DD`

## Search Inputs

Main search endpoint inputs:

- `file`
  - optional Excel file with `Company Name` and `Website Link`
- `company_urls`
  - optional list of company URLs
- one of `file` or `company_urls`
  - required
- `resume`
  - mandatory resume file
- `company_names`
  - optional list of company names to filter from the Excel file
- `location`
- `job_title`
- `keywords`
  - optional list
- `days_recent`
- `company_limit`

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

Run files are created only when at least one matching job is found.

## Viewing Results

- `GET /jobs`
  - shows only today's results if no date is passed
  - you can also filter by a specific date
  - example: `http://127.0.0.1:8000/jobs?date=2026-03-20`

## Suggested Next Improvements

- Add Playwright for sites that need browser automation
- Add notifications by email or Telegram
- Add Workday / Ashby / custom careers page adapters
- Add authentication and a frontend dashboard

