"""LLM-powered assessment for scraped apps.

This script reviews a slice of scraped app rows (default: 39-100, 1-based)
and asks an LLM to decide inclusion/exclusion using the article criteria.
Usage:
Directory:
python3 llm_assessment.py \
  --dir data \
  --model gemini-2.5-flash \
  --sleep 1.0 \
  --retries 3 \
  --backoff 10
Single File:
python3 llm_assessment.py \
  --csv data/app_store_asthma_apps_desc_set.csv \
  --out data/app_store_llm_review.csv \
  --model gemini-2.5-flash \
  --sleep 1.0 \
  --retries 3 \
  --backoff 10
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass
from typing import List, Optional

import google.genai as genai
from google.genai import errors as genai_errors
import pandas as pd


CRITERIA_SUMMARY = """
Decide if an app is RELEVANT (include) or NOT RELEVANT (exclude) for asthma/rhinitis/hay fever support.
Follow these rules:
1) Category: Prefer Medical, Health & Fitness, or Weather. However, if Category is Lifestyle or Productivity but the Title/Description clearly indicates asthma symptom tracking, INCLUDE.
2) Updates: If the update date is missing, look for clues in the description. If the app mentions modern iPhone features, assume it is active.
3) Evidence-based: Strictly EXCLUDE homeopathy/alternative medicine.
4) Relevance: The app must be for tracking, monitoring, or forecasting asthma/hay fever/rhinitis symptoms.
Return a JSON object with fields: include (true/false) and reason (short, under 200 chars).
"""


@dataclass
class AppRow:
    idx: int
    title: str
    description: str
    genre: str
    updated: Optional[str]

    @classmethod
    def from_series(cls, idx: int, row: pd.Series) -> "AppRow":
        return cls(
            idx=idx,
            title=str(row.get("App Name", row.get("title", ""))),
            description=str(row.get("Description", row.get("description", ""))),
            genre=str(row.get("Genre", row.get("genre", ""))),
            updated=row.get("updated"),
        )


def build_prompt(app: AppRow) -> str:
    return (
        f"You are reviewing scraped app metadata. Decide include/exclude.\n"
        f"App index: {app.idx}\n"
        f"Title: {app.title}\n"
        f"Genre: {app.genre}\n"
        f"Updated: {app.updated}\n"
        f"Description:\n{app.description}\n\n"
        f"Criteria:\n{CRITERIA_SUMMARY}\n"
        f"Respond with JSON only."
    )


def run_llm(client, model_name: str, prompt: str, retries: int, backoff_s: float) -> str:
    for attempt in range(retries + 1):
        try:
            config = {"max_output_tokens": 200}

            if "gemini" in model_name:
                config["response_mime_type"] = "application/json"

            resp = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config,
            )

            return resp.text or ""
        except genai_errors.ClientError as e:
            msg = str(e)
            if "429" in msg or "quota" in msg.lower():
                if attempt < retries:
                    wait = backoff_s * (attempt + 1)
                    print(f"[429] Rate limit hit. Cooling down {wait:.1f}s...")
                    time.sleep(wait)
                    continue
            raise


def assess_rows(df: pd.DataFrame, start: Optional[int], end: Optional[int], client, model_name: str, pause_s: float, retries: int, backoff_s: float) -> List[dict]:
    start_idx = max(1, start) if start is not None else 1
    end_idx = min(len(df), end) if end is not None else len(df)
    results = []
    for i in range(start_idx, end_idx + 1):
        row = df.iloc[i - 1]
        app = AppRow.from_series(i, row)
        prompt = build_prompt(app)
        print(f"[LLM] Processing row {i}/{end_idx}: {app.title[:40]}...")
        sys.stdout.flush()

        decision_text = run_llm(client, model_name, prompt, retries, backoff_s)
        results.append({
            "index": i,
            "title": app.title,
            "genre": app.genre,
            "updated": app.updated,
            "llm_decision": decision_text,
        })
        if pause_s > 0:
            time.sleep(pause_s)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="LLM inclusion/exclusion for scraped apps")
    parser.add_argument("--csv", help="Input CSV file (scraped apps)")
    parser.add_argument("--dir", default="data", help="Directory containing CSVs to process (used if --csv not provided)")
    parser.add_argument("--start", type=int, default=None, help="1-based start index (inclusive). Default: first row")
    parser.add_argument("--end", type=int, default=None, help="1-based end index (inclusive). Default: last row")
    parser.add_argument("--out", default="llm_assessment_output.csv", help="Output CSV file")
    parser.add_argument("--model", default="gemini-1.5-flash", help="Gemini model name (e.g., gemini-1.5-flash or gemini-2.5-flash)")
    parser.add_argument("--sleep", type=float, default=0.5, help="Seconds to sleep between requests to avoid rate limits")
    parser.add_argument("--retries", type=int, default=2, help="Retries on 429s")
    parser.add_argument("--backoff", type=float, default=10.0, help="Base backoff seconds for 429 retries")
    args = parser.parse_args()

    if not os.getenv("GOOGLE_API_KEY"):
        sys.exit("GOOGLE_API_KEY is not set. Please export it before running.")

    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    model_name = args.model

    targets = []
    if args.csv:
        targets.append((args.csv, args.out))
    else:
        data_dir = args.dir
        if not os.path.isdir(data_dir):
            sys.exit(f"Directory not found: {data_dir}")
        for fname in sorted(os.listdir(data_dir)):
            if fname.lower().endswith(".csv"):
                in_path = os.path.join(data_dir, fname)
                out_path = os.path.join(data_dir, f"{os.path.splitext(fname)[0]}_llm.csv")
                targets.append((in_path, out_path))

    if not targets:
        sys.exit("No CSV files to process.")

    for in_csv, out_csv in targets:
        df = pd.read_csv(in_csv)
        if df.empty:
            print(f"[skip] {in_csv} is empty")
            continue

        assessments = assess_rows(df, args.start, args.end, client, model_name, args.sleep, args.retries, args.backoff)
        pd.DataFrame(assessments).to_csv(out_csv, index=False)
        start_shown = args.start if args.start is not None else 1
        end_shown = args.end if args.end is not None else len(df)
        print(f"Saved LLM assessments for rows {start_shown}-{end_shown} to {out_csv}")


if __name__ == "__main__":
    main()
