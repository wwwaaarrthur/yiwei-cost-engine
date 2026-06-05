"""Public-demo display sanitization for Yiwei Cost Engine.

The public Streamlit app should demonstrate workflow and evaluation quality
without exposing row-level commercial details from the factory dataset.
"""
from __future__ import annotations

import hashlib
from typing import Any

import pandas as pd


REDACTED_TEXT = "PUBLIC_DEMO_REDACTED"


def _stable_id(*values: Any) -> int:
    raw = "|".join("" if value is None else str(value) for value in values)
    digest = hashlib.md5(raw.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 999 + 1


def _case_category(value: Any) -> str:
    text = str(value or "").lower()
    if any(token in text for token in ("水剂", "瓶", "壶", "liquid")):
        return "液体农化包装"
    if any(token in text for token in ("颗粒", "袋", "粉", "granule")):
        return "固体农化包装"
    if any(token in text for token in ("外贸", "出口", "export")):
        return "出口纸箱"
    if any(token in text for token in ("硬管", "tube")):
        return "工业品纸箱"
    return "制造业纸箱"


def _flute_label(row: pd.Series) -> str:
    for key in ("flute_normalized", "flute_type", "flute_eval"):
        value = row.get(key)
        if value and str(value).strip():
            return str(value).strip()
    return "瓦型"


def sanitize_process_sheets_for_public(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with public-facing text fields generalized.

    Numeric dimensions, quantities, and derived metrics remain available so the
    app can still demonstrate operations logic. Customer, product, material,
    file, path, and notes fields are generalized for public presentation.
    """
    if df.empty:
        return df.copy()

    safe = df.copy()
    ids = safe.apply(
        lambda row: _stable_id(
            row.get("client"),
            row.get("product"),
            row.get("batch_no"),
            row.get("box_l"),
            row.get("box_w"),
            row.get("box_h"),
        ),
        axis=1,
    )

    safe["product"] = [
        f"{_case_category(product)}案例-{case_id:03d}"
        for product, case_id in zip(safe.get("product", []), ids)
    ]

    for column in ("file", "dirname", "filepath"):
        if column in safe.columns:
            safe[column] = "PUBLIC_DEMO_ONLY"

    for column in ("paper_spec", "padding_material", "padding_size", "grid_material", "print_qty_str"):
        if column in safe.columns:
            safe[column] = REDACTED_TEXT

    if "board_material" in safe.columns:
        safe["board_material"] = safe.apply(
            lambda row: f"{_flute_label(row)} 脱敏纸板配置-{_stable_id(row.get('board_material')):03d}",
            axis=1,
        )

    if "notes" in safe.columns:
        safe["notes"] = REDACTED_TEXT

    return safe


def sanitize_precheck_costs_for_public(cost_df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with row-level precheck identity fields generalized."""
    if cost_df.empty:
        return cost_df.copy()

    safe = cost_df.copy()
    ids = safe.apply(
        lambda row: _stable_id(
            row.get("product"),
            row.get("material"),
            row.get("file"),
            row.get("qty"),
        ),
        axis=1,
    )

    if "product" in safe.columns:
        safe["product"] = [f"价格评估样本-{case_id:03d}" for case_id in ids]

    if "material" in safe.columns:
        safe["material"] = safe.apply(
            lambda row: f"{_flute_label(row)} 脱敏材料配置-{_stable_id(row.get('material')):03d}",
            axis=1,
        )

    if "file" in safe.columns:
        safe["file"] = [f"PUBLIC_PRECHECK_{case_id:03d}" for case_id in ids]

    return safe
