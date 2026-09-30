"""
Dual-Track Decision System Engine (雙軌決策系統引擎)
Track 1: 確定性 KD 決策狀態機（含標的屬性分流：債券 vs 股票/權值ETF、低檔破底風控與債券鎖利加碼）
Track 2: 連跌分批與 5 項續跌風控判斷 (左側加碼與防禦機制)
"""
import re
import pandas as pd
import numpy as np

def check_is_bond(symbol: str = "", name: str = "") -> bool:
    """
    一、標的屬性判定 (is_bond)：
    - 自動識別股票代號或名稱：
      * 代碼結尾帶有「B」（如 00679B、00720B、00687B、00937B 等）。
      * 標的名稱包含「債」、「美債」、「公司債」、「金融債」、「公債」、「國債」、「投等債」等關鍵字。
      * 符合者判定為「債券」，其餘一律判定為「一般個股與股票型 ETF」。
    """
    sym = (symbol or "").strip().upper()
    base_sym = re.sub(r'\.(TW|TWO)$', '', sym)
    if base_sym.endswith("B"):
        return True
    
    nm = (name or "").strip()
    bond_keywords = ["債", "美債", "公司債", "金融債", "公債", "國債", "投等債", "短期債", "長期債"]
    if any(kw in nm for kw in bond_keywords):
        return True
    return False

def check_bottom_break_risk(df: pd.DataFrame) -> dict:
    """
    檢查是否符合「光腳黑棒收最低」或「無量陰跌破底」：
    1. 光腳黑棒收最低：今日收黑，且收在當日最低價附近 (下影線佔比 <= 8% 或收在當日最低)
    2. 無量陰跌破底：今日收盤價創近 10 日新低，且成交量萎縮小於近 5 日平均量
    """
    if df is None or len(df) < 5:
        return {"has_risk": False, "reasons": [], "warning_msg": ""}
    
    reasons = []
    try:
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        c = float(latest["Close"])
        o = float(latest.get("Open", c))
        h = float(latest.get("High", c))
        l = float(latest.get("Low", c))
        
        # 1. 光腳黑棒收最低
        is_bearish = (c < o) or (c < float(prev["Close"]))
        amplitude = h - l
        if is_bearish and amplitude > 0:
            lower_shadow_ratio = (c - l) / amplitude
            if lower_shadow_ratio <= 0.08 or c == l:
                reasons.append("光腳黑棒收最低")
        
        # 2. 無量陰跌破底
        recent_closes = df["Close"].tail(10).values
        if len(recent_closes) >= 5:
            min_close = np.min(recent_closes[:-1])
            if c <= min_close:
                vol_col = "Volume" if "Volume" in df.columns else ("vol" if "vol" in df.columns else None)
                if vol_col:
                    v = float(latest.get(vol_col, 0))
                    vol_ma5 = df[vol_col].tail(6).iloc[:-1].mean()
                    if vol_ma5 > 0 and v < vol_ma5:
                        reasons.append("無量陰跌破底")
    except Exception:
        pass
        
    has_risk = len(reasons) > 0
    warning_msg = "⚠️ 留意空方慣性破底，未見長下影線或爆量前切勿進場" if has_risk else ""
    return {"has_risk": has_risk, "reasons": reasons, "warning_msg": warning_msg}

def evaluate_deterministic_kd_state(
    k: float,
    d: float,
    is_bond: bool = False,
    df: pd.DataFrame = None,
    prev_k: float = None,
    prev_d: float = None
) -> dict:
    """
    KD 雙向區間智慧操作策略矩陣：
    1. 債券型標的強制條款 (is_bond == True)：
       - IF K < D AND K < 60:
         * status = "【低檔鎖利／蓋牌領息觀望】"
         * action_type = "中立" (非賣出！)
         * desc = "債券核心本質為鎖定殖利率與領息，短線技術面死叉不具備個股崩跌風險，切勿砍在阿呆谷。"
       - IF K > D AND K <= 30:
         * status = "【低檔轉強／鎖利加碼】"
         * action_type = "買進"
         * desc = "債券跌深出現低檔黃金交叉，兼具高殖利率鎖利與反彈資本利得空間，啟動分批加碼。"

    2. 第一維度：K > D (多頭排列/轉強)：
       - IF K >= 80:
         * status = "【續抱不追高】" (action_type = "買進", desc = "行情狂熱強勢噴出，嚴禁追價，持股續抱")
       - ELSE IF 60 <= K < 80:
         * status = "【順勢偏多／輕倉試單】" (action_type = "買進", desc = "多頭結構健康，展開波段攻擊，為波段買進或續抱勝率最高區")
       - ELSE IF 20 < K < 60:
         * status = "【多頭復甦／持股觀望】" (action_type = "中立", desc = "股價自低檔爬升或中軸震盪，動能未完全爆發，持股續抱，空倉小量試單")
       - ELSE IF K <= 20:
         * status = "【低檔黃金交叉／分批佈局】" (action_type = "買進", desc = "跌深後主力扭轉訊號，為落後補漲起漲點，適合分批建倉")

    3. 第二維度：K < D (空頭排列/轉弱)：
       - IF K >= 80:
         * status = "【高檔死叉／獲利了結】" (action_type = "賣出", desc = "高檔見頂回落，多頭力道竭盡，果斷落袋為安")
       - ELSE IF 60 <= K < 80:
         * status = "【持股觀望／停止加碼】" (action_type = "中立", desc = "不急著砍倉，但也不宜進場，靜待量價沉澱")
       - ELSE IF 20 < K < 60:
         * status = "【持股觀望／禁止加碼】" (action_type = "中立", desc = "進入波段修正，賣出稍嫌太晚，絕對禁止進場攤平，耐性等止穩")
       - ELSE IF K <= 20:
         * status = "【低檔觀望／嚴禁殺低】" (action_type = "中立", desc = "股價跌至阿呆谷極低點，禁止認賠割肉，靜待落底反彈")
    """
    k = float(k)
    d = float(d)

    # 即時金叉/死叉訊號
    cross_signal = ""
    if prev_k is not None and prev_d is not None:
        if prev_k <= prev_d and k > d:
            cross_signal = "黃金交叉 🚀"
        elif prev_k >= prev_d and k < d:
            cross_signal = "死亡交叉 📉"

    risk_warning = ""
    bottom_break = {"has_risk": False, "reasons": [], "warning_msg": ""}

    # 1. 債券型標的強制條款 (is_bond == True 且 K < D 且 K < 60)
    if is_bond and k < d and k < 60.0:
        status = "【低檔鎖利／蓋牌領息觀望】"
        action_type = "中立"
        light = "🟡 觀望"
        desc = "債券核心本質為鎖定殖利率與領息，短線技術面死叉不具備個股崩跌風險，切勿砍在阿呆谷。"
        risk_ctrl = "現有部位安心領息，不盲目殺低，靜待KD由下往上金叉轉折"
        rule_name = "債券低檔鎖利觀望 (is_bond 且 K < D 且 K < 60)"

    # 債券低檔金叉分流 (is_bond == True 且 K <= 30 且 K > D)
    elif is_bond and k > d and k <= 30.0:
        status = "【低檔轉強／鎖利加碼】"
        action_type = "買進"
        light = "🟢 加碼"
        desc = "債券跌深出現低檔黃金交叉，兼具高殖利率鎖利與反彈資本利得空間，啟動分批加碼。"
        risk_ctrl = "鎖利加碼部位，防範降息路徑反覆，以分批佈局領息為主"
        rule_name = "債券低檔金叉 (is_bond 且 K <= 30 且 K > D)"

    # 2. 第一維度：K > D (多頭排列/轉強)
    elif k > d:
        if k >= 80.0:
            status = "【續抱不追高】"
            action_type = "買進"
            light = "🟢 續抱"
            desc = "行情狂熱強勢噴出，嚴禁追價，持股續抱"
            risk_ctrl = "設高檔移動停利點，嚴禁追高，若跌破5日線或死叉即刻獲利了結"
            rule_name = "高檔超買鈍化 (K >= 80 且 K > D)"
        elif k >= 60.0:
            status = "【順勢偏多／輕倉試單】"
            action_type = "買進"
            light = "🟢 偏多"
            desc = "多頭結構健康，展開波段攻擊，為波段買進或續抱勝率最高區"
            risk_ctrl = "順勢操作，以波段持有為主，跌破短期支撐再行調節"
            rule_name = "中高軸偏多攻擊 (60 <= K < 80 且 K > D)"
        elif k > 20.0:
            status = "【多頭復甦／持股觀望】"
            action_type = "中立"
            light = "⚪ 觀望"
            desc = "股價自低檔爬升或中軸震盪，動能未完全爆發，持股續抱，空倉小量試單"
            risk_ctrl = "持股續抱，空倉小量試單，不宜重倉追價，觀察量能是否放大"
            rule_name = "中低軸多頭復甦 (20 < K < 60 且 K > D)"
        else: # k <= 20.0
            status = "【低檔黃金交叉／分批佈局】"
            action_type = "買進"
            light = "🟢 佈局"
            desc = "跌深後主力扭轉訊號，為落後補漲起漲點，適合分批建倉"
            risk_ctrl = "設近9日低點為紀律停損，採左側分批逢低承接策略"
            rule_name = "極端超賣金叉 (K <= 20 且 K > D)"

    # 3. 第二維度：K <= D (空頭排列/轉弱)
    else:
        if k >= 80.0:
            status = "【高檔死叉／獲利了結】"
            action_type = "賣出"
            light = "🔴 賣出"
            desc = "高檔見頂回落，多頭力道竭盡，果斷落袋為安"
            risk_ctrl = "即刻分批停利獲利了結，防動能竭盡後之大幅拉回修正"
            rule_name = "高檔超買死叉 (K >= 80 且 K <= D)"
        elif k >= 60.0:
            status = "【持股觀望／停止加碼】"
            action_type = "中立"
            light = "⚪ 觀望"
            desc = "不急著砍倉，但也不宜進場，靜待量價沉澱"
            risk_ctrl = "停止加碼，觀察是否守穩關鍵均線，多看少做"
            rule_name = "中高軸死叉整理 (60 <= K < 80 且 K <= D)"
        elif k > 20.0:
            status = "【持股觀望／禁止加碼】"
            action_type = "中立"
            light = "⚪ 觀望"
            desc = "進入波段修正，賣出稍嫌太晚，絕對禁止進場攤平，耐性等止穩"
            risk_ctrl = "絕對禁止盲目攤平，靜待指標落底止穩或長下影線訊號"
            rule_name = "中低軸波段修正 (20 < K < 60 且 K <= D)"
        else: # k <= 20.0
            status = "【低檔觀望／嚴禁殺低】"
            action_type = "中立"
            light = "🟡 觀望"
            desc = "股價跌至阿呆谷極低點，禁止認賠割肉，靜待落底反彈"
            bottom_break = check_bottom_break_risk(df)
            if bottom_break["has_risk"]:
                risk_warning = bottom_break["warning_msg"]
                risk_ctrl = f"低檔鈍化觀望；{risk_warning}，嚴禁殺低認賠"
            else:
                risk_ctrl = "股價跌至極低位階阿呆谷，禁止認賠割肉，耐性等待落底轉折"
            rule_name = "極端超賣觀望 (K <= 20 且 K <= D)"

    badge = f"{light.split()[0]} {status}"

    return {
        "rule_name": rule_name,
        "recommendation": action_type,
        "action_type": action_type,
        "label": status,
        "status": status,
        "light": light,
        "badge": badge,
        "strategy_desc": desc,
        "risk_control": risk_ctrl,
        "cross_signal": cross_signal,
        "k": k,
        "d": d,
        "is_bond": is_bond,
        "risk_warning": risk_warning,
        "bottom_break": bottom_break
    }

def evaluate_track1_kd(
    k: float,
    d: float,
    prev_k: float = None,
    prev_d: float = None,
    symbol: str = "",
    name: str = "",
    is_bond: bool = None,
    df: pd.DataFrame = None
) -> dict:
    """
    軌道一：升級為全新確定性 KD 決策狀態機
    """
    if is_bond is None:
        is_bond = check_is_bond(symbol, name)
    return evaluate_deterministic_kd_state(
        k=k,
        d=d,
        is_bond=is_bond,
        df=df,
        prev_k=prev_k,
        prev_d=prev_d
    )

def calculate_drop_streak(closes: list) -> int:
    """計算日線收盤價連續下跌天數"""
    if not closes or len(closes) < 2:
        return 0
    streak = 0
    for i in range(len(closes) - 1, 0, -1):
        diff = closes[i] - closes[i - 1]
        if diff < 0:
            streak += 1
        else:
            break
    return streak

def check_right_side_confirmation(df: pd.DataFrame) -> bool:
    """
    檢查是否符合「站回 5 日線翻紅（右側確認）」：
    1. 前波曾出現連續下跌 >= 2 天 (在近 5 日內)
    2. 今日收紅 (Close > Prev_Close)
    3. 今日收盤價站回 5 日線 (Close > MA5)
    4. 昨日仍在 5 日線下方或剛突破 (Prev_Close <= Prev_MA5)
    """
    if df is None or len(df) < 6:
        return False
    try:
        closes = df["Close"].values
        ma5 = df["Close"].rolling(5).mean().values
        
        today_close = closes[-1]
        prev_close = closes[-2]
        today_ma5 = ma5[-1]
        prev_ma5 = ma5[-2]
        
        # 今日收紅且站上 MA5
        if today_close > prev_close and today_close > today_ma5 and prev_close <= prev_ma5:
            # 檢查前 5 日內是否曾有連跌 2 天以上
            for i in range(len(closes) - 2, max(0, len(closes) - 7), -1):
                sub_closes = closes[:i+1]
                if calculate_drop_streak(sub_closes) >= 2:
                    return True
    except Exception:
        pass
    return False

def evaluate_track2_risk(
    stock_df: pd.DataFrame,
    latest_quote: dict,
    market_data: dict = None
) -> dict:
    """
    軌道二：連跌分批與 5 項續跌風控判斷（左側加碼與防禦機制）
    - 計算連續下跌天數：
      * 連跌 2 天：提示「連跌2日：左側第1筆試單 (20%)」。
      * 連跌 3 天：計算 5 大續跌特徵（光腳黑棒、量縮破低、KD鈍化、融資增加/籌碼偏弱、期貨空單/大盤偏弱）：
        - 若符合 >= 3 項：警示「🔴 第4天續跌警示：暫緩第2筆加碼」（建議部位 0% 或暫緩）。
        - 若爆量長下影線（成交量 > 5MA量 1.5倍 且 下影線佔比 >= 40%）：提示「🟢 止跌反轉：啟動第2筆加碼 (30%)」。
        - 其餘情況：提示「連跌3日：評估第2筆加碼 (30%)」。
      * 連跌 4~5 天：提示「極端超賣：第3筆加碼 (30%)」。
      * 站回 5 日線翻紅（右側確認）：提示「右側確認：第4筆完成建倉 (20%)」。
      * 平盤或上漲個股（連跌天數 = 0）：提示「設移動停利（如退回10日線跌破，或 K < D 死叉出場）」，不干擾軌道一的 KD 訊號。
    """
    if stock_df is None or stock_df.empty:
        # Fallback if no full history
        return {
            "drop_streak": 0,
            "status_label": "設移動停利",
            "action_text": "設移動停利（如退回10日線跌破，或 K < D 死叉出場）",
            "suggested_ratio": "維持部位",
            "warning": False,
            "warning_type": "none",
            "features_matched": [],
            "is_reversal": False,
            "is_right_side": False,
            "badge": "🛡️ 設移動停利"
        }

    closes = stock_df["Close"].dropna().tolist()
    drop_streak = calculate_drop_streak(closes)

    # 檢查右側確認 (翻紅且站上 5MA)
    is_right_side = check_right_side_confirmation(stock_df)
    if is_right_side and drop_streak == 0:
        return {
            "drop_streak": 0,
            "status_label": "右側確認 (20%)",
            "action_text": "右側確認：第4筆完成建倉 (20%)",
            "suggested_ratio": "20%",
            "warning": False,
            "warning_type": "right_side",
            "features_matched": [],
            "is_reversal": False,
            "is_right_side": True,
            "badge": "🟢 右側確認 (20%)"
        }

    if drop_streak == 0:
        return {
            "drop_streak": 0,
            "status_label": "設移動停利",
            "action_text": "設移動停利（如退回10日線跌破，或 K < D 死叉出場）",
            "suggested_ratio": "維持部位",
            "warning": False,
            "warning_type": "none",
            "features_matched": [],
            "is_reversal": False,
            "is_right_side": False,
            "badge": "🛡️ 設移動停利"
        }

    if drop_streak == 1:
        return {
            "drop_streak": 1,
            "status_label": "連跌1日 (觀望)",
            "action_text": "連跌1日：觀察重要支撐，暫不急於搶進",
            "suggested_ratio": "0%",
            "warning": False,
            "warning_type": "none",
            "features_matched": [],
            "is_reversal": False,
            "is_right_side": False,
            "badge": "⚪ 連跌1日 (觀望)"
        }

    if drop_streak == 2:
        return {
            "drop_streak": 2,
            "status_label": "連跌2日 (試單20%)",
            "action_text": "連跌2日：左側第1筆試單 (20%)",
            "suggested_ratio": "20%",
            "warning": False,
            "warning_type": "first_buy",
            "features_matched": [],
            "is_reversal": False,
            "is_right_side": False,
            "badge": "🔵 連跌2日：試單 (20%)"
        }

    if drop_streak == 3:
        # 連跌 3 天：計算 5 大續跌特徵與爆量長下影線
        matched_features = []
        
        # 取得最新一根 K 棒數據
        latest_row = stock_df.iloc[-1]
        prev_row = stock_df.iloc[-2] if len(stock_df) > 1 else latest_row
        
        open_p = float(latest_row.get("Open", latest_row["Close"]))
        high_p = float(latest_row.get("High", latest_row["Close"]))
        low_p = float(latest_row.get("Low", latest_row["Close"]))
        close_p = float(latest_row["Close"])
        vol_curr = float(latest_row.get("Volume", 0))
        vol_prev = float(prev_row.get("Volume", 0))
        
        # 5MA 均量
        vol_5ma = stock_df["Volume"].tail(5).mean() if "Volume" in stock_df.columns else vol_curr
        if pd.isna(vol_5ma) or vol_5ma <= 0:
            vol_5ma = vol_curr
            
        candle_range = max(high_p - low_p, 1e-4)
        lower_shadow = max(min(open_p, close_p) - low_p, 0.0)
        lower_shadow_ratio = lower_shadow / candle_range
        
        # 1. 光腳黑棒: Close < Open 且 下影線佔比 <= 15%
        is_bare_foot = (close_p < open_p) and (lower_shadow_ratio <= 0.15)
        if is_bare_foot:
            matched_features.append("光腳黑棒 (賣壓貫到底)")
            
        # 2. 量縮破低: (Low < PrevLow 或 Close < PrevClose) 且 (Volume < 5MA量 或 Volume < 前日量)
        is_vol_down_low = (low_p < float(prev_row.get("Low", low_p)) or close_p < float(prev_row["Close"])) and \
                          (vol_curr < vol_5ma or vol_curr < vol_prev)
        if is_vol_down_low:
            matched_features.append("量縮破低 (承接力道衰竭)")
            
        # 3. KD 鈍化: K < 20 或 (K < D 且 K < 30)
        k_val = float(latest_quote.get("k", latest_row.get("K", 50)))
        d_val = float(latest_quote.get("d", latest_row.get("D", 50)))
        is_kd_bearish = (k_val < 20.0) or (k_val < d_val and k_val < 30.0)
        if is_kd_bearish:
            matched_features.append("KD鈍化 (空方動能鎖定)")
            
        # 4. 融資增加 / 籌碼偏弱: 單日跌幅超越大盤 0.5% 以上
        change_pct = float(latest_quote.get("change_pct", 0.0))
        market_change_pct = 0.0
        market_weak_flag = False
        if market_data and market_data.get("latest"):
            market_change_pct = float(market_data["latest"].get("change_pct", 0.0))
            if market_change_pct < 0 or market_data["latest"].get("k", 50) < market_data["latest"].get("d", 50):
                market_weak_flag = True
        elif market_data and market_data.get("table_df") is not None and not market_data["table_df"].empty:
            try:
                first_row = market_data["table_df"].iloc[0]
                chg_str = str(first_row.get("漲跌幅 (%)", "0%")).replace("%", "")
                market_change_pct = float(chg_str)
                if market_change_pct < 0:
                    market_weak_flag = True
            except Exception:
                pass
                
        if change_pct < (market_change_pct - 0.5):
            matched_features.append("籌碼偏弱 (弱於大盤)")
            
        # 5. 期貨空單 / 大盤偏弱: 大盤收黑或大盤連跌
        if market_weak_flag or market_change_pct < 0:
            matched_features.append("大盤偏弱 (系統性避險承壓)")
            
        # 爆量長下影線反轉檢驗:
        # 成交量 > 5MA量 1.5倍 且 下影線佔比 >= 40%
        is_reversal = (vol_curr > 1.5 * vol_5ma) and (lower_shadow_ratio >= 0.40)
        if is_reversal:
            return {
                "drop_streak": 3,
                "status_label": "止跌反轉 (30%)",
                "action_text": "🟢 止跌反轉：爆量長下影線，啟動第2筆加碼 (30%)",
                "suggested_ratio": "30%",
                "warning": False,
                "warning_type": "reversal",
                "features_matched": matched_features,
                "is_reversal": True,
                "is_right_side": False,
                "badge": "🟢 止跌反轉：加碼 (30%)"
            }

        # 續跌警示: 若符合 >= 3 項特徵
        if len(matched_features) >= 3:
            features_str = "、".join(matched_features)
            return {
                "drop_streak": 3,
                "status_label": "🔴 續跌警示 (暫緩加碼)",
                "action_text": f"🔴 第4天續跌警示：符合{len(matched_features)}項續跌特徵（{features_str}），暫緩第2筆加碼",
                "suggested_ratio": "0% (暫緩)",
                "warning": True,
                "warning_type": "continuation_alert",
                "features_matched": matched_features,
                "is_reversal": False,
                "is_right_side": False,
                "badge": "🔴 續跌警示 (暫緩加碼)"
            }
        else:
            return {
                "drop_streak": 3,
                "status_label": "連跌3日 (評估加碼30%)",
                "action_text": "連跌3日：未觸發過度續跌警示，評估第2筆加碼 (30%)",
                "suggested_ratio": "30%",
                "warning": False,
                "warning_type": "second_buy",
                "features_matched": matched_features,
                "is_reversal": False,
                "is_right_side": False,
                "badge": "🟡 連跌3日：評估加碼 (30%)"
            }

    # 連跌 4~5 天或以上：極端超賣
    if drop_streak >= 4:
        return {
            "drop_streak": drop_streak,
            "status_label": f"極端超賣連跌{drop_streak}日 (30%)",
            "action_text": f"極端超賣：已連跌 {drop_streak} 天，籌碼浮額大幅清洗，執行第3筆加碼 (30%)",
            "suggested_ratio": "30%",
            "warning": False,
            "warning_type": "extreme_oversold",
            "features_matched": [],
            "is_reversal": False,
            "is_right_side": False,
            "badge": f"🟣 極端超賣連跌{drop_streak}日：第3筆 (30%)"
        }

    return {
        "drop_streak": drop_streak,
        "status_label": "設移動停利",
        "action_text": "設移動停利（如退回10日線跌破，或 K < D 死叉出場）",
        "suggested_ratio": "維持部位",
        "warning": False,
        "warning_type": "none",
        "features_matched": [],
        "is_reversal": False,
        "is_right_side": False,
        "badge": "🛡️ 設移動停利"
    }

def evaluate_dual_track_system(
    stock_data: dict,
    market_data: dict = None
) -> dict:
    """
    雙軌決策系統整合評估入口
    同時計算【軌道一：KD 常規矩陣】與【軌道二：連跌風控體系】
    產出互不衝突的兩套清晰指標與綜合權衡理由
    """
    k = float(stock_data.get("k", 50))
    d = float(stock_data.get("d", 50))
    prev_k = stock_data.get("prev_k")
    prev_d = stock_data.get("prev_d")
    symbol = stock_data.get("symbol", "")
    name = stock_data.get("name", "")
    df = stock_data.get("df")
    
    # 1. 軌道一：全新確定性 KD 決策狀態機
    track1 = evaluate_track1_kd(
        k=k, d=d, prev_k=prev_k, prev_d=prev_d,
        symbol=symbol, name=name, df=df
    )
    
    # 2. 軌道二：連跌分批與風控判斷
    track2 = evaluate_track2_risk(df, stock_data, market_data)
    
    # 3. 雙軌整合權衡理由建構
    streak = track2["drop_streak"]
    reasons = []
    reasons.append(f"【軌道一 KD】{track1['label']} (9K={k:.1f}, 9D={d:.1f})")
    if track1.get("risk_warning"):
        reasons.append(f"【破底風控】{track1['risk_warning']}")
    
    if streak == 0:
        if track2.get("is_right_side"):
            reasons.append(f"【軌道二 風控】{track2['action_text']}")
        else:
            reasons.append("【軌道二 風控】連跌0日，設常規移動停利，不干擾KD常態訊號")
    elif streak == 2:
        reasons.append(f"【軌道二 風控】連跌 2 日，啟動左側第 1 筆試單 (20%)")
    elif streak == 3:
        if track2.get("warning"):
            feat_desc = "、".join(track2["features_matched"])
            reasons.append(f"【軌道二 風控】連跌 3 日且符合 {len(track2['features_matched'])} 項續跌特徵（{feat_desc}），發出🔴第4天續跌警示，暫緩加碼 (0%)")
        elif track2.get("is_reversal"):
            reasons.append(f"【軌道二 風控】連跌 3 日爆量長下影線，觸發🟢止跌反轉，啟動第 2 筆加碼 (30%)")
        else:
            reasons.append(f"【軌道二 風控】連跌 3 日，無顯著續跌惡化，評估第 2 筆加碼 (30%)")
    elif streak >= 4:
        reasons.append(f"【軌道二 風控】連跌 {streak} 日極端超賣，浮額沈澱，啟動第 3 筆加碼 (30%)")
    else:
        reasons.append(f"【軌道二 風控】連跌 1 日，維持觀望支撐")
        
    integrated_reason = "；".join(reasons)
    
    return {
        "track1": track1,
        "track2": track2,
        "strategy_state": track1["label"],             # 總覽表格【KD策略建議狀態】
        "strategy_badge": track1["badge"],
        "action_type": track1["action_type"],
        "risk_control": track2["action_text"],          # 總覽表格【風控與連跌策略】
        "risk_badge": track2.get("badge", "🛡️ 設移動停利"),
        "drop_streak": streak,
        "suggested_ratio": track2["suggested_ratio"],
        "integrated_reason": integrated_reason
    }

def screen_kd_extremes(
    limit: int = 150,
    expanded: bool = False,
    custom_symbols: list = None
) -> dict:
    """
    全市場 KD 極端值快速選股核心邏輯：
    針對選定股票池，提取 Yahoo 官方最新 9K 與 9D 數值：
    - 【極端超賣轉折組 (K > D 且 K < 20)】：
      * 判定意涵：指標處於 20 以下極端超賣區，且已由下往上穿越 D 值（低檔金叉或轉強），具備跌深反彈與左側安全邊際。
      * 標註：🟢【超賣區金叉 / 築底反轉】
    - 【極端超買轉折組 (K < D 且 K > 80)】：
      * 判定意涵：指標處於 80 以上極端超買區，且已跌破 D 值（高檔死叉），短線動能竭盡，拉回風險高。
      * 標註：🔴【高檔死叉 / 超買警戒】
    """
    import time
    from src.stock_data import fetch_popular_universe, fetch_batch_quotes_kd, fetch_kd_extremes_screener

    if not custom_symbols:
        return fetch_kd_extremes_screener(limit=limit, expanded=expanded)

    t0 = time.time()
    universe = custom_symbols
    quotes = fetch_batch_quotes_kd(universe)

    oversold_list = []
    overbought_list = []

    for q in quotes:
        k = q.get("k", 50.0)
        d = q.get("d", 50.0)

        # 條件 1: 買方轉折區 (超賣金叉 / 築底)：K > D 且 K < 20
        if k > d and k < 20.0:
            item = dict(q)
            item["tag"] = "🟢【超賣區金叉 / 築底反轉】"
            item["condition"] = "K > D 且 K < 20"
            item["meaning"] = "指標處於 20 以下極端超賣區，且已由下往上穿越 D 值（低檔金叉或轉強），具備跌深反彈與左側安全邊際。"
            oversold_list.append(item)

        # 條件 2: 賣方警戒區 (超買死叉 / 鈍化)：K < D 且 K > 80
        elif k < d and k > 80.0:
            item = dict(q)
            item["tag"] = "🔴【高檔死叉 / 超買警戒】"
            item["condition"] = "K < D 且 K > 80"
            item["meaning"] = "指標處於 80 以上極端超買區，且已跌破 D 值（高檔死叉），短線動能竭盡，拉回風險高。"
            overbought_list.append(item)

    oversold_list.sort(key=lambda x: x["k"])
    overbought_list.sort(key=lambda x: -x["k"])

    elapsed = round(time.time() - t0, 2)

    return {
        "timestamp": time.time(),
        "total_scanned": len(quotes),
        "oversold": oversold_list,
        "overbought": overbought_list,
        "oversold_symbols": [s["symbol"] for s in oversold_list],
        "overbought_symbols": [s["symbol"] for s in overbought_list],
        "elapsed_seconds": elapsed
    }
