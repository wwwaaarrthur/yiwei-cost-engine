#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════╗
║  毅伟成本引擎 · AI Eval Runner v1.0                    ║
║  评估报价公式准确度 → 质量层核心产出物                  ║
╚══════════════════════════════════════════════════════════╝

评测对象：app.py 中的报价公式（纸板面积 × 瓦型基准价 × 数量系数 ÷ 毛利率）
Ground Truth（真实值）：precheck_costs 表中的实际成本（unit_cost）

5 个模块：
  1. Loader     — 加载 ground truth 数据
  2. Predictor  — 用报价公式生成预测值
  3. Metrics    — 计算 MAE / MAPE / Bias / R²
  4. Breakdown  — 按瓦型分层精度报告
  5. Regression — 参数变更前后的回归测试

运行：python3 eval_runner.py
"""

import sqlite3
import json
import sys
import re
from datetime import datetime
import numpy as np

DB = "data/process_sheets.db"

# ═══════════════════════════════════════════════════════════
# 模块 1: Loader — 加载 ground truth
# ═══════════════════════════════════════════════════════════
# 概念：Ground Truth = "正确答案"，即预核单中的实际成本
# 面试对应："你的测试数据从哪来？多大？代表性强吗？"


def load_ground_truth():
    """从预核单加载实际成本作为 ground truth"""
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT product, size_w, size_h, material, unit_cost
        FROM precheck_costs
        WHERE size_w > 0 AND size_h > 0 AND unit_cost > 0
    """)

    records = []
    for row in cursor.fetchall():
        records.append({
            'product': row[0],
            'size_w': float(row[1]),
            'size_h': float(row[2]),
            'material': str(row[3]) if row[3] else '',
            'unit_cost': float(row[4]),
        })

    conn.close()
    print(f"\n✅ 加载 {len(records)} 条预核单作为 ground truth")
    return records


# ═══════════════════════════════════════════════════════════
# 模块 2: Predictor — 生成预测值
# ═══════════════════════════════════════════════════════════
# 概念：Prediction = 报价公式算出来的"应该多少钱"
# 面试对应："你的系统怎么根据输入给出价格？"


def detect_flute(material_str):
    """
    从材料字符串识别瓦型
    如 "140gB+120gE" → 'EB', "200gB+160gC" → 'BC'
    """
    m = str(material_str)
    has_b = bool(re.search(r'\d+gB', m))
    has_e = bool(re.search(r'\d+gE', m))
    has_c = bool(re.search(r'\d+gC', m))

    if has_b and has_e:
        return 'EB'
    if has_b and has_c:
        return 'BC'
    if has_e and not has_b:
        return '单E瓦'
    if has_b and not has_e:
        return '单B瓦'
    return 'EB'


def predict_cost(record, fcb_params):
    """
    对一条预核单，用报价公式计算预测 ¥/m²

    简化版公式（与 app.py 一致）：
      predicted_cpm = 基准价（按瓦型）
    """
    board_area = record['size_w'] * record['size_h'] / 1_000_000
    flute_type = detect_flute(record['material'])
    base_price = fcb_params.get(flute_type, 1.5)
    predicted_cpm = base_price

    return predicted_cpm, flute_type


# ═══════════════════════════════════════════════════════════
# 模块 3: Metrics — 计算评估指标
# ═══════════════════════════════════════════════════════════
# 概念：Metrics = 用数字告诉你"预测有多准"
# 面试对应："你用什么指标衡量模型质量？"


def calculate_metrics(predictions, actuals):
    """
    输入：预测值列表 + 真实值列表
    返回：4 个核心指标
    """
    preds = np.array(predictions)
    acts = np.array(actuals)
    errors = preds - acts  # 正=高估，负=低估

    n = len(preds)

    # 1. MAE — 平均绝对误差。面试说法："平均每单偏差 ¥X"
    mae = float(np.mean(np.abs(errors)))

    # 2. MAPE — 平均绝对百分比误差。面试说法："平均误差 X%"
    mape = float(np.mean(np.abs(errors) / acts) * 100)

    # 3. Bias — 平均偏差（正=系统性高估，负=系统性低估）
    bias = float(np.mean(errors))

    # 4. R² — 决定系数（0=瞎猜，1=完美预测）
    ss_res = float(np.sum((acts - preds) ** 2))
    ss_tot = float(np.sum((acts - acts.mean()) ** 2))
    r2 = float(1 - ss_res / ss_tot) if ss_tot > 0 else 0.0

    return {
        'n': n,
        'mae': round(mae, 4),
        'mape': round(mape, 1),
        'bias': round(bias, 4),
        'r2': round(r2, 4),
    }


# ═══════════════════════════════════════════════════════════
# 模块 4: Breakdown — 按瓦型分层
# ═══════════════════════════════════════════════════════════
# 概念：分层评估 = 不只看"整体"，拆开看每类表现
# 面试对应："你们系统对哪类订单表现最好？哪类最差？"


def breakdown_by_flute(records, fcb_params):
    """按瓦型分组计算指标"""
    flute_groups = {}

    for r in records:
        pred, flute = predict_cost(r, fcb_params)
        board_area = r['size_w'] * r['size_h'] / 1_000_000
        actual_cpm = r['unit_cost'] / board_area

        if flute not in flute_groups:
            flute_groups[flute] = {'preds': [], 'actuals': [], 'products': []}

        flute_groups[flute]['preds'].append(pred)
        flute_groups[flute]['actuals'].append(actual_cpm)
        flute_groups[flute]['products'].append(r['product'][:15])

    print("\n" + "═" * 60)
    print("📊 按瓦型精度报告")
    print("═" * 60)

    for flute in sorted(flute_groups.keys()):
        g = flute_groups[flute]
        m = calculate_metrics(g['preds'], g['actuals'])
        rating = '🟢 可用' if m['mape'] < 15 else ('🟡 一般' if m['mape'] < 30 else '🔴 需改善')
        print(f"\n  {rating} {flute}瓦 (n={m['n']})")
        print(f"    基准价: ¥{fcb_params.get(flute, 1.5):.2f}/m²")
        print(f"    实际中位: ¥{np.median(g['actuals']):.2f}/m²")
        print(f"    MAE: ¥{m['mae']:.3f}/m²  |  MAPE: {m['mape']:.1f}%  |  Bias: {m['bias']:+.3f}")

    return flute_groups


# ═══════════════════════════════════════════════════════════
# 模块 5: Regression Test — 回归测试
# ═══════════════════════════════════════════════════════════
# 概念：回归测试 = 改了参数后，跑老数据确认没退化
# 面试对应："你改基准价后怎么确认没把别的订单搞崩？"


def regression_test(records, old_fcb, new_fcb):
    """对比两组基准价的精度变化"""
    print("\n" + "═" * 60)
    print("🔄 回归测试：参数变更前后对比")
    print("═" * 60)

    all_actuals = []
    old_preds = []
    new_preds = []

    for r in records:
        board_area = r['size_w'] * r['size_h'] / 1_000_000
        actual = r['unit_cost'] / board_area
        all_actuals.append(actual)

        old_p, _ = predict_cost(r, old_fcb)
        new_p, _ = predict_cost(r, new_fcb)
        old_preds.append(old_p)
        new_preds.append(new_p)

    old_m = calculate_metrics(old_preds, all_actuals)
    new_m = calculate_metrics(new_preds, all_actuals)

    # 输出对比表
    print(f"\n  {'指标':<10} {'旧参数':>10} {'新参数':>10} {'变化':>12}")
    print(f"  {'─' * 10} {'─' * 10} {'─' * 10} {'─' * 12}")

    for key, label, fmt, better_lower in [
        ('mae', 'MAE ¥/m²', '.4f', True),
        ('mape', 'MAPE %', '.1f', True),
        ('bias', 'Bias ¥', '.4f', False),
        ('r2', 'R²', '.4f', False),
    ]:
        old_v = old_m[key]
        new_v = new_m[key]
        diff = new_v - old_v
        if better_lower:
            arrow = '✅ 改善' if diff < 0 else ('⚠️ 退化' if diff > 0 else '➖ 不变')
        else:
            arrow = '✅ 改善' if diff > 0 else ('⚠️ 退化' if diff < 0 else '➖ 不变')
        print(f"  {label:<10} {old_v:{fmt}} {new_v:{fmt}} {diff:+.4f} {arrow}")

    return {'old': old_m, 'new': new_m}


# ═══════════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════════

if __name__ == '__main__':
    print("╔════════════════════════════════════════╗")
    print("║  毅伟成本引擎 · AI Eval Report         ║")
    print(f"║  {datetime.now().strftime('%Y-%m-%d %H:%M')}                        ║")
    print("╚════════════════════════════════════════╝")

    # Step 1: 加载 ground truth
    records = load_ground_truth()

    if len(records) < 3:
        print("⚠️  预核单数据不足（需≥3条），无法评估。")
        sys.exit(0)

    # Step 2: 当前基准价（与 app.py fcb 同步）
    current_fcb = {
        'EB': 1.50, 'BC': 2.00, 'AB': 2.20,
        '单C瓦': 1.50, '单B瓦': 1.30, '单E瓦': 1.10, 'EE': 1.40,
    }

    # Step 3-4: 对每条记录预测 + 计算整体指标
    all_preds = []
    all_actuals = []
    for r in records:
        board_area = r['size_w'] * r['size_h'] / 1_000_000
        pred_cpm, _ = predict_cost(r, current_fcb)
        actual_cpm = r['unit_cost'] / board_area
        all_preds.append(pred_cpm)
        all_actuals.append(actual_cpm)

    overall = calculate_metrics(all_preds, all_actuals)
    print(f"\n📊 整体指标 (n={overall['n']})")
    print(f"  MAE:  ¥{overall['mae']:.4f}/m²      ← 平均每单偏差")
    print(f"  MAPE: {overall['mape']:.1f}%          ← 平均百分比误差")
    print(f"  Bias: {overall['bias']:+.4f} ¥/m²    ← +高估/-低估")
    print(f"  R²:   {overall['r2']:.4f}           ← 0=瞎猜 1=完美")

    if overall['mape'] < 15:
        print(f"\n  🟢 整体可用（MAPE {overall['mape']:.1f}% < 15%）")
    elif overall['mape'] < 30:
        print(f"\n  🟡 整体一般（MAPE {overall['mape']:.1f}%），建议分瓦型查看")
    else:
        print(f"\n  🔴 整体需改善（MAPE {overall['mape']:.1f}% ≥ 30%）")

    # Step 5: 按瓦型分层
    flute_breakdown = breakdown_by_flute(records, current_fcb)

    # Step 6: 回归测试（演示：EB 基准价从 1.50 → 1.30）
    new_fcb = dict(current_fcb)
    new_fcb['EB'] = 1.30
    regression_test(records, current_fcb, new_fcb)

    print("\n" + "═" * 60)
    print("✅ 评估完成。以上报告可直接放入架构文档「质量评估」章节。")
    print("═" * 60)
