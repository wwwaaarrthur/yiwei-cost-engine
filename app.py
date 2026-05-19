#!/usr/bin/env python3
"""毅伟包装 · 纸箱成本AI智能核算系统 v3.0"""
import os
import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import re, numpy as np

# DB 路径策略：本地有生产数据库则用真实数据；公开部署（Streamlit Cloud）fallback 到 anonymized demo.db
# 使用绝对路径避免 Streamlit Cloud 工作目录不确定导致 sqlite3 静默创建空文件
_HERE = os.path.dirname(os.path.abspath(__file__))
_DB_PROD = os.path.join(_HERE, "data", "process_sheets.db")
_DB_DEMO = os.path.join(_HERE, "data", "demo.db")
DB = _DB_PROD if os.path.exists(_DB_PROD) else _DB_DEMO

# 提前校验：若 DB 文件确实不存在则报清晰错误（含 debug 信息），避免 sqlite3 创建空文件后才在 pandas 报错
if not os.path.exists(DB):
    raise FileNotFoundError(
        f"Database file not found: {DB}\n"
        f"  HERE={_HERE}\n"
        f"  CWD={os.getcwd()}\n"
        f"  DB_PROD exists: {os.path.exists(_DB_PROD)}\n"
        f"  DB_DEMO exists: {os.path.exists(_DB_DEMO)}\n"
        f"Hint: ensure data/demo.db is committed (it should NOT be in .gitignore)"
    )

st.set_page_config(page_title="毅伟包装", page_icon="📦", layout="wide")

# Custom CSS (轻量美化，零依赖)
st.markdown("""
<style>
    /* 全局字体 */
    html, body, [class*="css"] { font-family: 'SF Pro Display', 'PingFang SC', sans-serif; }
    /* 主色调覆盖 */
    .stButton > button {
        border-radius: 8px; font-weight: 600; transition: all 0.2s;
    }
    .stButton > button:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(27,94,138,0.25); }
    /* 卡片式容器 */
    [data-testid="stMetric"] {
        background: linear-gradient(135deg, #f8f9fa, #e9ecef);
        border-radius: 12px; padding: 16px; border: 1px solid #dee2e6;
    }
    /* 表格美化 */
    [data-testid="stDataFrame"] { border-radius: 8px; overflow: hidden; }
    /* 顶栏标题 */
    .main-header { font-size: 2rem; font-weight: 700; color: #1B5E8A; margin-bottom: 0.5rem; }
</style>
""", unsafe_allow_html=True)
st.markdown("<meta name='google' content='notranslate'>", unsafe_allow_html=True)

# ====== Data Loading ======
@st.cache_resource
def load_all():
    conn = sqlite3.connect(DB)
    df = pd.read_sql("SELECT * FROM process_sheets WHERE error IS NULL", conn)
    try:
        cost_df = pd.read_sql("SELECT * FROM precheck_costs", conn)
    except:
        cost_df = pd.DataFrame()
    conn.close()
    
    def n_flute(f):
        if not f: return '未知'
        f = str(f).strip()
        if 'EB' in f and 'BC' not in f and 'AB' not in f: return 'EB'
        if 'BC' in f or 'BC瓦' in f: return 'BC'
        if 'AB' in f or 'AB瓦' in f: return 'AB'
        if '单C' in f: return '单C瓦'
        if '单B' in f: return '单B瓦'
        if '单E' in f: return '单E瓦'
        return f
    df['flute_normalized'] = df['flute_type'].apply(n_flute)
    
    # Clean messy dates (date ranges, missing days, typos, Chinese chars)
    def fix_date(d):
        if not isinstance(d, str): return d
        d = d.strip()
        if not d or d.startswith('制单'): return None
        d = d.replace('／', '/').replace('一', '-').replace(' ', '')
        # Handle typos like 20235 → 2025, 20223 → 2023
        d = re.sub(r'^(\d{4})\d-(\d{2})', r'\1-\2', d)
        # Date range → take first date
        if '/' in d and not re.search(r'\d{2}/\d{2}/\d{4}', d):
            d = d.split('/')[0]
        # Missing day → add "-01"
        if re.match(r'^\d{4}-\d{2}$', d):
            d = d + '-01'
        # Missing month+day → add "-01-01"
        if re.match(r'^\d{4}-$', d):
            d = d + '01-01'
        return d
    df['order_date'] = df['order_date'].apply(fix_date)
    df['order_date_parsed'] = pd.to_datetime(df['order_date'], errors='coerce')
    df['year'] = df['order_date_parsed'].dt.year
    df['month'] = df['order_date_parsed'].dt.month
    df['box_volume'] = df['box_l'] * df['box_w'] * df['box_h'] / 1_000_000
    df['board_area'] = df['board_w'] * df['board_h'] / 1_000_000
    g = lambda m: sum(int(x) for x in re.findall(r'(\d+)\s*g', str(m))) if m and isinstance(m, str) else 0
    df['total_gram'] = df['board_material'].apply(g)
    
    if len(cost_df) > 0:
        cost_df['board_area'] = cost_df['size_w'] * cost_df['size_h'] / 1_000_000
        cost_df['cost_per_m2'] = cost_df['unit_cost'] / cost_df['board_area']
        cost_df['total_gram'] = cost_df['material'].apply(g)
        def df2(m):
            m = str(m)
            has_b = bool(re.search(r'\d+gB', m))
            has_e = bool(re.search(r'\d+gE', m))
            has_c = bool(re.search(r'\d+gC', m))
            if has_b and has_e: return 'EB'
            if has_b and has_c: return 'BC'
            if has_e and not has_b: return '单E瓦'
            if has_b and not has_e: return '单B瓦'
            return 'EB'
        cost_df['flute_type'] = cost_df['material'].apply(df2)
    
    return df, cost_df

df, cost_df = load_all()

# Init session state defaults (before any widget creation)
for k, v in [('ql', 370), ('qw', 280), ('qh', 255), ('qq', 10000)]:
    if k not in st.session_state:
        st.session_state[k] = v

# Baselines
fcb = {'EB': 1.5, 'BC': 2.0, 'AB': 2.2, '单C瓦': 1.5, '单B瓦': 1.3, '单E瓦': 1.1, 'EE': 1.4}
if len(cost_df) > 0:
    for ft in cost_df['flute_type'].unique():
        s = cost_df[cost_df['flute_type'] == ft]
        if len(s) > 0: fcb[ft] = float(s['cost_per_m2'].median())

# Gram model
gm = None
if len(cost_df) > 0 and cost_df['total_gram'].sum() > 0:
    gd = cost_df[cost_df['total_gram'] > 0]
    if len(gd) >= 3:
        try:
            gm = np.polyfit(gd['total_gram'].values, gd['cost_per_m2'].values, 1)
        except: pass

# Client tier
def ctier(c):
    if not c: return 'small'
    c = str(c).strip()
    # VIP/Medium/Small 客户分层（基于 anonymized 客户标签）
    if c in ['大型农化客户A', '大型农化客户B', '大型农化客户A-HK']: return 'vip'
    if any(k in c for k in ['制造企业客户', '物流企业客户', '外贸企业客户', '连锁零售客户', '香港企业客户']): return 'medium'
    return 'small'

def qty_margin_base(qty):
    # qty 阶梯基线毛利 (22 行 .xls ground truth 实测中位)
    if qty <= 500: return 0.30
    if qty <= 2000: return 0.22
    if qty <= 5000: return 0.12
    if qty <= 20000: return 0.08
    return 0.06

def cmargin(t, qty=None, is_export=False):
    if qty is None:
        return {'vip': 0.10, 'medium': 0.14, 'small': 0.18}[t]
    adj = {'vip': -0.02, 'medium': 0.0, 'small': +0.03}[t]
    export_adj = 0.04 if is_export else 0.0  # 出口加 4pp (4L 实测 14.8% vs 内销 8.5%)
    return max(0.03, qty_margin_base(qty) + adj + export_adj)

# 印刷成本表 (基于硅酮硬管 4 数量段实测 + 单色/多色案例)
# (setup_fee, unit_var): print_cost = max(setup/qty, unit_var)
PRINT_TABLE = {
    1: (150, 0.18),    # 单色 (中域740 / 新安8600 / 590mL 实测 0.21)
    2: (300, 0.21),
    3: (500, 0.30),
    4: (900, 0.45),    # 4L 外贸彩印 实测 0.35-0.44
    5: (1250, 0.63),   # 5 色+: 硅酮硬管 实测 K=1250, v=0.63
}

def print_cost_fn(colors, qty):
    setup, unit_var = PRINT_TABLE.get(colors, PRINT_TABLE[2])
    return max(setup / qty, unit_var)

# 制费默认值 (实测中位)
OTHER_COST_DEFAULT = {'内销': 0.82, '出口': 1.07}

# Phase D5: 板材切割方式 (基于 2039 单 demo.db 反推)
# 实测 tab_w 中位 40mm (与默认一致), flap_w 中位 12mm (vs 旧默认 20mm 偏高)
# 占比 (n=2039): 双拼×双拼 46.5% / 单件 33% / 四联板 15.5% / 倒单页 5%
BOARD_CUTTING_MODES = {
    '双拼×双拼 (RSC 标准 46.5%)': lambda l, w, h, tab, flap: (2*l + 2*w + tab, 2*h + 2*w + flap),
    '双拼×单拼 (四联板 15.5%)':   lambda l, w, h, tab, flap: (2*l + 2*w + tab, h + w + flap),
    '单拼×双拼 (倒单页 5%)':      lambda l, w, h, tab, flap: (l + w + tab, 2*h + 2*w + flap),
    '单拼×单拼 (单件板 33%)':     lambda l, w, h, tab, flap: (l + w + tab, h + w + flap),
}

CN = {
    'client': '客户', 'product': '产品', 'order_qty': '数量', 'order_date': '日期',
    'box_l': '长', 'box_w': '宽', 'box_h': '高', 'flute_normalized': '瓦型',
    'board_material': '纸板材质', 'paper_spec': '面纸', 'total_gram': '克重',
    'lamination': '覆膜', 'print_style': '印刷', 'board_area': '纸板面积',
    'box_volume': '箱体积', 'cost_per_m2': '¥/m²',
}
def cn(df, cols):
    df = df.rename(columns={c: CN.get(c, c) for c in df.columns})
    return df[[CN.get(c, c) for c in cols if CN.get(c, c) in df.columns]]

# ====== Tabs ======
tab1, tab2, tab3, tab4 = st.tabs(["🏠 首页报价", "🔍 订单查找", "⚙️ 高级分析", "🤖 AI 咨询师"])

# ========================
# TAB 1: 快速报价
# ========================
with tab1:
    st.title("📦 纸箱快速报价")
    st.caption("输入尺寸 → 一键出价")
    
    left, right = st.columns([5, 3])
    with left:
        c1, c2 = st.columns(2)
        with c1:
            l = st.number_input("箱长 L (mm)", 100, 2000, 370, key="ql")
            w = st.number_input("箱宽 W (mm)", 100, 2000, 280, key="qw")
            h = st.number_input("箱高 H (mm)", 50, 2000, 255, key="qh")
        with c2:
            qty = st.number_input("数量 (只)", 100, 50000, 10000, 500, key="qq")
            ft = st.selectbox("瓦型", ['EB','BC','AB','单C瓦','单B瓦','单E瓦','EE'], key="qf")
            ct_label = st.selectbox("客户类型", ['大客户', '中等客户', '小客户/农户'], key="qc")
            order_type = st.selectbox("订单类型", ['内销', '出口'], key="qot",
                                       help="出口: 制费 1.07/只 + 毛利 +4pp (4L 实测 14.8%); 内销: 0.82/只")
            cutting_mode = st.selectbox(
                "切割方式", list(BOARD_CUTTING_MODES.keys()), index=0, key="qcm",
                help="基于 2039 单 demo.db 反推: 46.5% 双拼×双拼 (主力 1L*12瓶 RSC)/33% 单件/15.5% 四联板/5% 倒单页. 选错会让板面积错 60-290%"
            )
            print_colors = st.selectbox("印刷色数", [1, 2, 3, 4, 5], index=1, key="qpc",
                                         help="数量摊销: 印刷开机费/qty + 单只变动 (实测硅酮 5色 K=1250)")
            lam = st.checkbox("覆膜", False, key="qlm")
            pad = st.checkbox("垫片", False, key="qpd")
        
        with st.expander("📋 常用模板", expanded=False):
            tc = st.columns(5)
            templates = {
                "1L×12瓶出口": (370, 280, 255, 10000, "EB", True),
                "4L×6壶外贸": (400, 300, 350, 5000, "BC", True),
                "5kg桔子箱": (370, 180, 190, 4000, "EB", True),
                "250g农药袋": (300, 200, 150, 5000, "EB", False),
                "10kg椪柑箱": (400, 250, 230, 3000, "BC", True),
            }
            def apply_template(params):
                st.session_state['ql'], st.session_state['qw'], st.session_state['qh'] = params[0], params[1], params[2]
                st.session_state['qq'] = params[3]
                st.session_state['qf'] = params[4]
                st.session_state['qlm'] = params[5]
            for i, (name, params) in enumerate(templates.items()):
                tc[i % 5].button(name, key=f"tpl_{i}", on_click=apply_template, args=(params,))
        
        quote_btn = st.button("💰 开始报价", type="primary", width="stretch")
    
    with right:
        with st.expander("💰 实时价格", expanded=False):
            st.caption("改后立即生效")
            rc1, rc2 = st.columns(2)
            flutes = ['EB','BC','AB','单C瓦','单B瓦','单E瓦','EE']
            for i, ft_name in enumerate(flutes):
                col = rc1 if i % 2 == 0 else rc2
                new_val = col.number_input(
                    f"{ft_name} ¥/m²", 0.5, 15.0, float(fcb.get(ft_name, 1.5)), 0.05,
                    key=f"price_{ft_name}"
                )
                fcb[ft_name] = new_val
            st.divider()
            rc3, rc4 = st.columns(2)
            with rc3:
                global_paper_gsm = st.number_input(
                    "白板克重 g/m²", 100, 500, 250, 10, key="global_paper_gsm",
                    help="实测主流 250g 白板 (22 行 ground truth)"
                )
            with rc4:
                global_paper_per_tonne = st.number_input(
                    "白板 ¥/吨", 2000, 6000, 3410, 50, key="global_paper_per_tonne",
                    help="实测 3360-3460 ¥/吨 (鲸鲨/华天等品牌)"
                )
            rc5, rc6 = st.columns(2)
            with rc5:
                global_lam = st.number_input("覆膜费 ¥/只", 0.0, 2.0, 0.25, 0.05, key="global_lam")
            with rc6:
                global_other = st.number_input(
                    "其他制费 ¥/只", 0.3, 2.0, 0.82, 0.05, key="global_other",
                    help="后勤工资+房租+税收+工艺工资+胶水+运费 (实测中位 0.82, 出口 1.07)"
                )
            # Phase D1: 白板 ¥/m² 从克重 × 吨价派生
            global_pp = (global_paper_gsm * global_paper_per_tonne) / 1_000_000
            st.caption(f"📐 白板 ¥/m² 派生: {global_paper_gsm}g/m² × ¥{global_paper_per_tonne}/吨 / 10⁶ = **¥{global_pp:.3f}/m²**")
    
    # Quote logic
    if quote_btn:
        tier_map = {'大客户': 'vip', '中等客户': 'medium', '小客户/农户': 'small'}
        tier = tier_map[ct_label]
        is_export = (order_type == '出口')
        margin = cmargin(tier, qty=qty, is_export=is_export)

        # Phase D5: 按切割方式分支 (基于 2039 单反推: tab_w=40, flap_w=12 实测中位)
        TAB_W = 40
        FLAP_W = 12  # 旧默认 20, 改为 2039 单实测中位 12
        cut_fn = BOARD_CUTTING_MODES[cutting_mode]
        blong, bshort = cut_fn(l, w, h, TAB_W, FLAP_W)
        barea = blong * bshort / 1_000_000
        paper_long = 2*l + 2*w + 50
        paper_short = h + w + 20
        parea = paper_long * paper_short / 1_000_000

        # Cost
        bp = fcb.get(ft, 1.5)
        pp = global_pp
        bc = barea * bp
        pc = parea * pp
        lc = global_lam if lam else 0
        pdc = 0.15 if pad else 0

        if qty <= 500: sf = 1.15
        elif qty <= 2000: sf = 1.05
        elif qty <= 5000: sf = 1.0
        elif qty <= 20000: sf = 0.93
        else: sf = 0.88

        # Phase C: 印刷按色数表 + 数量摊销
        print_cost = print_cost_fn(print_colors, qty)
        # Phase C: 制费按订单类型 (sidebar global_other 覆盖默认)
        other_default = OTHER_COST_DEFAULT[order_type]
        other_cost = global_other if abs(global_other - 0.82) > 0.01 else other_default
        base = bc + pc + lc + pdc + print_cost + other_cost
        cost = base * sf
        price = cost / (1 - margin)
        mp = margin * 100
        
        st.divider()
        st.subheader("💰 报价结果")

        # 亏损/低毛利告警 (基于 02-02 案例 -15.9% 教训)
        if mp < 5:
            st.error(f"🔴 当前毛利率 {mp:.1f}% < 5% — 接近亏损！历史教训: 2026-02-02 新安 19659 只大单实际 -15.9%, 单笔亏 ¥13,000")
        elif mp < 8:
            st.warning(f"🟡 毛利率 {mp:.1f}% 偏薄 — 建议复核同客户同尺寸历史均值")

        r1, r2, r3 = st.columns(3)
        with r1:
            st.metric("单只成本", f"¥{cost:.2f}")
        with r2:
            st.metric("建议报价", f"¥{price:.2f}", delta=f"毛利¥{price-cost:.2f} ({mp:.0f}%)")
        with r3:
            st.metric("纸板尺寸", f"{blong}×{bshort}mm")

        # Comparable prices
        with st.expander("📊 成本明细 & 其他客户报价", expanded=False):
            print_setup_fee, print_unit_var = PRINT_TABLE.get(print_colors, PRINT_TABLE[2])
            st.write(f"**成本构成**: 纸板¥{bc:.2f} + 面纸¥{pc:.2f} + 覆膜¥{lc:.2f} + 垫片¥{pdc:.2f} + 印刷¥{print_cost:.2f} + 制费¥{other_cost:.2f} = ¥{base:.2f} × {sf} = ¥{cost:.2f}")
            st.caption(f"切割方式: {cutting_mode} → 纸板 {blong}×{bshort}mm = {barea:.3f}m² (tab=40 flap=12 实测中位)")
            st.caption(f"印刷({print_colors}色): max(开机费¥{print_setup_fee}/qty {qty}, 单只变动¥{print_unit_var}) = ¥{print_cost:.2f}/只")
            st.caption(f"制费({order_type}): default ¥{other_default}/只" + (" (sidebar 覆盖)" if abs(global_other - 0.82) > 0.01 else ""))
            st.caption(f"qty={qty} 阶梯毛利基线: {qty_margin_base(qty)*100:.0f}% (≤500=30%/501-2k=22%/2k-5k=12%/5k-20k=8%/>20k=6%)" + (" + 出口 +4pp" if is_export else ""))
            st.write(f"**纸板**: {barea:.3f}m² × ¥{bp:.2f}/m² | **面纸**: {parea:.3f}m² × ¥{pp:.3f}/m² ({global_paper_gsm}g × ¥{global_paper_per_tonne}/吨)")
            tier_df = pd.DataFrame({
                '客户类型': ['大客户', '中等客户', '小客户/农户'],
                '毛利率': [f"{cmargin('vip', qty, is_export)*100:.0f}%", f"{cmargin('medium', qty, is_export)*100:.0f}%", f"{cmargin('small', qty, is_export)*100:.0f}%"],
                '报价': [f"¥{cost/(1-cmargin('vip', qty, is_export)):.2f}", f"¥{cost/(1-cmargin('medium', qty, is_export)):.2f}", f"¥{cost/(1-cmargin('small', qty, is_export)):.2f}"],
            })
            st.dataframe(tier_df, hide_index=True, width="stretch")
        
        # Similar orders
        with st.expander("📋 相似历史订单", expanded=False):
            sim = df[(df['flute_normalized']==ft)&(df['has_lamination']==(1 if lam else 0))].copy()
            if len(sim) == 0: sim = df.copy()
            sim['ds'] = abs(sim['box_l']*sim['box_w']*sim['box_h'] - l*w*h) / max(l*w*h, 1)
            sim = sim.nsmallest(5, 'ds')
            sc = ['client','product','order_qty','box_l','box_w','box_h','flute_normalized','board_material','order_date']
            st.dataframe(cn(sim[sc], sc), width="stretch")

# ========================
# TAB 2: 订单查找
# ========================
with tab2:
    st.header("🔍 订单查找")
    st.caption("输入产品名/客户名/材料关键词，快速找到历史订单")
    
    s1, s2 = st.columns([4, 1])
    with s1:
        search = st.text_input("搜索", placeholder="如: 1L*12瓶, 农化客户, 出口纸箱, P-817...", label_visibility="collapsed")
    with s2:
        search_btn = st.button("🔍 搜索", width="stretch")
    
    if search or search_btn:
        mask = (df['product'].str.contains(search, na=False, case=False) |
                df['client'].str.contains(search, na=False, case=False) |
                df['board_material'].str.contains(search, na=False, case=False))
        results = df[mask]
        total = len(results)
        
        # Pagination
        PER_PAGE = 50
        total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
        
        # Reset page on new search
        if 'search_page' not in st.session_state or st.session_state.get('last_search', '') != search:
            st.session_state['search_page'] = 1
            st.session_state['last_search'] = search
        
        page = st.session_state['search_page']
        start = (page - 1) * PER_PAGE
        end = min(start + PER_PAGE, total)
        
        # Top bar: count + page nav
        p1, p2, p3, p4 = st.columns([3, 1, 2, 1])
        with p1:
            st.write(f"找到 **{total}** 条")
        with p2:
            def prev():
                st.session_state['search_page'] = max(1, st.session_state['search_page'] - 1)
            st.button("◀ 上一页", disabled=(page <= 1), key="prev_page", on_click=prev)
        with p3:
            st.write(f"第 {page}/{total_pages} 页")
        with p4:
            def nxt():
                st.session_state['search_page'] = min(total_pages, st.session_state['search_page'] + 1)
            st.button("下一页 ▶", disabled=(page >= total_pages), key="next_page", on_click=nxt)
        
        display = results.iloc[start:end]
        sc = ['order_date','client','product','order_qty','box_l','box_w','box_h',
              'flute_normalized','total_gram','board_material','paper_spec']
        st.dataframe(cn(display[sc], sc), width="stretch", height=700)
        
        if st.button("📥 导出全部搜索结果"):
            csv = results.to_csv(index=False)
            st.download_button("下载 CSV", csv, f"search_{search[:20]}.csv", "text/csv")

# ========================
# TAB 3: 高级分析
# ========================
with tab3:
    st.header("⚙️ 高级功能")
    st.caption("数据分析、图表、纸板计算、价格调整")
    
    # Sub-tabs within advanced
    at0, at1, at2, at3, at4 = st.tabs(["📊 报价精度", "📊 数据统计", "📐 纸板计算", "💰 价格调整", "📋 数据浏览"])
    
    with at0:
        st.subheader("📊 报价模型精度评估")
        st.caption("用预核单实际成本验证报价基准的准确性 — 按瓦型分别评估")
        
        if len(cost_df) < 3:
            st.info("预核单数据不足（需≥3条），无法评估精度。添加更多预核单后自动启用。")
        else:
            eval_df = cost_df[cost_df['material'].notna() & (cost_df['material'] != '')].copy()
            if len(eval_df) == 0:
                st.info("预核单缺少材料数据")
            else:
                eval_df['board_area'] = eval_df['size_w'] * eval_df['size_h'] / 1_000_000
                eval_df['actual_cpm'] = eval_df['unit_cost'] / eval_df['board_area']
                
                def map_flute_eval(m):
                    m = str(m)
                    has_b = bool(re.search(r'\d+gB', m))
                    has_e = bool(re.search(r'\d+gE', m))
                    has_c = bool(re.search(r'\d+gC', m))
                    if has_b and has_e: return 'EB'
                    if has_b and has_c: return 'BC'
                    if has_e and not has_b: return '单E瓦'
                    if has_b and not has_e: return '单B瓦'
                    return 'EB'
                eval_df['flute_eval'] = eval_df['material'].apply(map_flute_eval)
                eval_df['estimated_cpm'] = eval_df['flute_eval'].map(lambda ft: fcb.get(ft, 1.5))
                eval_df['error'] = eval_df['actual_cpm'] - eval_df['estimated_cpm']
                eval_df['error_pct'] = (eval_df['error'] / eval_df['actual_cpm'] * 100)
                
                # Per-flute metrics
                st.write("### 按瓦型精度")
                flute_stats = []
                for ft in sorted(eval_df['flute_eval'].unique()):
                    s = eval_df[eval_df['flute_eval'] == ft]
                    n = len(s)
                    mape = s['error_pct'].abs().mean()
                    mae = s['error'].abs().mean()
                    n_ok = (s['error_pct'].abs() < 15).sum()
                    flute_stats.append({
                        '瓦型': ft, '样本': n, 'fcb基准': fcb.get(ft, 1.5),
                        '实际中位': s['actual_cpm'].median(),
                        '平均误差': mape, '¥误差': mae,
                        '±15%内': f"{n_ok}/{n}",
                        '评级': '🟢 可用' if mape < 15 else ('🟡 一般' if mape < 30 else '🔴 需改善')
                    })
                
                stats_df = pd.DataFrame(flute_stats)
                st.dataframe(
                    stats_df.style.format({'fcb基准': '¥{:.2f}', '实际中位': '¥{:.2f}', '平均误差': '{:.1f}%', '¥误差': '¥{:.2f}'}),
                    hide_index=True, width="stretch"
                )
                
                # Insight
                eb_s = eval_df[eval_df['flute_eval'] == 'EB']
                if len(eb_s) > 0 and eb_s['error_pct'].abs().mean() < 15:
                    st.success(f"EB 瓦（主力，{len(eb_s)}条）：精度 {eb_s['error_pct'].abs().mean():.1f}%，可用。克重越重成本越高，中位数能代表多数订单。")
                bc_s = eval_df[eval_df['flute_eval'] == 'BC']
                if len(bc_s) > 0 and bc_s['error_pct'].abs().mean() > 30:
                    st.warning(f"BC 瓦（{len(bc_s)}条）：误差偏大，因同一瓦型下材料质量跨度大（普通纸→高耐破），需更多样本后细分。")
                
                st.divider()
                
                # Scatter by flute
                fig = px.scatter(
                    eval_df, x='estimated_cpm', y='actual_cpm',
                    color='flute_eval',
                    text=eval_df['product'].str[:12],
                    title=f"报价基准 vs 实际成本（{len(eval_df)}条预核单，按瓦型着色）",
                    labels={'estimated_cpm': '报价基准 ¥/m²', 'actual_cpm': '实际成本 ¥/m²', 'flute_eval': '瓦型'}
                )
                mm = min(eval_df['estimated_cpm'].min(), eval_df['actual_cpm'].min())
                mx = max(eval_df['estimated_cpm'].max(), eval_df['actual_cpm'].max())
                fig.add_shape(type='line', x0=mm, y0=mm, x1=mx, y1=mx,
                             line=dict(dash='dash', color='gray'))
                st.plotly_chart(fig, width="stretch")
                st.caption("虚线=y=x：点越靠近虚线，报价基准越准。蓝色=EB（主力），红色=BC。")
                
                st.divider()
                st.write("**详细对比**")
                show_df = eval_df[['product','material','flute_eval','board_area','estimated_cpm','actual_cpm','error_pct']].copy()
                show_df.columns = ['产品','材料','瓦型','面积m²','基准¥/m²','实际¥/m²','误差%']
                show_df = show_df.round({'面积m²':4,'基准¥/m²':2,'实际¥/m²':2,'误差%':1})
                st.dataframe(show_df, hide_index=True, width="stretch")
    
    with at1:
        st.subheader("客户订单分布")
        cc = df['client'].value_counts().head(15)
        fig = px.bar(x=cc.index, y=cc.values, labels={'x':'客户','y':'订单数'})
        st.plotly_chart(fig, width="stretch")
        
        c1, c2 = st.columns(2)
        with c1:
            fc = df['flute_normalized'].value_counts()
            fig = px.pie(values=fc.values, names=fc.index, title="瓦型分布")
            st.plotly_chart(fig, width="stretch")
        with c2:
            if gm is not None and len(cost_df) > 0:
                gd = cost_df[cost_df['total_gram'] > 0]
                fig = px.scatter(gd, x='total_gram', y='cost_per_m2', color='flute_type',
                    trendline='ols', title="材料克重→成本",
                    labels={'total_gram':'克重(g/m²)','cost_per_m2':'¥/m²'})
                st.plotly_chart(fig, width="stretch")
    
    with at2:
        st.subheader("📐 纸板尺寸计算")
        st.caption("⚠️ 参考值：公式基于历史数据反推，非公司标准。以实际工艺单为准。")
        pc1, pc2 = st.columns(2)
        with pc1:
            cl = st.number_input("箱长 L", 50, 3000, 370, key="bcl")
            cw = st.number_input("箱宽 W", 50, 3000, 280, key="bcw")
            ch = st.number_input("箱高 H", 20, 3000, 255, key="bch")
        with pc2:
            cs = st.selectbox("成型方式", ['双拼','两页成型','单页成型'], key="bcs")
            tab_w = st.slider("搭接舌宽度", 25, 60, 40)
            flap_w = st.slider("摇盖余量", 10, 40, 20)
        
        if st.button("📐 计算", type="primary"):
            if cs == '双拼':
                bdl = 2*cl + 2*cw + tab_w
                bdw = 2*ch + 2*cw + flap_w
            elif cs == '两页成型':
                bdl = cl + cw + tab_w
                bdw = ch + cw + flap_w
            else:  # 单页成型
                bdl = 2*cl + 2*cw + tab_w
                bdw = ch + cw + flap_w
            st.metric("瓦楞纸板", f"{bdl} × {bdw} mm")
            st.metric("面纸(含出血)", f"{bdl+30} × {bdw+15} mm")
            st.metric("用料面积", f"{bdl*bdw/1_000_000:.4f} m²")
            if cs == '双拼':
                st.caption(f"公式: 2×{cl}+2×{cw}+{tab_w}={bdl} | 2×({ch}+{cw})+{flap_w}={bdw}")
            elif cs == '两页成型':
                st.caption(f"公式: {cl}+{cw}+{tab_w}={bdl} | {ch}+{cw}+{flap_w}={bdw}")
            else:
                st.caption(f"公式: 2×{cl}+2×{cw}+{tab_w}={bdl} | {ch}+{cw}+{flap_w}={bdw}")
    
    with at3:
        st.subheader("💰 原材料价格调整")
        st.caption("修改后首页报价将自动使用新价格")
        mc1, mc2, mc3 = st.columns(3)
        with mc1:
            bp_new = st.number_input("瓦楞纸板 ¥/m²", 0.5, 10.0, fcb.get('EB', 1.5), 0.05)
        with mc2:
            pp_new = st.number_input("面纸 ¥/m²", 0.1, 5.0, 0.45, 0.05)
        with mc3:
            lp_new = st.number_input("覆膜费 ¥/只", 0.0, 2.0, 0.25, 0.05)
        st.caption("💡 当前为全局默认值，按瓦型细分请查看下方参考表")
        if len(cost_df) > 0:
            st.write("**预核单成本参考**")
            st.dataframe(cost_df[['product','qty','unit_cost','contract_price','cost_per_m2']].rename(
                columns={'product':'产品','qty':'数量','unit_cost':'成本','contract_price':'合同价','cost_per_m2':'¥/m²'}),
                hide_index=True, width="stretch")
    
    with at4:
        st.subheader("📋 全部数据")
        yy = sorted(df['year'].dropna().unique())
        sy = st.multiselect("年份", yy, yy[-2:])
        fd = df[df['year'].isin(sy)] if sy else df
        st.write(f"{len(fd)} 条")
        sc = ['order_date','client','product','order_qty','box_l','box_w','box_h',
              'flute_normalized','total_gram','board_material']
        st.dataframe(cn(fd[sc], sc).head(200), width="stretch", height=400)
        
        if st.button("📥 导出全部(CSV)"):
            st.download_button("下载", fd.to_csv(index=False), "yiwei_all.csv", "text/csv")

# ============================================================================
# Tab 4: 🤖 AI 咨询师 — Multi-Agent 协作报价分析
# ============================================================================
with tab4:
    st.header("🤖 AI 咨询师 · Multi-Agent 协作")
    st.caption("3 角色协作（情报 → 分析 → 审查）+ 跨 provider 降级链 · 详见 [agents/README.md](https://github.com/wwwaaarrthur/yiwei-cost-engine/blob/main/agents/README.md)")

    # ---- Sidebar: LLM mode toggle ----
    with st.sidebar.expander("🤖 AI 咨询师配置", expanded=False):
        use_real_llm = st.toggle("启用真实 Claude API 调用", value=False,
                                  help="需在 Streamlit Secrets 配置 ANTHROPIC_API_KEY，否则默认 Mock 模式")
        st.caption("Mock 模式：基于历史数据的启发式推荐，0 API 成本。Real 模式：调用 Claude API。")

    # ---- Demo queries ----
    st.markdown("**💡 演示问题**（点击快速填入）")
    demo_cols = st.columns(3)
    demo_queries = [
        "1L*12 瓶水剂出口纸箱，BC 瓦防水的，怎么报价？",
        "4kg 农化颗粒剂包装，EB 瓦，月用量 2 万只，给个区间报价",
        "新客户询价 3L 桔子箱，没有历史订单，怎么办？",
    ]
    if "advisor_query" not in st.session_state:
        st.session_state["advisor_query"] = ""
    for i, dq in enumerate(demo_queries):
        with demo_cols[i]:
            if st.button(f"📝 示例 {i+1}", key=f"demo_{i}", help=dq):
                st.session_state["advisor_query"] = dq

    # ---- Input ----
    user_query = st.text_area(
        "你的问题",
        value=st.session_state.get("advisor_query", ""),
        placeholder="例：1L*12 瓶水剂出口纸箱，BC 瓦防水的，怎么报价？",
        height=80,
    )

    flute_col, btn_col = st.columns([1, 2])
    with flute_col:
        flute_hint = st.selectbox("瓦型提示（可选）", ["自动识别", "BC", "EB", "BE", "单E"])
    with btn_col:
        st.write("")
        run_advisor = st.button("🚀 运行 Multi-Agent 分析", type="primary", width="stretch")

    # ---- Run pipeline ----
    if run_advisor and user_query.strip():
        try:
            from agents import AdvisorOrchestrator
            # API key from secrets (only if user toggled real mode)
            api_key = None
            if use_real_llm:
                try:
                    api_key = st.secrets.get("ANTHROPIC_API_KEY", None)
                except Exception:
                    api_key = None
                if not api_key:
                    st.warning("⚠️ 未在 Streamlit Secrets 配置 ANTHROPIC_API_KEY，自动降级到 Mock 模式")

            orch = AdvisorOrchestrator(
                use_llm=use_real_llm and bool(api_key),
                api_key=api_key,
            )

            with st.spinner("3 Agent 协作中..."):
                result = orch.advise(
                    user_query.strip(),
                    flute_hint=None if flute_hint == "自动识别" else flute_hint,
                )

            # ---- Timeline ----
            t = result.get("timestamps", {})
            st.markdown(
                f"⏱️ **总耗时**: {result.get('total_ms', 0)} ms "
                f"(情报 {t.get('intelligence_ms', 0)} ms · 分析 {t.get('analysis_ms', 0)} ms · 审查 {t.get('critic_ms', 0)} ms)"
            )

            # ---- Final recommendation ----
            final = result["final_recommendation"]
            v = final["verdict"]
            if v == "approve":
                st.success(f"✅ **{final['message_to_user']}**")
            elif v == "revise":
                st.warning(f"⚠️ **{final['message_to_user']}**")
            else:
                st.error(f"🛑 **{final['message_to_user']}**")

            # Confidence bar
            st.progress(final["confidence"], text=f"Critic Agent 置信度: {final['confidence']:.0%}")

            # ---- Agent collaboration details ----
            st.markdown("### 🔍 3 Agent 协作过程")
            agent_tabs = st.tabs(["🔎 情报 Agent", "🧠 分析 Agent", "⚖️ 审查 Agent"])

            with agent_tabs[0]:
                intel = result["intelligence"]
                st.write(f"**关键词提取**: {intel.get('keywords_extracted', [])}")
                st.write(f"**瓦型过滤**: {intel.get('flute_filter') or '（无）'}")
                st.metric("匹配历史订单", intel.get("n_matches", 0))
                pr = intel.get("price_range", {})
                pcols = st.columns(3)
                pcols[0].metric("p25", f"¥{pr.get('p25', 'N/A')}/m²")
                pcols[1].metric("p50（中位）", f"¥{pr.get('p50', 'N/A')}/m²")
                pcols[2].metric("p75", f"¥{pr.get('p75', 'N/A')}/m²")
                if intel.get("warnings"):
                    st.markdown("**⚠️ 警告**")
                    for w in intel["warnings"]:
                        st.warning(w)
                if intel.get("similar_orders"):
                    st.markdown("**前 5 条相似订单**")
                    st.dataframe(pd.DataFrame(intel["similar_orders"][:5]), width="stretch")

            with agent_tabs[1]:
                ana = result["analysis"]
                st.write(f"**模式**: `{ana.get('mode', 'unknown')}`")
                if ana.get("notice"):
                    st.info(ana["notice"])
                if ana.get("recommended_price_per_m2") is not None:
                    st.metric("建议单价", f"¥{ana['recommended_price_per_m2']}/m²")
                st.markdown("**假设**")
                for a in ana.get("assumptions", []):
                    st.write(f"- {a}")
                st.markdown("**推理**")
                st.write(ana.get("rationale", "（无）"))
                st.markdown("**Trade-offs**")
                for t in ana.get("trade_offs", []):
                    st.write(f"- {t}")
                st.markdown("**风险**")
                for r in ana.get("risks", []):
                    sev = r.get("severity", "low")
                    icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(sev, "⚪")
                    st.write(f"{icon} **{r.get('risk')}** — _Mitigation_: {r.get('mitigation')}")

            with agent_tabs[2]:
                crit = result["critic"]
                vd = crit.get("verdict", "unknown")
                st.write(f"**Verdict**: `{vd}` (mode: `{crit.get('mode', 'mock')}`)")
                st.write(f"**Confidence**: {crit.get('confidence', 0):.0%}")
                if crit.get("issues"):
                    st.markdown("**审查发现**")
                    for i in crit["issues"]:
                        sev = i.get("severity", "low")
                        icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(sev, "⚪")
                        st.write(f"{icon} **{i.get('type', '?')}** — {i.get('detail', '')}")
                else:
                    st.success("✅ 4 个维度审查全通过：sanity bounds / citation integrity / risk coverage / trade-off honesty")

        except Exception as e:
            st.error(f"🛑 Multi-Agent 流程失败：{type(e).__name__}: {e}")
            st.caption("这本身是 system 思维的证据 — 失败应该可见，不应该静默")

    elif run_advisor and not user_query.strip():
        st.warning("请输入问题或点击演示按钮填入示例")

# Footer
st.sidebar.markdown("## 📊 毅伟包装成本系统")
st.sidebar.markdown(f"**数据**: {len(df):,}条工艺单 + {len(cost_df)}条成本")
# Dynamic date range from actual data
valid_dates = df['order_date_parsed'].dropna()
dr = f"{valid_dates.min().strftime('%Y.%m')} - {valid_dates.max().strftime('%Y.%m')}" if len(valid_dates) > 0 else "N/A"
st.sidebar.markdown(f"**跨度**: {dr}")
st.sidebar.markdown(f"**客户**: {df['client'].nunique()}家")
st.sidebar.markdown("---")
st.sidebar.markdown("## 💰 瓦型成本基准")
for ft, p in sorted(fcb.items()):
    st.sidebar.markdown(f"- **{ft}**: ¥{p:.2f}/m²")
st.sidebar.markdown("---")
st.sidebar.markdown("*v3.0 工厂极简版*")
