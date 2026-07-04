#!/usr/bin/env python3
"""Compute Yi-vs-critic agreement for the human anchor CSV."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


ALLOWED = {"approve", "revise", "reject"}


def cohen_kappa(pairs: list[tuple[str, str]]) -> float | None:
    if not pairs:
        return None
    n = len(pairs)
    observed = sum(1 for critic, yi in pairs if critic == yi) / n
    critic_counts = Counter(critic for critic, _ in pairs)
    yi_counts = Counter(yi for _, yi in pairs)
    expected = sum((critic_counts[label] / n) * (yi_counts[label] / n) for label in ALLOWED)
    if expected == 1:
        return 1.0 if observed == 1 else 0.0
    return round((observed - expected) / (1 - expected), 6)


def compute(path: Path) -> dict:
    rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
    labeled: list[dict] = []
    invalid: list[dict] = []

    for row in rows:
        critic = (row.get("critic_verdict") or "").strip().lower()
        yi = (row.get("yi_verdict") or "").strip().lower()
        if not yi:
            continue
        if critic not in ALLOWED or yi not in ALLOWED:
            invalid.append({
                "case_id": row.get("case_id", ""),
                "critic_verdict": critic,
                "yi_verdict": yi,
            })
            continue
        labeled.append({**row, "critic_verdict": critic, "yi_verdict": yi})

    pairs = [(row["critic_verdict"], row["yi_verdict"]) for row in labeled]
    disagreements = [
        {
            "case_id": row["case_id"],
            "critic_verdict": row["critic_verdict"],
            "yi_verdict": row["yi_verdict"],
            "yi_note": row.get("yi_note", ""),
        }
        for row in labeled
        if row["critic_verdict"] != row["yi_verdict"]
    ]
    agreement = (sum(1 for critic, yi in pairs if critic == yi) / len(pairs)) if pairs else None
    return {
        "status": "ok" if pairs and not invalid else ("invalid-labels" if invalid else "pending-labels"),
        "source": str(path),
        "total_rows": len(rows),
        "labeled_rows": len(labeled),
        "invalid_rows": invalid,
        "agreement_rate": round(agreement, 6) if agreement is not None else None,
        "cohen_kappa": cohen_kappa(pairs),
        "disagreement_count": len(disagreements),
        "disagreements": disagreements,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path", type=Path)
    args = parser.parse_args()
    print(json.dumps(compute(args.csv_path), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
