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

from src.stock_data import fetch_stock_data, format_symbol, fetch_market_index_data
from src.etf_nav import get_valuation_or_nav
from src.news_fetcher import fetch_stock_news
from src.file_parser import parse_uploaded_file
from src.ai_analyzer import analyze_stock_with_ai

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

# Sidebar Layout
st.sidebar.title("📊 儀表板控制台")

# Stock Input Box
stock_input = st.sidebar.text_area(
    "股票與 ETF 清單 (以逗號分隔)",
    value=DEFAULT_STOCKS,
    height=100,
    help="請輸入 10 支台股代號（例如：2330.TW, 0050.TW）"
)

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

refresh_btn = st.sidebar.button("🔄 重新載入並分析 (清除快取)", use_container_width=True)
if refresh_btn:
    st.cache_data.clear()
    st.rerun()

# Parse uploaded file
attachment_text = ""
if uploaded_file is not None:
    attachment_text = parse_uploaded_file(uploaded_file)
    st.sidebar.success(f"已成功解析附件: {uploaded_file.name}")

# Main Header
st.title("📈 台股Dashboard")
st.caption("即時價量數據 | 9日 KD 技術指標 | ETF 折溢價比 / 個股本益比 | 24-48H 新聞 | AI 買賣評估")

# Parse Stock List with robust splitting for half/fullwidth comma and spaces
raw_symbols = [s.strip().upper() for s in re.split(r'[,，\s]+', stock_input) if s.strip()]
if not raw_symbols:
    st.warning("請在側邊欄輸入至少 1 支股票代號。")
    st.stop()

# Cache data loading using st.cache_data for speed (ttl=10 for fresh KD data)
@st.cache_data(ttl=10, show_spinner=False)
def load_all_stock_data(symbols_list):
    results = []
    for sym in symbols_list:
        clean_sym = sym.strip().upper()
        try:
            data = fetch_stock_data(clean_sym)
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

@st.cache_data(ttl=60, show_spinner=False)
def load_market_data():
    return fetch_market_index_data("^TWII")


# Market Index (^TWII) 10-Day Technical & Capital Overview
market_data = load_market_data()

with st.spinner("正在抓取最新價量數據、KD 指標與財經新聞..."):
    stock_dataset = load_all_stock_data(raw_symbols)

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

    table_rows.append({
        "股票代號": sd["symbol"],
        "股票名稱": sd["name"],
        "資料日期": sd.get("latest_date", "N/A"),
        "現價": close_str,
        "漲跌幅": change_str,
        "9K": k_str,
        "9D": d_str,
        "數據校驗": validation_badge,
        "KD策略建議狀態": ai.get("strategy_state", "【觀望】"),
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
    strategy_state = ai.get("strategy_state", "【觀望】")
    risk_text = ai.get("risk_control", "設移動停利")
    
    expander_title = f"{rating_icon} 【{sd['symbol']}】{sd['name']} | 現價: ${sd['latest_close']:.2f} ({sd['change_pct']:+.2f}%) | KD: {strategy_state} | 風控: {risk_text} | AI評級: {rating}"
    
    with st.expander(expander_title, expanded=False):
        c1, c2 = st.columns([0.55, 0.45])
        
        with c1:
            st.markdown("##### 📈 歷史股價與 9日 KD 走勢")
            fig = plot_stock_chart(sd["df"], f"{sd['symbol']} {sd['name']}")
            st.plotly_chart(fig, use_container_width=True)
            
        with c2:
            st.markdown("##### 🤖 雙軌決策系統與 AI 綜合研判")
            st.warning(f"**🎯 軌道一：KD 策略建議狀態**: {strategy_state}  \n**🛡️ 軌道二：風控與連跌策略**: {risk_text}")
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
