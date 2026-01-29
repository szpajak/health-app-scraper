# health-app-scraper

Tools and notebooks for scraping health-related mobile apps and repositories, then triaging them with rule-based filters and an LLM for inclusion/exclusion decisions.

## Overview
- **App store scraping:** Pulls metadata from Apple and Google Play using keyword searches (e.g., hay fever, asthma, rhinitis) and saves CSVs. 
- **Repository scraping:** CSV exports of GitHub/GitLab asthma-related repos live in `data/`.
- **Filtering:** Article-based criteria filter apps by category, recency, keywords, and exclusions like alternative medicine. 
- **LLM assessment:** `llm_assessment.py` queries a Gemini model to include/exclude apps and writes per-row decisions. 

## Repository structure
- `app_scraper.ipynb` — Apple App Store scraping notebook for asthma-related keywords. Outputs `data/app_store_asthma_apps_desc.csv` and variants.
- `app_scraper_article.ipynb` — Reproduction of article methodology: Apple + Google scraping across US/GB/AU, filtering logic, and saved CSVs.
- `llm_assessment.py` — CLI script to run Gemini on CSV rows and save `_llm.csv` outputs.
- `data/` — Collected datasets (Apple/Google app exports, filtered sets, GitHub/GitLab repo lists).
- `pyproject.toml` / `requirements.txt` — Dependencies (requests, pandas, google-play-scraper, google-genai). 

## Setup
1) Python 3.12+ (project targets 3.12). 
2) Create and activate a virtual environment (example):
```bash
python -m venv .venv
. .venv/bin/activate  # Windows: .venv\Scripts\activate
```
3) Install dependencies:
```bash
pip install -r requirements.txt
# or: pip install -e .
```
4) For LLM assessments, export `GOOGLE_API_KEY` (Gemini). 

## Using the notebooks
Open notebooks in Jupyter or VS Code. Cells include logging and save CSVs to `data/`.

### `app_scraper.ipynb` (Apple App Store)
- Scrapes US store for multiple asthma-related keywords and saves metadata to `data/app_store_asthma_apps_desc.csv` (and derived sets). 
- Adjust keywords, country, and result limits near the top of the notebook if needed.

### `app_scraper_article.ipynb` (Article methodology)
- Searches Apple + Google Play across countries `['us','gb','au']` and keywords such as hay fever, asthma, rhinitis. 
- Applies filtering rules: allowed categories (Medical/Health & Fitness/Weather), recency (<3 years), symptom keyword presence, and exclusion of alternative medicine/homeopathy. 
- Fetches extra Google Play details when missing updates, then writes filtered CSVs (e.g., `asthma_apps_filtered_relevant.csv`). 

## LLM assessment CLI (`llm_assessment.py`)
Run Gemini to include/exclude apps using the article criteria summary.

Single CSV:
```bash
python llm_assessment.py \
  --csv data/app_store_asthma_apps_desc_set.csv \
  --out data/app_store_llm_review.csv \
  --model gemini-2.5-flash \
  --sleep 1.0 \
  --retries 3 \
  --backoff 10
```

Directory mode (process all CSVs in `data/`):
```bash
python llm_assessment.py \
  --dir data \
  --model gemini-1.5-flash \
  --sleep 0.5
```

Key flags: `--start/--end` to limit rows (1-based), `--sleep` to avoid rate limits, `--retries/--backoff` for 429 handling. 

## Data outputs (selected)
- `app_store_asthma_apps_desc.csv` — Apple scrape with detailed descriptions.
- `google_play_asthma_apps_desc.csv` — Google Play scrape with descriptions.
- `asthma_apps_filtered_relevant.csv` — Filtered relevant apps after article criteria.
- `*_set.csv` / `*_llm.csv` — Variants with deduped sets and LLM-reviewed decisions.
- `github_asthma_repos*.csv`, `gitlab_asthma_repos*.csv` — Repository search exports.

## Notes
- Respect store rate limits; notebooks include short sleeps between requests.
- Gemini responses are treated as JSON; choose models that support JSON output (e.g., gemini-1.5/2.5-flash).
