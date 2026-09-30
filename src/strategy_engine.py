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
    二、KD 策略狀態機實裝 (嚴格依照下列四大優先順序與條件判定)：

    1. 【第一優先：債券標的低檔分流 (is_bond == True 且 K <= 30)】
       - IF is_bond AND K <= 30:
         * IF K > D:
           - 狀態文字 = "【低檔轉強／鎖利加碼】"
           - 燈號 = 🟢 加碼
           - 說明 = "債券跌深出現低檔黃金交叉，兼具高殖利率鎖利與反彈資本利得空間，啟動分批加碼。"
         * IF K <= D:
           - 狀態文字 = "【低檔鎖利／領息觀望】"
           - 燈號 = 🟡 觀望
           - 說明 = "固定收益標的具保底息收特質，低檔鈍化不殺低，現有部位安心領息，靜待動能止穩。"

    2. 【第二優先：高檔超買區 (K >= 80)】
       - IF K >= 80:
         * IF K > D:
           - 狀態文字 = "【續抱不追高】"
           - 燈號 = 🟢 續抱
           - 說明 = "多頭強勢但正乖離擴大，持股續抱，嚴禁追高，隨時注意反轉風險。"
         * IF K <= D:
           - 狀態文字 = "【高檔減碼／獲利了結】"
           - 燈號 = 🔴 減碼
           - 說明 = "高檔動能竭盡並向下死叉，啟動波段減碼，鎖定獲利。"

    3. 【第三優先：一般股票之低檔超賣區 (is_bond == False 且 K <= 30)】
       - IF not is_bond AND K <= 30:
         * IF K > D:
           - 狀態文字 = "【低檔轉強／分批加碼】"
           - 燈號 = 🟢 加碼
           - 說明 = "超賣區出現低檔黃金交叉，跌深落後補漲，啟動左側分批加碼。"
         * IF K <= D:
           - 狀態文字 = "【空方鈍化／禁止接刀】"
           - 燈號 = 🔴 警戒
           - 說明 = "指標低檔鈍化，空方主導嚴禁盲目攤平，跌破前低仍須紀律停損。"
           - 風控聯動：主動檢查是否符合「光腳黑棒收最低」或「無量陰跌破底」，若符合則追加警示「⚠️ 留意空方慣性破底，未見長下影線或爆量前切勿進場」。

    4. 【第四優先：中軸震盪區 (30 < K < 80)】
       - ELSE:
         * IF K > D:
           - 狀態文字 = "【偏多持股】"
           - 燈號 = 🟢 偏多
           - 說明 = "股價重回多頭軌道，部位順勢續抱。"
         * IF K <= D:
           - 狀態文字 = "【持股觀望】"
           - 燈號 = ⚪ 中立
           - 說明 = "盤勢進入中性整理，停止追加部位，靜待方向明朗。"
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

    # 1. 第一優先：債券標的低檔分流 (is_bond == True 且 K <= 30)
    if is_bond and k <= 30.0:
        if k > d:
            label = "【低檔轉強／鎖利加碼】"
            light = "🟢 加碼"
            badge = "🟢 【低檔轉強／鎖利加碼】"
            rec = "買進"
            rule_name = "債券低檔金叉 (is_bond 且 K <= 30, K > D)"
            desc = "債券跌深出現低檔黃金交叉，兼具高殖利率鎖利與反彈資本利得空間，啟動分批加碼。"
            risk_ctrl = "鎖利加碼部位，防範降息路徑反覆，以分批佈局領息為主"
        else:
            label = "【低檔鎖利／領息觀望】"
            light = "🟡 觀望"
            badge = "🟡 【低檔鎖利／領息觀望】"
            rec = "中立"
            rule_name = "債券低檔鈍化 (is_bond 且 K <= 30, K <= D)"
            desc = "固定收益標的具保底息收特質，低檔鈍化不殺低，現有部位安心領息，靜待動能止穩。"
            risk_ctrl = "現有部位安心領息，不盲目殺低，靜待KD由下往上金叉轉折"

    # 2. 第二優先：高檔超買區 (K >= 80)
    elif k >= 80.0:
        if k > d:
            label = "【續抱不追高】"
            light = "🟢 續抱"
            badge = "🟢 【續抱不追高】"
            rec = "續抱"
            rule_name = "高檔超買鈍化 (K >= 80 且 K > D)"
            desc = "多頭強勢但正乖離擴大，持股續抱，嚴禁追高，隨時注意反轉風險。"
            risk_ctrl = "設高檔移動停利點，嚴禁追高，若跌破5日線或死叉即刻獲利了結"
        else:
            label = "【高檔減碼／獲利了結】"
            light = "🔴 減碼"
            badge = "🔴 【高檔減碼／獲利了結】"
            rec = "賣出"
            rule_name = "高檔超買死叉 (K >= 80 且 K <= D)"
            desc = "高檔動能竭盡並向下死叉，啟動波段減碼，鎖定獲利。"
            risk_ctrl = "即刻分批停利獲利了結，防動能竭盡後之大幅拉回修正"

    # 3. 第三優先：一般股票之低檔超賣區 (is_bond == False 且 K <= 30)
    elif (not is_bond) and k <= 30.0:
        if k > d:
            label = "【低檔轉強／分批加碼】"
            light = "🟢 加碼"
            badge = "🟢 【低檔轉強／分批加碼】"
            rec = "買進"
            rule_name = "股票低檔超賣金叉 (K <= 30 且 K > D)"
            desc = "超賣區出現低檔黃金交叉，跌深落後補漲，啟動左側分批加碼。"
            risk_ctrl = "設近9日最低點為紀律停損點，防無底跌勢續摔"
        else:
            label = "【空方鈍化／禁止接刀】"
            light = "🔴 警戒"
            badge = "🔴 【空方鈍化／禁止接刀】"
            rec = "賣出"
            rule_name = "股票低檔超賣死叉 (K <= 30 且 K <= D)"
            desc = "指標低檔鈍化，空方主導嚴禁盲目攤平，跌破前低仍須紀律停損。"
            bottom_break = check_bottom_break_risk(df)
            if bottom_break["has_risk"]:
                risk_warning = bottom_break["warning_msg"]
                risk_ctrl = f"空方極弱勢鈍化；{risk_warning}，嚴格執行紀律停損"
            else:
                risk_ctrl = "空方主導嚴禁盲目攤平接刀，跌破前低支撐務必嚴格執行停損"

    # 4. 第四優先：中軸震盪區 (30 < K < 80)
    else:
        if k > d:
            label = "【偏多持股】"
            light = "🟢 偏多"
            badge = "🟢 【偏多持股】"
            rec = "買進"
            rule_name = "中軸偏多 (30 < K < 80 且 K > D)"
            desc = "股價重回多頭軌道，部位順勢續抱。"
            risk_ctrl = "設常規移動停利（如10日均線或KD死叉），部位順勢續抱"
        else:
            label = "【持股觀望】"
            light = "⚪ 中立"
            badge = "⚪ 【持股觀望】"
            rec = "中立"
            rule_name = "中軸中立整理 (30 < K < 80 且 K <= D)"
            desc = "盤勢進入中性整理，停止追加部位，靜待方向明朗。"
            risk_ctrl = "中立整理區間多看少做，停止追加部位，靜待量能表態或金叉"

    return {
        "rule_name": rule_name,
        "recommendation": rec,
        "label": label,
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
