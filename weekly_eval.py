#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════╗
║  毅伟成本引擎 · Weekly Drift Monitor (Phase D4)         ║
║  System 7-piece-set 第 7 件: Drift Detection            ║
╚══════════════════════════════════════════════════════════╝

定时跑 eval_runner.py 的关键指标，对比上次 → 输出漂移告警。

用法:
  python3 weekly_eval.py              # 跑一次, 追加到历史
  python3 weekly_eval.py --history    # 查看历史趋势
  python3 weekly_eval.py --dry-run    # 跑但不写入历史

退出码:
  0 = 无漂移 (所有指标变化 < 5pp)
  1 = 漂移检测到 (任一指标变化 ≥ 5pp)
  2 = eval 失败 (数据缺失/语法错误等)

挂 cron 示例 (每周一 09:00):
  0 9 * * 1  cd /path/to/yiwei-cost-engine && python3 weekly_eval.py >> logs/weekly.log 2>&1

GitHub Actions 示例:
  schedule: cron: '0 1 * * 1'  # UTC 周一 01:00 = HK 周一 09:00
  run: python3 weekly_eval.py
"""
import os
import sys
import json
from datetime import datetime
from collections import defaultdict
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
HISTORY = os.path.join(HERE, 'data', 'eval_history.jsonl')
DRIFT_THRESHOLD_PP = 5.0  # 单指标漂移阈值 (pp)

# 导入 eval 函数
sys.path.insert(0, HERE)
from eval_runner import (
    load_xls_ground_truth,
    predict_cost_full,
    calculate_metrics,
)


def run_eval():
    """跑完整 eval, 返回关键指标 dict"""
    csv_path = os.path.join(HERE, 'data', 'ground_truth_22rows.csv')
    if not os.path.exists(csv_path):
        return None, f"❌ ground truth csv 不存在: {csv_path}"

    rows = load_xls_ground_truth(csv_path)
    params = {'tier': 'vip'}

    # 整体
    cost_preds, cost_acts = [], []
    contract_preds, contract_acts = [], []
    # 按 flute 分层
    by_flute = defaultdict(lambda: {'preds': [], 'acts': []})

    for r in rows:
        if not r.get('area_m2'):
            continue
        cost_p, price_p, _ = predict_cost_full(r, params)
        if r.get('total_cost'):
            cost_preds.append(cost_p)
            cost_acts.append(r['total_cost'])
        if r.get('contract_price'):
            contract_preds.append(price_p)
            contract_acts.append(r['contract_price'])
            by_flute[r['flute']]['preds'].append(price_p)
            by_flute[r['flute']]['acts'].append(r['contract_price'])

    cost_m = calculate_metrics(cost_preds, cost_acts) if cost_preds else None
    contract_m = calculate_metrics(contract_preds, contract_acts) if contract_preds else None
    flute_m = {ft: calculate_metrics(d['preds'], d['acts'])
               for ft, d in by_flute.items() if d['preds']}

    return {
        'ts': datetime.now().isoformat(timespec='seconds'),
        'n_rows': len(rows),
        'n_cost': cost_m['n'] if cost_m else 0,
        'n_contract': contract_m['n'] if contract_m else 0,
        'cost': cost_m,
        'contract': contract_m,
        'by_flute': flute_m,
    }, None


def load_history():
    """加载历史 JSONL"""
    if not os.path.exists(HISTORY):
        return []
    out = []
    with open(HISTORY, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return out


def append_history(entry):
    os.makedirs(os.path.dirname(HISTORY), exist_ok=True)
    with open(HISTORY, 'a') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')


def fmt_diff(new, old, key):
    """格式化指标变化"""
    if not (new and old):
        return '-'
    nv = new.get(key)
    ov = old.get(key)
    if nv is None or ov is None:
        return '-'
    diff = nv - ov
    arrow = '🔴' if abs(diff) >= DRIFT_THRESHOLD_PP else ('🟢' if diff <= 0 else '🟡')
    return f"{nv:.1f} ({diff:+.1f}pp) {arrow}"


def detect_drift(new, old):
    """检测漂移: 任一关键指标变化 ≥ 阈值 → True"""
    if not old:
        return False, []
    alerts = []
    for label, new_m, old_m in [
        ('整体 contract MAPE', new.get('contract'), old.get('contract')),
        ('整体 cost MAPE', new.get('cost'), old.get('cost')),
    ]:
        if new_m and old_m:
            diff = new_m['mape'] - old_m['mape']
            if abs(diff) >= DRIFT_THRESHOLD_PP:
                alerts.append(f"{label}: {old_m['mape']:.1f}% → {new_m['mape']:.1f}% ({diff:+.1f}pp)")
    # flute breakdown
    new_fl = new.get('by_flute', {})
    old_fl = old.get('by_flute', {})
    for ft in set(new_fl) & set(old_fl):
        diff = new_fl[ft]['mape'] - old_fl[ft]['mape']
        if abs(diff) >= DRIFT_THRESHOLD_PP:
            alerts.append(f"{ft} 瓦 MAPE: {old_fl[ft]['mape']:.1f}% → {new_fl[ft]['mape']:.1f}% ({diff:+.1f}pp)")
    return len(alerts) > 0, alerts


def print_report(new, old=None):
    print("╔════════════════════════════════════════════════════╗")
    print("║  毅伟成本引擎 · Weekly Drift Monitor              ║")
    print(f"║  {new['ts']}                          ║")
    print("╚════════════════════════════════════════════════════╝")
    print(f"\nGround truth: {new['n_rows']} rows ({new['n_contract']} 含合同价)\n")

    if old:
        print(f"对比上次: {old['ts']}\n")
        print(f"{'指标':<28}{'本次':>12}{'上次':>12}{'变化':>14}")
        print('─' * 70)
        if new['contract'] and old['contract']:
            print(f"{'整体 contract MAPE %':<28}{new['contract']['mape']:>11.1f}%{old['contract']['mape']:>11.1f}%{fmt_diff(new['contract'], old['contract'], 'mape'):>17}")
            print(f"{'整体 contract Bias':<28}{new['contract']['bias']:>11.3f} {old['contract']['bias']:>11.3f} {fmt_diff(new['contract'], old['contract'], 'bias'):>17}")
        if new['cost'] and old['cost']:
            print(f"{'整体 cost MAPE %':<28}{new['cost']['mape']:>11.1f}%{old['cost']['mape']:>11.1f}%{fmt_diff(new['cost'], old['cost'], 'mape'):>17}")
        for ft in sorted(set(new.get('by_flute', {})) | set(old.get('by_flute', {}))):
            n_m = new.get('by_flute', {}).get(ft)
            o_m = old.get('by_flute', {}).get(ft)
            if n_m and o_m:
                print(f"{ft + ' 瓦 contract MAPE %':<28}{n_m['mape']:>11.1f}%{o_m['mape']:>11.1f}%{fmt_diff(n_m, o_m, 'mape'):>17}")
    else:
        print("(首次跑, 无历史对比)\n")
        if new['contract']:
            m = new['contract']
            rating = '🟢 工业级' if m['mape'] < 10 else ('🟢 可用' if m['mape'] < 15 else ('🟡 一般' if m['mape'] < 25 else '🔴 需改善'))
            print(f"  整体 contract: MAPE {m['mape']:.1f}% / Bias {m['bias']:+.3f} / R² {m['r2']:.4f}  {rating}")
        if new['cost']:
            m = new['cost']
            print(f"  整体 cost    : MAPE {m['mape']:.1f}% / Bias {m['bias']:+.3f}")
        for ft, m in sorted(new.get('by_flute', {}).items()):
            print(f"  {ft} 瓦 (n={m['n']}): contract MAPE {m['mape']:.1f}%")
    print()


def print_history():
    hist = load_history()
    if not hist:
        print("历史为空, 先跑一次 weekly_eval.py")
        return
    print(f"\n历史 ({len(hist)} 条):\n")
    print(f"{'时间戳':<22}{'contract MAPE':>15}{'EB':>10}{'BC':>10}")
    print('─' * 60)
    for e in hist[-20:]:
        c = e.get('contract')
        fl = e.get('by_flute', {})
        eb = fl.get('EB', {}).get('mape')
        bc = fl.get('BC', {}).get('mape')
        print(f"{e['ts'][:19]:<22}{(c['mape'] if c else 0):>14.1f}%{(eb or 0):>9.1f}%{(bc or 0):>9.1f}%")
    print()


def main():
    if '--history' in sys.argv:
        print_history()
        return 0

    dry_run = '--dry-run' in sys.argv

    new, err = run_eval()
    if err:
        print(err, file=sys.stderr)
        return 2

    hist = load_history()
    old = hist[-1] if hist else None
    print_report(new, old)

    drifted, alerts = detect_drift(new, old)
    if drifted:
        print(f"🔴 漂移告警 (阈值 ±{DRIFT_THRESHOLD_PP}pp):")
        for a in alerts:
            print(f"  - {a}")
        print()
    else:
        print(f"🟢 无漂移 (所有关键指标变化 < ±{DRIFT_THRESHOLD_PP}pp)\n")

    if not dry_run:
        append_history(new)
        print(f"✅ 已追加到历史: {HISTORY}")

    return 1 if drifted else 0


if __name__ == '__main__':
    sys.exit(main())
