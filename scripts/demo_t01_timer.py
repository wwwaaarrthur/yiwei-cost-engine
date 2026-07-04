#!/usr/bin/env python3
"""Time the public Yiwei quote demo without logging in.

This script never fabricates a timing claim. It only reports a median when the
quote result, cost breakdown, and similar historical orders all render.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_URL = "https://yiwei-cost-engine.streamlit.app"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def elapsed(start: float) -> float:
    return round(time.perf_counter() - start, 3)


def blocked_payload(reason: str, runs: int, details: list[dict] | None = None) -> dict:
    return {
        "status": "blocked",
        "reason": reason,
        "runs_requested": runs,
        "median_total_seconds": None,
        "runs": details or [],
        "generated_at_utc": now_iso(),
    }


def app_frame(page):
    """Streamlit Community Cloud serves the app inside an iframe at <url>/~/+/.

    Locators on the top-level page see zero widgets, so interactions must target
    the app frame. Falls back to the page itself for locally served apps.
    """
    for frame in page.frames:
        if "/~/+" in frame.url:
            return frame
    return page


def run_once(playwright, url: str, timeout_ms: int, run_index: int) -> dict:
    start = time.perf_counter()
    checkpoints: dict[str, float] = {"start_open_url": 0.0}
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1400, "height": 1000})
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        checkpoints["domcontentloaded"] = elapsed(start)
        page.wait_for_timeout(8000)
        checkpoints["post_streamlit_wait"] = elapsed(start)

        title = page.title()
        checkpoints["title_seen"] = elapsed(start)
        if "Yiwei Cost Engine" not in title:
            return {
                "run": run_index,
                "status": "blocked-ui",
                "reason": "title-marker-missing",
                "title": title,
                "checkpoints": checkpoints,
                "elapsed_until_block_seconds": elapsed(start),
            }

        app = app_frame(page)
        checkpoints["app_frame_resolved"] = elapsed(start)

        # HITL gate: three needs-confirmation selects (成型方式/面纸拼版/瓦楞下料拼版)
        # must be set before the app will quote. Confirming them is part of the
        # workflow being timed.
        selects = app.locator('[data-baseweb="select"]')
        confirmed = 0
        for i in range(selects.count()):
            box = selects.nth(i)
            if not box.is_visible():
                continue
            label = box.inner_text()[:20]
            if "请选择" not in label and "需确认" not in label:
                continue
            box.click(timeout=10000)
            page.wait_for_timeout(600)
            options = app.locator('li[role="option"]')
            for j in range(options.count()):
                text = options.nth(j).inner_text()
                if "请选择" not in text and "需确认" not in text:
                    options.nth(j).click(timeout=10000)
                    confirmed += 1
                    break
            page.wait_for_timeout(400)
        checkpoints["required_params_confirmed"] = elapsed(start)
        checkpoints["required_params_count"] = confirmed

        quote_button = app.get_by_role("button", name="开始报价")
        if quote_button.count() == 0:
            body_text = app.locator("body").inner_text(timeout=5000)
            return {
                "run": run_index,
                "status": "blocked-ui",
                "reason": "quote-button-not-visible",
                "title": title,
                "app_frame_url": getattr(app, "url", ""),
                "body_chars": len(body_text),
                "checkpoints": checkpoints,
                "elapsed_until_block_seconds": elapsed(start),
            }

        quote_button.first.click(timeout=timeout_ms)
        checkpoints["quote_clicked"] = elapsed(start)
        # Markers below only render after a successful quote; the intro sentence
        # contains 建议报价/成本拆解/相似历史订单, so those are unsafe markers.
        app.get_by_text("报价结果", exact=False).first.wait_for(timeout=timeout_ms)
        checkpoints["quote_result_rendered"] = elapsed(start)

        app.get_by_text("成本明细", exact=False).first.wait_for(timeout=timeout_ms)
        checkpoints["cost_breakdown_rendered"] = elapsed(start)

        app.get_by_text("📋 相似历史订单", exact=False).first.wait_for(timeout=timeout_ms)
        checkpoints["similar_orders_rendered"] = elapsed(start)

        return {
            "run": run_index,
            "status": "ok",
            "title": title,
            "checkpoints": checkpoints,
            "total_seconds": checkpoints["similar_orders_rendered"],
        }
    except Exception as exc:  # noqa: BLE001 - CLI evidence should preserve failure type
        return {
            "run": run_index,
            "status": "blocked-ui",
            "reason": f"{type(exc).__name__}: {str(exc)[:180]}",
            "checkpoints": checkpoints,
            "elapsed_until_block_seconds": elapsed(start),
        }
    finally:
        browser.close()


def build_payload(url: str, runs: int, timeout_ms: int) -> dict:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # noqa: BLE001
        return blocked_payload(f"playwright-unavailable:{type(exc).__name__}", runs)

    details: list[dict] = []
    with sync_playwright() as playwright:
        for idx in range(1, runs + 1):
            details.append(run_once(playwright, url, timeout_ms, idx))

    ok_totals = [row["total_seconds"] for row in details if row.get("status") == "ok"]
    if len(ok_totals) != runs:
        return blocked_payload("ui-checkpoints-not-all-rendered", runs, details)

    return {
        "status": "ok",
        "url": url,
        "runs_requested": runs,
        "median_total_seconds": round(statistics.median(ok_totals), 3),
        "runs": details,
        "generated_at_utc": now_iso(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--timeout-ms", type=int, default=60000)
    parser.add_argument("--output")
    args = parser.parse_args()

    payload = build_payload(args.url, args.runs, args.timeout_ms)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    print(text)
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    return 0 if payload["status"] == "ok" else 2


if __name__ == "__main__":
    sys.exit(main())
