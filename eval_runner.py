#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════╗
║  毅伟成本引擎 · AI Eval Runner v1.0                    ║
║  评估报价公式准确度 → 质量层核心产出物                  ║
╚══════════════════════════════════════════════════════════╝

评测对象：已知材料面积条件下的价格公式，不验证尺寸引擎或拼版判断
Ground Truth（真实值）：precheck_costs 表中的实际成本（unit_cost）

5 个模块：
  1. Loader     — 加载 ground truth 数据
  2. Predictor  — 用报价公式生成预测值
  3. Metrics    — 计算 MAE / MAPE / Bias / R²
  4. Breakdown  — 按瓦型分层精度报告
  5. Regression — 参数变更前后的回归测试

运行：python3 eval_runner.py
"""

import os
import sqlite3
import json
import sys
import re
from datetime import datetime
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PROD = os.path.join(HERE, "data", "process_sheets.db")
DB_DEMO = os.path.join(HERE, "data", "demo.db")
DB = DB_PROD if os.path.exists(DB_PROD) else DB_DEMO

# ═══════════════════════════════════════════════════════════
# 模块 1: Loader — 加载 ground truth
# ═══════════════════════════════════════════════════════════
# 概念：Ground Truth = "正确答案"，即预核单中的实际成本
# 面试对应："你的测试数据从哪来？多大？代表性强吗？"


def load_ground_truth():
    """从预核单加载实际成本作为 ground truth"""
    if not os.path.exists(DB):
        raise FileNotFoundError(
            f"No evaluation database found. Expected either:\n"
            f"  - {DB_PROD} (private production DB)\n"
            f"  - {DB_DEMO} (public anonymized demo DB)"
        )

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
    db_label = "production" if DB == DB_PROD else "anonymized demo"
    print(f"\n✅ 加载 {len(records)} 条预核单作为 ground truth ({db_label} DB)")
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
    对一条预核单，用报价公式计算预测 ¥/m² (Baseline V1: 仅瓦楞基准价)

    简化版公式：predicted_cpm = 基准价（按瓦型）
    评估目标：material ¥/m² (= unit_cost / board_area)
    """
    board_area = record['size_w'] * record['size_h'] / 1_000_000
    flute_type = detect_flute(record['material'])
    base_price = fcb_params.get(flute_type, 1.5)
    predicted_cpm = base_price

    return predicted_cpm, flute_type


# ═══════════════════════════════════════════════════════════
# Phase B+C: 条件价格公式（材料面积已知）
# ═══════════════════════════════════════════════════════════
# 评估目标：contract_price (真实合同价) 而非 material ¥/m²
# 数据源：9 张 .xls 预核单 22 行 ground truth

PRINT_TABLE = {
    1: (150, 0.18), 2: (300, 0.21), 3: (500, 0.30),
    4: (900, 0.45), 5: (1250, 0.63),
}
OTHER_COST_DEFAULT = {'内销': 0.82, '出口': 1.07}


def qty_margin_base(qty):
    if qty <= 500: return 0.30
    if qty <= 2000: return 0.22
    if qty <= 5000: return 0.12
    if qty <= 20000: return 0.08
    return 0.06


def cmargin_v2(tier, qty, is_export=False):
    adj = {'vip': -0.02, 'medium': 0.0, 'small': +0.03}[tier]
    export_adj = 0.04 if is_export else 0.0
    return max(0.03, qty_margin_base(qty) + adj + export_adj)


def predict_cost_full(record, params):
    """
    Phase C 完整 6 项条件价格公式预测。

    优先输入 sizing_engine 产出的独立面积：
      board_area_m2, face_area_m2
    旧预核单只有 area_m2 时，面纸面积仍回退为板材面积的 60%。该回退只用于
    保持历史评估可复现，不能代表员工确认的尺寸规则。
    不使用 ground truth 字段 (corr_cpm/pad_total/white_unit/print_unit/film_unit/other_cost)
    否则等同"用真值预测真值"

    params: dict {fcb, tier}
    返回: (predicted_cost_per_unit, predicted_contract_price, breakdown_dict)
    """
    board_area = record.get('board_area_m2') or record.get('area_m2') or 0
    face_area = record.get('face_area_m2')
    if face_area is None:
        face_area = board_area * 0.6
        area_source = 'legacy_board_area_with_60pct_face_fallback'
    else:
        area_source = 'independent_sizing_engine_areas'
    qty = record.get('qty') or 1
    flute = record.get('flute') or 'EB'
    fcb = params.get('fcb', {
        'EB': 1.5, 'BC': 2.0, 'AB': 2.2,
        '单C瓦': 1.5, '单B瓦': 1.3, '单E瓦': 1.1, 'EE': 1.4,
    })
    bp = fcb.get(flute, 1.5)
    bc = board_area * bp                        # 瓦楞 (fcb 学习)
    # Phase D1: 面纸按克重 × ¥/吨 精算 (替代 0.45 ¥/m² 硬编码)
    paper_gsm = params.get('paper_gsm', 250)
    paper_per_tonne = params.get('paper_per_tonne', 3410)
    paper_cpm = (paper_gsm * paper_per_tonne) / 1_000_000   # 实测 250×3410/1e6 = 0.853
    pc = face_area * paper_cpm                  # 面纸 (独立面积 × 实测 ¥/m²)
    lc = 0.25 if record.get('has_lam') else 0   # 覆膜 (default 0.25 ¥/只)
    pdc = 0.15 if record.get('has_pad') else 0  # 垫片 (default 0.15 ¥/只)
    # 印刷按色数表
    colors = record.get('print_colors', 2)
    setup, var = PRINT_TABLE.get(colors, PRINT_TABLE[2])
    print_cost = max(setup / qty, var)
    # 制费按订单类型
    order_type = record.get('order_type', '内销')
    other_cost = OTHER_COST_DEFAULT[order_type]
    # 数量系数
    if qty <= 500: sf = 1.15
    elif qty <= 2000: sf = 1.05
    elif qty <= 5000: sf = 1.0
    elif qty <= 20000: sf = 0.93
    else: sf = 0.88
    base = bc + pc + lc + pdc + print_cost + other_cost
    cost = base * sf
    # 毛利
    is_export = (order_type == '出口')
    tier = params.get('tier', 'vip')
    margin = cmargin_v2(tier, qty, is_export=is_export)
    price = cost / (1 - margin)
    breakdown = {
        'bc': round(bc, 3), 'pc': round(pc, 3), 'lc': round(lc, 3),
        'pdc': round(pdc, 3), 'print': round(print_cost, 3),
        'other': round(other_cost, 3), 'sf': sf, 'margin': round(margin, 3),
        'area_source': area_source,
    }
    return round(cost, 3), round(price, 3), breakdown


def infer_print_colors(print_unit):
    """从 .xls print_unit 反推印刷色数"""
    if print_unit is None: return 2  # 默认双色
    if print_unit <= 0.20: return 1
    if print_unit <= 0.25: return 2
    if print_unit <= 0.35: return 3
    if print_unit <= 0.50: return 4
    return 5


def load_xls_ground_truth(csv_path):
    """加载 22 行 .xls ground truth CSV (含 6 项成本拆解 + 合同价)"""
    import csv
    rows = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            def f2(k):
                try:
                    return float(r[k]) if r[k] else None
                except (ValueError, KeyError):
                    return None

            pad_total = f2('pad_total')
            film_unit = f2('film_unit')
            print_unit = f2('print_unit')
            rows.append({
                'file': r['file'], 'product': r['product'],
                'qty': int(float(r['qty'])) if r['qty'] else 0,
                'area_m2': f2('area_m2'), 'flute': r['flute'],
                # Ground truth (用于评估对比, 不输入预测函数)
                'corr_cpm': f2('corr_cpm'), 'corr_unit': f2('corr_unit'),
                'pad_total': pad_total,
                'white_unit': f2('white_unit'), 'print_unit': print_unit,
                'film_unit': film_unit, 'other_cost': f2('other_cost'),
                'total_cost': f2('total_cost'),
                'contract_price': f2('contract_price'),
                'margin_pct': f2('margin_pct'),
                # 输入特征 (从 .xls 推断, 模拟 app.py UI 输入)
                'order_type': '出口' if '4L外贸' in r['file'] else '内销',
                'has_lam': bool(film_unit and film_unit > 0),
                'has_pad': bool(pad_total and pad_total > 0),
                'print_colors': infer_print_colors(print_unit),
            })
    return rows


def evaluate_xls_contract(xls_rows, tier='vip'):
    """对 22 行 .xls ground truth 跑完整公式 → 评估合同价 MAPE"""
    params = {'tier': tier}
    cost_preds, cost_acts = [], []
    contract_preds, contract_acts = [], []
    for r in xls_rows:
        if not r.get('area_m2'):
            continue
        cost_p, price_p, _ = predict_cost_full(r, params)
        if r.get('total_cost'):
            cost_preds.append(cost_p)
            cost_acts.append(r['total_cost'])
        if r.get('contract_price'):
            contract_preds.append(price_p)
            contract_acts.append(r['contract_price'])
    return {
        'cost': calculate_metrics(cost_preds, cost_acts) if cost_preds else None,
        'contract': calculate_metrics(contract_preds, contract_acts) if contract_preds else None,
    }


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
        rating = '🟢 条件通过' if m['mape'] < 15 else ('🟡 一般' if m['mape'] < 30 else '🔴 需改善')
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
    print("⚠️  Scope: price accuracy conditional on provided material area; sizing accuracy is tested separately.")

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
        print(f"\n  🟢 已知材料面积条件下通过（MAPE {overall['mape']:.1f}% < 15%）")
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

    # ═══════════════════════════════════════════════════════════
    # Step 7: Conditional Contract Price Eval (材料面积已知)
    # ═══════════════════════════════════════════════════════════
    # 数据源：9 张 .xls 预核单 22 行 ground truth (含合同价 17 行)
    # 评估目标：客户实际合同价 (vs 仅材料 ¥/m²)
    csv_path = os.path.join(HERE, 'data', 'ground_truth_22rows.csv')
    if os.path.exists(csv_path):
        print("\n" + "═" * 60)
        print("📊 Step 7: Conditional Contract Price Eval (provided material area)")
        print("═" * 60)
        print(f"\n  数据源: {os.path.relpath(csv_path, HERE)}")
        xls_rows = load_xls_ground_truth(csv_path)
        print(f"  加载 {len(xls_rows)} 行 ground truth")

        result = evaluate_xls_contract(xls_rows, tier='vip')
        if result['cost']:
            m = result['cost']
            print(f"\n  📊 成本预测 (vs .xls total_cost, n={m['n']})")
            print(f"    MAE:  ¥{m['mae']:.3f}/只  |  MAPE: {m['mape']:.1f}%")
            print(f"    Bias: {m['bias']:+.3f}/只  |  R²: {m['r2']:.4f}")
        if result['contract']:
            m = result['contract']
            print(f"\n  📊 合同价预测 (vs .xls contract_price, n={m['n']})")
            print(f"    MAE:  ¥{m['mae']:.3f}/只  |  MAPE: {m['mape']:.1f}%")
            print(f"    Bias: {m['bias']:+.3f}/只  |  R²: {m['r2']:.4f}")
            if m['mape'] < 15:
                print(f"  🟢 合同价 MAPE {m['mape']:.1f}% < 15% — 条件评估通过，不含尺寸验证")
            elif m['mape'] < 25:
                print(f"  🟡 合同价 MAPE {m['mape']:.1f}% 一般")
            else:
                print(f"  🔴 合同价 MAPE {m['mape']:.1f}% 需改善")
    else:
        print(f"\n⚠️  Step 7 跳过 (csv 未找到: {csv_path})")

    print("\n" + "═" * 60)
    print("✅ 评估完成。以上报告可直接放入架构文档「质量评估」章节。")
    print("═" * 60)
