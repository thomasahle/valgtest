#!/usr/bin/env python3
"""
Combine candidate answer data from multiple source directories into one dataset.

Usage:
  python combine.py <source1> <source2> [source3 ...] [--out <dir>]

  Each source directory must contain questions.json and candidates.json.
  Candidates are matched by urlKey (identical across sources).
  For questions that appear in multiple sources, the first source that has
  an answer for a given candidate wins.

Example:
  python combine.py . altinget --out combined
  python analyze.py combined
  python plot.py combined
"""

import json
import sys
from pathlib import Path


def load_source(src_dir):
    src = Path(src_dir)
    questions = json.loads((src / "questions.json").read_text())
    candidates = json.loads((src / "candidates.json").read_text())
    return questions, candidates


def main():
    # Parse arguments: source dirs + optional --out
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)

    out_dir = Path("combined")
    sources = []
    require_all = False
    i = 0
    while i < len(args):
        if args[i] == "--out":
            out_dir = Path(args[i + 1])
            i += 2
        elif args[i] == "--require-all":
            require_all = True
            i += 1
        else:
            sources.append(args[i])
            i += 1

    if len(sources) < 2:
        print("Error: need at least two source directories", file=sys.stderr)
        sys.exit(1)

    source_names = [Path(s).name if Path(s) != Path(".") else "dr" for s in sources]
    print(f"Combining sources: {', '.join(source_names)} → {out_dir}/")

    # ── 1. Merge questions (union, deduplicated by ID) ────────────────────────
    merged_questions = {}   # qid → question dict
    for src in sources:
        questions, _ = load_source(src)
        for q in questions:
            qid = q.get("Id") or q.get("id") or q.get("QuestionID")
            if qid not in merged_questions:
                merged_questions[qid] = q

    merged_q_list = list(merged_questions.values())
    print(f"Questions: {[len(json.loads((Path(s)/'questions.json').read_text())) for s in sources]} "
          f"→ {len(merged_q_list)} combined")

    # ── 2. Merge candidates ───────────────────────────────────────────────────
    # Strategy: match by urlKey first, then fall back to normalised name.
    # This handles the case where different sources assign different urlKeys
    # to the same person (e.g. TV 2's large external IDs vs DR/Altinget IDs).

    def norm_name(n):
        return (n or "").lower().strip()

    # Build per-source lookups
    source_data = []   # list of (by_urlkey, by_name) dicts
    for src in sources:
        _, candidates = load_source(src)
        by_key  = {c["urlKey"]: c for c in candidates}
        by_name = {norm_name(c["name"]): c for c in candidates}
        source_data.append((by_key, by_name))

    # Collect canonical keys from the first source, then extend with unmatched
    # candidates from later sources (matched by name or added as new).
    canonical: dict[str, dict] = {}   # canonical_urlKey → merged candidate

    # Pass 1: seed with all candidates from source 0
    by_key0, by_name0 = source_data[0]
    for url_key, c in by_key0.items():
        canonical[url_key] = {
            "urlKey": url_key,
            "name": c.get("name") or url_key,
            "party": c.get("party") or "Ukendt",
            "partyCode": c.get("partyCode") or "",
            "answers": {a["QuestionID"]: a
                        for a in c.get("answers", [])
                        if a.get("Answer", 0) > 0},
        }

    # Pass 2+: merge each additional source
    for by_key, by_name in source_data[1:]:
        for url_key, c in by_key.items():
            # Resolve to a canonical key
            if url_key in canonical:
                canon_key = url_key
            else:
                # Try name-based match against already-known candidates
                nn = norm_name(c.get("name"))
                # First look in source-0 name lookup
                ref = by_name0.get(nn)
                canon_key = ref["urlKey"] if ref else url_key

            if canon_key not in canonical:
                canonical[canon_key] = {
                    "urlKey": canon_key,
                    "name": c.get("name") or canon_key,
                    "party": c.get("party") or "Ukendt",
                    "partyCode": c.get("partyCode") or "",
                    "answers": {},
                }

            # Merge answers (first source wins for duplicate question IDs)
            existing = canonical[canon_key]["answers"]
            for a in c.get("answers", []):
                qid = a["QuestionID"]
                if qid not in existing and a.get("Answer", 0) > 0:
                    existing[qid] = a

    merged_candidates = []
    for entry in canonical.values():
        merged_candidates.append({
            "urlKey": entry["urlKey"],
            "name": entry["name"],
            "party": entry["party"],
            "partyCode": entry["partyCode"],
            "answers": list(entry["answers"].values()),
            "_source_count": entry.get("_source_count", 1),
        })

    # --require-all: drop candidates not found in every source
    if require_all:
        n_sources = len(sources)
        # Track how many sources contributed answers to each candidate
        # by counting how many source-exclusive question sets are covered.
        # Simplest proxy: keep only candidates whose answer count is close
        # to the maximum (i.e. they answered questions from all sources).
        max_q = len(merged_questions)
        # A candidate has answered questions from all sources if their answer
        # count is within a reasonable margin of max_q (allowing for a few
        # skipped questions per source).
        # More precisely: compute the minimum per-source question count and
        # require the candidate answered at least one question from each source.
        source_qids = []
        for src in sources:
            qs, _ = load_source(src)
            qids = {q.get("Id") or q.get("id") or q.get("QuestionID") for q in qs}
            source_qids.append(qids)

        def in_all_sources(cand):
            answered = {a["QuestionID"] for a in cand["answers"]}
            return all(answered & sq for sq in source_qids)

        before = len(merged_candidates)
        merged_candidates = [c for c in merged_candidates if in_all_sources(c)]
        print(f"--require-all: kept {len(merged_candidates)} / {before} candidates "
              f"(present in all {n_sources} sources)")

    # Strip internal tracking field
    for c in merged_candidates:
        c.pop("_source_count", None)

    n_answers = [len(c["answers"]) for c in merged_candidates]
    print(f"Candidates: {len(merged_candidates)}  "
          f"(avg {sum(n_answers)/len(n_answers):.1f} answers/candidate, "
          f"max {max(n_answers)})")

    # ── 3. Save ───────────────────────────────────────────────────────────────
    out_dir.mkdir(exist_ok=True)
    (out_dir / "questions.json").write_text(
        json.dumps(merged_q_list, ensure_ascii=False, indent=2)
    )
    (out_dir / "candidates.json").write_text(
        json.dumps(merged_candidates, ensure_ascii=False, indent=2)
    )
    print(f"Saved {out_dir}/questions.json and {out_dir}/candidates.json")
    print(f"\nNext steps:")
    print(f"  python analyze.py {out_dir}")
    print(f"  python plot.py {out_dir}")


if __name__ == "__main__":
    main()
