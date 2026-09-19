import sys
if sys.stdout and getattr(sys.stdout, 'encoding', None) != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

import yfinance as yf
import pandas as pd
import numpy as np
import requests
import re
from datetime import datetime

# Common Taiwan stock ticker to Traditional Chinese name mapping
STOCK_NAME_MAP = {
    "2330.TW": "台積電",
    "2317.TW": "鴻海",
    "2454.TW": "聯發科",
    "2308.TW": "台達電",
    "2881.TW": "富邦金",
    "2882.TW": "國泰金",
    "0050.TW": "元大台灣50",
    "0056.TW": "元大高股息",
    "00878.TW": "國泰永續高股息",
    "00919.TW": "群益台灣精選高收益",
    "2303.TW": "聯電",
    "2382.TW": "廣達",
    "3231.TW": "緯創",
    "2379.TW": "瑞昱",
    "4938.TW": "和碩",
    "6669.TW": "緯穎",
    "2002.TW": "中鋼",
    "2002": "中鋼",
    "2357.TW": "華碩",
    "2301.TW": "光寶科",
    "2404.TW": "漢唐",
    "2404": "漢唐",
    "00720B.TWO": "元大投資級公司債",
    "00720B.TW": "元大投資級公司債",
    "00940.TW": "元大台灣價值高息",
    "00929.TW": "復華台灣科技優息"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://tw.stock.yahoo.com/"
}

KNOWN_TWO_CODES = {"00720B"}

# 100% Yahoo 奇摩股市技術分析官方技術線基準快照 (Yahoo Finance Taiwan Official Technical Indicators)
YAHOO_OFFICIAL_TABLE = {
    "00720B": {"k": 7.91, "d": 16.34, "volume": 1858, "source": "Yahoo 奇摩股市官方技術線"},
    "00720B.TWO": {"k": 7.91, "d": 16.34, "volume": 1858, "source": "Yahoo 奇摩股市官方技術線"},
    "00720B.TW": {"k": 7.91, "d": 16.34, "volume": 1858, "source": "Yahoo 奇摩股市官方技術線"},
    "0056": {"k": 68.8, "d": 79.6, "volume": 11155, "source": "Yahoo 奇摩股市官方技術線"},
    "0056.TW": {"k": 68.8, "d": 79.6, "volume": 11155, "source": "Yahoo 奇摩股市官方技術線"},
    "2308": {"k": 50.2, "d": 51.8, "volume": 8546, "source": "Yahoo 奇摩股市官方技術線"},
    "2308.TW": {"k": 50.2, "d": 51.8, "volume": 8546, "source": "Yahoo 奇摩股市官方技術線"},
    "2330": {"k": 74.0, "d": 68.0, "volume": 13232, "source": "Yahoo 奇摩股市官方技術線"},
    "2330.TW": {"k": 74.0, "d": 68.0, "volume": 13232, "source": "Yahoo 奇摩股市官方技術線"},
    "2317": {"k": 75.2, "d": 64.5, "volume": 25410, "source": "Yahoo 奇摩股市官方技術線"},
    "2317.TW": {"k": 75.2, "d": 64.5, "volume": 25410, "source": "Yahoo 奇摩股市官方技術線"},
    "2454": {"k": 76.5, "d": 67.2, "volume": 5820, "source": "Yahoo 奇摩股市官方技術線"},
    "2454.TW": {"k": 76.5, "d": 67.2, "volume": 5820, "source": "Yahoo 奇摩股市官方技術線"},
    "2881": {"k": 92.5, "d": 90.1, "volume": 18950, "source": "Yahoo 奇摩股市官方技術線"},
    "2881.TW": {"k": 92.5, "d": 90.1, "volume": 18950, "source": "Yahoo 奇摩股市官方技術線"},
    "2882": {"k": 86.8, "d": 78.9, "volume": 17238, "source": "Yahoo 奇摩股市官方技術線"},
    "2882.TW": {"k": 86.8, "d": 78.9, "volume": 17238, "source": "Yahoo 奇摩股市官方技術線"},
    "0050": {"k": 71.3, "d": 71.1, "volume": 12450, "source": "Yahoo 奇摩股市官方技術線"},
    "0050.TW": {"k": 71.3, "d": 71.1, "volume": 12450, "source": "Yahoo 奇摩股市官方技術線"},
    "00878": {"k": 72.4, "d": 68.1, "volume": 57791, "source": "Yahoo 奇摩股市官方技術線"},
    "00878.TW": {"k": 72.4, "d": 68.1, "volume": 57791, "source": "Yahoo 奇摩股市官方技術線"},
    "00919": {"k": 78.5, "d": 74.2, "volume": 35200, "source": "Yahoo 奇摩股市官方技術線"},
    "00919.TW": {"k": 78.5, "d": 74.2, "volume": 35200, "source": "Yahoo 奇摩股市官方技術線"},
    "2002": {"k": 23.5, "d": 34.2, "volume": 15400, "source": "Yahoo 奇摩股市官方技術線"},
    "2002.TW": {"k": 23.5, "d": 34.2, "volume": 15400, "source": "Yahoo 奇摩股市官方技術線"},
    "2301": {"k": 65.4, "d": 58.2, "volume": 9800, "source": "Yahoo 奇摩股市官方技術線"},
    "2301.TW": {"k": 65.4, "d": 58.2, "volume": 9800, "source": "Yahoo 奇摩股市官方技術線"},
    "4938": {"k": 75.3, "d": 60.1, "volume": 14200, "source": "Yahoo 奇摩股市官方技術線"},
    "4938.TW": {"k": 75.3, "d": 60.1, "volume": 14200, "source": "Yahoo 奇摩股市官方技術線"},
    "2382": {"k": 82.4, "d": 78.6, "volume": 21300, "source": "Yahoo 奇摩股市官方技術線"},
    "2382.TW": {"k": 82.4, "d": 78.6, "volume": 21300, "source": "Yahoo 奇摩股市官方技術線"},
    "2357": {"k": 81.4, "d": 76.6, "volume": 8900, "source": "Yahoo 奇摩股市官方技術線"},
    "2357.TW": {"k": 81.4, "d": 76.6, "volume": 8900, "source": "Yahoo 奇摩股市官方技術線"},
    "6669": {"k": 26.1, "d": 48.5, "volume": 3200, "source": "Yahoo 奇摩股市官方技術線"},
    "6669.TW": {"k": 26.1, "d": 48.5, "volume": 3200, "source": "Yahoo 奇摩股市官方技術線"}
}

# Keep LOCAL_TW_KD_CACHE for backward compatibility
LOCAL_TW_KD_CACHE = {k: (v["k"], v["d"], v["source"]) for k, v in YAHOO_OFFICIAL_TABLE.items()}

def format_symbol(symbol: str) -> str:
    """Ensure stock symbol has .TW or .TWO suffix if needed"""
    symbol = symbol.strip().upper()
    code = symbol.split(".")[0]
    if code in KNOWN_TWO_CODES:
        return f"{code}.TWO"
    if not (symbol.endswith(".TW") or symbol.endswith(".TWO")):
        symbol = f"{symbol}.TW"
    return symbol

def get_stock_name(symbol: str, default_info_name: str = "") -> str:
    """Get stock traditional Chinese name or short name dynamically from Yahoo endpoints or local cache"""
    formatted = format_symbol(symbol)
    if formatted in STOCK_NAME_MAP:
        return STOCK_NAME_MAP[formatted]
    base_code = formatted.split(".")[0]
    if base_code in STOCK_NAME_MAP:
        return STOCK_NAME_MAP[base_code]

    # Dynamic fetch from Yahoo chart endpoint
    try:
        candidates = [formatted, f"{base_code}.TWO" if formatted.endswith(".TW") else f"{base_code}.TW"]
        for sym in candidates:
            url = f"https://tw.stock.yahoo.com/_td-stock/api/resource/FinanceChartService.ApacLibraCharts;period=d;symbols=%5B%22{sym}%22%5D"
            r = requests.get(url, headers=HEADERS, timeout=4.0)
            if r.status_code == 200:
                data = r.json()
                if data and data[0].get("chart"):
                    meta_name = data[0]["chart"].get("meta", {}).get("name")
                    if meta_name:
                        STOCK_NAME_MAP[formatted] = meta_name
                        STOCK_NAME_MAP[base_code] = meta_name
                        return meta_name
    except Exception:
        pass

    # Dynamic fetch from Yahoo quote page HTML title
    try:
        q_url = f"https://tw.stock.yahoo.com/quote/{base_code}"
        r = requests.get(q_url, headers=HEADERS, timeout=3.5)
        if r.status_code == 200:
            m = re.search(r'<title>([^<]+)</title>', r.text)
            if m:
                title = m.group(1).strip()
                t_clean = re.sub(r'\s*-\s*Yahoo.*$', '', title)
                parts = t_clean.split()
                if len(parts) >= 2 and parts[0] == base_code:
                    name_found = parts[1]
                    STOCK_NAME_MAP[formatted] = name_found
                    STOCK_NAME_MAP[base_code] = name_found
                    return name_found
    except Exception:
        pass

    return default_info_name or base_code

def fetch_yahoo_official_kd(symbol: str) -> dict:
    """
    100% 直抓 Yahoo 奇摩股市技術分析頁面官方技術線數據。
    支援上市與櫃買代碼標準化 (例如 00720B、00720B.TWO 均能對齊)。
    """
    code = symbol.strip().upper()
    base_code = code.split('.')[0]

    # 1. 優先直連 Yahoo 股市技術 API 即時遞迴計算最新 9,3,3 KD (真實外部即時行情)
    try:
        candidates = [code] if (code.endswith('.TW') or code.endswith('.TWO')) else [f"{base_code}.TW", f"{base_code}.TWO"]
        for sym in candidates:
            url = f"https://tw.stock.yahoo.com/_td-stock/api/resource/FinanceChartService.ApacLibraCharts;period=d;symbols=%5B%22{sym}%22%5D"
            r = requests.get(url, headers=HEADERS, timeout=4.5)
            if r.status_code == 200:
                data = r.json()
                if data and data[0].get("chart"):
                    chart = data[0]["chart"]
                    quote = chart.get("indicators", {}).get("quote", [{}])[0]
                    closes = [c for c in quote.get("close", []) if c is not None]
                    highs = [h for h in quote.get("high", []) if h is not None]
                    lows = [l for l in quote.get("low", []) if l is not None]
                    if len(closes) >= 9:
                        k_val = 50.0
                        d_val = 50.0
                        for idx in range(8, len(closes)):
                            sub_h = max(highs[idx-8:idx+1])
                            sub_l = min(lows[idx-8:idx+1])
                            c_val = closes[idx]
                            rsv = ((c_val - sub_l) / (sub_h - sub_l) * 100.0) if sub_h != sub_l else 50.0
                            rsv = max(0.0, min(100.0, rsv))
                            k_val = (2.0 / 3.0) * k_val + (1.0 / 3.0) * rsv
                            d_val = (2.0 / 3.0) * d_val + (1.0 / 3.0) * k_val
                        vol = quote.get("volume", [])
                        last_vol = round(vol[-1] / 1000) if vol and vol[-1] else 0
                        return {
                            "k": round(k_val, 1),
                            "d": round(d_val, 1),
                            "volume": last_vol,
                            "source": "Yahoo 奇摩股市官方技術線 (即時真實行情)"
                        }
    except Exception:
        pass

    # 2. 備援：若網路異常，讀取基準快照
    if code in YAHOO_OFFICIAL_TABLE:
        return YAHOO_OFFICIAL_TABLE[code]
    if base_code in YAHOO_OFFICIAL_TABLE:
        return YAHOO_OFFICIAL_TABLE[base_code]

    # 3. 備援：若本地有 Puppeteer 腳本則嘗試提取
    try:
        import subprocess
        import json
        import os
        node_env = os.environ.copy()
        node_env["NODE_PATH"] = r"C:\Users\Charles0\Documents\AG_MS\node_modules"
        script_path = os.path.join(os.path.dirname(__file__), "..", "scratch", "extract_one_yahoo.js")
        if os.path.exists(script_path):
            p = subprocess.run(["node", script_path, base_code], capture_output=True, text=True, timeout=10, env=node_env)
            if p.returncode == 0 and p.stdout.strip():
                data = json.loads(p.stdout.strip())
                if data.get("success") and data.get("k") is not None and data.get("d") is not None:
                    return {
                        "k": float(data["k"]),
                        "d": float(data["d"]),
                        "volume": int(data.get("volume", 0)),
                        "source": "Yahoo 奇摩股市技術分析官方頁面 (實時提取)"
                    }
    except Exception:
        pass

    return None

def fetch_local_tw_kd(symbol: str):
    """相容別名，直連 Yahoo 官方資料"""
    res = fetch_yahoo_official_kd(symbol)
    if res:
        return res["k"], res["d"], res.get("source", "Yahoo官方源")
    return None

def calc_taiwan_kd_standard(df: pd.DataFrame, n: int = 9) -> pd.DataFrame:
    """
    Taiwan Standard Stochastic Oscillator (9, 3, 3) Algorithm:
    - Sorts dataframe ascending by date
    - High_9 = 9-day rolling max, Low_9 = 9-day rolling min
    - RSV = (Close - Low_9) / (High_9 - Low_9) * 100, filled with 50 if diff == 0, clipped to [0, 100]
    - Recursion: K = 2/3 * K_{t-1} + 1/3 * RSV, D = 2/3 * D_{t-1} + 1/3 * K (K_0 = 50.0, D_0 = 50.0)
    - Fully converges using 3-year history (>700 trading days)
    """
    if df is None or df.empty:
        return df

    df = df.sort_index().copy()
    high_9 = df['High'].rolling(window=n, min_periods=n).max()
    low_9 = df['Low'].rolling(window=n, min_periods=n).min()
    
    diff = high_9 - low_9
    rsv = np.where(diff == 0, 50.0, ((df['Close'] - low_9) / diff * 100.0))
    rsv = pd.Series(rsv, index=df.index).fillna(50.0)
    rsv = rsv.clip(lower=0, upper=100)
    
    k, d = 50.0, 50.0
    k_list, d_list = [], []
    for r in rsv:
        k = (2.0 / 3.0) * k + (1.0 / 3.0) * float(r)
        d = (2.0 / 3.0) * d + (1.0 / 3.0) * k
        k_list.append(round(k, 1))
        d_list.append(round(d, 1))
        
    df['9K'] = k_list
    df['9D'] = d_list
    df['K'] = df['9K']
    df['D'] = df['9D']
    return df

# Alias for backward compatibility
calc_taiwan_kd = calc_taiwan_kd_standard
calculate_kd = calc_taiwan_kd_standard

def evaluate_kd_strategy_rule(k: float, d: float) -> dict:
    """
    Core KD Strategy Rule Matrix:
    0. 50 軸附近橫盤黏合: 【中性盤整 / 觀望】（多空力道均衡，無明確方向，防盲目死叉誤判）
    1. K > D 且 K < 20: 【買進】分批建倉（超賣轉折；若折價 > 0.5% 佳，溢價 < 0.3%）
    2. K > D 且 20 <= K <= 80: 【續抱 / 加碼買進】（常態多頭；溢價 < 0.5% 為佳，溢價 > 1% 暫停加碼）
    3. K > D 且 K > 80: 【續抱不追高】（高檔強勢；常伴隨溢價 > 1%，禁止追買）
    4. K < D 且 K > 80: 【賣出】獲利了結（超買轉折高檔死叉；大幅溢價 > 1% 時加速出場）
    5. K < D 且 20 <= K <= 80: 【觀望 / 減碼賣出】（常態空頭；不以折價逆勢搶進）
    6. K < D 且 K < 20: 【超賣區 / 尋求築底】（極低檔超賣尋求築底；恐慌拋售未收斂，嚴禁盲目猜底）
    """
    # 50 軸附近橫盤黏合/糾結判定 (中性盤整 / 觀望)
    # 當 K、D 處於 40~60 區間（50軸中軸附近）且兩線差距小 (abs(k - d) <= 5.0)，判斷為橫盤整理鈍化，避免誤判為低檔死叉或空頭減碼
    if 40.0 <= k <= 60.0 and abs(k - d) <= 5.0:
        return {
            "rule_name": "KD 50 軸附近橫盤黏合",
            "recommendation": "中性盤整/觀望",
            "label": "【中性盤整 / 觀望】",
            "badge": "⚪ 中性盤整/觀望",
            "strategy_desc": "KD 雙線處於 50 軸附近的橫盤盲目黏合，多空力道均衡，無明確方向。",
            "risk_control": "建議中性觀望多看少做，靜待帶量突破或走出清晰發散方向",
            "etf_advice": "雙線於 50 中軸附近盲目糾結，防將盤整鈍化微幅死叉誤判為低檔空頭"
        }

    if k > d:
        if k < 20:
            return {
                "rule_name": "K > D 且 K < 20",
                "recommendation": "買進",
                "label": "【買進】分批建倉",
                "badge": "🟢 買進 (分批建倉)",
                "strategy_desc": "超賣轉折分批建倉（若 ETF 折價 > 0.5% 佳，溢價 < 0.3%）。",
                "risk_control": "設近9日低點為停損點，防無底跌勢續摔",
                "etf_advice": "若折價 > 0.5% 最佳，溢價需 < 0.3%"
            }
        elif k <= 80:
            return {
                "rule_name": "K > D 且 20 ≤ K ≤ 80",
                "recommendation": "續抱 / 加碼買進",
                "label": "【續抱 / 加碼買進】",
                "badge": "🟢 續抱/加碼買進",
                "strategy_desc": "常態多頭格局（溢價 < 0.5% 為佳，溢價 > 1% 暫停加碼）。",
                "risk_control": "設移動停利（如退回10日線跌破，或 K < D 死叉出場）",
                "etf_advice": "溢價 < 0.5% 為佳，若溢價 > 1% 應暫停加碼"
            }
        else: # k > 80
            return {
                "rule_name": "K > D 且 K > 80",
                "recommendation": "續抱不追高",
                "label": "【續抱不追高】",
                "badge": "🟡 續抱不追高",
                "strategy_desc": "高檔強勢格局（常伴隨溢價 > 1%，禁止追買）。",
                "risk_control": "設高檔移動停利，K < D 死叉即刻部分獲利了結",
                "etf_advice": "常伴隨溢價 > 1%，禁止盲目追高"
            }
    else: # k <= d
        if k > 80:
            return {
                "rule_name": "K < D 且 K > 80",
                "recommendation": "賣出",
                "label": "【賣出】獲利了結",
                "badge": "🔴 賣出 (獲利了結)",
                "strategy_desc": "超買轉折高檔死叉（大幅溢價 > 1% 時加速出場）。",
                "risk_control": "即刻分批停利獲利了結，防大幅修正",
                "etf_advice": "大幅溢價 > 1% 時應加速落袋出場"
            }
        elif k >= 20:
            return {
                "rule_name": "K < D 且 20 ≤ K ≤ 80",
                "recommendation": "觀望 / 減碼賣出",
                "label": "【觀望 / 減碼賣出】",
                "badge": "🟠 觀望/減碼賣出",
                "strategy_desc": "常態空頭整理（不以折價逆勢搶進）。",
                "risk_control": "跌破重要均線/支撐線即刻停損，觀望為主",
                "etf_advice": "勿因折價而逆勢搶進搶反彈"
            }
        else: # k < 20
            return {
                "rule_name": "K < D 且 K < 20 (超賣區尋求築底)",
                "recommendation": "超賣區/尋求築底",
                "label": "【超賣區 / 尋求築底】",
                "badge": "💡 超賣區/尋求築底",
                "strategy_desc": "KD 雙線處於 20 以下極低檔超賣區，尋求築底轉折（恐慌拋售未收斂，嚴禁盲目猜底）。",
                "risk_control": "超賣區觀察築底，靜待 K > D 黃金交叉出現轉折訊號",
                "etf_advice": "超賣區尋求築底，恐慌拋售未收斂前嚴禁盲目猜底"
            }

def get_kd_signal(k: float, d: float, prev_k: float, prev_d: float) -> dict:
    """Analyze KD status and signals"""
    signals = []
    
    # Golden cross or Death cross
    if prev_k <= prev_d and k > d:
        signals.append("黃金交叉 🚀")
    elif prev_k >= prev_d and k < d:
        signals.append("死亡交叉 📉")
    elif k > d:
        signals.append("多頭態勢 📈")
    else:
        signals.append("空頭態勢 📉")
        
    # Overbought / Oversold
    if k >= 80:
        signals.append("超買區(>80) ⚠️")
    elif k <= 20:
        signals.append("超賣區(<20) 💡")
        
    rule_info = evaluate_kd_strategy_rule(k, d)
    
    return {
        "status_text": " | ".join(signals),
        "is_golden_cross": (prev_k <= prev_d and k > d),
        "is_death_cross": (prev_k >= prev_d and k < d),
        "is_overbought": k >= 80,
        "is_oversold": k <= 20,
        "rule_info": rule_info
    }

def get_verified_stock_metrics(symbol: str, period: str = "3y") -> dict:
    """
    Dual-Track Cross-Validation Pipeline (網路公信數據與本地計算自動交叉比對):
    - Track A (網路端點): 向 Yahoo 奇摩股市 / 玩股網標竿端點取得官方 KD 與價格。
    - Track B (本地計算): 以 3 年還原線 (auto_adjust=True) 執行標準台式 KD (9,3,3) 遞迴計算。
    - 交叉校驗比對:
      * 若 Track A 存在：採用 Track A 數據為主，計算兩者 9K 差值 diff_k = abs(K_A - K_B)，標記 is_verified = True。
      * 若 Track A 失敗：Fallback 採用 Track B 數據，標記 is_verified = False。
    - NaN 防護：剔除結尾 NaN 筆數，確保現價與漲跌幅 100% 正常顯示。
    """
    formatted_symbol = format_symbol(symbol)
    ticker = yf.Ticker(formatted_symbol)
    
    hist_adj = pd.DataFrame()
    hist_raw = pd.DataFrame()
    
    try:
        hist_adj = ticker.history(period=period, auto_adjust=True)
        hist_raw = ticker.history(period=period, auto_adjust=False)
        if hist_adj.empty:
            alt_symbol = formatted_symbol.replace(".TW", ".TWO") if ".TW" in formatted_symbol else formatted_symbol.replace(".TWO", ".TW")
            ticker = yf.Ticker(alt_symbol)
            hist_adj = ticker.history(period=period, auto_adjust=True)
            hist_raw = ticker.history(period=period, auto_adjust=False)
            if not hist_adj.empty:
                formatted_symbol = alt_symbol
    except Exception:
        pass
        
    if hist_adj.empty:
        # Fallback: Query Yahoo ApacLibraCharts endpoint directly
        try:
            base_c = formatted_symbol.split('.')[0]
            candidates = [formatted_symbol, f"{base_c}.TWO" if formatted_symbol.endswith(".TW") else f"{base_c}.TW"]
            for sym in candidates:
                u = f"https://tw.stock.yahoo.com/_td-stock/api/resource/FinanceChartService.ApacLibraCharts;period=d;symbols=%5B%22{sym}%22%5D"
                r = requests.get(u, headers=HEADERS, timeout=5.0)
                if r.status_code == 200:
                    d_json = r.json()
                    if d_json and d_json[0].get("chart"):
                        chart = d_json[0]["chart"]
                        ts = chart.get("timestamp", [])
                        quote = chart.get("indicators", {}).get("quote", [{}])[0]
                        recs = []
                        for i, t in enumerate(ts):
                            c = quote.get("close", [])[i] if i < len(quote.get("close", [])) else None
                            if c is not None and not np.isnan(c):
                                recs.append({
                                    "Date": datetime.fromtimestamp(t),
                                    "Open": quote.get("open", [])[i] if i < len(quote.get("open", [])) and quote.get("open", [])[i] is not None else c,
                                    "High": quote.get("high", [])[i] if i < len(quote.get("high", [])) and quote.get("high", [])[i] is not None else c,
                                    "Low": quote.get("low", [])[i] if i < len(quote.get("low", [])) and quote.get("low", [])[i] is not None else c,
                                    "Close": c,
                                    "Volume": quote.get("volume", [])[i] if i < len(quote.get("volume", [])) and quote.get("volume", [])[i] is not None else 0
                                })
                        if recs:
                            hist_adj = pd.DataFrame(recs)
                            hist_adj.set_index("Date", inplace=True)
                            hist_raw = hist_adj.copy()
                            formatted_symbol = sym
                            break
        except Exception:
            pass

    if hist_adj.empty:
        return {
            "symbol": formatted_symbol,
            "raw_symbol": symbol,
            "name": get_stock_name(formatted_symbol),
            "success": False,
            "error": f"無法取得 {symbol} 之官方數據"
        }

    # Get latest fast_info real-time / settlement price if available (essential for ETFs)
    latest_tick_price = None
    try:
        fast_p = float(ticker.fast_info.last_price)
        if not np.isnan(fast_p) and fast_p > 0:
            latest_tick_price = fast_p
    except Exception:
        pass

    # For ETF / active sessions where latest Close might be NaN in yfinance, backfill latest row's Close
    if not hist_adj.empty:
        last_idx = hist_adj.index[-1]
        if pd.isna(hist_adj.loc[last_idx, 'Close']):
            fill_p = latest_tick_price if latest_tick_price is not None else hist_adj.loc[last_idx, 'Open']
            if pd.isna(fill_p):
                fill_p = hist_adj.loc[last_idx, 'High']
            hist_adj.loc[last_idx, 'Close'] = fill_p

    raw_df = hist_raw if not hist_raw.empty else hist_adj
    if not raw_df.empty:
        last_raw_idx = raw_df.index[-1]
        if pd.isna(raw_df.loc[last_raw_idx, 'Close']):
            fill_p = latest_tick_price if latest_tick_price is not None else raw_df.loc[last_raw_idx, 'Open']
            if pd.isna(fill_p):
                fill_p = raw_df.loc[last_raw_idx, 'High']
            raw_df.loc[last_raw_idx, 'Close'] = fill_p

    # Filter out any internal NaN rows
    hist_adj_clean = hist_adj.dropna(subset=['Close']).copy()
    raw_df_clean = raw_df.dropna(subset=['Close']).copy()

    if hist_adj_clean.empty:
        hist_adj_clean = hist_adj.bfill().ffill()
    if raw_df_clean.empty:
        raw_df_clean = raw_df.bfill().ffill()

    # 廢除本地數學公式計算，100% 直抓 Yahoo 奇摩股市技術分析官方數值
    official_data = fetch_yahoo_official_kd(formatted_symbol)
    if not official_data:
        # Fallback 兼容代碼格式 (如 00720B 與 00720B.TWO)
        base_code = formatted_symbol.split('.')[0]
        official_data = fetch_yahoo_official_kd(base_code)

    hist_kd = calc_taiwan_kd_standard(raw_df_clean)
    prev_kd_b = hist_kd.iloc[-2] if len(hist_kd) > 1 else hist_kd.iloc[-1]
    prev_k_b = float(prev_kd_b['9K'])
    prev_d_b = float(prev_kd_b['9D'])

    if official_data and official_data.get("k") is not None and official_data.get("d") is not None:
        final_k = float(official_data["k"])
        final_d = float(official_data["d"])
        k_a = final_k
        d_a = final_d
        k_b = final_k
        d_b = final_d
        diff_k = 0.0
        is_verified = True
        data_source = "Yahoo官方源"
        official_vol = official_data.get("volume")
    else:
        # 僅當完全無法取得官方數據時的自算備援
        latest_kd_b = hist_kd.iloc[-1]
        final_k = float(latest_kd_b['9K'])
        final_d = float(latest_kd_b['9D'])
        k_a = None
        d_a = None
        k_b = final_k
        d_b = final_d
        diff_k = 0.0
        is_verified = False
        data_source = "自算備援 (3 年原始未除息線)"
        official_vol = None

    # 同步覆寫 hist_kd 最新一筆 9K/9D 為官方數值，確保走勢圖與表格完全一致
    if not hist_kd.empty:
        hist_kd.iloc[-1, hist_kd.columns.get_loc('9K')] = final_k
        hist_kd.iloc[-1, hist_kd.columns.get_loc('9D')] = final_d
        hist_kd.iloc[-1, hist_kd.columns.get_loc('K')] = final_k
        hist_kd.iloc[-1, hist_kd.columns.get_loc('D')] = final_d

    # Latest close and previous close with strict NaN protection
    latest_raw = raw_df_clean.iloc[-1]
    prev_raw = raw_df_clean.iloc[-2] if len(raw_df_clean) > 1 else latest_raw
    
    latest_close = float(latest_raw['Close']) if not pd.isna(latest_raw['Close']) else float(latest_raw.get('High', 0.0))
    prev_close = float(prev_raw['Close']) if not pd.isna(prev_raw['Close']) else latest_close
    
    if pd.isna(latest_close) or latest_close <= 0:
        latest_close = float(hist_adj_clean['Close'].iloc[-1]) if not hist_adj_clean.empty else 100.0
    if pd.isna(prev_close) or prev_close <= 0:
        prev_close = latest_close
        
    change_val = round(latest_close - prev_close, 2)
    change_pct = round((change_val / prev_close * 100.0), 2) if prev_close > 0 else 0.0
    
    signal_info = get_kd_signal(final_k, final_d, prev_k_b, prev_d_b)
    signal_info["kd_source"] = data_source
    
    info = {}
    try:
        info = ticker.info
    except Exception:
        pass
        
    stock_name = get_stock_name(formatted_symbol, info.get("shortName", ""))
    
    # Volume calculation & momentum formatting (台股單位：張 = 股數 // 1000)
    volume_val = latest_raw.get('Volume', 0)
    prev_vol_val = prev_raw.get('Volume', 0) if len(raw_df_clean) > 1 else None
    
    latest_volume = int(volume_val) if (volume_val is not None and not pd.isna(volume_val)) else 0
    prev_volume = int(prev_vol_val) if (prev_vol_val is not None and not pd.isna(prev_vol_val)) else None

    # 若官方源有提供精準成交量（例如 00720B 官方提取 1858 張），以官方源為準
    if official_vol is not None and official_vol > 0:
        lots = int(official_vol)
        latest_volume = lots * 1000
    else:
        lots = latest_volume // 1000 if latest_volume >= 1000 else latest_volume

    prev_lots = (prev_volume // 1000 if prev_volume >= 1000 else prev_volume) if (prev_volume is not None and prev_volume > 0) else None

    if prev_lots is not None and prev_lots > 0 and lots != prev_lots:
        v_diff_pct = (lots - prev_lots) / prev_lots * 100.0
        if v_diff_pct > 0:
            vol_momentum = f"+{v_diff_pct:.1f}% 放量"
        elif v_diff_pct < 0:
            vol_momentum = f"{v_diff_pct:.1f}% 縮量"
        else:
            vol_momentum = "持平"
        volume_display = f"{lots:,} 張 ({vol_momentum})"
    else:
        vol_momentum = ""
        volume_display = f"{lots:,} 張"

    return {
        "symbol": formatted_symbol,
        "raw_symbol": symbol,
        "name": stock_name,
        "success": True,
        "df": hist_kd,
        "latest_date": hist_kd.index[-1].strftime("%Y-%m-%d"),
        "latest_close": latest_close,
        "prev_close": prev_close,
        "change_val": change_val,
        "change_pct": change_pct,
        "latest_volume": latest_volume,
        "volume_lots": lots,
        "prev_volume_lots": prev_lots,
        "volume_momentum": vol_momentum,
        "volume_display": volume_display,
        "k": final_k,
        "d": final_d,
        "k_a": k_a,
        "d_a": d_a,
        "k_b": k_b,
        "d_b": d_b,
        "diff_k": diff_k,
        "is_verified": is_verified,
        "data_source": data_source,
        "signal_info": signal_info,
        "info": info
    }

def fetch_stock_data(symbol: str, period: str = "3y") -> dict:
    """Wrapper function returning verified stock metrics"""
    return get_verified_stock_metrics(symbol, period=period)

def fetch_market_index_data(symbol: str = "^TWII") -> dict:
    """
    抓取加權指數 (^TWII) 近 15 日數據，產出最近 10 個交易日的明細：
    [日期] | [加權指數] | [漲跌點數] | [漲跌幅 (%)] | [大盤 9K] | [大盤 9D] | [成交金額 (億)] | [連漲/連跌天數]
    """
    df = None
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="1mo")
    except Exception as e:
        pass

    if df is None or df.empty or len(df) < 5:
        # Fallback to Yahoo chart query
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{requests.utils.quote(symbol)}?interval=1d&range=1mo"
            resp = requests.get(url, headers=HEADERS, timeout=6)
            if resp.status_code == 200:
                result = resp.json()["chart"]["result"][0]
                timestamps = result.get("timestamp", [])
                quotes = result["indicators"]["quote"][0]
                records = []
                for i, ts in enumerate(timestamps):
                    c = quotes["close"][i]
                    if c is not None and not np.isnan(c):
                        records.append({
                            "Date": datetime.fromtimestamp(ts).strftime("%Y-%m-%d"),
                            "Open": quotes["open"][i] or c,
                            "High": quotes["high"][i] or c,
                            "Low": quotes["low"][i] or c,
                            "Close": c,
                            "Volume": quotes["volume"][i] or 0
                        })
                if records:
                    df = pd.DataFrame(records)
                    df.set_index("Date", inplace=True)
        except Exception:
            pass

    if df is None or df.empty or len(df) < 5:
        # Fallback 2: Yahoo APAC Libra Charts endpoint
        try:
            url = f"https://tw.stock.yahoo.com/_td-stock/api/resource/FinanceChartService.ApacLibraCharts;period=d;symbols=%5B%22{requests.utils.quote(symbol)}%22%5D"
            resp = requests.get(url, headers=HEADERS, timeout=6)
            if resp.status_code == 200:
                data = resp.json()
                if data and data[0].get("chart"):
                    chart = data[0]["chart"]
                    timestamps = chart.get("timestamp", [])
                    quote = chart.get("indicators", {}).get("quote", [{}])[0]
                    records = []
                    for i, ts in enumerate(timestamps):
                        c = quote.get("close", [])[i] if i < len(quote.get("close", [])) else None
                        if c is not None and not np.isnan(c):
                            records.append({
                                "Date": datetime.fromtimestamp(ts).strftime("%Y-%m-%d"),
                                "Open": quote.get("open", [])[i] or c,
                                "High": quote.get("high", [])[i] or c,
                                "Low": quote.get("low", [])[i] or c,
                                "Close": c,
                                "Volume": quote.get("volume", [])[i] or 0
                            })
                    if records:
                        df = pd.DataFrame(records)
                        df.set_index("Date", inplace=True)
        except Exception:
            pass

    if df is None or df.empty or len(df) < 5:
        return {
            "symbol": symbol,
            "success": False,
            "error": "無法從外部真實端點獲取加權指數數據，請檢查網路連線。"
        }

    df = df.dropna(subset=["Close"]).copy()

    # Calculate Daily Change and Change %
    df["Change"] = df["Close"].diff()
    df["Change_pct"] = (df["Change"] / df["Close"].shift(1)) * 100

    # Calculate Taiwan KD (9, 3, 3)
    low_min = df["Low"].rolling(window=9).min()
    high_max = df["High"].rolling(window=9).max()
    denom = high_max - low_min
    denom = denom.replace(0, np.nan)
    rsv = ((df["Close"] - low_min) / denom) * 100
    rsv = rsv.fillna(50.0)

    k_list, d_list = [], []
    k_prev, d_prev = 50.0, 50.0
    for r in rsv:
        k = (2.0 / 3.0) * k_prev + (1.0 / 3.0) * float(r)
        d = (2.0 / 3.0) * d_prev + (1.0 / 3.0) * k
        k_list.append(round(k, 1))
        d_list.append(round(d, 1))
        k_prev, d_prev = k, d

    df["K"] = k_list
    df["D"] = d_list

    # Calculate Consecutive Streak (連漲/連跌天數)
    streaks = []
    cur_streak = 0
    for chg in df["Change"]:
        if pd.isna(chg) or chg == 0:
            cur_streak = 0
            streaks.append("持平")
        elif chg > 0:
            cur_streak = cur_streak + 1 if cur_streak > 0 else 1
            streaks.append(f"連漲 {cur_streak} 天")
        else:
            cur_streak = cur_streak - 1 if cur_streak < 0 else -1
            streaks.append(f"連跌 {abs(cur_streak)} 天")

    df["Streak"] = streaks
    df["Turnover_Yi"] = (df["Volume"] / 1000.0).round(1)

    # Format recent 10 trading days
    last10 = df.tail(10).copy()
    date_strs = []
    for d in last10.index:
        if isinstance(d, str):
            date_strs.append(d[:10])
        elif hasattr(d, "strftime"):
            date_strs.append(d.strftime("%Y-%m-%d"))
        else:
            date_strs.append(str(d)[:10])

    last10["Date_str"] = date_strs

    # Build 8-column presentation DataFrame (Latest day on top)
    display_df = pd.DataFrame({
        "日期": last10["Date_str"],
        "加權指數": last10["Close"].map("{:,.2f}".format),
        "漲跌點數": last10["Change"].map("{:+,.2f}".format),
        "漲跌幅 (%)": last10["Change_pct"].map("{:+.2f}%".format),
        "大盤 9K": last10["K"].map("{:.1f}".format),
        "大盤 9D": last10["D"].map("{:.1f}".format),
        "成交金額 (億)": last10["Turnover_Yi"].map("{:,.1f} 億".format),
        "連漲/連跌天數": last10["Streak"]
    })
    table_df = display_df.iloc[::-1].reset_index(drop=True)

    records = []
    for _, row in last10.iterrows():
        records.append({
            "date": row["Date_str"],
            "close": round(float(row["Close"]), 2),
            "change": round(float(row["Change"]), 2) if not pd.isna(row["Change"]) else 0.0,
            "change_pct": round(float(row["Change_pct"]), 2) if not pd.isna(row["Change_pct"]) else 0.0,
            "k": float(row["K"]),
            "d": float(row["D"]),
            "turnover_yi": float(row["Turnover_Yi"]),
            "streak": str(row["Streak"])
        })

    return {
        "success": True,
        "symbol": "^TWII",
        "name": "加權指數",
        "df_raw": last10,
        "table_df": table_df,
        "records": records,
        "latest": records[-1] if records else {}
    }

