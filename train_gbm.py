#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════╗
║  毅伟成本引擎 · Phase D6 GBM Baseline                   ║
║  HistGradientBoostingRegressor (sklearn 自带) vs        ║
║  flute-median baseline (当前 fcb)                       ║
╚══════════════════════════════════════════════════════════╝

数据源:
  - data/demo.db.precheck_costs (44 rows, 43 valid material-cost rows) + data/ground_truth_22rows.csv (n=22, 部分重叠去重)

特征:
  - area_m2 (板材面积)
  - qty (订单量, log 变换)
  - flute (label encoded)
  - total_gram (材料克重总和)
  - has_lam (推断)
  - is_export (file 名含 '外贸')

目标:
  - cost_per_m2 = unit_cost / board_area  (与 EVAL_REPORT §1-3 baseline 一致)

输出:
  - 5-fold CV: MAE / MAPE / Bias / R²
  - models/gbm_cpm.pkl 保存模型

用法:
  python3 train_gbm.py           # 训练 + 5-fold CV + 保存
  python3 train_gbm.py --eval    # 加载模型 + 在 22 行 ground truth 评估
"""
import os
import sys
import sqlite3
import csv
import re
import pickle
import numpy as np
from collections import defaultdict
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import KFold

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, 'data', 'demo.db')
CSV_22 = os.path.join(HERE, 'data', 'ground_truth_22rows.csv')
MODEL = os.path.join(HERE, 'models', 'gbm_cpm.pkl')

# 复用 eval_runner 中的 detect_flute
sys.path.insert(0, HERE)
from eval_runner import detect_flute

FLUTE_LABELS = {'EB': 0, 'BC': 1, 'AB': 2, '单C瓦': 3, '单B瓦': 4, '单E瓦': 5, 'EE': 6}


def extract_total_gram(material):
    """从 '150gB瓦+115g皮芯纸+170gE瓦' 抽 grams 加总"""
    if not material:
        return 0
    return sum(int(m) for m in re.findall(r'(\d+)\s*g', str(material)))


def is_export(file_name):
    if not file_name:
        return 0
    return 1 if ('外贸' in file_name or '出口' in file_name) else 0


def featurize(area_m2, qty, flute, total_gram, has_lam, is_exp):
    return [
        area_m2,
        np.log1p(qty),
        FLUTE_LABELS.get(flute, 0),
        total_gram,
        int(has_lam) if has_lam is not None else 0,
        is_exp,
    ]


FEATURE_NAMES = ['area_m2', 'log_qty', 'flute', 'total_gram', 'has_lam', 'is_export']


def load_training_data():
    """合并 demo.db.precheck_costs + ground_truth_22rows.csv (n=22, 去重)"""
    rows = []
    seen = set()

    # 1. demo.db.precheck_costs
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("""
        SELECT product, qty, size_w, size_h, material, unit_cost, file
        FROM precheck_costs
        WHERE unit_cost > 0 AND size_w > 0 AND size_h > 0
    """)
    for product, qty, sw, sh, mat, uc, file in cur.fetchall():
        area = float(sw) * float(sh) / 1_000_000
        cpm = float(uc) / area if area > 0 else None
        if cpm is None:
            continue
        key = (str(product), int(qty), int(sw), int(sh))
        if key in seen:
            continue
        seen.add(key)
        flute = detect_flute(mat)
        gram = extract_total_gram(mat)
        rows.append({
            'source': 'demo.db',
            'product': product, 'qty': int(qty),
            'area_m2': area, 'flute': flute, 'total_gram': gram,
            'has_lam': 0,  # demo.db 无该字段, 假设无覆膜
            'is_export': is_export(file or ''),
            'unit_cost': float(uc),
            'cost_per_m2': cpm,
        })
    conn.close()

    # 2. data/ground_truth_22rows.csv
    with open(CSV_22, 'r', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            try:
                qty = int(float(r['qty']))
                sw = int(r['size_w'])
                sh = int(r['size_h'])
                uc = float(r['corr_unit']) if r['corr_unit'] else 0
                if uc == 0:
                    continue
                area = sw * sh / 1_000_000
                cpm = uc / area if area > 0 else None
                if cpm is None:
                    continue
                key = (str(r['product']), qty, sw, sh)
                if key in seen:
                    continue
                seen.add(key)
                flute = r['flute'] if r['flute'] in FLUTE_LABELS else 'EB'
                gram = extract_total_gram(r.get('material', ''))
                has_lam = 1 if (r.get('film_unit') and float(r['film_unit']) > 0) else 0
                is_exp = is_export(r.get('file', ''))
                rows.append({
                    'source': 'csv22',
                    'product': r['product'], 'qty': qty,
                    'area_m2': area, 'flute': flute, 'total_gram': gram,
                    'has_lam': has_lam, 'is_export': is_exp,
                    'unit_cost': uc, 'cost_per_m2': cpm,
                })
            except (ValueError, KeyError):
                continue

    return rows


def metrics(preds, acts):
    preds = np.array(preds)
    acts = np.array(acts)
    errs = preds - acts
    n = len(preds)
    mae = float(np.mean(np.abs(errs)))
    mape = float(np.mean(np.abs(errs) / acts) * 100)
    bias = float(np.mean(errs))
    ss_res = float(np.sum((acts - preds) ** 2))
    ss_tot = float(np.sum((acts - acts.mean()) ** 2))
    r2 = float(1 - ss_res / ss_tot) if ss_tot > 0 else 0.0
    return {'n': n, 'mae': round(mae, 4), 'mape': round(mape, 1),
            'bias': round(bias, 4), 'r2': round(r2, 4)}


def flute_median_baseline(train_rows, test_rows):
    """flute-median baseline (与 EVAL_REPORT §1-3 一致)"""
    medians = {}
    for ft in FLUTE_LABELS:
        vs = [r['cost_per_m2'] for r in train_rows if r['flute'] == ft]
        if vs:
            medians[ft] = float(np.median(vs))
    default = float(np.median([r['cost_per_m2'] for r in train_rows]))
    preds = []
    for r in test_rows:
        preds.append(medians.get(r['flute'], default))
    acts = [r['cost_per_m2'] for r in test_rows]
    return preds, acts


def main():
    print("╔════════════════════════════════════════════╗")
    print("║  Phase D6 GBM Baseline Training            ║")
    print("╚════════════════════════════════════════════╝\n")

    rows = load_training_data()
    print(f"训练集合并: n={len(rows)} (demo.db + ground_truth_22rows, 去重后)")
    src_count = defaultdict(int)
    for r in rows:
        src_count[r['source']] += 1
    for k, v in src_count.items():
        print(f"  {k}: {v}")
    flute_count = defaultdict(int)
    for r in rows:
        flute_count[r['flute']] += 1
    print(f"\nflute 分布:")
    for k, v in sorted(flute_count.items()):
        print(f"  {k}: {v}")

    # 特征矩阵
    X = np.array([featurize(r['area_m2'], r['qty'], r['flute'], r['total_gram'],
                            r['has_lam'], r['is_export']) for r in rows])
    y = np.array([r['cost_per_m2'] for r in rows])

    print(f"\nX shape: {X.shape}, y shape: {y.shape}")
    print(f"y range: {y.min():.2f} ~ {y.max():.2f}  median: {float(np.median(y)):.2f}")

    # 5-fold CV: GBM vs flute-median
    print("\n" + "═" * 60)
    print("5-fold CV: GBM vs flute-median baseline")
    print("═" * 60)

    kf = KFold(n_splits=5, shuffle=True, random_state=42)
    gbm_preds, base_preds, acts = [], [], []
    for fold, (train_idx, test_idx) in enumerate(kf.split(X)):
        X_tr, X_te = X[train_idx], X[test_idx]
        y_tr, y_te = y[train_idx], y[test_idx]
        train_rows = [rows[i] for i in train_idx]
        test_rows = [rows[i] for i in test_idx]

        # GBM
        gbm = HistGradientBoostingRegressor(
            max_iter=100, max_depth=4, learning_rate=0.1,
            min_samples_leaf=3, random_state=42
        )
        gbm.fit(X_tr, y_tr)
        gp = gbm.predict(X_te)
        gbm_preds.extend(gp.tolist())

        # Baseline
        bp, ba = flute_median_baseline(train_rows, test_rows)
        base_preds.extend(bp)
        acts.extend(y_te.tolist())

    gbm_m = metrics(gbm_preds, acts)
    base_m = metrics(base_preds, acts)

    print(f"\n{'指标':<12}{'flute-median':>15}{'GBM':>15}{'改善':>15}")
    print('─' * 60)
    for k, label, lower_better in [('mae', 'MAE', True), ('mape', 'MAPE %', True),
                                    ('bias', 'Bias', None), ('r2', 'R²', False)]:
        bv, gv = base_m[k], gbm_m[k]
        diff = gv - bv
        if lower_better is None:
            arrow = '✅ 改善' if abs(gv) < abs(bv) else ('⚠️ 退化' if abs(gv) > abs(bv) else '➖')
        elif lower_better:
            arrow = '✅ 改善' if diff < 0 else ('⚠️ 退化' if diff > 0 else '➖')
        else:
            arrow = '✅ 改善' if diff > 0 else ('⚠️ 退化' if diff < 0 else '➖')
        print(f"{label:<12}{bv:>15.4f}{gv:>15.4f}{diff:>+15.4f} {arrow}")

    # 训练最终模型 (full data) + 保存
    os.makedirs(os.path.dirname(MODEL), exist_ok=True)
    gbm_final = HistGradientBoostingRegressor(
        max_iter=100, max_depth=4, learning_rate=0.1,
        min_samples_leaf=3, random_state=42
    )
    gbm_final.fit(X, y)
    with open(MODEL, 'wb') as f:
        pickle.dump({'model': gbm_final, 'feature_names': FEATURE_NAMES,
                     'flute_labels': FLUTE_LABELS}, f)
    print(f"\n✅ 模型保存: {MODEL}")
    print(f"   特征: {FEATURE_NAMES}")
    return gbm_m, base_m


if __name__ == '__main__':
    main()
