"""
Dual-Track Decision System Engine (雙軌決策系統引擎)
Track 1: KD 常規技術矩陣核心邏輯 (100% Yahoo 奇摩股市官方數據與 6 大規則 + 50軸橫盤判定)
Track 2: 連跌分批與 5 項續跌風控判斷 (左側加碼與防禦機制)
"""
import pandas as pd
import numpy as np

def evaluate_track1_kd(k: float, d: float, prev_k: float = None, prev_d: float = None) -> dict:
    """
    軌道一：保留原有 KD 策略核心邏輯（常規技術訊號）
    - 100% 採用 Yahoo 股市官方數據
    - 判定規則：
      1. 50 軸附近橫盤黏合：【中性盤整 / 觀望】
      2. K > D 且 20 <= K <= 80：【續抱 / 加碼買進】
      3. K > D 且 K > 80：【超買鈍化 / 續抱不追高】
      4. K > D 且 K < 20：【買進】分批建倉
      5. K < D 且 20 <= K <= 80：【觀望 / 減碼賣出】
      6. K < D 且 K < 20：【超賣區 / 尋求築底】
      7. K < D 且 K > 80：【賣出】獲利了結
    """
    # 50 軸附近橫盤黏合/糾結判定
    if 40.0 <= k <= 60.0 and abs(k - d) <= 5.0:
        label = "【中性盤整 / 觀望】"
        badge = "⚪ 中性盤整/觀望"
        rec = "中立"
        rule_name = "KD 50 軸附近橫盤黏合"
        desc = "KD 雙線處於 50 軸附近的橫盤盲目黏合，多空力道均衡，無明確方向。"
        risk_ctrl = "建議中性觀望多看少做，靜待帶量突破或走出清晰發散方向"
    elif k > d:
        if k < 20.0:
            label = "【買進】分批建倉"
            badge = "🟢 買進 (分批建倉)"
            rec = "買進"
            rule_name = "K > D 且 K < 20"
            desc = "超賣轉折分批建倉（若 ETF 折價 > 0.5% 佳，溢價 < 0.3%）。"
            risk_ctrl = "設近9日低點為停損點，防無底跌勢續摔"
        elif k <= 80.0:
            label = "【續抱 / 加碼買進】"
            badge = "🟢 續抱/加碼買進"
            rec = "買進"
            rule_name = "K > D 且 20 ≤ K ≤ 80"
            desc = "常態多頭格局（溢價 < 0.5% 為佳，溢價 > 1% 暫停加碼）。"
            risk_ctrl = "設移動停利（如退回10日線跌破，或 K < D 死叉出場）"
        else: # k > 80
            label = "【超買鈍化 / 續抱不追高】"
            badge = "🟡 續抱不追高"
            rec = "中立"
            rule_name = "K > D 且 K > 80"
            desc = "高檔強勢格局（常伴隨溢價 > 1%，禁止追買）。"
            risk_ctrl = "設高檔移動停利，K < D 死叉即刻部分獲利了結"
    else: # k <= d
        if k > 80.0:
            label = "【賣出】獲利了結"
            badge = "🔴 賣出 (獲利了結)"
            rec = "賣出"
            rule_name = "K < D 且 K > 80"
            desc = "超買轉折高檔死叉（大幅溢價 > 1% 時加速出場）。"
            risk_ctrl = "即刻分批停利獲利了結，防大幅修正"
        elif k >= 20.0:
            label = "【觀望 / 減碼賣出】"
            badge = "🟠 觀望/減碼賣出"
            rec = "賣出"
            rule_name = "K < D 且 20 ≤ K ≤ 80"
            desc = "常態空頭整理（不以折價逆勢搶進）。"
            risk_ctrl = "跌破重要均線/支撐線即刻停損，觀望為主"
        else: # k < 20
            label = "【超賣區 / 尋求築底】"
            badge = "💡 超賣區/尋求築底"
            rec = "中立"
            rule_name = "K < D 且 K < 20"
            desc = "KD 雙線處於 20 以下極低檔超賣區，尋求築底轉折（恐慌拋售未收斂，嚴禁盲目猜底）。"
            risk_ctrl = "超賣區觀察築底，靜待 K > D 黃金交叉出現轉折訊號"

    # 即時金叉/死叉訊號
    cross_signal = ""
    if prev_k is not None and prev_d is not None:
        if prev_k <= prev_d and k > d:
            cross_signal = "黃金交叉 🚀"
        elif prev_k >= prev_d and k < d:
            cross_signal = "死亡交叉 📉"

    return {
        "rule_name": rule_name,
        "recommendation": rec,
        "label": label,
        "badge": badge,
        "strategy_desc": desc,
        "risk_control": risk_ctrl,
        "cross_signal": cross_signal,
        "k": k,
        "d": d
    }

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
    
    # 1. 軌道一：KD 常規技術矩陣
    track1 = evaluate_track1_kd(k, d, prev_k, prev_d)
    
    # 2. 軌道二：連跌分批與風控判斷
    df = stock_data.get("df")
    track2 = evaluate_track2_risk(df, stock_data, market_data)
    
    # 3. 雙軌整合權衡理由建構
    streak = track2["drop_streak"]
    reasons = []
    reasons.append(f"【軌道一 KD】{track1['label']} (9K={k:.1f}, 9D={d:.1f})")
    
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
