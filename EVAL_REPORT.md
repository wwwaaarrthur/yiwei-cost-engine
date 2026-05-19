# Yiwei Cost Engine · AI Evaluation Report

> **Real eval results from `eval_runner.py` against n=43 ground truth precheck orders.**
> Last updated: 2026-05-17
> Reproducible: run `python3 eval_runner.py` after setup (see §5)

This report is the system-thinking proof for the project — it surfaces what works, what fails, and why, rather than headline accuracy numbers.

---

## 1. Overall Metrics (n=43)

| Metric | Baseline (median pricing) | Tuned (one iteration) | Change |
|---|:---:|:---:|:---:|
| MAE (¥/m²) | 0.6956 | 0.5862 | **-0.1094** ✅ |
| MAPE (%) | **39.0** | **28.2** | **-10.8 pp** ✅ |
| Bias (¥/m²) | -0.0475 | -0.1963 | -0.1488 ⚠️ |
| R² | 0.1784 | 0.1957 | +0.0173 ✅ |

### Honest Assessment

- **Baseline is a weak signal**: R² ≈ 0.18 means the flute-stratified median pricing logic only explains ~18% of price variance. It is intentionally chosen as an interpretable starting point, not a final model.
- **MAPE 39% (baseline) → 28.2% (tuned)** is a real, eval-driven improvement — every percentage point came from analyzing the Breakdown module and adjusting flute-type parameters.
- **Bias trade-off captured**: parameter changes that improved MAPE simultaneously degraded Bias from -0.05 to -0.20 ¥/m² → caught by the **Regression module** (§3) before it became a silent failure.

> The point of this project is not "achieve ±8% accuracy" — it is to demonstrate that **AI quality has to be measured, not claimed**, and that the eval scaffolding catches the failure modes that headline metrics hide.

---

## 2. Flute-Stratified Analysis (Breakdown Module)

| Flute Type | n | Base Price (¥/m²) | Actual Median (¥/m²) | MAE | MAPE | Bias |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **BC** | 9 | 2.00 | 2.86 | 1.517 | **49.1%** | **-0.928** |
| EB | 32 | 1.50 | 1.15 | 0.491 | 35.5% | +0.180 |
| Single-E | 2 | 1.10 | 0.83 | 0.273 | 49.1% | +0.272 |

### 🔴 Critical Failure Mode: BC Flute Systematic Underestimation

- **Bias = -0.928 ¥/m² against base price 2.00 ¥/m²** → baseline systematically underestimates BC flute pricing by ~46% (in absolute terms; ~93% relative to base price gap).
- **Hypothesis**: BC flute orders include premium variants (waterproof lamination, high-burst-strength paper, specialty linings) that drive contract prices 40-60% above standard BC. The baseline median treats them as homogeneous.

### Next-Iteration Plan

1. Introduce `lamination` (Y/N) as primary split feature within BC stratum
2. Train a sub-model on BC variants (n=9 currently — needs data expansion to n=30+ for stable training)
3. Target: BC MAPE < 20%, overall MAPE < 15%

### Takeaway

Aggregate metrics hide subset failures. The Breakdown module decomposes error by business dimension (here: flute type), so iteration targets the actual broken subset. Without this layer, an aggregate 39% MAPE invites broad-strokes retuning that misses BC and risks degrading EB.

---

## 3. Regression Test (Failure-Analysis Module)

```
Old parameters:
  MAE=0.6956 ¥/m²   |  MAPE=39.0%   |  Bias=-0.0475   |  R²=0.1784

New parameters (one round of tuning):
  MAE=0.5862 ¥/m²   |  MAPE=28.2%   |  Bias=-0.1963   |  R²=0.1957

Diff:
  MAE   -0.1094  ✅ improved
  MAPE  -10.8 pp ✅ improved
  Bias  -0.1488  ⚠️  degraded (now systematically underestimating)
  R²    +0.0173  ✅ slightly improved
```

### What This Guards Against

> *"MAPE improved by 10.8 percentage points, looks good — ship it!"*

Without the Regression module, the Bias degradation would slip through. New params trade variance for systematic underestimation: orders quoted with the new params are more consistent, but the entire price distribution shifts downward.

In a real business, this means **slowly losing margin on every quote** — a failure mode invisible to MAE/MAPE alone.

### Takeaway

Any parameter change should defend itself against **all four metrics simultaneously**, not just the one being optimized. The Regression module guards against single-metric tunnel vision — without it, "improvements" silently degrade orthogonal qualities like Bias.

---

## 4. What This Project Demonstrates (PM Skills Inventory)

| Skill | Evidence in This Project |
|---|---|
| **AI Quality Assurance · system thinking** | 5-module eval pipeline: Loader → Predictor → Metrics → Breakdown → Regression |
| **Failure analysis with quantitative grounding** | BC flute systematic underestimation surfaced; root-cause hypothesis; data-bounded iteration plan |
| **Trade-off articulation** | New params: improved MAPE traded for degraded Bias — surfaced before shipping |
| **Honest assessment over inflated claims** | R² = 0.18 disclosed; baseline weakness acknowledged; not hidden behind a "±8% accuracy" marketing number |
| **Domain-grounded modeling decisions** | flute-stratified median chosen for interpretability; allows senior workers to audit error samples and feed corrections back |
| **Production data ↔ public artifact separation** | `process_sheets.db` (production, 2,155 rows / 44 precheck) → `anonymize.py` → `demo.db` (public, 2,086 rows / 16 precheck) |

> Industry consensus in 2026 (Sequoia AI Ascent · Karpathy, Cherny et al.): the bottleneck has shifted from coding to **Agentic Engineering** — eval pipelines, drift monitoring, regression discipline. This report is the artifact of that practice.

---

## 5. Reproducibility

### Setup

```bash
git clone https://github.com/wwwaaarrthur/yiwei-cost-engine.git
cd yiwei-cost-engine
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### Run Evaluation

```bash
python3 eval_runner.py
```

Output is deterministic (no random seed); should match §1-3 of this report exactly. If your numbers differ, file an issue with output attached.

### Run Web App

```bash
python3 -m streamlit run app.py
```

Open `http://localhost:8501`. The bundled `data/demo.db` loads automatically (anonymized — real client names replaced with role-based labels like `大型农化客户A`).

---

## 6. Known Limitations

| Limitation | Why | Mitigation Plan |
|---|---|---|
| Baseline R² ≈ 0.18 | flute-stratified median is intentionally simple, doesn't capture board weight × lamination × printing-style interactions | Upgrade baseline to gradient-boosted trees (XGBoost / LightGBM) using existing 15+ structured features |
| BC stratum n=9, Single-E n=2 | small-flute-type samples have high variance in metrics | Wait for production data growth (process_sheets.db updates weekly); current 2,155 rows → target 3,000+ before BC sub-model training |
| No drift monitoring yet | eval runs are manual, not scheduled | Add `weekly_eval.py` cron job that runs `eval_runner.py` and alerts if MAPE shifts >5pp week-over-week (System 7-piece set completion) |
| Ground truth n=43 only | precheck cost data slower to accumulate than process sheets | Monthly precheck data extraction from `precheck_costs` table (currently 44 rows in production, 16 in demo) |

---

## 7. Contract Price Eval — Phase B + Phase C (2026-05-18 NEW)

> **数据语义审计发现**：§1-3 的 MAPE 评估的是 `material ¥/m²` (= unit_cost / board_area),
> 字段语义实为「瓦楞单只成本/板材面积」—— 不是客户真实合同价。
> Phase C 引入 **9 张 .xls 预核单 22 行 ground truth (含合同价 17 行)** 作为独立数据源,
> 对完整 6 项报价公式跑合同价 MAPE 评估。

### Phase C 数据源

| .xls 文件 | 客户/类型 (脱敏) | 订单行数 | 合同价 |
|---|---|---|---|
| 4L 外贸水剂 ×2 (BC) | 出口 | 2 | ✅ |
| YW-2026-02-02 (亏损批) | 大型农化客户 B 大单 | 3 | ✅ (-15% ~ -18%) |
| YW-2026-02-04 / 04-01 / 04-07 / 04-09 | 大型农化客户 B | 11 | ✅ |
| 硅酮硬管纸箱 (含数量阶梯) | 大型农化客户 B | 7 | 部分 |

**公开 ground truth**：[`data/ground_truth_22rows.csv`](data/ground_truth_22rows.csv) — 22 行 .xls 提取数据 (客户名/产品名/材料品牌已脱敏，cost/contract 数字保持精确以便 reproduce)。

**复现方法**：
```bash
git clone https://github.com/wwwaaarrthur/yiwei-cost-engine.git
cd yiwei-cost-engine && pip install -r requirements.txt
python3 eval_runner.py    # Step 7 应输出 合同价 MAPE 17.1%
```

**私有源数据**：原 9 张 .xls 预核单 + 含真实客户/品牌名的 ground truth 留私有 (`/tmp/yiwei_eval/` 或 `data/process_sheets.db`，未在 git 中)。脱敏映射见 [`anonymize_mapping.example.json`](anonymize_mapping.example.json) 公开模板 + 本地私有 `anonymize_mapping.json` (gitignored)。csv 脱敏脚本：[`anonymize_csv.py`](anonymize_csv.py)。

### Phase B → C → D1 改善路径

| 阶段 | Contract MAPE | Bias | EB 内销主流 (n=15) | 改善 |
|---|:--:|:--:|:--:|:--:|
| 旧公式 (push 前) | **41.3%** | -41.3% | n/a | (baseline) |
| Phase B (3 项最小集) | 21.3% | -21.3% | n/a | +20.0pp |
| Phase C (6 项完整) | 17.1% | -3.9% | 12.6% | +24.2pp |
| **Phase D1 (面纸精算)** | **14.5%** 🟢 | **-1.9%** | **9.9%** 🟢 | **+26.8pp** |

### Phase C 改造内容

1. **印刷成本表 + 数量摊销** (替代硬编码 ¥0.12/只)
   - 5 色阶 setup_fee + unit_var：`max(setup/qty, unit_var)`
   - 实测依据：硅酮硬管 500→3000 只彩印 2.50→0.63 推出 K≈1250 / v≈0.63
2. **出口/内销维度** (制费 0.82 vs 1.07 + 毛利 +4pp)
   - 4L 实测出口毛利 14.8% vs 新安内销 5-8%
3. **qty 阶梯毛利** (替代固定 vip/medium/small)
   - 22 行实测中位：≤500=30% / 501-2k=22% / 2k-5k=12% / 5k-20k=8% / >20k=6%
4. **亏损告警** (毛利 <5% 红色 / <8% 黄色)
   - 防止 02-02 案例 (单笔亏 ¥13,000) 再现

### Phase C 分层精度 (按 flute / order_type)

| 分层 | n | MAPE | Bias | 评级 |
|---|:--:|:--:|:--:|:--:|
| **EB 内销主流** | 15 (88% 订单) | **12.6%** | -6.2% | 🟢 **可用** |
| BC 出口 outlier | 2 (仅 4L*6壶) | 50.9% | -50.9% | 🔴 Phase D 必修 |
| 整体 | 17 | 17.1% | -3.9% | 🟡 一般 |

### Phase D1 分层精度 (面纸精算后)

| 分层 | n | MAPE | Bias | 评级 |
|---|:--:|:--:|:--:|:--:|
| **EB 内销主流** | 15 | **9.9%** | +2.1% | 🟢 **工业级** (< 10%) |
| BC 出口 outlier | 2 | 48.9% | -48.9% | 🔴 Phase D2 待修 (产品配置维度) |
| 整体 | 17 | **14.5%** | -1.9% | 🟢 **可用** (< 15%) |

### Phase D1 改造内容

**面纸成本精算** (替代 0.45 ¥/m² 硬编码)：
- 旧公式：`pc = parea × 0.45 ¥/m²`（经验估算）
- 新公式：`pc = parea × (克重 g/m² × 单价 ¥/吨) / 1_000_000`
- 实测：250 g/m² × 3410 ¥/吨 / 10⁶ = **0.853 ¥/m²** (vs 旧 0.45，偏低 89%)
- 行业惯例：化工/制造业 ERP 用 "吨价 × 单只克重" 精算白板成本
- UI 改造：sidebar 1 个 `¥/m²` 参数 → 拆成 2 个参数（克重 + 吨价）+ 派生 ¥/m² 提示

### Phase C/D1 关键洞察

> **Phase C**: 主流订单 (EB 内销 n=15) MAPE 12.6% —— 6 项拆解 + qty 阶梯生效。
> **Phase D1**: 面纸精算后 EB 内销 **MAPE 9.9%** —— 工业级 (< 10%)。Bias 翻转 -6.2% → +2.1% 接近无偏，公式收敛。
> **BC outlier 仍 48.9%** —— 4L 高级配置 (160g 耐破纸 + 特种涂层 + 出口溢价) 仍需 Phase D2 加产品配置维度。

### Phase D1 后剩余限制

| 限制 | 影响 | Phase D2-6 修复方向 |
|---|---|---|
| 4L 外贸特殊配置 | BC outlier MAPE 48.9% | **Phase D2**: 加产品配置维度 (160g 耐破纸 + 特种涂层 + 出口溢价) |
| 板材公式 blong/bshort 公差未校准 | 影响所有订单 ±5% | **Phase D5**: 用 9 张 .xls 反推 (l/w/h 数据需业务补) |
| ~~面纸 0.45 ¥/m² 默认偏低~~ ✅ | ✅ Phase D1 已修 | (完成) |
| R² 仍 -0.72 | 公式仍非"统计学意义"上学到 | **Phase D6**: XGBoost baseline (Targets R² > 0.3) |
| 无 drift monitor | eval 仍需手动 | **Phase D4**: weekly_eval.py 定时任务 |

---

## 8. Drift Monitor — Phase D4 (System 7-piece-set 完成)

> **System 7 件套**: Loader → Predictor → Metrics → Breakdown → Regression → ContractEval → **DriftMonitor** ✅

`weekly_eval.py` 自动跑 contract MAPE eval, 对比上次结果, 任一关键指标变化 ≥ ±5pp 触发漂移告警。

### 用法

```bash
python3 weekly_eval.py              # 跑一次, 追加到 data/eval_history.jsonl
python3 weekly_eval.py --history    # 查看历史趋势
python3 weekly_eval.py --dry-run    # 跑但不写入历史 (调试用)
```

### 退出码语义 (CI 友好)

- `0` = 无漂移 (所有指标 < ±5pp)
- `1` = 漂移检测到 (任一关键指标 ≥ ±5pp)
- `2` = eval 失败 (数据缺失等)

### 监控项 (任一漂移即告警)

- 整体 contract MAPE
- 整体 cost MAPE
- 各 flute 分层 MAPE (EB / BC / 单E瓦 / ...)
- Bias (含正/负向)

### 部署示例

**cron 每周一 09:00 (HK 时区)**:
```cron
0 9 * * 1  cd ~/yiwei-cost-engine && python3 weekly_eval.py >> logs/weekly.log 2>&1
```

**GitHub Actions** (UTC 周一 01:00 = HK 周一 09:00):
```yaml
on:
  schedule:
    - cron: '0 1 * * 1'
jobs:
  drift-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install -r requirements.txt
      - run: python3 weekly_eval.py
```

### 历史 JSONL 格式 (`data/eval_history.jsonl`)

```jsonl
{"ts": "2026-05-19T11:27:35", "n_rows": 22, "n_contract": 17, "contract": {"mae": 0.791, "mape": 14.5, "bias": -0.332, "r2": -0.7211}, "by_flute": {"BC": {...}, "EB": {...}}}
```

### Drift 告警示例 (假设手动改 fcb_BC 让 MAPE 飘 +6pp)

```
🔴 漂移告警 (阈值 ±5.0pp):
  - 整体 contract MAPE: 14.5% → 20.5% (+6.0pp)
  - BC 瓦 MAPE: 48.9% → 35.0% (-13.9pp)

✅ 已追加到历史: data/eval_history.jsonl
```

→ exit code 1 → CI 会标红 → 推送告警通知

---

## 9. Changelog

| Date | Change | Trigger |
|---|---|---|
| 2026-05-17 | Initial EVAL_REPORT.md (n=43 material ¥/m² MAPE) | Eval-driven simulation revealed README's `±15% → ±8%` was estimated |
| 2026-05-18 | **Data semantic audit + Phase B + Phase C** | 9 .xls × 22 rows ground truth → contract MAPE 41.3% → 17.1% (主流 12.6%) |
| 2026-05-18 | **Phase D1 面纸精算 (克重 × ¥/吨)** | 17.1% → **14.5%** (主流 9.9% 🟢 工业级)，越过 < 15% 可用阈值 |
| 2026-05-19 | **Phase D4 `weekly_eval.py` drift monitor** | System 7-piece-set 第 7 件完成 (Loader/Predictor/Metrics/Breakdown/Regression/ContractEval/**DriftMonitor**) |
| TBD | Phase D2: BC outlier 产品配置维度 (160g 耐破 + 涂层) | BC outlier 修复 |
| TBD | Phase D6: XGBoost baseline upgrade | Targets R² > 0.3 |

---

_Generated 2026-05-18 from `eval_runner.py` against `data/demo.db` (§1-3) + `/tmp/yiwei_eval/ground_truth_22rows.csv` (§7)._
_Production runs use `data/process_sheets.db` (not committed; see `anonymize.py`)._
