#!/usr/bin/env python3
"""一键生成面试演示数据库（脱敏真实数据）

用法:
  1. cp anonymize_mapping.example.json anonymize_mapping.json
  2. 编辑 anonymize_mapping.json 填入真实公司名 → 脱敏标签 映射
  3. python3 anonymize.py
  输出: data/demo.db (可直接用 app.py 加载演示)

脱敏覆盖范围：
- client / product / board_material / notes / supplier 字段
- 使用四层映射：CLIENT_MAP / SUPPLIER_MAP / BRAND_MAP / SENSITIVE_TOKENS（兜底 hash）

⚠️ 隐私要求：
- anonymize_mapping.json 含真实公司名，已在 .gitignore 中
- 提交到公开仓库前请运行 `python3 anonymize.py --verify` 自动校验残留
"""
import sqlite3, random, os, re, hashlib, json, sys

HERE = os.path.dirname(__file__)
SRC = os.path.join(HERE, "data", "process_sheets.db")
DST = os.path.join(HERE, "data", "demo.db")
MAPPING_FILE = os.path.join(HERE, "anonymize_mapping.json")

def load_mapping():
    """从私有 JSON 加载映射表，文件不存在则给清晰提示"""
    if not os.path.exists(MAPPING_FILE):
        print(f"❌ 映射文件不存在: {MAPPING_FILE}")
        print(f"   请运行: cp anonymize_mapping.example.json anonymize_mapping.json")
        print(f"   然后填入真实公司名 → 脱敏标签 映射")
        sys.exit(1)
    with open(MAPPING_FILE, 'r', encoding='utf-8') as f:
        m = json.load(f)
    return (
        m.get('CLIENT_MAP', {}),
        m.get('SUPPLIER_MAP', {}),
        m.get('BRAND_MAP', {}),
        tuple(t for t in m.get('SENSITIVE_TOKENS', []) if not t.startswith('_')),
    )

CLIENT_MAP, SUPPLIER_MAP, BRAND_MAP, SENSITIVE_TOKENS = load_mapping()

def _hash_token(s, prefix='X'):
    """fallback：兜底 hash 化敏感 token"""
    h = hashlib.md5(s.encode('utf-8')).hexdigest()[:4].upper()
    return f"{prefix}-{h}"

def anonymize_client(name):
    if not name: return None
    name = str(name).strip()
    if name in CLIENT_MAP: return CLIENT_MAP[name]
    for k in sorted(CLIENT_MAP.keys(), key=len, reverse=True):
        if k in name:
            return CLIENT_MAP[k]
    for tok in SENSITIVE_TOKENS:
        if tok in name:
            return _hash_token(name, 'C')
    return name

def anonymize_product(name):
    """全字段脱敏 product 字段：CLIENT_MAP + BRAND_MAP + 订单代码 + 兜底"""
    if not name: return None
    name = str(name).strip()
    for k in sorted(CLIENT_MAP.keys(), key=len, reverse=True):
        if k in name:
            name = name.replace(k, CLIENT_MAP[k])
    for k in sorted(BRAND_MAP.keys(), key=len, reverse=True):
        if k in name:
            name = name.replace(k, BRAND_MAP[k])
    name = re.sub(r'X\d{4,}', lambda m: f"P-{int(m.group()[1:])%1000:03d}", name)
    for tok in SENSITIVE_TOKENS:
        if tok in name:
            name = name.replace(tok, _hash_token(tok, 'T'))
    return name

def anonymize_material(mat):
    if not mat: return None
    mat = str(mat)
    for s in sorted(SUPPLIER_MAP.keys(), key=len, reverse=True):
        mat = mat.replace(s, SUPPLIER_MAP[s])
    for b in sorted(BRAND_MAP.keys(), key=len, reverse=True):
        mat = mat.replace(b, BRAND_MAP[b])
    for tok in SENSITIVE_TOKENS:
        if tok in mat:
            mat = mat.replace(tok, _hash_token(tok, 'M'))
    return mat

def anonymize_notes(notes):
    if not notes: return None
    notes = str(notes)
    for k in sorted(CLIENT_MAP.keys(), key=len, reverse=True):
        notes = notes.replace(k, CLIENT_MAP[k])
    for s in sorted(SUPPLIER_MAP.keys(), key=len, reverse=True):
        notes = notes.replace(s, SUPPLIER_MAP[s])
    for b in sorted(BRAND_MAP.keys(), key=len, reverse=True):
        notes = notes.replace(b, BRAND_MAP[b])
    for tok in SENSITIVE_TOKENS:
        if tok in notes:
            notes = notes.replace(tok, _hash_token(tok, 'N'))
    return notes

def jitter_price(price, pct=0.05):
    """Add ±5% random noise to protect exact pricing"""
    if price is None: return None
    try:
        p = float(price)
        return round(p * (1 + random.uniform(-pct, pct)), 2)
    except:
        return price

def verify(db_path=DST):
    """校验脱敏后的 db 是否还有敏感 token 残留"""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    total = 0
    for tok in SENSITIVE_TOKENS:
        for col in ('client', 'product', 'board_material', 'notes'):
            try:
                cnt = cur.execute(
                    f"SELECT COUNT(*) FROM process_sheets WHERE {col} LIKE ?",
                    (f'%{tok}%',)
                ).fetchone()[0]
                if cnt > 0:
                    print(f"  🔴 残留 token '{tok}' in {col}: {cnt} 处")
                    total += cnt
            except Exception:
                pass
    conn.close()
    if total == 0:
        print(f"✅ 校验通过: 0 敏感 token 残留 in {db_path}")
        return True
    else:
        print(f"🔴 校验失败: {total} 处敏感 token 残留")
        return False

def main():
    if '--verify' in sys.argv:
        sys.exit(0 if verify() else 1)

    print("🔒 生成脱敏演示数据库...")

    src = sqlite3.connect(SRC)
    dst = sqlite3.connect(DST)

    df = src.execute("SELECT * FROM process_sheets").fetchall()
    cols = [row[1] for row in src.execute("PRAGMA table_info(process_sheets)")]

    dst.execute("DROP TABLE IF EXISTS process_sheets")
    src_schema = src.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='process_sheets'").fetchone()[0]
    dst.execute(src_schema)

    anonymized_client = 0
    anonymized_product = 0
    total = 0
    for row in df:
        row = list(row)
        d = dict(zip(cols, row))
        total += 1

        if d.get('client'):
            old = d['client']
            d['client'] = anonymize_client(d['client'])
            if old != d['client']: anonymized_client += 1

        if d.get('product'):
            old = d['product']
            d['product'] = anonymize_product(d['product'])
            if old != d['product']: anonymized_product += 1

        if d.get('board_material'):
            d['board_material'] = anonymize_material(d['board_material'])

        if d.get('notes'):
            d['notes'] = anonymize_notes(d['notes'])

        vals = [d.get(c) for c in cols]
        dst.execute(f"INSERT INTO process_sheets VALUES ({','.join(['?']*len(cols))})", vals)

    try:
        pc = src.execute("SELECT * FROM precheck_costs").fetchall()
        if pc:
            pc_cols = [row[1] for row in src.execute("PRAGMA table_info(precheck_costs)")]
            src_schema2 = src.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='precheck_costs'").fetchone()[0]
            dst.execute(f"DROP TABLE IF EXISTS precheck_costs")
            dst.execute(src_schema2)

            for row in pc:
                row = list(row)
                d = dict(zip(pc_cols, row))
                if d.get('product'):
                    d['product'] = anonymize_product(d['product'])
                if d.get('material'):
                    d['material'] = anonymize_material(d['material'])
                if d.get('unit_cost'):
                    d['unit_cost'] = jitter_price(d['unit_cost'], 0.03)
                if d.get('contract_price'):
                    d['contract_price'] = jitter_price(d['contract_price'], 0.03)

                vals = [d.get(c) for c in pc_cols]
                dst.execute(f"INSERT INTO precheck_costs VALUES ({','.join(['?']*len(pc_cols))})", vals)
    except Exception as e:
        print(f"⚠️  precheck_costs 处理跳过: {e}")

    dst.commit()
    src.close()
    dst.close()

    print(f"✅ 脱敏完成: {total} 条 process_sheets 记录 → {DST}")
    print(f"🔒 客户名脱敏: {anonymized_client} / {total}")
    print(f"🔒 产品名脱敏: {anonymized_product} / {total}")
    print(f"📊 成本数据 ±3% 随机抖动（precheck_costs）")
    print()
    print("--- 校验 ---")
    verify()

if __name__ == '__main__':
    main()
