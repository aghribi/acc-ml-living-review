#!/usr/bin/env python3
"""
Calibrate the NLI adjudicator thresholds on the easy-slice eval sets.

Scores every paper in data/eval/{positives,negatives}.json with the NLI
model (cached to data/eval/scores_cache.json so re-sweeps are instant),
sweeps the accept/reject cutoffs, and reports precision/recall plus the
size of the pending band.

Pick:
- `accept` = the lowest hi with precision >= 0.98 on the negatives slice
  (i.e. almost no junk clears the accept bar),
- `reject` = the highest lo with recall >= 0.98 on the positives slice
  (i.e. almost no genuine paper falls below the reject bar).

Then write the chosen values into living_review/config.py NLI_THRESHOLDS
and paste the sweep table into docs/source/methodology.rst.

Caveat (documented in methodology.rst): the easy slices are gate-derived,
so this bounds the NLI only on unambiguous cases. The hard boundary
(medical / light-source) is pinned only once the hand-labeled gold slices
exist — see data/eval/gold/README.md and TODO.md.

Usage:
    python scripts/calibrate_thresholds.py [--eval-dir data/eval] [--out sweep.md]
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from living_review.adjudicator import NLIAdjudicator  # noqa: E402
from living_review.data_model import Paper  # noqa: E402


def load_eval(path: Path):
    records = json.loads(path.read_text(encoding="utf-8"))
    return [
        Paper.from_dict({"id": r["id"], "title": r["title"], "abstract": r["abstract"]})
        for r in records
    ]


def get_scores(eval_dir: Path):
    cache = eval_dir / "scores_cache.json"
    if cache.exists():
        data = json.loads(cache.read_text(encoding="utf-8"))
        return data["positives"], data["negatives"], data["model"]

    adj = NLIAdjudicator()
    pos = load_eval(eval_dir / "positives.json")
    neg = load_eval(eval_dir / "negatives.json")
    print(f"[info] Scoring {len(pos)} positives + {len(neg)} negatives ...")
    pos_scores = adj.score(pos)
    neg_scores = adj.score(neg)
    cache.write_text(
        json.dumps(
            {"positives": pos_scores, "negatives": neg_scores, "model": adj.model_name},
            indent=2,
        ),
        encoding="utf-8",
    )
    return pos_scores, neg_scores, adj.model_name


def sweep(pos, neg, out_path=None):
    lines = [
        "| accept≥ | reject≤ | junk accepted | genuine rejected | genuine accepted | pending band (of all) |",
        "|---|---|---|---|---|---|",
    ]
    n_pos, n_neg = len(pos), len(neg)
    candidates = []
    his = [round(0.50 + 0.05 * i, 2) for i in range(10)]
    los = [round(0.05 + 0.05 * i, 2) for i in range(9)]
    for hi in his:
        for lo in los:
            if lo >= hi:
                continue
            junk_acc = sum(1 for s in neg if s >= hi)
            gen_rej = sum(1 for s in pos if s <= lo)
            gen_acc = sum(1 for s in pos if s >= hi)
            pending = sum(1 for s in pos + neg if lo < s < hi)
            precision = 1 - junk_acc / max(n_neg, 1)
            recall_floor = 1 - gen_rej / max(n_pos, 1)
            lines.append(
                f"| {hi} | {lo} | {junk_acc}/{n_neg} | {gen_rej}/{n_pos} "
                f"| {gen_acc}/{n_pos} | {pending}/{n_pos + n_neg} |"
            )
            if precision >= 0.98 and recall_floor >= 0.98:
                candidates.append((pending, -gen_acc, hi, lo))
    table = "\n".join(lines)
    if out_path:
        Path(out_path).write_text(table + "\n", encoding="utf-8")
    if candidates:
        pending, neg_acc, hi, lo = min(candidates)
        print(f"\n[recommendation] NLI_THRESHOLDS = {{'accept': {hi}, 'reject': {lo}}}")
        print(f"  genuine auto-accepted: {-neg_acc}/{len(pos)}, pending band: {pending}")
    else:
        print("\n[warn] No (hi, lo) pair met precision>=0.98 AND recall>=0.98 — inspect the table.")
    return table


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval-dir", default="data/eval")
    ap.add_argument("--out", default=None, help="Write the sweep table to this file")
    args = ap.parse_args()

    eval_dir = Path(args.eval_dir)
    pos, neg, model = get_scores(eval_dir)
    print(f"[info] Model: {model}")
    print(f"[info] positives: n={len(pos)}  min={min(pos):.3f} median={sorted(pos)[len(pos)//2]:.3f} max={max(pos):.3f}")
    print(f"[info] negatives: n={len(neg)}  min={min(neg):.3f} median={sorted(neg)[len(neg)//2]:.3f} max={max(neg):.3f}")
    table = sweep(pos, neg, args.out)
    if not args.out:
        print("\n" + table)


if __name__ == "__main__":
    main()
