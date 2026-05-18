#!/usr/bin/env python3
"""Anonymize ground_truth_22rows.csv → data/ground_truth_22rows.csv

复用 anonymize.py 的脱敏函数（CLIENT_MAP / SUPPLIER_MAP / BRAND_MAP / SENSITIVE_TOKENS）。
策略: 只脱敏名称字段, 保持 cost/contract 数字精确 (让 EVAL_REPORT §7 17.1% MAPE 在
GitHub 公开 reproduce). 22 行预核单数据时效性弱 (2026 上半年), 商业敏感度低.

用法:
  python3 anonymize_csv.py [输入 csv] [输出 csv]
  默认: /tmp/yiwei_eval/ground_truth_22rows.csv → data/ground_truth_22rows.csv

验证:
  python3 anonymize_csv.py --verify
"""
import csv
import sys
import os
from anonymize import (
    anonymize_client, anonymize_product, anonymize_material, anonymize_notes,
    SENSITIVE_TOKENS,
)

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SRC = '/tmp/yiwei_eval/ground_truth_22rows.csv'
DEFAULT_DST = os.path.join(HERE, 'data', 'ground_truth_22rows.csv')


def anonymize_file_name(fname):
    """文件名也走脱敏 (.xls 文件名含产品 / 客户线索)"""
    if not fname:
        return fname
    f = str(fname)
    # 走 CLIENT_MAP + BRAND_MAP
    from anonymize import CLIENT_MAP, BRAND_MAP
    for k in sorted(CLIENT_MAP.keys(), key=len, reverse=True):
        if k in f:
            f = f.replace(k, CLIENT_MAP[k])
    for k in sorted(BRAND_MAP.keys(), key=len, reverse=True):
        if k in f:
            f = f.replace(k, BRAND_MAP[k])
    # 兜底 token
    from anonymize import _hash_token
    for tok in SENSITIVE_TOKENS:
        if tok in f:
            f = f.replace(tok, _hash_token(tok, 'F'))
    return f


def verify_csv(csv_path):
    """校验 csv 0 敏感 token 残留"""
    if not os.path.exists(csv_path):
        print(f"❌ csv 不存在: {csv_path}")
        return False
    total = 0
    with open(csv_path, 'r', encoding='utf-8') as f:
        content = f.read()
    for tok in SENSITIVE_TOKENS:
        cnt = content.count(tok)
        if cnt > 0:
            print(f"  🔴 残留 token '{tok}': {cnt} 处")
            total += cnt
    if total == 0:
        print(f"✅ 校验通过: 0 敏感 token 残留 in {csv_path}")
        return True
    else:
        print(f"🔴 校验失败: {total} 处残留")
        return False


def main():
    if '--verify' in sys.argv:
        sys.exit(0 if verify_csv(DEFAULT_DST) else 1)

    src = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SRC
    dst = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_DST

    if not os.path.exists(src):
        print(f"❌ src csv 不存在: {src}")
        sys.exit(1)

    os.makedirs(os.path.dirname(dst), exist_ok=True)

    print(f"🔒 Anonymize {src} → {dst}")

    with open(src, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames

    n_client, n_product, n_material, n_file = 0, 0, 0, 0
    for r in rows:
        if r.get('file'):
            old = r['file']
            r['file'] = anonymize_file_name(r['file'])
            if r['file'] != old:
                n_file += 1
        if r.get('client'):
            old = r['client']
            r['client'] = anonymize_client(r['client']) or ''
            if r['client'] != old:
                n_client += 1
        if r.get('product'):
            old = r['product']
            r['product'] = anonymize_product(r['product']) or ''
            if r['product'] != old:
                n_product += 1
        if r.get('material'):
            old = r['material']
            r['material'] = anonymize_material(r['material']) or ''
            if r['material'] != old:
                n_material += 1
        if r.get('note'):
            r['note'] = anonymize_notes(r['note']) or ''

    with open(dst, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    print(f"✅ Anonymized: {len(rows)} 行")
    print(f"   client 脱敏: {n_client}")
    print(f"   product 脱敏: {n_product}")
    print(f"   material 脱敏: {n_material}")
    print(f"   file 脱敏: {n_file}")
    print(f"   cost/contract 数字: 保持精确（让 EVAL_REPORT 17.1% MAPE 可 reproduce）")
    print()
    print("--- 校验 ---")
    verify_csv(dst)


if __name__ == '__main__':
    main()
