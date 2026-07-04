#!/usr/bin/env python3
"""Expand the human-anchor CSV with real demo.db order cases.

The first 10 seed rows are preserved byte-for-byte at the CSV field level. New
rows are sampled from data/demo.db process_sheets and reviewed by the same real
DeepSeek critic pipeline used by commit 75ba282. No Yi labels are generated.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import re
import sqlite3
import sys
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.analysis_agent import AnalysisAgent  # noqa: E402
from agents.critic_agent import CriticAgent  # noqa: E402
from agents.intelligence_agent import IntelligenceAgent  # noqa: E402


FIELDNAMES = [
    "case_id",
    "input_summary",
    "critic_verdict",
    "critic_reason_summary",
    "yi_verdict",
    "yi_note",
]
ALLOWED_VERDICTS = {"approve", "revise", "reject"}
EXPORT_PATTERN = re.compile(r"出口|外贸", re.I)


@dataclass(frozen=True)
class DemoOrder:
    id: int
    product: str
    client: str
    qty: int
    box_l: int | None
    box_w: int | None
    box_h: int | None
    flute_raw: str
    flute_norm: str
    order_type: str
    has_lamination: int
    print_style: str

    @property
    def case_id(self) -> str:
        return f"demo-order-{self.id:04d}"

    @property
    def bucket(self) -> tuple[str, str]:
        return (self.order_type, self.flute_norm)


def load_env_file(path: Path) -> None:
    """Load KEY=VALUE pairs without printing secrets."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def normalize_flute(value: str | None) -> str:
    text = (value or "").strip().upper().replace(" ", "")
    text = text.replace("（", "(").replace("）", ")").replace("瓦", "")
    if not text or set(text) <= {"-"}:
        return "UNKNOWN"
    if "/" in text or "或" in text or "(" in text:
        if "AB" in text and "BC" in text:
            return "MIXED_AB_BC"
        if "EB" in text and "BC" in text:
            return "MIXED_EB_BC"
        return "MIXED_OTHER"
    if "单E" in text or text == "E":
        return "SINGLE_E"
    if "单B" in text or text == "B":
        return "SINGLE_B"
    if "单C" in text or text == "C":
        return "SINGLE_C"
    if text.startswith("EB"):
        return "EB"
    if text.startswith("BC"):
        return "BC"
    if text.startswith("AB"):
        return "AB"
    if text.startswith("EE"):
        return "EE"
    return text


def infer_order_type(*parts: str | None) -> str:
    blob = " ".join(part or "" for part in parts)
    return "export" if EXPORT_PATTERN.search(blob) else "domestic_or_unspecified"


def fetch_orders(db_path: Path, existing_case_ids: set[str]) -> list[DemoOrder]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT id, product, client, COALESCE(order_qty, finished_qty) AS qty,
               box_l, box_w, box_h, flute_type,
               has_lamination, print_style, notes, file, batch_no
        FROM process_sheets
        WHERE error IS NULL
          AND flute_type IS NOT NULL
          AND flute_type != ''
          AND COALESCE(order_qty, finished_qty) IS NOT NULL
          AND COALESCE(order_qty, finished_qty) > 0
        ORDER BY id
        """
    ).fetchall()
    conn.close()

    orders: list[DemoOrder] = []
    for row in rows:
        case_id = f"demo-order-{int(row['id']):04d}"
        if case_id in existing_case_ids:
            continue
        order = DemoOrder(
            id=int(row["id"]),
            product=row["product"] or "",
            client=row["client"] or "",
            qty=int(row["qty"]),
            box_l=row["box_l"],
            box_w=row["box_w"],
            box_h=row["box_h"],
            flute_raw=row["flute_type"] or "",
            flute_norm=normalize_flute(row["flute_type"]),
            order_type=infer_order_type(
                row["product"], row["notes"], row["file"], row["batch_no"]
            ),
            has_lamination=int(row["has_lamination"] or 0),
            print_style=row["print_style"] or "",
        )
        if order.flute_norm != "UNKNOWN":
            orders.append(order)
    return orders


def _round_robin_by_bucket(
    orders: Iterable[DemoOrder],
    n: int,
    seed: int,
    bucket_key,
) -> list[DemoOrder]:
    rng = random.Random(seed)
    buckets: dict[str, list[DemoOrder]] = defaultdict(list)
    for order in orders:
        buckets[bucket_key(order)].append(order)
    for bucket_orders in buckets.values():
        rng.shuffle(bucket_orders)
    queues = {
        bucket: deque(bucket_orders)
        for bucket, bucket_orders in sorted(
            buckets.items(),
            key=lambda item: (-len(item[1]), item[0]),
        )
    }

    selected: list[DemoOrder] = []
    while len(selected) < n and any(queues.values()):
        progressed = False
        for bucket in list(queues):
            if len(selected) >= n:
                break
            if queues[bucket]:
                selected.append(queues[bucket].popleft())
                progressed = True
        if not progressed:
            break
    return selected


def stratified_sample(orders: Iterable[DemoOrder], n: int, seed: int) -> tuple[list[DemoOrder], dict]:
    order_list = list(orders)
    buckets: dict[tuple[str, str], list[DemoOrder]] = defaultdict(list)
    by_order_type: dict[str, list[DemoOrder]] = defaultdict(list)
    for order in order_list:
        buckets[order.bucket].append(order)
        by_order_type[order.order_type].append(order)

    availability = {
        f"{order_type}/{flute}": len(bucket_orders)
        for (order_type, flute), bucket_orders in sorted(buckets.items())
    }

    export_orders = by_order_type.get("export", [])
    domestic_orders = by_order_type.get("domestic_or_unspecified", [])
    if export_orders and domestic_orders:
        export_target = min(len(export_orders), n // 2)
        domestic_target = n - export_target
        selected = _round_robin_by_bucket(export_orders, export_target, seed, lambda o: o.flute_norm)
        selected.extend(
            _round_robin_by_bucket(domestic_orders, domestic_target, seed + 1, lambda o: o.flute_norm)
        )
    else:
        selected = _round_robin_by_bucket(order_list, n, seed, lambda o: f"{o.order_type}/{o.flute_norm}")

    metadata = {
        "available_buckets": availability,
        "selected_buckets": dict(Counter(f"{o.order_type}/{o.flute_norm}" for o in selected)),
        "selected_order_type": dict(Counter(o.order_type for o in selected)),
        "selected_flute": dict(Counter(o.flute_norm for o in selected)),
    }
    return selected, metadata


def load_existing_rows(path: Path, preserve_count: int) -> tuple[list[dict], list[dict]]:
    rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
    if len(rows) < preserve_count:
        raise ValueError(f"{path} has {len(rows)} rows; need at least {preserve_count}")
    for index, row in enumerate(rows[:preserve_count], start=1):
        if row.get("case_id") != f"case-{index:02d}-" + row.get("case_id", "").split("-", 2)[2]:
            if not row.get("case_id", "").startswith(f"case-{index:02d}-"):
                raise ValueError(f"seed row {index} has unexpected case_id={row.get('case_id')}")
    return rows[:preserve_count], rows[preserve_count:]


def build_query(order: DemoOrder) -> str:
    size = (
        f"{order.box_l}x{order.box_w}x{order.box_h}mm"
        if order.box_l and order.box_w and order.box_h
        else "尺寸缺失"
    )
    order_word = "出口" if order.order_type == "export" else "内销"
    return (
        f"{order.product} {order_word} {order.flute_raw} 纸箱报价, "
        f"{order.qty}只, 箱规{size}"
    )


def build_input_summary(order: DemoOrder, query: str, context: dict, draft: dict) -> str:
    pr = context.get("price_range", {})
    size = (
        f"{order.box_l}x{order.box_w}x{order.box_h}mm"
        if order.box_l and order.box_w and order.box_h
        else ""
    )
    return (
        f"source=demo.db.process_sheets#{order.id}; query={query}; "
        f"order_type={order.order_type}; flute={order.flute_raw}; "
        f"flute_norm={order.flute_norm}; qty={order.qty}; box={size}; "
        f"client={order.client}; lamination={order.has_lamination}; "
        f"print_style={order.print_style}; n_matches={context.get('n_matches')}; "
        f"p25={pr.get('p25')}; p50={pr.get('p50')}; p75={pr.get('p75')}; "
        f"draft_price={draft.get('recommended_price_per_m2')}; "
        f"warnings={'; '.join(context.get('warnings', []))}"
    )


def summarize_review(review: dict) -> str:
    message = review.get("recommendation_to_user")
    issues = review.get("issues") or []
    if message:
        return str(message).replace("\n", " ")[:500]
    if issues:
        return "; ".join(
            f"{item.get('type', 'issue')}: {item.get('detail', '')}" for item in issues
        )[:500]
    raw_text = review.get("raw_text")
    if raw_text:
        return str(raw_text).replace("\n", " ")[:500]
    return "No critic reason returned."


def review_orders(
    orders: list[DemoOrder],
    db_path: Path,
    provider: str,
    model: str,
    api_key: str,
    desired_count: int,
    max_attempts: int = 2,
) -> tuple[list[dict], list[dict], list[dict]]:
    intel = IntelligenceAgent(db_path=str(db_path), top_k=10)
    analysis = AnalysisAgent(use_llm=False)
    critic = CriticAgent(use_llm=True, provider=provider, model=model, api_key=api_key)
    if not critic._llm or critic._llm.provider == "mock":
        raise RuntimeError("real DeepSeek critic unavailable; refusing to generate fallback anchors")

    rows: list[dict] = []
    traces: list[dict] = []
    failures: list[dict] = []
    for idx, order in enumerate(orders, start=1):
        if len(rows) >= desired_count:
            break
        query = build_query(order)
        context = intel.gather(query, flute_hint=order.flute_raw)
        draft = analysis.recommend(context, query)

        review = {}
        trace = {}
        verdict = ""
        failure_reason = ""
        for attempt in range(1, max_attempts + 1):
            review = critic.review(context, draft, query)
            trace = review.get("trace") or {}
            verdict = str(review.get("verdict", "")).strip().lower()
            if trace.get("fallback") or review.get("mode") != "real":
                failure_reason = f"not-real-or-fallback attempt={attempt} trace={trace}"
                continue
            if verdict not in ALLOWED_VERDICTS:
                failure_reason = f"invalid-verdict attempt={attempt} verdict={verdict!r}"
                continue
            failure_reason = ""
            break

        if failure_reason:
            failures.append({
                "case_id": order.case_id,
                "source_order_id": order.id,
                "order_type": order.order_type,
                "flute_norm": order.flute_norm,
                "reason": failure_reason,
                "last_trace": trace,
            })
            print(
                f"[skip] {order.case_id} {order.order_type}/{order.flute_norm} {failure_reason}",
                flush=True,
            )
            continue

        rows.append({
            "case_id": order.case_id,
            "input_summary": build_input_summary(order, query, context, draft),
            "critic_verdict": verdict,
            "critic_reason_summary": summarize_review(review),
            "yi_verdict": "",
            "yi_note": "",
        })
        traces.append({
            "case_id": order.case_id,
            "source_order_id": order.id,
            "order_type": order.order_type,
            "flute_norm": order.flute_norm,
            "critic_verdict": verdict,
            "mode": review.get("mode"),
            "model": review.get("model"),
            "latency_ms": trace.get("latency_ms"),
            "usage": trace.get("usage"),
            "fallback": trace.get("fallback"),
            "candidate_index": idx,
            "valid_index": len(rows),
        })
        print(
            f"[{len(rows):02d}/{desired_count} cand={idx:02d}] {order.case_id} "
            f"{order.order_type}/{order.flute_norm} verdict={verdict} "
            f"latency_ms={trace.get('latency_ms')}",
            flush=True,
        )
    if len(rows) < desired_count:
        raise RuntimeError(f"Only collected {len(rows)} valid rows; need {desired_count}")
    return rows, traces, failures


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in FIELDNAMES})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--existing", type=Path, default=Path("eval/human_anchor/anchor_set_40.csv"))
    parser.add_argument("--db", type=Path, default=Path("data/demo.db"))
    parser.add_argument("--output", type=Path, default=Path("eval/human_anchor/anchor_set_40.csv"))
    parser.add_argument("--metadata", type=Path, default=Path("eval/human_anchor/anchor_expansion_20260704.json"))
    parser.add_argument("--preserve-count", type=int, default=10)
    parser.add_argument("--new-count", type=int, default=30)
    parser.add_argument("--seed", type=int, default=20260704)
    parser.add_argument("--provider", default="deepseek")
    parser.add_argument("--model", default="deepseek-v4-pro")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    args = parser.parse_args()

    load_env_file(args.env_file)
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise SystemExit("DEEPSEEK_API_KEY is not available; refusing to run mock fallback")

    preserved, old_extra = load_existing_rows(args.existing, args.preserve_count)
    existing_ids = {row["case_id"] for row in preserved + old_extra}
    orders = fetch_orders(args.db, existing_ids)
    candidate_count = min(len(orders), max(args.new_count + 15, args.new_count))
    selected, strat_meta = stratified_sample(orders, candidate_count, args.seed)
    if len(selected) < args.new_count:
        raise SystemExit(f"Only selected {len(selected)} candidate orders; need {args.new_count}")

    new_rows, traces, failures = review_orders(
        selected,
        db_path=args.db,
        provider=args.provider,
        model=args.model,
        api_key=api_key,
        desired_count=args.new_count,
    )
    all_rows = preserved + new_rows
    write_csv(args.output, all_rows)

    metadata = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "critic_reference_commit": "75ba282",
        "provider": args.provider,
        "model": args.model,
        "db": str(args.db),
        "preserved_seed_rows": len(preserved),
        "new_rows": len(new_rows),
        "total_rows": len(all_rows),
        "yi_verdict_nonempty": sum(bool(row["yi_verdict"].strip()) for row in all_rows),
        "yi_note_nonempty": sum(bool(row["yi_note"].strip()) for row in all_rows),
        "old_extra_rows_discarded": len(old_extra),
        "candidate_rows": len(selected),
        "failed_candidates": failures,
        **strat_meta,
        "valid_selected_buckets": dict(Counter(
            f"{trace['order_type']}/{trace['flute_norm']}" for trace in traces
        )),
        "valid_selected_order_type": dict(Counter(trace["order_type"] for trace in traces)),
        "valid_selected_flute": dict(Counter(trace["flute_norm"] for trace in traces)),
        "traces": traces,
    }
    args.metadata.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: metadata[k] for k in (
        "preserved_seed_rows",
        "new_rows",
        "total_rows",
        "valid_selected_order_type",
        "valid_selected_flute",
        "yi_verdict_nonempty",
        "yi_note_nonempty",
    )}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
