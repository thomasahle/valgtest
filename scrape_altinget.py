#!/usr/bin/env python3
"""
Scrape Altinget's Kandidattest data via their VAA API.
Outputs into the 'altinget/' subdirectory:
  - questions.json   — 29 questions
  - candidates.json  — all candidates with answers

API base: https://api.altinget.dk/vaa-api/
Auth header: Authorization: <VAA_API_KEY>
Election: FT26 (Folketingsvalg 2026, electionId=13, valgomatId=15)
"""

import json
import sys
import time
from pathlib import Path

import requests

BASE_URL = "https://api.altinget.dk/vaa-api"
VAA_API_KEY = "7f8ef1d7-ccb1-4be8-af80-4616c704a816"
ELECTION_ID = 13
VALGOMAT_ID = 15

SESSION = requests.Session()
SESSION.headers["Authorization"] = VAA_API_KEY
SESSION.headers["User-Agent"] = "Mozilla/5.0 (compatible; valgtest-scraper/1.0; research)"

DELAY = 0.3  # seconds between requests


def get(path, params=None, retries=3):
    url = f"{BASE_URL}{path}"
    for attempt in range(retries):
        try:
            r = SESSION.get(url, params=params, timeout=15)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if attempt == retries - 1:
                raise
            print(f"  Retry {attempt+1} for {url}: {e}", file=sys.stderr)
            time.sleep(2)


def get_questions():
    print("Fetching questions...")
    qs = get("/v1/GetAllQuestions", params={
        "electionId": ELECTION_ID,
        "valgomatId": VALGOMAT_ID,
        "frontpage": "true",
    })
    # Normalize to same schema as DR: use 'Id' field name
    normalized = []
    for q in qs:
        normalized.append({
            "Id": q["ID"],
            "Title": q.get("Title") or "",
            "Question": q.get("Question") or "",
            "Info": q.get("Info") or "",
            "ArgumentFor": q.get("ArgumentFor") or "",
            "ArgumentAgainst": q.get("ArgumentAgainst") or "",
        })
    print(f"  Got {len(normalized)} questions")
    return normalized


def get_all_candidates():
    print("Fetching candidate list...")
    candidates = get("/v1/GetCandidates", params={
        "electionId": ELECTION_ID,
        "valgomatId": VALGOMAT_ID,
        "frontpage": "true",
    })
    print(f"  Got {len(candidates)} candidates")
    return candidates


def get_candidate_answers(candidate_id):
    answers = get("/v1/GetCandidateAnswers", params={
        "candidateId": candidate_id,
        "electionId": ELECTION_ID,
        "valgomatId": VALGOMAT_ID,
        "frontpage": "true",
    })
    return [
        {
            "QuestionID": a["QuestionID"],
            "Answer": a["Answer"],
            "Info": a.get("Info") or "",
        }
        for a in answers
        if a.get("Answer") and a["Answer"] > 0  # filter unanswered (Answer=0)
    ]


def main():
    out_dir = Path("altinget")
    out_dir.mkdir(exist_ok=True)

    # 1. Questions
    q_path = out_dir / "questions.json"
    if q_path.exists():
        print("altinget/questions.json already exists, skipping")
    else:
        questions = get_questions()
        q_path.write_text(json.dumps(questions, ensure_ascii=False, indent=2))
        print(f"  Saved {len(questions)} questions to {q_path}")

    # 2. Candidate list
    candidates_raw = get_all_candidates()

    # 3. Scrape each candidate's answers (resumable)
    done_path = out_dir / "candidates.json"
    done_ids: set = set()
    candidates = []

    if done_path.exists():
        candidates = json.loads(done_path.read_text())
        done_ids = {c["candidateId"] for c in candidates}
        print(f"Resuming: {len(done_ids)} candidates already scraped")

    remaining = [c for c in candidates_raw if c["ID"] not in done_ids]
    print(f"Scraping {len(remaining)} candidates...")

    for i, c in enumerate(remaining):
        cid = c["ID"]
        name = f"{c.get('Firstname','')} {c.get('LastName','')}".strip() or c.get("UrlKey", str(cid))
        party = c.get("CurrentParty") or c.get("LinedUpForParty") or "Ukendt"
        party_code = c.get("CurrentPartyCode") or c.get("LinedUpForPartyCode") or ""
        url_key = c.get("UrlKey") or str(cid)

        print(f"  [{i+1}/{len(remaining)}] {name} ({party})", end="", flush=True)
        try:
            answers = get_candidate_answers(cid)
            candidates.append({
                "candidateId": cid,
                "urlKey": url_key,
                "name": name,
                "party": party,
                "partyCode": party_code,
                "answers": answers,
            })
            print(f" [{len(answers)} answers]")
        except Exception as e:
            print(f" — ERROR: {e}", file=sys.stderr)

        if (i + 1) % 50 == 0:
            done_path.write_text(json.dumps(candidates, ensure_ascii=False, indent=2))
            print(f"  [checkpoint: {len(candidates)} saved]")

        time.sleep(DELAY)

    done_path.write_text(json.dumps(candidates, ensure_ascii=False, indent=2))
    print(f"\nDone. {len(candidates)} candidates saved to {done_path}")


if __name__ == "__main__":
    main()
