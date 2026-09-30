import sys
if sys.stdout and getattr(sys.stdout, 'encoding', None) != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import re
import time
from datetime import datetime

from src.stock_data import fetch_stock_data, format_symbol, fetch_market_index_data, get_stock_name, fetch_kd_extremes_screener
from src.etf_nav import get_valuation_or_nav
from src.news_fetcher import fetch_stock_news
from src.file_parser import parse_uploaded_file
from src.ai_analyzer import analyze_stock_with_ai
from src.strategy_engine import screen_kd_extremes

# Set page config
st.set_page_config(
    page_title="台股Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS styling
st.markdown("""
<style>
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 15px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        text-align: center;
    }
    .badge-buy {
        background-color: #28a745;
        color: white;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: bold;
        display: inline-block;
    }
    .badge-hold {
        background-color: #ffc107;
        color: #212529;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: bold;
        display: inline-block;
    }
    .badge-sell {
        background-color: #dc3545;
        color: white;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: bold;
        display: inline-block;
    }
    .news-link {
        color: #0066cc;
        text-decoration: none;
        font-weight: 500;
    }
    .news-link:hover {
        text-decoration: underline;
    }
</style>
""", unsafe_allow_html=True)

DEFAULT_STOCKS = "2330.TW, 2317.TW, 2454.TW, 2308.TW, 2881.TW, 2882.TW, 0050.TW, 0056.TW, 00878.TW, 00919.TW"

def plot_stock_chart(df: pd.DataFrame, title: str) -> go.Figure:
    """Create a Plotly chart with Price/Candlestick and KD Indicators Subplot"""
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        subplot_titles=(f"{title} 走勢圖", "9日 KD 技術指標"),
        row_heights=[0.65, 0.35]
    )
    
    # Row 1: Candlestick or Line Chart
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df['Open'],
            high=df['High'],
            low=df['Low'],
            close=df['Close'],
            name="K線圖",
            increasing_line_color="#d62728", # Taiwan Stock red for up
            decreasing_line_color="#2ca02c"  # Taiwan Stock green for down
        ),
        row=1, col=1
    )
    
    # Row 2: K and D lines
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df['K'],
            mode='lines',
            name='K (9日)',
            line=dict(color='#1f77b4', width=2)
        ),
        row=2, col=1
    )
    
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df['D'],
            mode='lines',
            name='D (9日)',
            line=dict(color='#ff7f0e', width=2)
        ),
        row=2, col=1
    )
    
    # Add Overbought (>80) and Oversold (<20) reference lines
    fig.add_hline(y=80, line_dash="dash", line_color="gray", row=2, col=1, annotation_text="超買 80")
    fig.add_hline(y=20, line_dash="dash", line_color="gray", row=2, col=1, annotation_text="超賣 20")
    
    fig.update_layout(
        height=500,
        margin=dict(l=20, r=20, t=40, b=20),
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    fig.update_yaxes(title_text="股價 (TWD)", row=1, col=1)
    fig.update_yaxes(title_text="KD 值", range=[0, 100], row=2, col=1)
    
    return fig

def plot_market_index_chart(df: pd.DataFrame) -> go.Figure:
    """Create compact Plotly chart for Taiwan Weighted Index (^TWII) with Close Points and KD Indicators"""
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.10,
        subplot_titles=("加權指數收盤點位走勢", "大盤 9日 KD 指標"),
        row_heights=[0.60, 0.40]
    )
    
    x_axis = df["Date_str"] if "Date_str" in df.columns else [d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)[:10] for d in df.index]
    
    # Row 1: Line chart with markers and fill
    fig.add_trace(
        go.Scatter(
            x=x_axis,
            y=df["Close"],
            mode="lines+markers",
            name="加權指數",
            line=dict(color="#d62728", width=2.5),
            marker=dict(size=6, color="#d62728"),
            fill="tozeroy",
            fillcolor="rgba(214, 39, 40, 0.08)"
        ),
        row=1, col=1
    )
    
    # Row 2: K and D lines
    fig.add_trace(
        go.Scatter(
            x=x_axis,
            y=df["K"],
            mode="lines+markers",
            name="大盤 9K",
            line=dict(color="#1f77b4", width=2),
            marker=dict(size=5)
        ),
        row=2, col=1
    )
    
    fig.add_trace(
        go.Scatter(
            x=x_axis,
            y=df["D"],
            mode="lines+markers",
            name="大盤 9D",
            line=dict(color="#ff7f0e", width=2),
            marker=dict(size=5)
        ),
        row=2, col=1
    )
    
    fig.add_hline(y=80, line_dash="dash", line_color="gray", row=2, col=1, annotation_text="超買 80")
    fig.add_hline(y=20, line_dash="dash", line_color="gray", row=2, col=1, annotation_text="超賣 20")
    
    fig.update_layout(
        height=380,
        margin=dict(l=20, r=20, t=35, b=20),
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    fig.update_yaxes(title_text="指數點位", row=1, col=1)
    fig.update_yaxes(title_text="KD 值", range=[0, 100], row=2, col=1)
    return fig

# Initialize session_state
if "last_refresh_time" not in st.session_state:
    st.session_state["last_refresh_time"] = time.time()
if "last_stock_input" not in st.session_state:
    st.session_state["last_stock_input"] = DEFAULT_STOCKS
if "refresh_counter" not in st.session_state:
    st.session_state["refresh_counter"] = 0

# Sidebar Layout
st.sidebar.title("📊 儀表板控制台")

# Stock Input Box inside Form (pressing Enter inside text input natively triggers form submit)
with st.sidebar.form(key="stock_search_form", clear_on_submit=False):
    stock_input = st.text_area(
        "【輸入查詢股號】",
        value=st.session_state.get("last_stock_input", DEFAULT_STOCKS),
        height=90,
        help="請輸入台股代號（例如：2330.TW, 0050.TW），多檔以逗號分隔。在文字框按 Enter 或點擊下方按鈕即可查詢"
    )
    submit_btn = st.form_submit_button("🔍 查詢 / 同步最新即時行情 (Enter)", use_container_width=True)

# Dedicated Force Refresh Button
force_refresh_btn = st.sidebar.button("🔄 同步最新即時行情 (強制向外重抓)", use_container_width=True)

# Gemini API Key Input
api_key = st.sidebar.text_input(
    "Gemini API Key (選填)",
    type="password",
    value=os.environ.get("GEMINI_API_KEY", ""),
    help="輸入 Google Gemini API Key 以啟用 LLM 分析；若未填寫將自動採用智慧型啟發式規則引擎評估。"
)

# Attachment Uploader
uploaded_file = st.sidebar.file_uploader(
    "上傳策略或研報附件 (PDF / CSV / TXT)",
    type=["pdf", "csv", "txt", "md"],
    help="上傳後，AI 買賣評估將結合附件內容進行綜合分析。"
)

# Detect if Enter / Submit / Force Refresh / Value Change occurred
force_refresh = False
if submit_btn or force_refresh_btn:
    force_refresh = True

if stock_input != st.session_state.get("last_stock_input"):
    force_refresh = True
    st.session_state["last_stock_input"] = stock_input

if force_refresh:
    st.cache_data.clear()
    st.session_state["last_refresh_time"] = time.time()
    st.session_state["refresh_counter"] = st.session_state.get("refresh_counter", 0) + 1

# Current Cache Buster Token
current_rf_token = st.session_state["last_refresh_time"]
sync_time_str = datetime.fromtimestamp(current_rf_token).strftime("%H:%M:%S")

# Parse uploaded file
attachment_text = ""
if uploaded_file is not None:
    attachment_text = parse_uploaded_file(uploaded_file)
    st.sidebar.success(f"已成功解析附件: {uploaded_file.name}")

# Main Header
st.title("📈 台股Dashboard")
st.caption(f"即時價量數據 | 9日 KD 技術指標 | ETF 折溢價比 / 個股本益比 | 24-48H 新聞 | AI 買賣評估 (最後同步：{sync_time_str})")

# Toast notification for screener
if "screener_msg" in st.session_state:
    st.toast(st.session_state["screener_msg"], icon="🎯")
    del st.session_state["screener_msg"]

# Parse Stock List with robust splitting for half/fullwidth comma and spaces
raw_symbols = [s.strip().upper() for s in re.split(r'[,，\s]+', stock_input) if s.strip()]
if not raw_symbols:
    st.warning("請在側邊欄輸入至少 1 支股票代號。")
    st.stop()

# Cache data loading using st.cache_data (TTL=300s, with refresh_time cache buster)
@st.cache_data(ttl=300, show_spinner=False)
def load_all_stock_data(symbols_list, refresh_time=None):
    results = []
    for sym in symbols_list:
        clean_sym = sym.strip().upper()
        try:
            data = fetch_stock_data(clean_sym, refresh_time=refresh_time)
            if data.get("success"):
                try:
                    val_info = get_valuation_or_nav(data["symbol"], data["latest_close"], data.get("info"))
                    data["valuation_info"] = val_info
                except Exception:
                    data["valuation_info"] = {"display_text": "N/A", "label": "本益比", "value": None}
                
                try:
                    news = fetch_stock_news(data["symbol"], data["name"])
                    data["news"] = news
                except Exception:
                    data["news"] = []
            results.append(data)
        except Exception as e:
            results.append({
                "symbol": clean_sym,
                "raw_symbol": clean_sym,
                "name": get_stock_name(clean_sym),
                "success": False,
                "error": f"抓取 {clean_sym} 發生例外: {str(e)}"
            })
    return results

@st.cache_data(ttl=300, show_spinner=False)
def load_market_data(refresh_time=None):
    return fetch_market_index_data("^TWII", refresh_time=refresh_time)


# Market Index (^TWII) 10-Day Technical & Capital Overview
market_data = load_market_data(refresh_time=current_rf_token)

with st.spinner("正在抓取最新價量數據、KD 指標與財經新聞..."):
    stock_dataset = load_all_stock_data(raw_symbols, refresh_time=current_rf_token)

# Perform AI Evaluation for each stock
analyzed_data = []
buy_count = 0
hold_count = 0
sell_count = 0

for data in stock_dataset:
    if not data.get("success"):
        analyzed_data.append({
            "stock_data": data,
            "ai_result": {
                "rating": "中立",
                "confidence": "低",
                "reason": "資料抓取失敗",
                "citations": [],
                "engine": "N/A"
            }
        })
        hold_count += 1
        continue
        
    ai_res = analyze_stock_with_ai(
        stock_info=data,
        valuation_info=data["valuation_info"],
        news_items=data["news"],
        attachment_text=attachment_text,
        api_key=api_key,
        market_data=market_data
    )
    
    rating = ai_res.get("rating", "中立")
    if rating == "買進":
        buy_count += 1
    elif rating == "賣出":
        sell_count += 1
    else:
        hold_count += 1
        
    analyzed_data.append({
        "stock_data": data,
        "ai_result": ai_res
    })

# Summary Metric Cards
m_col1, m_col2, m_col3, m_col4 = st.columns(4)
with m_col1:
    st.metric("分析總檔數", f"{len(raw_symbols)} 支")
with m_col2:
    st.metric("🟢 建議買進", f"{buy_count} 支")
with m_col3:
    st.metric("🟡 建議中立", f"{hold_count} 支")
with m_col4:
    st.metric("🔴 建議賣出", f"{sell_count} 支")

st.divider()

# Market Index Display
if market_data.get("success"):
    with st.expander("📊 台股加權指數 (^TWII) 近 10 日技術與資金面一覽", expanded=True):
        m_tab_col, m_chart_col = st.columns([0.55, 0.45])
        with m_tab_col:
            st.markdown("##### 📋 近 10 個交易日明細紀錄")
            st.dataframe(
                market_data["table_df"],
                use_container_width=True,
                hide_index=True
            )
        with m_chart_col:
            st.markdown("##### 📈 點位走勢與 9日 KD 雙線圖")
            fig_market = plot_market_index_chart(market_data["df_raw"])
            st.plotly_chart(fig_market, use_container_width=True)
    st.divider()

# =====================================================================================
# 二、獨立【🎯 Yahoo 官方全市場 KD 極端值快速選股看板】
# =====================================================================================
with st.expander("🎯 Yahoo 官方全市場 KD 極端值快速選股看板", expanded=True):
    col_hdr1, col_hdr2, col_hdr3 = st.columns([0.50, 0.30, 0.20])
    with col_hdr1:
        st.markdown("**即時選股母池**：台股上市櫃成交量前 100~150 檔權值與熱門活躍標的 (台灣50+中型100+熱門ETF)")
    with col_hdr2:
        expand_screener = st.checkbox("🔍 擴大掃描至前 300 檔", value=False, key="chk_expand_screener_main")
    with col_hdr3:
        btn_refresh_screener = st.button("🔄 立即重新掃描", key="btn_refresh_screener_main", use_container_width=True)

    scan_limit = 300 if expand_screener else 150
    screener_res = fetch_kd_extremes_screener(
        limit=scan_limit,
        expanded=expand_screener,
        force_refresh=btn_refresh_screener
    )

    oversold_items = screener_res.get("oversold", [])
    overbought_items = screener_res.get("overbought", [])
    total_scanned = screener_res.get("total_scanned", 0)
    elapsed_sec = screener_res.get("elapsed_seconds", 0)

    st.caption(f"⚡ 掃描完成：共掃描 **{total_scanned}** 檔活躍標的，耗時 **{elapsed_sec}** 秒（快取有效期限 120 秒）")

    # 兩大子分頁
    tab_ovs, tab_ovb = st.tabs([
        f"🟢【超賣金叉區 (K > D 且 K < 20)】({len(oversold_items)} 檔)",
        f"🔴【超買死叉區 (K < D 且 K > 80)】({len(overbought_items)} 檔)"
    ])

    def render_screener_table(items, tab_type="oversold"):
        if not items:
            if tab_type == "oversold":
                st.info("目前全市場活躍標的無符合【超賣金叉：K > D 且 K < 20】之標的。")
            else:
                st.info("目前全市場活躍標的無符合【超買死叉：K < D 且 K > 80】之標的。")
            return

        all_syms = [it["symbol"] for it in items]
        col_t1, col_t2 = st.columns([0.75, 0.25])
        with col_t1:
            if tab_type == "oversold":
                st.markdown("💡 **策略特性**：跌深築底、轉折向上，具備跌深反彈與左側安全邊際。")
            else:
                st.markdown("💡 **策略特性**：高檔過熱、動能竭盡，短線拉回風險偏高。")
        with col_t2:
            if st.button(f"➕ 一鍵全加入查詢 ({len(items)} 檔)", key=f"add_all_{tab_type}", use_container_width=True):
                cur_input = st.session_state.get("last_stock_input", DEFAULT_STOCKS)
                cur_tokens = [s.strip().upper() for s in re.split(r'[,，\s]+', cur_input) if s.strip()]
                new_tokens = list(cur_tokens)
                for s in all_syms:
                    if s not in new_tokens and s.replace(".TW", "").replace(".TWO", "") not in new_tokens:
                        new_tokens.append(s)
                st.session_state["last_stock_input"] = ", ".join(new_tokens)
                st.cache_data.clear()
                st.session_state["last_refresh_time"] = time.time()
                st.session_state["screener_msg"] = f"已將 {len(all_syms)} 檔標的加入查詢清單！"
                st.rerun()

        # 表格欄位: [股票代號] | [股票名稱] | [現價] | [今日漲跌幅] | [9K] | [9D] | [狀態標記] | [快速加入查詢]
        h1, h2, h3, h4, h5, h6, h7, h8 = st.columns([1.1, 1.2, 0.9, 1.1, 0.8, 0.8, 2.2, 1.2])
        h1.markdown("**股票代號**")
        h2.markdown("**股票名稱**")
        h3.markdown("**現價**")
        h4.markdown("**今日漲跌幅**")
        h5.markdown("**9K**")
        h6.markdown("**9D**")
        h7.markdown("**狀態標記**")
        h8.markdown("**快速加入查詢**")

        st.markdown("<hr style='margin: 4px 0 8px 0; border-color: #31333f;'>", unsafe_allow_html=True)

        for idx, it in enumerate(items):
            r1, r2, r3, r4, r5, r6, r7, r8 = st.columns([1.1, 1.2, 0.9, 1.1, 0.8, 0.8, 2.2, 1.2])
            sym = it["symbol"]
            nm = it["name"]
            px = f"${it['latest_close']:.2f}"
            chg = it["change_pct"]
            sign = "+" if chg > 0 else ""
            chg_str = f"{sign}{chg:.2f}%"
            k_val = f"{it['k']:.1f}"
            d_val = f"{it['d']:.1f}"
            tag = it["tag"]

            r1.write(f"**{sym}**")
            r2.write(f"**{nm}**")
            r3.write(px)
            r4.write(f"{chg_str}")
            r5.write(f"**{k_val}**")
            r6.write(f"**{d_val}**")
            r7.write(f"{tag}")

            cur_tokens = [s.strip().upper() for s in re.split(r'[,，\s]+', st.session_state.get("last_stock_input", DEFAULT_STOCKS)) if s.strip()]
            is_already_added = (sym in cur_tokens or sym.replace(".TW", "").replace(".TWO", "") in cur_tokens)

            if is_already_added:
                r8.markdown("<span style='color: #a0aec0; font-size: 11px;'>✅ 已在清單</span>", unsafe_allow_html=True)
            else:
                if r8.button("➕ 加入查詢", key=f"btn_add_{tab_type}_{sym}_{idx}", use_container_width=True):
                    new_tokens = list(cur_tokens) + [sym]
                    st.session_state["last_stock_input"] = ", ".join(new_tokens)
                    st.cache_data.clear()
                    st.session_state["last_refresh_time"] = time.time()
                    st.session_state["screener_msg"] = f"已將 {sym} {nm} 加入查詢清單！"
                    st.rerun()

    with tab_ovs:
        render_screener_table(oversold_items, "oversold")

    with tab_ovb:
        render_screener_table(overbought_items, "overbought")

st.divider()


# Section 1: Overview Table
st.subheader("📋 股票評估一覽表 (雙軌決策系統：KD 常規矩陣 + 連跌風控)")

table_rows = []
for item in analyzed_data:
    sd = item["stock_data"]
    ai = item["ai_result"]
    
    if not sd.get("success"):
        table_rows.append({
            "股票代號": sd.get("symbol", sd.get("raw_symbol")),
            "股票名稱": "未知",
            "資料日期": "N/A",
            "現價": "N/A",
            "漲跌幅": "N/A",
            "9K": "N/A",
            "9D": "N/A",
            "數據校驗": "❌ 數據異常",
            "KD策略建議狀態": "資料異常",
            "風控與連跌策略": "N/A",
            "折溢價比/估值": "N/A",
            "成交量 (張)": "0 張",
            "AI評級": "未知",
            "綜合權衡理由": sd.get("error", "失敗")
        })
        continue
        
    rating = ai.get("rating", "中立")
    rating_badge = f"🟢 {rating}" if rating == "買進" else (f"🔴 {rating}" if rating == "賣出" else f"🟡 {rating}")
    
    # Safe NaN protection for price & change percentage
    l_close = sd.get('latest_close')
    c_pct = sd.get('change_pct')
    close_str = f"{l_close:.2f}" if (l_close is not None and not pd.isna(l_close)) else "N/A"
    change_str = f"{c_pct:+.2f}%" if (c_pct is not None and not pd.isna(c_pct)) else "+0.00%"
    
    is_verified = sd.get("is_verified", True)
    if is_verified:
        validation_badge = "✅ Yahoo官方源"
    else:
        validation_badge = "⚠️ 自算備援"

    k_val = sd.get('k')
    d_val = sd.get('d')
    k_str = f"{k_val:.2f}" if (k_val is not None and round(k_val, 1) != round(k_val, 2)) else (f"{k_val:.1f}" if k_val is not None else "N/A")
    d_str = f"{d_val:.2f}" if (d_val is not None and round(d_val, 1) != round(d_val, 2)) else (f"{d_val:.1f}" if d_val is not None else "N/A")

    raw_state = ai.get("strategy_state", "【持股觀望】")
    if "鎖利加碼" in raw_state or "分批加碼" in raw_state or "偏多持股" in raw_state or "續抱" in raw_state:
        state_badge = f"🟢 {raw_state}"
    elif "領息觀望" in raw_state:
        state_badge = f"🟡 {raw_state}"
    elif "禁止接刀" in raw_state or "獲利了結" in raw_state or "減碼" in raw_state:
        state_badge = f"🔴 {raw_state}"
    else:
        state_badge = f"⚪ {raw_state}"

    table_rows.append({
        "股票代號": sd["symbol"],
        "股票名稱": sd["name"],
        "資料日期": sd.get("latest_date", "N/A"),
        "現價": close_str,
        "漲跌幅": change_str,
        "9K": k_str,
        "9D": d_str,
        "數據校驗": validation_badge,
        "KD策略建議狀態": state_badge,
        "風控與連跌策略": ai.get("risk_control", "設移動停利"),
        "折溢價比/估值": sd["valuation_info"]["display_text"],
        "成交量 (張)": sd.get("volume_display", "0 張"),
        "AI評級": rating_badge,
        "綜合權衡理由": ai.get("reason", "")
    })

df_table = pd.DataFrame(table_rows)

# Render Styled Streamlit Dataframe
st.dataframe(
    df_table,
    use_container_width=True,
    column_config={
        "股票代號": st.column_config.TextColumn("股票代號", width="small"),
        "股票名稱": st.column_config.TextColumn("股票名稱", width="small"),
        "資料日期": st.column_config.TextColumn("資料日期", width="small"),
        "現價": st.column_config.TextColumn("現價", width="small"),
        "漲跌幅": st.column_config.TextColumn("漲跌幅", width="small"),
        "9K": st.column_config.TextColumn("9K", width="small"),
        "9D": st.column_config.TextColumn("9D", width="small"),
        "數據校驗": st.column_config.TextColumn("數據校驗", width="medium"),
        "KD策略建議狀態": st.column_config.TextColumn("KD策略建議狀態 (軌道一)", width="medium"),
        "風控與連跌策略": st.column_config.TextColumn("風控與連跌策略 (軌道二)", width="large"),
        "折溢價比/估值": st.column_config.TextColumn("折溢價比/估值", width="medium"),
        "成交量 (張)": st.column_config.TextColumn("成交量 (張)", width="medium"),
        "AI評級": st.column_config.TextColumn("AI評級", width="small"),
        "綜合權衡理由": st.column_config.TextColumn("綜合權衡理由", width="large"),
    },
    hide_index=True
)

st.divider()

# Section 2: Detailed Stock Cards (Expandable View)
st.subheader("🔍 各個股 / ETF 歷史圖表與新聞詳情")

for item in analyzed_data:
    sd = item["stock_data"]
    ai = item["ai_result"]
    
    if not sd.get("success"):
        with st.expander(f"⚠️ {sd.get('raw_symbol')} - 資料抓取失敗"):
            st.error(sd.get("error"))
        continue
        
    rating = ai.get("rating", "中立")
    rating_icon = "🟢" if rating == "買進" else ("🔴" if rating == "賣出" else "🟡")
    strategy_state = ai.get("strategy_state", "【持股觀望】")
    risk_text = ai.get("risk_control", "設移動停利")
    
    card_state_badge = strategy_state
    if not any(strategy_state.startswith(icon) for icon in ["🟢", "🟡", "🔴", "⚪"]):
        if "鎖利加碼" in strategy_state or "分批加碼" in strategy_state or "偏多持股" in strategy_state or "續抱" in strategy_state:
            card_state_badge = f"🟢 {strategy_state}"
        elif "領息觀望" in strategy_state:
            card_state_badge = f"🟡 {strategy_state}"
        elif "禁止接刀" in strategy_state or "獲利了結" in strategy_state or "減碼" in strategy_state:
            card_state_badge = f"🔴 {strategy_state}"
        else:
            card_state_badge = f"⚪ {strategy_state}"
    
    expander_title = f"{rating_icon} 【{sd['symbol']}】{sd['name']} | 現價: ${sd['latest_close']:.2f} ({sd['change_pct']:+.2f}%) | KD: {card_state_badge} | 風控: {risk_text} | AI評級: {rating}"
    
    with st.expander(expander_title, expanded=False):
        c1, c2 = st.columns([0.55, 0.45])
        
        with c1:
            st.markdown("##### 📈 歷史股價與 9日 KD 走勢")
            fig = plot_stock_chart(sd["df"], f"{sd['symbol']} {sd['name']}")
            st.plotly_chart(fig, use_container_width=True)
            
        with c2:
            st.markdown("##### 🤖 雙軌決策系統與 AI 綜合研判")
            st.warning(f"**🎯 軌道一：KD 策略建議狀態**: {card_state_badge}  \n**🛡️ 軌道二：風控與連跌策略**: {risk_text}")
            
            # 若觸發【空方鈍化／禁止接刀】，明確提示停損點與防破底風控
            if "禁止接刀" in strategy_state:
                st.error("🚨 **【空方鈍化／禁止接刀】風控警戒**：指標處於低檔鈍化，空方主導嚴禁盲目攤平，跌破前低仍須紀律停損。  \n⚠️ **防破底風控**：留意空方慣性破底，未見長下影線或爆量前切勿進場！")
            elif "鎖利加碼" in strategy_state:
                st.success("💎 **【低檔轉強／鎖利加碼】固定收益優勢**：債券跌深出現低檔黃金交叉，兼具高殖利率鎖利與反彈資本利得空間，啟動分批加碼。")
                
            st.info(f"**🤖 AI 評估結論**: {rating} ({ai.get('confidence')}信心) | **評估引擎**: {ai.get('engine')}")
            st.write(f"**💡 綜合權衡理由**: {ai.get('reason')}")
            
            st.markdown("##### 📰 近 24-48 小時新聞與引用來源")
            news_list = sd.get("news", [])
            citations = ai.get("citations", [])
            
            if not news_list:
                st.caption("近 24-48 小時內暫無新聞。")
            else:
                for idx, n in enumerate(news_list, 1):
                    # Check if this news item was cited by AI
                    is_cited = any(c.get("link") == n.get("link") or c.get("title") == n.get("title") for c in citations)
                    cite_tag = "📌 [AI引用] " if is_cited else ""
                    
                    st.markdown(
                        f"{idx}. {cite_tag}**[{n['title']}]({n['link']})**  \n"
                        f"   <small style='color:gray;'>來源: {n['source']} | 發布時間: {n['published']}</small>",
                        unsafe_allow_html=True
                    )
                    st.write("")
                    
            if attachment_text:
                with st.popover("📄 檢視參考附件內容"):
                    st.text(attachment_text[:1000] + ("..." if len(attachment_text) > 1000 else ""))

st.markdown("---")
st.caption("免責聲明：本儀表板提供之技術指標與 AI 評估僅供參考，不構成任何投資建議。投資人應獨立思考並自負投資風險。")
