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

from db_config import resolve_db_config
from public_view import sanitize_precheck_costs_for_public, sanitize_process_sheets_for_public
from sizing_engine import (
    FORMING_SINGLE_PAGE,
    FORMING_TWO_PAGE,
    LAYOUT_DOUBLE,
    LAYOUT_SINGLE,
    PAIR_LONG,
    PAIR_SHORT,
    Size2D,
    calculate_sizing,
    infer_process_modes,
)

# DB 路径策略：显式 public/internal 双模式，默认 auto 兼容本地与 Streamlit Cloud
_HERE = os.path.dirname(os.path.abspath(__file__))
DB_CONFIG = resolve_db_config(_HERE)
DB = DB_CONFIG.path
IS_PUBLIC_MODE = DB_CONFIG.is_public

st.set_page_config(
    page_title="Yiwei Cost Engine | 毅伟包装 AI 报价与运营台",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS (轻量美化，零依赖)
st.markdown("""
<style>
    html, body, [class*="css"] {
        font-family: 'SF Pro Display', 'PingFang SC', 'Microsoft YaHei', sans-serif;
        color: #172026;
    }
    .main .block-container {
        max-width: 1320px;
        padding-top: 1.25rem;
        padding-bottom: 2rem;
    }
    h1, h2, h3 { letter-spacing: 0; }
    .stButton > button {
        border-radius: 8px;
        font-weight: 650;
        border: 1px solid #C9D3DD;
        transition: border-color 0.15s ease, box-shadow 0.15s ease;
    }
    .stButton > button:hover {
        border-color: #0F766E;
        box-shadow: 0 2px 8px rgba(15, 118, 110, 0.14);
    }
    [data-testid="stMetric"] {
        background: #FFFFFF;
        border-radius: 8px;
        padding: 14px 16px;
        border: 1px solid #DDE2E7;
        box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
    }
    [data-testid="stDataFrame"] { border-radius: 8px; overflow: hidden; }
    .app-kicker {
        color: #667085;
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin-bottom: 0.25rem;
    }
    .app-title {
        font-size: 2rem;
        line-height: 1.18;
        font-weight: 760;
        color: #172026;
        margin: 0;
    }
    .app-subtitle {
        color: #667085;
        font-size: 0.98rem;
        margin-top: 0.35rem;
        margin-bottom: 0.85rem;
    }
    .mode-pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        border-radius: 999px;
        padding: 4px 10px;
        font-size: 0.76rem;
        font-weight: 760;
        border: 1px solid #DDE2E7;
        white-space: nowrap;
    }
    .mode-public {
        color: #7A4B00;
        background: #FFF7E6;
        border-color: #F3D39B;
    }
    .mode-internal {
        color: #075E54;
        background: #EAF7F3;
        border-color: #B8E1D5;
    }
    .section-label {
        color: #667085;
        font-size: 0.78rem;
        font-weight: 760;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        margin-bottom: 0.15rem;
    }
    .compact-note {
        color: #667085;
        font-size: 0.88rem;
        margin-top: -0.15rem;
    }
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
    process_modes = df['notes'].apply(infer_process_modes)
    inferred_modes = {
        'forming_mode': process_modes.apply(lambda modes: modes.forming_mode),
        'face_layout': process_modes.apply(lambda modes: modes.face_layout),
        'board_layout': process_modes.apply(lambda modes: modes.board_layout),
    }
    for field, inferred in inferred_modes.items():
        if field in df.columns:
            structured = df[field].replace('', np.nan)
            df[f'{field}_derived'] = structured.fillna(inferred)
        else:
            df[f'{field}_derived'] = inferred
    df['forming_mode_label'] = df['forming_mode_derived'].map({
        FORMING_SINGLE_PAGE: '单页成型',
        FORMING_TWO_PAGE: '双页成型',
    }).fillna('未识别')
    df['face_layout_label'] = df['face_layout_derived'].map({
        LAYOUT_SINGLE: '单拼',
        LAYOUT_DOUBLE: '双拼',
    }).fillna('未识别')
    df['board_layout_label'] = df['board_layout_derived'].map({
        LAYOUT_SINGLE: '单拼',
        LAYOUT_DOUBLE: '双拼',
    }).fillna('未识别')
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
if IS_PUBLIC_MODE:
    df = sanitize_process_sheets_for_public(df)
    cost_df = sanitize_precheck_costs_for_public(cost_df)

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

# 印刷成本表 (基于工业品硬管 4 数量段实测 + 单色/多色案例)
# (setup_fee, unit_var): print_cost = max(setup/qty, unit_var)
PRINT_TABLE = {
    1: (150, 0.18),    # 单色 (匿名样本 A/B/C 实测 0.21)
    2: (300, 0.21),
    3: (500, 0.30),
    4: (900, 0.45),    # 4L 外贸彩印 实测 0.35-0.44
    5: (1250, 0.63),   # 5 色+: 工业品硬管实测 K=1250, v=0.63
}

def print_cost_fn(colors, qty):
    setup, unit_var = PRINT_TABLE.get(colors, PRINT_TABLE[2])
    return max(setup / qty, unit_var)

# 制费默认值 (实测中位)
OTHER_COST_DEFAULT = {'内销': 0.82, '出口': 1.07}

FORMING_OPTIONS = {
    '请选择/需确认': None,
    '单页成型': FORMING_SINGLE_PAGE,
    '双页成型': FORMING_TWO_PAGE,
}
LAYOUT_OPTIONS = {
    '请选择/需确认': None,
    '单拼': LAYOUT_SINGLE,
    '双拼': LAYOUT_DOUBLE,
}
PAIR_OPTIONS = {
    '沿短边拼': PAIR_SHORT,
    '沿长边拼': PAIR_LONG,
}


def render_sizing_controls(prefix: str, expanded: bool = False) -> dict:
    """Render separate forming, face-layout, and board-layout inputs."""
    p1, p2, p3 = st.columns(3)
    forming_label = p1.selectbox("成型方式", list(FORMING_OPTIONS), key=f"{prefix}_forming")
    face_layout_label = p2.selectbox("面纸拼版", list(LAYOUT_OPTIONS), key=f"{prefix}_face_layout")
    board_layout_label = p3.selectbox("瓦楞下料拼版", list(LAYOUT_OPTIONS), key=f"{prefix}_board_layout")

    forming_mode = FORMING_OPTIONS[forming_label]
    face_layout = LAYOUT_OPTIONS[face_layout_label]
    board_layout = LAYOUT_OPTIONS[board_layout_label]

    with st.expander("工艺参数与客户约束", expanded=expanded):
        st.caption("出血、胶口和验收要求独立记录；不会被偷偷混入面纸尺寸公式。")
        a1, a2, a3, a4 = st.columns(4)
        default_short = 18 if forming_mode == FORMING_TWO_PAGE else 20
        long_allowance_mm = a1.number_input(
            "长边公式余量 mm", 0, 100, 45, 1, key=f"{prefix}_long_allowance"
        )
        short_profile = a2.selectbox(
            "短边工艺余量",
            ["自动：单页20 / 双页18", "15mm：确认后降本", "18mm", "20mm", "自定义"],
            key=f"{prefix}_short_profile",
            help="自动值跟随成型方式；双页在设备与版面确认后可用15mm。",
        )
        if short_profile.startswith("自动"):
            short_allowance_mm = default_short
        elif short_profile.startswith("15"):
            short_allowance_mm = 15
        elif short_profile.startswith("18"):
            short_allowance_mm = 18
        elif short_profile.startswith("20"):
            short_allowance_mm = 20
        else:
            short_allowance_mm = a2.number_input(
                "自定义短边余量 mm", 0, 100, default_short, 1, key=f"{prefix}_short_custom"
            )
        face_adjust_long_mm = a3.number_input(
            "面纸长边版面调整 mm", -100, 200, 0, 1, key=f"{prefix}_face_adjust_long"
        )
        face_adjust_short_mm = a4.number_input(
            "面纸短边版面调整 mm", -100, 200, 0, 1, key=f"{prefix}_face_adjust_short"
        )

        face_pair_direction = PAIR_SHORT
        face_pair_reduction_mm = 20
        if face_layout == LAYOUT_DOUBLE:
            f1, f2 = st.columns(2)
            face_pair_direction = PAIR_OPTIONS[f1.selectbox(
                "面纸双拼方向", list(PAIR_OPTIONS), key=f"{prefix}_face_pair_direction"
            )]
            face_pair_reduction_mm = f2.number_input(
                "面纸双拼减量 mm", 0, 100, 20, 1, key=f"{prefix}_face_pair_reduction",
                help="手写公式为两片相加后减约20mm，最终值必须按版面复核。",
            )

        board_pair_direction = PAIR_SHORT
        board_pair_reduction_mm = 20
        if board_layout == LAYOUT_DOUBLE:
            b1, b2 = st.columns(2)
            board_pair_direction = PAIR_OPTIONS[b1.selectbox(
                "瓦楞双拼方向", list(PAIR_OPTIONS), key=f"{prefix}_board_pair_direction"
            )]
            board_pair_reduction_mm = b2.number_input(
                "瓦楞双拼减量 mm", 0, 100, 20, 1, key=f"{prefix}_board_pair_reduction",
                help="尚缺员工实际案例，系统会强制提示人工复核。",
            )

        d1, d2, d3, d4 = st.columns(4)
        board_delta_long_mm = d1.number_input(
            "面纸-瓦楞长边差 mm", 0, 30, 5, 1, key=f"{prefix}_board_delta_long"
        )
        board_delta_short_mm = d2.number_input(
            "面纸-瓦楞短边差 mm", 0, 30, 7, 1, key=f"{prefix}_board_delta_short"
        )
        bleed_limit_mm = d3.number_input(
            "允许最大单边出血 mm", 0, 30, 10, 1, key=f"{prefix}_bleed_limit",
            help="记录项，不直接增加面纸尺寸。",
        )
        customer_glue_flap_mm = d4.number_input(
            "客户胶口要求 mm", 0, 60, 0, 1, key=f"{prefix}_glue_flap",
            help="0表示客户未指定；不作为统一公式常量。",
        )

        q1, q2, q3 = st.columns(3)
        standard = q1.selectbox(
            "验收依据",
            ["GB/T 6543-2025", "客户合同指定", "自定义/待确认"],
            key=f"{prefix}_standard",
        )
        size_tolerance_mm = q2.number_input(
            "客户/订单尺寸允许偏差 ±mm", 0, 30, 0, 1, key=f"{prefix}_size_tolerance",
            help="0表示未单独指定，按验收依据执行；不能把某张订单的±5mm套用于全部订单。",
        )
        compression_requirement_n = q3.number_input(
            "抗压要求 N（0=未提供）", 0, 100000, 0, 100, key=f"{prefix}_compression"
        )

        st.markdown("**人工最终拼版/下料尺寸（两边均为0时使用公式建议值）**")
        o1, o2, o3, o4 = st.columns(4)
        final_face_long_mm = o1.number_input(
            "最终面纸长边 mm", 0, 10000, 0, 1, key=f"{prefix}_final_face_long"
        )
        final_face_short_mm = o2.number_input(
            "最终面纸短边 mm", 0, 10000, 0, 1, key=f"{prefix}_final_face_short"
        )
        final_board_long_mm = o3.number_input(
            "最终瓦楞长边 mm", 0, 10000, 0, 1, key=f"{prefix}_final_board_long"
        )
        final_board_short_mm = o4.number_input(
            "最终瓦楞短边 mm", 0, 10000, 0, 1, key=f"{prefix}_final_board_short"
        )

    missing = [
        name for name, value in (
            ("成型方式", forming_mode),
            ("面纸拼版", face_layout),
            ("瓦楞下料拼版", board_layout),
        )
        if value is None
    ]
    override_errors = []
    if bool(final_face_long_mm) != bool(final_face_short_mm):
        override_errors.append("人工最终面纸尺寸需同时填写长、短边")
    if bool(final_board_long_mm) != bool(final_board_short_mm):
        override_errors.append("人工最终瓦楞尺寸需同时填写长、短边")
    final_face_sheet = (
        Size2D(final_face_long_mm, final_face_short_mm)
        if final_face_long_mm and final_face_short_mm else None
    )
    final_board_sheet = (
        Size2D(final_board_long_mm, final_board_short_mm)
        if final_board_long_mm and final_board_short_mm else None
    )
    if board_layout == LAYOUT_DOUBLE and final_board_sheet is None:
        override_errors.append("瓦楞双拼规则尚未员工确认，需填写最终瓦楞尺寸")
    problems = missing + override_errors
    return {
        "ready": not problems,
        "missing": missing,
        "problems": problems,
        "forming_label": forming_label,
        "face_layout_label": face_layout_label,
        "board_layout_label": board_layout_label,
        "forming_mode": forming_mode,
        "face_layout": face_layout,
        "board_layout": board_layout,
        "long_allowance_mm": long_allowance_mm,
        "short_allowance_mm": short_allowance_mm,
        "face_adjust_long_mm": face_adjust_long_mm,
        "face_adjust_short_mm": face_adjust_short_mm,
        "face_pair_direction": face_pair_direction,
        "face_pair_reduction_mm": face_pair_reduction_mm,
        "board_pair_direction": board_pair_direction,
        "board_pair_reduction_mm": board_pair_reduction_mm,
        "board_delta_long_mm": board_delta_long_mm,
        "board_delta_short_mm": board_delta_short_mm,
        "bleed_limit_mm": bleed_limit_mm,
        "customer_glue_flap_mm": customer_glue_flap_mm,
        "standard": standard,
        "size_tolerance_mm": size_tolerance_mm,
        "compression_requirement_n": compression_requirement_n,
        "final_face_sheet": final_face_sheet,
        "final_board_sheet": final_board_sheet,
    }

CN = {
    'batch_no': '批次/单号', 'client': '客户', 'product': '产品', 'order_qty': '数量', 'order_date': '日期',
    'box_l': '长', 'box_w': '宽', 'box_h': '高', 'flute_normalized': '瓦型',
    'board_material': '纸板材质', 'paper_spec': '面纸', 'total_gram': '克重',
    'lamination': '覆膜', 'print_style': '印刷', 'board_area': '纸板面积',
    'forming_mode_label': '成型方式', 'face_layout_label': '面纸拼版',
    'board_layout_label': '瓦楞拼版',
    'box_volume': '箱体积', 'cost_per_m2': '¥/m²',
}
def cn(df, cols):
    df = df.rename(columns={c: CN.get(c, c) for c in df.columns})
    return df[[CN.get(c, c) for c in cols if CN.get(c, c) in df.columns]]

valid_dates = df['order_date_parsed'].dropna()
DATA_RANGE = (
    f"{valid_dates.min().strftime('%Y.%m')} - {valid_dates.max().strftime('%Y.%m')}"
    if len(valid_dates) > 0 else "N/A"
)
DATA_RANGE_SHORT = (
    f"{valid_dates.max().year - valid_dates.min().year + 1}年"
    if len(valid_dates) > 0 else "N/A"
)
MODE_CLASS = "mode-public" if IS_PUBLIC_MODE else "mode-internal"
MODE_TEXT = "PUBLIC DEMO · ANONYMIZED" if IS_PUBLIC_MODE else "INTERNAL · REAL DATA"
MODE_CAPTION = (
    "公开演示库：客户/供应商已脱敏，适合 GitHub 与面试官查看。"
    if IS_PUBLIC_MODE
    else "内部工厂库：可按真实客户、产品、材料关键词查单，请勿外发截图。"
)


def render_sidebar_summary():
    st.sidebar.markdown("### 毅伟成本运营台")
    st.sidebar.markdown(
        f"<span class='mode-pill {MODE_CLASS}'>{MODE_TEXT}</span>",
        unsafe_allow_html=True,
    )
    st.sidebar.caption(MODE_CAPTION)
    st.sidebar.markdown("---")
    st.sidebar.markdown("**数据概览**")
    st.sidebar.markdown(f"- 工艺单: **{len(df):,}**")
    st.sidebar.markdown(f"- 成本样本: **{len(cost_df)}**")
    st.sidebar.markdown(f"- 客户: **{df['client'].nunique()}**")
    st.sidebar.markdown(f"- 跨度: **{DATA_RANGE}**")
    st.sidebar.markdown("---")
    st.sidebar.markdown("**使用路径**")
    if IS_PUBLIC_MODE:
        st.sidebar.markdown("- 面试官: 报价台 → 模型评估 → 核稿验证")
        st.sidebar.markdown("- 员工查单: 请使用 internal 入口")
    else:
        st.sidebar.markdown("- 员工: 订单搜索 → 报价台 → 导出")
        st.sidebar.markdown("- 复盘: 模型评估 → 核稿验证")
    with st.sidebar.expander("瓦型成本基准", expanded=False):
        for ft, p in sorted(fcb.items()):
            st.markdown(f"- **{ft}**: ¥{p:.2f}/m²")
    st.sidebar.caption("*v3.1 双模式轻量布局*")


def render_app_header():
    st.markdown(
        f"""
<div class="app-kicker">Digital Operations Portfolio</div>
<div style="display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap;">
  <div>
    <div class="app-title">Yiwei Cost Engine · 毅伟包装成本运营台</div>
    <div class="app-subtitle">
      AI-assisted corrugated box quotation, order retrieval, model evaluation, and prepress quality review
      for a traditional packaging factory. Built as a privacy-safe Digital Transformation portfolio case.
    </div>
    <div class="app-subtitle">
      中文摘要：把经验报价、历史工艺单、条件价格评估与印前核稿整合成一个可审计的制造业运营工作流。
    </div>
  </div>
  <span class="mode-pill {MODE_CLASS}">{MODE_TEXT}</span>
</div>
        """,
        unsafe_allow_html=True,
    )
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("工艺单", f"{len(df):,}")
    k2.metric("成本样本", f"{len(cost_df)}")
    k3.metric("客户数", f"{df['client'].nunique()}")
    k4.metric("跨度", DATA_RANGE_SHORT)


render_sidebar_summary()
render_app_header()

# ====== Tabs ======
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "报价台", "订单搜索", "模型评估", "AI 顾问", "核稿验证"
])

# ========================
# TAB 1: 快速报价
# ========================
with tab1:
    st.markdown("<div class='section-label'>Quote Workbench</div>", unsafe_allow_html=True)
    st.subheader("纸箱快速报价")
    st.caption("输入尺寸与订单条件，输出建议报价、成本拆解和相似历史订单。")
    
    left, right = st.columns([2, 1], gap="large")
    with left:
        st.markdown("**订单参数**")
        c1, c2 = st.columns(2)
        with c1:
            l = st.number_input("箱长 L (mm)", 20, 3000, 370, key="ql")
            w = st.number_input("箱宽 W (mm)", 20, 3000, 280, key="qw")
            h = st.number_input("箱高 H (mm)", 20, 3000, 255, key="qh")
        with c2:
            qty = st.number_input("数量 (只)", 1, 1_000_000, 10000, 500, key="qq")
            ft = st.selectbox("瓦型", ['EB','BC','AB','单C瓦','单B瓦','单E瓦','EE'], key="qf")
            ct_label = st.selectbox("客户类型", ['大客户', '中等客户', '小客户/农户'], key="qc")
            order_type = st.selectbox("订单类型", ['内销', '出口'], key="qot",
                                       help="出口: 制费 1.07/只 + 毛利 +4pp (4L 实测 14.8%); 内销: 0.82/只")
            board_cpm_override = st.number_input(
                "订单纸板核定成本 ¥/m²（0=使用瓦型基准）",
                0.0, 20.0, 0.0, 0.05, key="q_board_cpm_override",
                help="有供应商报价或预核单时优先填写，可降低仅按瓦型估价的误差。",
            )
            print_colors = st.selectbox("印刷色数", [1, 2, 3, 4, 5], index=1, key="qpc",
                                         help="数量摊销: 印刷开机费/qty + 单只变动 (匿名工业品 5色 K=1250)")
            lam = st.checkbox("覆膜", False, key="qlm")
            pad = st.checkbox("垫片", False, key="qpd")
            # Phase G1: 反向亏损告警 — 防 02-02 类亏损单 (客户压价 < 我方成本)
            client_quote = st.number_input(
                "客户已给价 ¥/只 (可选, 反向校验)", 0.0, 100.0, 0.0, 0.1, key="qcq",
                help="留空=按我方建议报价; 若客户已给定 → 实测毛利对比, 触发亏损告警 (02-02 案例防御)"
            )

        st.markdown("**成型与拼版参数**")
        quote_process = render_sizing_controls("quote")
        
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
        st.markdown("**价格基准**")
        with st.expander("调整瓦型/材料参数", expanded=False):
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
    quote_sizing = None
    if quote_btn and not quote_process["ready"]:
        st.error(f"请先确认：{'、'.join(quote_process['problems'])}。系统不再用历史占比猜测工艺。")
    elif quote_btn:
        try:
            quote_sizing = calculate_sizing(
                length_mm=l,
                width_mm=w,
                height_mm=h,
                forming_mode=quote_process["forming_mode"],
                face_layout=quote_process["face_layout"],
                board_layout=quote_process["board_layout"],
                long_allowance_mm=quote_process["long_allowance_mm"],
                short_allowance_mm=quote_process["short_allowance_mm"],
                face_adjust_long_mm=quote_process["face_adjust_long_mm"],
                face_adjust_short_mm=quote_process["face_adjust_short_mm"],
                face_pair_direction=quote_process["face_pair_direction"],
                face_pair_reduction_mm=quote_process["face_pair_reduction_mm"],
                board_pair_direction=quote_process["board_pair_direction"],
                board_pair_reduction_mm=quote_process["board_pair_reduction_mm"],
                board_delta_long_mm=quote_process["board_delta_long_mm"],
                board_delta_short_mm=quote_process["board_delta_short_mm"],
                final_face_sheet=quote_process["final_face_sheet"],
                final_board_sheet=quote_process["final_board_sheet"],
            )
        except ValueError as exc:
            st.error(f"尺寸参数无法计算：{exc}")

    if quote_btn and quote_sizing is not None:
        tier_map = {'大客户': 'vip', '中等客户': 'medium', '小客户/农户': 'small'}
        tier = tier_map[ct_label]
        is_export = (order_type == '出口')
        margin = cmargin(tier, qty=qty, is_export=is_export)

        blong, bshort = quote_sizing.board_sheet.long_mm, quote_sizing.board_sheet.short_mm
        barea = quote_sizing.board_area_per_carton_m2
        parea = quote_sizing.face_area_per_carton_m2

        # Cost
        bp = board_cpm_override if board_cpm_override > 0 else fcb.get(ft, 1.5)
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
        for warning in quote_sizing.warnings:
            st.warning(f"工艺复核：{warning}")
        if quote_process["bleed_limit_mm"] > 10:
            st.warning("允许出血超过当前工艺单常见的 <10mm，请设计复核。")
        if quote_process["compression_requirement_n"] == 0:
            st.info("未输入抗压要求：当前报价只按所选材料成本计算，不能证明满足客户抗压验收。")

        # Phase G1: 反向亏损告警 (输出侧, 优先级最高)
        # ground truth: 02-02 匿名大客户 19659 只，客户给价低于我方成本 → 亏损
        if client_quote > 0:
            actual_margin_pct = (client_quote - cost) / client_quote * 100
            actual_loss_per_unit = cost - client_quote
            total_loss = actual_loss_per_unit * qty
            if actual_margin_pct < 0:
                st.error(
                    f"🔴🔴 **亏损单警报!!!** 客户给价 ¥{client_quote:.2f} < 我方成本 ¥{cost:.2f} = "
                    f"亏 ¥{actual_loss_per_unit:.2f}/只 × {qty:,} 只 = **总亏 ¥{total_loss:,.0f}** "
                    f"({actual_margin_pct:.1f}%). "
                    f"⚠️ 02-02 匿名大客户案例: 19659 只大单同模式 -15.9% / 实测亏损. **拒签或重谈**!"
                )
            elif actual_margin_pct < 5:
                st.error(f"🔴 客户给价对应实测毛利仅 {actual_margin_pct:.1f}% (< 5%) — 薄利, 建议谈判")
            elif actual_margin_pct < 8:
                st.warning(f"🟡 客户给价实测毛利 {actual_margin_pct:.1f}% — 偏薄, 复核成本结构")
            else:
                st.success(f"🟢 客户给价 ¥{client_quote:.2f} → 实测毛利 {actual_margin_pct:.1f}% ✅ 可接")
            # 对比展示
            diff_vs_suggest = (client_quote - price) / price * 100
            st.caption(
                f"📊 客户价 ¥{client_quote:.2f} | 我方成本 ¥{cost:.2f} | 我方建议 ¥{price:.2f} | "
                f"客户给价 vs 我方建议: {diff_vs_suggest:+.1f}%"
                + (" (客户压价幅度大, 注意亏损模式)" if diff_vs_suggest < -10 else "")
            )

        # 输入侧告警 (我方建议价毛利, 兜底)
        if mp < 5:
            st.error(f"🔴 我方建议毛利率 {mp:.1f}% < 5% — 接近亏损！(历史教训: 2026-02-02 匿名大客户 19659 只大单 -15.9%)")
        elif mp < 8:
            st.warning(f"🟡 我方建议毛利率 {mp:.1f}% 偏薄 — 建议复核同客户同尺寸历史均值")

        r1, r2, r3, r4 = st.columns(4)
        with r1:
            st.metric("单只成本", f"¥{cost:.2f}")
        with r2:
            st.metric("建议报价", f"¥{price:.2f}", delta=f"毛利¥{price-cost:.2f} ({mp:.0f}%)")
        with r3:
            st.metric("单箱瓦楞面积", f"{barea:.4f}m²")
        with r4:
            st.metric("单箱面纸面积", f"{parea:.4f}m²")

        # Comparable prices
        with st.expander("📊 成本明细 & 其他客户报价", expanded=False):
            print_setup_fee, print_unit_var = PRINT_TABLE.get(print_colors, PRINT_TABLE[2])
            st.write(f"**成本构成**: 纸板¥{bc:.2f} + 面纸¥{pc:.2f} + 覆膜¥{lc:.2f} + 垫片¥{pdc:.2f} + 印刷¥{print_cost:.2f} + 制费¥{other_cost:.2f} = ¥{base:.2f} × {sf} = ¥{cost:.2f}")
            st.caption(
                f"成型: {quote_process['forming_label']} | 面纸: {quote_process['face_layout_label']} | "
                f"瓦楞: {quote_process['board_layout_label']} | 公式版本: {quote_sizing.formula_version}"
            )
            if quote_sizing.face_sheet != quote_sizing.suggested_face_sheet:
                st.caption(
                    f"面纸公式建议 {quote_sizing.suggested_face_sheet.long_mm}×"
                    f"{quote_sizing.suggested_face_sheet.short_mm}mm；已采用人工最终尺寸。"
                )
            if quote_sizing.board_sheet != quote_sizing.suggested_board_sheet:
                st.caption(
                    f"瓦楞公式建议 {quote_sizing.suggested_board_sheet.long_mm}×"
                    f"{quote_sizing.suggested_board_sheet.short_mm}mm；已采用人工最终尺寸。"
                )
            st.caption(
                f"面纸单片 {quote_sizing.face_piece.long_mm}×{quote_sizing.face_piece.short_mm}mm × "
                f"{quote_sizing.face_piece_count_per_carton}片/箱；拼版 "
                f"{quote_sizing.face_sheet.long_mm}×{quote_sizing.face_sheet.short_mm}mm × "
                f"{quote_sizing.face_sheets_per_carton:g}张/箱"
            )
            st.caption(
                f"瓦楞单片 {quote_sizing.board_piece.long_mm}×{quote_sizing.board_piece.short_mm}mm；下料 "
                f"{blong}×{bshort}mm × {quote_sizing.board_sheets_per_carton:g}张/箱"
            )
            glue_text = (
                f"{quote_process['customer_glue_flap_mm']}mm"
                if quote_process["customer_glue_flap_mm"] else "未指定"
            )
            compression_text = (
                f"{quote_process['compression_requirement_n']}N"
                if quote_process["compression_requirement_n"] else "未提供"
            )
            st.caption(
                f"约束: {quote_process['standard']} | 尺寸偏差 ±{quote_process['size_tolerance_mm']}mm | "
                f"出血上限 {quote_process['bleed_limit_mm']}mm | "
                f"客户胶口 {glue_text} | 抗压 {compression_text}"
            )
            st.caption(f"印刷({print_colors}色): max(开机费¥{print_setup_fee}/qty {qty}, 单只变动¥{print_unit_var}) = ¥{print_cost:.2f}/只")
            st.caption(f"制费({order_type}): default ¥{other_default}/只" + (" (sidebar 覆盖)" if abs(global_other - 0.82) > 0.01 else ""))
            st.caption(f"qty={qty} 阶梯毛利基线: {qty_margin_base(qty)*100:.0f}% (≤500=30%/501-2k=22%/2k-5k=12%/5k-20k=8%/>20k=6%)" + (" + 出口 +4pp" if is_export else ""))
            st.write(
                f"**纸板**: {barea:.3f}m² × ¥{bp:.2f}/m²"
                + ("（订单核定成本）" if board_cpm_override > 0 else "（瓦型基准）")
                + f" | **面纸**: {parea:.3f}m² × ¥{pp:.3f}/m² "
                f"({global_paper_gsm}g × ¥{global_paper_per_tonne}/吨)"
            )
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
            sc = [
                'client','product','order_qty','box_l','box_w','box_h','flute_normalized',
                'forming_mode_label','face_layout_label','board_layout_label','board_material','order_date',
            ]
            st.dataframe(cn(sim[sc], sc), width="stretch")

# ========================
# TAB 2: 订单查找
# ========================
with tab2:
    st.markdown("<div class='section-label'>Order Retrieval</div>", unsafe_allow_html=True)
    st.subheader("订单搜索")
    st.caption("按客户、产品、批次、材料或备注检索历史工艺单。")
    if IS_PUBLIC_MODE:
        st.info("当前是公开脱敏库：可搜索客户分层标签和产品关键词；真实客户名仅在 internal 入口可查。")
    else:
        st.success("当前是内部库：可按真实客户名、产品、批次/单号、材料关键词查单。")
    
    year_values = sorted([int(y) for y in df['year'].dropna().unique()])
    flute_values = sorted([x for x in df['flute_normalized'].dropna().unique()])
    s1, s2, s3, s4 = st.columns([4, 1.2, 1.2, 1])
    with s1:
        placeholder = "如: 1L*12瓶, 农化客户, EB, P-817..." if IS_PUBLIC_MODE else "输入真实客户名、产品、批次/单号或材料"
        search = st.text_input("搜索", placeholder=placeholder, label_visibility="collapsed")
    with s2:
        flute_filter = st.selectbox("瓦型", ["全部"] + flute_values, label_visibility="collapsed")
    with s3:
        year_filter = st.selectbox("年份", ["全部"] + [str(y) for y in year_values], label_visibility="collapsed")
    with s4:
        search_btn = st.button("🔍 搜索", width="stretch")
    
    search_term = search.strip()
    has_filter = bool(search_term) or flute_filter != "全部" or year_filter != "全部" or search_btn

    if has_filter:
        mask = pd.Series(True, index=df.index)
        if search_term:
            search_cols = [
                c for c in ['product', 'client', 'batch_no', 'board_material', 'paper_spec', 'notes', 'file']
                if c in df.columns
            ]
            text_mask = pd.Series(False, index=df.index)
            for col in search_cols:
                text_mask |= df[col].astype(str).str.contains(search_term, na=False, case=False, regex=False)
            mask &= text_mask
        if flute_filter != "全部":
            mask &= df['flute_normalized'].eq(flute_filter)
        if year_filter != "全部":
            mask &= df['year'].eq(int(year_filter))
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
        sc = ['order_date','batch_no','client','product','order_qty','box_l','box_w','box_h',
              'flute_normalized','forming_mode_label','face_layout_label','board_layout_label',
              'total_gram','board_material','paper_spec']
        st.dataframe(cn(display[sc], sc), width="stretch", height=700)
        
        if st.button("📥 导出全部搜索结果"):
            csv = results.to_csv(index=False)
            st.download_button("下载 CSV", csv, f"search_{search[:20]}.csv", "text/csv")
    else:
        st.markdown("**最近订单预览**")
        recent = df.sort_values('order_date_parsed', ascending=False).head(25)
        sc = ['order_date','batch_no','client','product','order_qty','box_l','box_w','box_h',
              'flute_normalized','forming_mode_label','face_layout_label','board_layout_label','board_material']
        st.dataframe(cn(recent[sc], sc), width="stretch", height=420)

# ========================
# TAB 3: 高级分析
# ========================
with tab3:
    st.markdown("<div class='section-label'>Evaluation & Tools</div>", unsafe_allow_html=True)
    st.subheader("模型评估与运营工具")
    st.caption("把条件价格误差、工艺尺寸计算和原材料参数放在同一处复盘。")
    
    # Sub-tabs within advanced
    at0, at1, at2, at3, at4 = st.tabs(["📊 条件价格精度", "📊 数据统计", "📐 工艺尺寸", "💰 价格调整", "📋 数据浏览"])
    
    with at0:
        st.subheader("📊 条件价格模型精度评估")
        st.caption(
            "使用预核单已知实际板材面积验证材料单价与价格公式；"
            "该指标不验证成型、拼版或尺寸引擎准确性。"
        )
        
        if len(cost_df) < 3:
            st.info("预核单数据不足（需≥3条），无法评估精度。添加更多预核单后自动启用。")
        else:
            eval_df = cost_df[cost_df['material'].notna() & (cost_df['material'] != '')].copy()
            if len(eval_df) == 0:
                st.info("预核单缺少材料数据")
            else:
                eval_df['board_area'] = eval_df['size_w'] * eval_df['size_h'] / 1_000_000
                eval_df['actual_cpm'] = eval_df['unit_cost'] / eval_df['board_area']
                
                def map_flute_eval(row):
                    existing = row.get("flute_type")
                    if existing and str(existing).strip():
                        return str(existing).strip()
                    m = str(row.get("material", ""))
                    has_b = bool(re.search(r'\d+gB', m))
                    has_e = bool(re.search(r'\d+gE', m))
                    has_c = bool(re.search(r'\d+gC', m))
                    if has_b and has_e: return 'EB'
                    if has_b and has_c: return 'BC'
                    if has_e and not has_b: return '单E瓦'
                    if has_b and not has_e: return '单B瓦'
                    return 'EB'
                eval_df['flute_eval'] = eval_df.apply(map_flute_eval, axis=1)
                eval_df['estimated_cpm'] = eval_df['flute_eval'].map(lambda ft: fcb.get(ft, 1.5))
                eval_df['error'] = eval_df['actual_cpm'] - eval_df['estimated_cpm']
                eval_df['error_pct'] = (eval_df['error'] / eval_df['actual_cpm'] * 100)
                public_scale = eval_df['actual_cpm'].median() if IS_PUBLIC_MODE else 1
                public_scale = public_scale if public_scale and public_scale > 0 else 1
                
                # Per-flute metrics
                st.write("### 按瓦型精度")
                if IS_PUBLIC_MODE:
                    st.info("公开模式隐藏行级成本与合同价，只展示标准化指数、误差和样本结构。")
                flute_stats = []
                for ft in sorted(eval_df['flute_eval'].unique()):
                    s = eval_df[eval_df['flute_eval'] == ft]
                    n = len(s)
                    mape = s['error_pct'].abs().mean()
                    mae = s['error'].abs().mean()
                    n_ok = (s['error_pct'].abs() < 15).sum()
                    row = {
                        '瓦型': ft, '样本': n,
                        '平均误差': mape,
                        '±15%内': f"{n_ok}/{n}",
                        '评级': '🟢 条件通过' if mape < 15 else ('🟡 一般' if mape < 30 else '🔴 需改善')
                    }
                    if IS_PUBLIC_MODE:
                        row.update({
                            '基准指数': fcb.get(ft, 1.5) / public_scale * 100,
                            '实际中位指数': s['actual_cpm'].median() / public_scale * 100,
                            '绝对误差指数': mae / public_scale * 100,
                        })
                    else:
                        row.update({
                            'fcb基准': fcb.get(ft, 1.5),
                            '实际中位': s['actual_cpm'].median(),
                            '¥误差': mae,
                        })
                    flute_stats.append(row)
                
                stats_df = pd.DataFrame(flute_stats)
                if IS_PUBLIC_MODE:
                    st.dataframe(
                        stats_df.style.format({
                            '基准指数': '{:.0f}',
                            '实际中位指数': '{:.0f}',
                            '绝对误差指数': '{:.1f}',
                            '平均误差': '{:.1f}%',
                        }),
                        hide_index=True, width="stretch"
                    )
                else:
                    st.dataframe(
                        stats_df.style.format({'fcb基准': '¥{:.2f}', '实际中位': '¥{:.2f}', '平均误差': '{:.1f}%', '¥误差': '¥{:.2f}'}),
                        hide_index=True, width="stretch"
                    )
                
                # Insight
                eb_s = eval_df[eval_df['flute_eval'] == 'EB']
                if len(eb_s) > 0 and eb_s['error_pct'].abs().mean() < 15:
                    st.success(
                        f"EB 瓦（主力，{len(eb_s)}条）：已知材料面积条件下误差 "
                        f"{eb_s['error_pct'].abs().mean():.1f}%，条件评估通过。"
                    )
                bc_s = eval_df[eval_df['flute_eval'] == 'BC']
                if len(bc_s) > 0 and bc_s['error_pct'].abs().mean() > 30:
                    st.warning(f"BC 瓦（{len(bc_s)}条）：误差偏大，因同一瓦型下材料质量跨度大（普通纸→高耐破），需更多样本后细分。")
                
                st.divider()
                
                # Scatter by flute
                if IS_PUBLIC_MODE:
                    eval_df['estimated_index'] = eval_df['estimated_cpm'] / public_scale * 100
                    eval_df['actual_index'] = eval_df['actual_cpm'] / public_scale * 100
                    fig = px.scatter(
                        eval_df, x='estimated_index', y='actual_index',
                        color='flute_eval',
                        text=eval_df['product'].str[:12],
                        title=f"报价基准指数 vs 实际成本指数（{len(eval_df)}条脱敏预核单）",
                        labels={'estimated_index': '报价基准指数', 'actual_index': '实际成本指数', 'flute_eval': '瓦型'}
                    )
                    mm = min(eval_df['estimated_index'].min(), eval_df['actual_index'].min())
                    mx = max(eval_df['estimated_index'].max(), eval_df['actual_index'].max())
                else:
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
                st.caption("虚线=y=x：点越靠近虚线，报价基准越准。公开模式使用标准化指数，不展示真实成本价。")
                
                st.divider()
                st.write("**详细对比**")
                if IS_PUBLIC_MODE:
                    show_df = eval_df[['product','material','flute_eval','board_area','error_pct']].copy()
                    show_df.columns = ['样本','材料配置','瓦型','面积m²','误差%']
                    show_df = show_df.round({'面积m²':4,'误差%':1})
                else:
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
                if IS_PUBLIC_MODE:
                    cost_scale = gd['cost_per_m2'].median()
                    cost_scale = cost_scale if cost_scale and cost_scale > 0 else 1
                    gd = gd.copy()
                    gd['cost_index'] = gd['cost_per_m2'] / cost_scale * 100
                    fig = px.scatter(gd, x='total_gram', y='cost_index', color='flute_type',
                        trendline='ols', title="材料克重→成本指数",
                        labels={'total_gram':'克重(g/m²)','cost_index':'成本指数'})
                else:
                    fig = px.scatter(gd, x='total_gram', y='cost_per_m2', color='flute_type',
                        trendline='ols', title="材料克重→成本",
                        labels={'total_gram':'克重(g/m²)','cost_per_m2':'¥/m²'})
                st.plotly_chart(fig, width="stretch")
    
    with at2:
        st.subheader("📐 工艺尺寸计算")
        st.caption("员工确认公式自动计算；双拼方向、减量和特殊版面仍需人工复核。")
        pc1, pc2 = st.columns(2)
        with pc1:
            cl = st.number_input("箱长 L", 20, 3000, 370, key="bcl")
            cw = st.number_input("箱宽 W", 20, 3000, 280, key="bcw")
            ch = st.number_input("箱高 H", 20, 3000, 255, key="bch")
        with pc2:
            st.info(
                "成型方式决定单片公式与片数；双拼只是面纸或瓦楞的拼版方式，"
                "不能再当作成型方式。"
            )
        calc_process = render_sizing_controls("calc", expanded=True)

        if st.button("📐 计算", type="primary"):
            if not calc_process["ready"]:
                st.error(f"请先确认：{'、'.join(calc_process['problems'])}。")
            else:
                try:
                    calc_result = calculate_sizing(
                        length_mm=cl,
                        width_mm=cw,
                        height_mm=ch,
                        forming_mode=calc_process["forming_mode"],
                        face_layout=calc_process["face_layout"],
                        board_layout=calc_process["board_layout"],
                        long_allowance_mm=calc_process["long_allowance_mm"],
                        short_allowance_mm=calc_process["short_allowance_mm"],
                        face_adjust_long_mm=calc_process["face_adjust_long_mm"],
                        face_adjust_short_mm=calc_process["face_adjust_short_mm"],
                        face_pair_direction=calc_process["face_pair_direction"],
                        face_pair_reduction_mm=calc_process["face_pair_reduction_mm"],
                        board_pair_direction=calc_process["board_pair_direction"],
                        board_pair_reduction_mm=calc_process["board_pair_reduction_mm"],
                        board_delta_long_mm=calc_process["board_delta_long_mm"],
                        board_delta_short_mm=calc_process["board_delta_short_mm"],
                        final_face_sheet=calc_process["final_face_sheet"],
                        final_board_sheet=calc_process["final_board_sheet"],
                    )
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric(
                        "面纸单片",
                        f"{calc_result.face_piece.long_mm}×{calc_result.face_piece.short_mm}mm",
                    )
                    m2.metric(
                        "面纸拼版",
                        f"{calc_result.face_sheet.long_mm}×{calc_result.face_sheet.short_mm}mm",
                        delta=f"{calc_result.face_sheets_per_carton:g}张/箱",
                    )
                    m3.metric(
                        "瓦楞下料",
                        f"{calc_result.board_sheet.long_mm}×{calc_result.board_sheet.short_mm}mm",
                        delta=f"{calc_result.board_sheets_per_carton:g}张/箱",
                    )
                    m4.metric(
                        "单箱材料面积",
                        f"瓦楞 {calc_result.board_area_per_carton_m2:.4f}m²",
                        delta=f"面纸 {calc_result.face_area_per_carton_m2:.4f}m²",
                    )
                    st.caption(
                        f"单箱 {calc_result.face_piece_count_per_carton} 片；长边余量 "
                        f"{calc_result.long_allowance_mm}mm；短边余量 "
                        f"{calc_result.short_allowance_mm}mm；公式版本 "
                        f"{calc_result.formula_version}"
                    )
                    if calc_result.face_sheet != calc_result.suggested_face_sheet:
                        st.caption(
                            f"面纸公式建议 {calc_result.suggested_face_sheet.long_mm}×"
                            f"{calc_result.suggested_face_sheet.short_mm}mm；已采用人工最终尺寸。"
                        )
                    if calc_result.board_sheet != calc_result.suggested_board_sheet:
                        st.caption(
                            f"瓦楞公式建议 {calc_result.suggested_board_sheet.long_mm}×"
                            f"{calc_result.suggested_board_sheet.short_mm}mm；已采用人工最终尺寸。"
                        )
                    for warning in calc_result.warnings:
                        st.warning(f"工艺复核：{warning}")
                except ValueError as exc:
                    st.error(f"尺寸参数无法计算：{exc}")
    
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
            if IS_PUBLIC_MODE:
                st.info("公开模式不展示行级成本、合同价和供应商价格；内部模式可查看完整预核单参考。")
            else:
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
              'flute_normalized','forming_mode_label','face_layout_label','board_layout_label',
              'total_gram','board_material']
        st.dataframe(cn(fd[sc], sc).head(200), width="stretch", height=400)
        
        if IS_PUBLIC_MODE:
            st.info("公开模式关闭整库 CSV 下载；面试官可查看脱敏样本和聚合指标，内部运营数据不外发。")
        elif st.button("📥 导出全部(CSV)"):
            st.download_button("下载", fd.to_csv(index=False), "yiwei_all.csv", "text/csv")

# ============================================================================
# Tab 4: 🤖 AI 咨询师 — Multi-Agent 协作报价分析
# ============================================================================
with tab4:
    st.markdown("<div class='section-label'>Agentic Operations</div>", unsafe_allow_html=True)
    st.subheader("AI 顾问 · Multi-Agent 协作")
    st.caption("情报 → 分析 → 审查；情报层使用当前页面同一数据库模式。详见 [agents/README.md](https://github.com/wwwaaarrthur/yiwei-cost-engine/blob/main/agents/README.md)")

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
                db_path=DB,
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

# ============================================================================
# Tab 5: 📋 印前核稿验证 — 多模态质量门禁 (毅伟出口业务 3 单 5 次实战)
# ============================================================================
with tab5:
    st.markdown("<div class='section-label'>Quality Gate</div>", unsafe_allow_html=True)
    st.subheader("印前核稿验证 · 多模态质量门禁")
    st.caption(
        "毅伟出口业务实战 3 单 5 次 (CK1/CK2/CK3 系列) · "
        "客户 JPG 位图 vs 设计师 PDF 矢量跨模态字段对齐 · "
        "中/英/泰三语 OCR · 防错印整批高成本质量事故"
    )

    import json as _json
    import os as _os
    PREPRESS_DIR = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'data', 'prepress_reports')
    META_PATH = _os.path.join(PREPRESS_DIR, 'metadata.json')

    if not _os.path.exists(META_PATH):
        st.warning(f"⚠️ 元数据缺失: {META_PATH}")
    else:
        with open(META_PATH, 'r', encoding='utf-8') as _f:
            meta = _json.load(_f)
        cases = meta['cases']
        stats = meta['stats']
        narrative = meta['narrative']

        # ===== 业务总览 =====
        st.subheader("📊 实战业务总览")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("订单数", stats['total_orders'])
        col2.metric("核对次数", stats['total_reviews'])
        col3.metric("AI 端到端", stats['ai_end_to_end_time'])
        col4.metric("字段覆盖", stats['fields_per_review'])

        st.info(
            f"**核心价值**: {narrative['value_prop']}\n\n"
            f"**防御场景**: {narrative['failure_mode_prevented']}\n\n"
            f"**效率**: {narrative['speed_advantage']}"
        )

        # ===== 案例列表 =====
        st.divider()
        st.subheader("📁 案例库")

        case_df = []
        for c in cases:
            case_df.append({
                '订单号': c['order_id'],
                '日期': c['date'],
                '产品类型': c['product_type'],
                '批次': c['batch_code'],
                '客户分层': c['client_segment'],
                '核对轮次': c['review_round'],
                'OCR 语言': ' / '.join(c['ocr_languages']),
                '状态': {'passed': '✅ 通过', 'needs_correction': '🔄 待修改'}.get(c['status'], c['status']),
            })
        st.dataframe(pd.DataFrame(case_df), hide_index=True, width="stretch")

        # ===== 案例详情 =====
        st.divider()
        st.subheader("🔍 案例详情 + 完整核对报告")
        case_ids = [c['order_id'] for c in cases]
        selected = st.selectbox("选择案例", case_ids, index=len(case_ids) - 1, key="prepress_case")
        case = next(c for c in cases if c['order_id'] == selected)

        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**订单**: {case['order_id']}")
            st.markdown(f"**日期**: {case['date']}")
            st.markdown(f"**产品**: {case['product_type']}")
            st.markdown(f"**批次**: {case['batch_code']}")
            st.markdown(f"**客户分层**: {case['client_segment']}")
        with c2:
            st.markdown(f"**核对轮次**: 第 {case['review_round']} 次")
            st.markdown(f"**OCR 语言**: {' / '.join(case['ocr_languages'])}")
            st.markdown(f"**状态**: {case['status']}")
            st.markdown(f"**备注**: {case['notes']}")

        with st.expander("📂 涉及文件", expanded=False):
            for f in case['files']:
                st.markdown(f"- `{f}`")

        # ===== 完整报告 (X01233) =====
        if case.get('full_report'):
            report_path = _os.path.join(PREPRESS_DIR, case['full_report'])
            if _os.path.exists(report_path):
                st.divider()
                with st.expander(f"📄 完整核对报告 ({case['full_report']})", expanded=True):
                    with open(report_path, 'r', encoding='utf-8') as _rf:
                        st.markdown(_rf.read())
            else:
                st.warning(f"报告文件缺失: {report_path}")
        else:
            st.caption("（本案例为元数据展示, 完整报告仅 X01233 已公开 anonymized 版本）")

        # ===== 技术栈 + 简历叙事 =====
        st.divider()
        st.subheader("🛠️ 技术栈 + 简历叙事")
        tc1, tc2 = st.columns(2)
        with tc1:
            st.markdown("**多模态比对技术栈**")
            for t in stats['tools']:
                st.markdown(f"- {t}")
        with tc2:
            st.markdown("**简历叙事 (产销闭环)**")
            st.markdown("""
- **报价端** (本系统): 已知材料面积条件下 public fixture MAPE 15.1% / EB 9.9%，尺寸引擎单独验证
- **核稿端** (本 Tab): 3 单 5 次实战 / 27/27 字段全匹配 / 0 错误
- **闭环价值**: AI 不仅算成本, 还能验成品 — 防错印整批 ¥15,000-35,000 损失
            """)

        st.caption(
            "📌 **隐私架构**: 原始设计稿、客户名、制造商与脱敏映射保留在私有工作区；"
            "公开 repo 仅含 anonymized 元数据 + X01233 脱敏报告。"
            "脱敏规则示例见 `anonymize_mapping.example.json`。"
        )
