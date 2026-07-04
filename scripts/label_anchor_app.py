#!/usr/bin/env python3
"""One-click human-anchor labeling UI for Yi.

Reads eval/human_anchor/anchor_set_40.csv, shows one case at a time, and writes
Yi's verdict/note back to the same CSV. Only the yi_verdict / yi_note columns
are ever modified; a timestamped backup is created on first write.

Run:  .venv/bin/streamlit run scripts/label_anchor_app.py
"""

from __future__ import annotations

import csv
import shutil
import time
from pathlib import Path

import streamlit as st

REPO = Path(__file__).resolve().parents[1]
CSV_PATH = REPO / "eval" / "human_anchor" / "anchor_set_40.csv"
VERDICTS = ["approve", "revise", "reject"]
VERDICT_HELP = {
    "approve": "✅ approve — 草稿可用，只带常规注意事项",
    "revise": "✏️ revise — 有缺口：上下文缺失/理由弱/措辞有风险，需人工修订后才能用",
    "reject": "⛔ reject — 不能用：数据不足、越治理边界、或会误导使用者",
}


def load_rows() -> list[dict]:
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save_rows(rows: list[dict]) -> None:
    backup = CSV_PATH.with_suffix(f".csv.bak-{time.strftime('%Y%m%d')}")
    if not backup.exists():
        shutil.copy2(CSV_PATH, backup)
    fieldnames = ["case_id", "input_summary", "critic_verdict",
                  "critic_reason_summary", "yi_verdict", "yi_note"]
    tmp = CSV_PATH.with_suffix(".csv.tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(CSV_PATH)


st.set_page_config(page_title="Human Anchor 标注台", layout="wide")
rows = load_rows()
labeled = [r for r in rows if r["yi_verdict"].strip()]
pending = [i for i, r in enumerate(rows) if not r["yi_verdict"].strip()]

st.sidebar.title("Human Anchor 标注台")
st.sidebar.metric("进度", f"{len(labeled)} / {len(rows)}")
st.sidebar.progress(len(labeled) / max(len(rows), 1))
st.sidebar.caption("规则速记：样本少/BC 外销/缺覆膜/无匹配数据 → 至少 revise，"
                   "除非 critic 已明确拦下不安全结论。拿不准就选一个并写一句 yi_note，"
                   "分歧本身就是有价值的数据。")

mode = st.sidebar.radio("模式", ["顺序标注（推荐）", "浏览/修改已标"])

if mode == "顺序标注（推荐）":
    if not pending:
        st.success("🎉 40 例全部完成！运行下一步：\n\n"
                   "`python3 scripts/compute_anchor_agreement.py eval/human_anchor/anchor_set_40.csv`")
        st.stop()
    idx = pending[0]
else:
    choice = st.sidebar.selectbox("选择案例", [f"{i+1:02d} · {r['case_id']} · {r['yi_verdict'] or '未标'}"
                                              for i, r in enumerate(rows)])
    idx = int(choice.split(" ·")[0]) - 1

row = rows[idx]
st.subheader(f"案例 {idx + 1} / {len(rows)} · `{row['case_id']}`")

left, right = st.columns([3, 2])
with left:
    st.markdown("**订单与上下文**")
    st.info(row["input_summary"])
with right:
    st.markdown(f"**Critic 判定：`{row['critic_verdict']}`**")
    st.warning(row["critic_reason_summary"] or "（无理由摘要）")

st.markdown("**你的判定（以你的行业标准，这份审查草稿该如何处置？）**")
for v in VERDICTS:
    st.caption(VERDICT_HELP[v])

default_v = row["yi_verdict"] if row["yi_verdict"] in VERDICTS else None
picked = st.radio("yi_verdict", VERDICTS, horizontal=True,
                  index=VERDICTS.index(default_v) if default_v else None,
                  label_visibility="collapsed")
note = st.text_input("yi_note（可选，边界案例/不同意 critic 时写一句原因）",
                     value=row["yi_note"])

if st.button("保存并下一例 ▶", type="primary", use_container_width=True,
             disabled=picked is None):
    rows[idx]["yi_verdict"] = picked
    rows[idx]["yi_note"] = note.strip()
    save_rows(rows)
    st.rerun()
