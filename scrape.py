#!/usr/bin/env python3
"""
Scrape DR's Kandidattest data.
Outputs:
  - questions.json   — 25 questions with Id, Title, Question, etc.
  - candidates.json  — all candidates with name, party, constituency, answers
"""

import json
import re
import time
import sys
from pathlib import Path

import requests

BASE = "https://www.dr.dk"
QUESTIONS_URL = f"{BASE}/nyheder/politik/folketingsvalg/api/GetQuestions?districtId=4"

# All valid constituency district IDs (1-103, skipping 404s)
DISTRICT_IDS = [
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20,
    21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 36, 38, 39, 40,
    41, 43, 44, 45, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61,
    62, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 79, 80, 81,
    82, 84, 85, 86, 87, 88, 89, 91, 92, 94, 95, 96, 98, 99, 100, 101, 102, 103,
]

SESSION = requests.Session()
SESSION.headers["User-Agent"] = (
    "Mozilla/5.0 (compatible; valgtest-scraper/1.0; research)"
)

DELAY = 0.4  # seconds between requests


def get(url, retries=3):
    for attempt in range(retries):
        try:
            r = SESSION.get(url, timeout=15)
            r.raise_for_status()
            return r
        except Exception as e:
            if attempt == retries - 1:
                raise
            print(f"  Retry {attempt+1} for {url}: {e}", file=sys.stderr)
            time.sleep(2)


def get_questions():
    print("Fetching questions...")
    data = get(QUESTIONS_URL).json()
    questions = data.get("questions", [])
    print(f"  Got {len(questions)} questions")
    return questions


def get_candidate_keys_for_district(district_id):
    """Extract candidate urlKeys from a district constituency page."""
    url = f"{BASE}/nyheder/politik/folketingsvalg/din-stemmeseddel/{district_id}"
    html = get(url).text
    # urlKeys are double-backslash-escaped in the Next.js server payload
    keys = re.findall(r'\\"urlKey\\":\\"([^\\"]+)\\"', html)
    return list(dict.fromkeys(keys))


def _get_nextjs_push_content(html, around_index):
    """
    Given an index into html where something of interest was found,
    extract and unescape the Next.js __next_f.push([1,"..."]) payload
    that contains that index.
    """
    push_starts = [m.start() for m in re.finditer(r'self\.__next_f\.push\(\[1,"', html)]
    push_starts.append(len(html))

    containing_start = None
    containing_end = None
    for i, ps in enumerate(push_starts[:-1]):
        if ps <= around_index < push_starts[i+1]:
            containing_start = ps
            containing_end = push_starts[i+1]
            break
    if containing_start is None:
        return None

    segment = html[containing_start:containing_end]
    str_start_idx = segment.index('[1,"') + 4
    content = segment[str_start_idx:]

    # Trim trailing JS: ends with \n"]) or "]);
    for end_marker in ['\\n"])', '"]);']:
        idx = content.rfind(end_marker)
        if idx >= 0:
            keep = len('\\n') if end_marker.startswith('\\n') else 0
            content = content[:idx + keep]
            break

    try:
        return json.loads('"' + content + '"')
    except json.JSONDecodeError:
        return None


def _parse_json_object_around(text, index):
    """Find and parse the JSON object that contains `index` in `text`."""
    depth = 0
    start = None
    for i in range(index, -1, -1):
        c = text[i]
        if c == "}":
            depth += 1
        elif c == "{":
            if depth == 0:
                start = i
                break
            depth -= 1
    if start is None:
        return None

    depth = 0
    end = None
    for i in range(start, len(text)):
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end is None:
        return None

    try:
        return json.loads(text[start:end])
    except json.JSONDecodeError:
        return None


def extract_candidate_data(html, url_key):
    """Extract candidate info and answers from a candidate page HTML."""
    ca_idx = html.find("candidateAnswers")
    if ca_idx == -1:
        return None

    unescaped = _get_nextjs_push_content(html, ca_idx)
    if unescaped is None:
        return None

    ca_idx2 = unescaped.find("candidateAnswers")
    if ca_idx2 == -1:
        return None

    obj = _parse_json_object_around(unescaped, ca_idx2)
    if obj is None or "candidateAnswers" not in obj:
        return None

    ci = obj.get("candidate", {})
    firstname = ci.get("Firstname") or ""
    lastname = ci.get("LastName") or ""
    name = f"{firstname} {lastname}".strip() or ci.get("Name") or url_key

    # Constituency: pick the Bigconstituency from LineUps if available
    constituency = None
    for lu in ci.get("LineUps", []):
        if lu.get("groupType") == "Bigconstituency":
            constituency = lu.get("lineUpName")
            break

    return {
        "urlKey": url_key,
        "name": name,
        "party": ci.get("CurrentParty") or ci.get("LinedUpForParty"),
        "partyCode": ci.get("CurrentPartyCode") or ci.get("LinedUpForPartyCode"),
        "constituency": constituency,
        "answers": [
            {
                "QuestionID": a["QuestionID"],
                "Answer": a["Answer"],
                "Info": a.get("Info") or "",
            }
            for a in obj["candidateAnswers"]
        ],
    }


def get_candidate_data(url_key):
    url = f"{BASE}/nyheder/politik/folketingsvalg/din-stemmeseddel/kandidater/{url_key}"
    html = get(url).text
    return extract_candidate_data(html, url_key)


def main():
    out_dir = Path(".")

    # 1. Questions
    q_path = out_dir / "questions.json"
    if q_path.exists():
        print("questions.json already exists, skipping")
    else:
        questions = get_questions()
        q_path.write_text(json.dumps(questions, ensure_ascii=False, indent=2))
        print(f"  Saved {len(questions)} questions")

    # 2. Collect all unique candidate URL keys from all districts
    keys_path = out_dir / "candidate_keys.json"
    if keys_path.exists():
        print("candidate_keys.json already exists, skipping")
        all_keys = json.loads(keys_path.read_text())
    else:
        all_keys = []
        seen = set()
        for i, did in enumerate(DISTRICT_IDS):
            print(f"  District {did} ({i+1}/{len(DISTRICT_IDS)})", end="", flush=True)
            try:
                keys = get_candidate_keys_for_district(did)
                new_keys = [k for k in keys if k not in seen]
                for k in new_keys:
                    seen.add(k)
                all_keys.extend(new_keys)
                print(f": {len(keys)} candidates ({len(new_keys)} new, total {len(all_keys)})")
            except Exception as e:
                print(f": ERROR {e}", file=sys.stderr)
            time.sleep(DELAY)
        keys_path.write_text(json.dumps(all_keys, ensure_ascii=False, indent=2))
        print(f"Total unique candidate keys: {len(all_keys)}")

    # 3. Scrape each candidate (resumable)
    done_path = out_dir / "candidates.json"
    done_keys: set = set()
    candidates = []

    if done_path.exists():
        candidates = json.loads(done_path.read_text())
        done_keys = {c["urlKey"] for c in candidates}
        print(f"Resuming: {len(done_keys)} candidates already scraped")

    remaining = [k for k in all_keys if k not in done_keys]
    print(f"Scraping {len(remaining)} candidates...")

    for i, key in enumerate(remaining):
        print(f"  [{i+1}/{len(remaining)}] {key}", end="", flush=True)
        try:
            data = get_candidate_data(key)
            if data:
                candidates.append(data)
                n_ans = len(data["answers"])
                print(f" — {data['name']} ({data['party']}) [{n_ans} answers]")
            else:
                print(" — FAILED (no candidateAnswers found)")
        except Exception as e:
            print(f" — ERROR: {e}", file=sys.stderr)

        if (i + 1) % 50 == 0:
            done_path.write_text(json.dumps(candidates, ensure_ascii=False, indent=2))
            print(f"  [checkpoint: {len(candidates)} saved]")

        time.sleep(DELAY)

    done_path.write_text(json.dumps(candidates, ensure_ascii=False, indent=2))
    print(f"\nDone. {len(candidates)} candidates saved to candidates.json")


if __name__ == "__main__":
    main()
