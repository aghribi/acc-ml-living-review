#!/usr/bin/env python3
"""
Nightly sanity gate on the published JSON, run in CI before committing.

Fails (exit 1) — blocking the commit — if:
- the new file is unparseable or has an empty `papers` map,
- the accepted paper count SHRANK (terminal decisions mean the published
  set must be monotonic; any shrink is a bug or a bad model change),
- the count grew by more than --max-growth (default 10%) in one night,
- any new title trips a spam heuristic (URLs, streaming/pirata patterns,
  phone numbers, excessive uppercase) — a real spam entry reached the
  published site once.

Usage (CI):
    git show HEAD:site/data/livingreview.json > /tmp/old.json
    python scripts/sanity_check.py --old /tmp/old.json --new site/data/livingreview.json
"""

import argparse
import json
import re
import sys

SPAM_PATTERNS = [
    re.compile(r"https?://", re.IGNORECASE),
    re.compile(r"\b(streaming|altadefinizione|cb01|guarda(re)?\s+film|film\s+completo)\b", re.IGNORECASE),
    re.compile(r"\b(watch|download)\b.*\b(free|online|hd)\b", re.IGNORECASE),
    re.compile(r"\+?\d[\d\s\-()]{9,}\d"),  # phone numbers
    re.compile(r"\b(viagra|casino|betting|crypto\s+giveaway)\b", re.IGNORECASE),
]


def load_titles(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    papers = data.get("papers")
    if not isinstance(papers, dict) or not papers:
        raise ValueError(f"{path}: empty or malformed 'papers'")
    return {p.get("title", "") for p in papers.values()}


DOMAIN_WORDS = re.compile(
    r"accelerat|beam|linac|synchrotron|cyclotron|cavit|neural|learning|machine",
    re.IGNORECASE,
)


def spam_heuristic(title):
    # All-caps alone is weak evidence: legitimate proceedings titles are
    # sometimes upper-cased. Only flag when no domain vocabulary is present.
    if (
        len(title) > 25
        and sum(c.isupper() for c in title) / max(len(title), 1) > 0.6
        and not DOMAIN_WORDS.search(title)
    ):
        return "excessive uppercase"
    for pat in SPAM_PATTERNS:
        if pat.search(title):
            return f"pattern {pat.pattern[:40]!r}"
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--old", required=True)
    ap.add_argument("--new", required=True)
    ap.add_argument("--max-growth", type=float, default=0.10)
    args = ap.parse_args()

    try:
        new_titles = load_titles(args.new)
    except Exception as e:
        print(f"[sanity] FAIL: new file invalid: {e}")
        sys.exit(1)

    try:
        old_titles = load_titles(args.old)
    except Exception as e:
        print(f"[sanity] old file unavailable ({e}); skipping delta checks")
        old_titles = None

    if old_titles is not None:
        n_old, n_new = len(old_titles), len(new_titles)
        if n_new < n_old:
            print(f"[sanity] FAIL: published count shrank {n_old} -> {n_new}")
            sys.exit(1)
        if n_new > n_old * (1 + args.max_growth):
            print(f"[sanity] FAIL: published count grew {n_old} -> {n_new} "
                  f"(> {args.max_growth:.0%} in one run)")
            sys.exit(1)
        fresh = new_titles - old_titles
    else:
        fresh = new_titles

    spam = [(t, r) for t in fresh if (r := spam_heuristic(t))]
    if spam:
        print("[sanity] FAIL: spam-suspect new titles:")
        for t, r in spam[:10]:
            print(f"  - {t[:100]!r}  ({r})")
        sys.exit(1)

    print(f"[sanity] OK: {len(new_titles)} published papers"
          + (f" ({len(fresh)} new)" if old_titles is not None else ""))


if __name__ == "__main__":
    main()
