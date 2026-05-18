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
def cmargin(t): return {'vip': 0.10, 'medium': 0.14, 'small': 0.18}[t]

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
tab1, tab2, tab3 = st.tabs(["🏠 首页报价", "🔍 订单查找", "⚙️ 高级分析"])

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
                global_pp = st.number_input("面纸 ¥/m²", 0.1, 5.0, 0.45, 0.05, key="global_pp")
            with rc4:
                global_lam = st.number_input("覆膜费 ¥/只", 0.0, 2.0, 0.25, 0.05, key="global_lam")
    
    # Quote logic
    if quote_btn:
        tier_map = {'大客户': 'vip', '中等客户': 'medium', '小客户/农户': 'small'}
        tier = tier_map[ct_label]
        margin = cmargin(tier)
        
        # Board calc
        blong = 2*l + 2*w + 40
        bshort = 2*h + 2*w + 20  # 双拼
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
        
        print_cost = 0.12
        base = bc + pc + lc + pdc + print_cost
        cost = base * sf
        price = cost / (1 - margin)
        mp = margin * 100
        
        st.divider()
        st.subheader("💰 报价结果")
        
        r1, r2, r3 = st.columns(3)
        with r1:
            st.metric("单只成本", f"¥{cost:.2f}")
        with r2:
            st.metric("建议报价", f"¥{price:.2f}", delta=f"毛利¥{price-cost:.2f} ({mp:.0f}%)")
        with r3:
            st.metric("纸板尺寸", f"{blong}×{bshort}mm")
        
        # Comparable prices
        with st.expander("📊 成本明细 & 其他客户报价", expanded=False):
            st.write(f"**成本构成**: 纸板¥{bc:.2f} + 面纸¥{pc:.2f} + 覆膜¥{lc:.2f} + 垫片¥{pdc:.2f} + 印刷¥{print_cost:.2f} = ¥{base:.2f} × {sf} = ¥{cost:.2f}")
            st.write(f"**纸板**: {barea:.3f}m² × ¥{bp:.2f}/m² | **面纸**: {parea:.3f}m² × ¥{pp:.2f}/m²")
            tier_df = pd.DataFrame({
                '客户类型': ['大客户', '中等客户', '小客户/农户'],
                '毛利率': ['10%', '14%', '18%'],
                '报价': [f"¥{cost/0.90:.2f}", f"¥{cost/0.86:.2f}", f"¥{cost/0.82:.2f}"],
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
