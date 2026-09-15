import os
import json
import re
from google import genai
from google.genai import types
from src.strategy_engine import evaluate_dual_track_system

def rule_based_fallback(
    stock_info: dict,
    valuation_info: dict,
    news_items: list,
    attachment_text: str = "",
    market_data: dict = None
) -> dict:
    """
    Smart rule-based heuristic fallback engine when LLM API Key is not available.
    Adheres strictly to the Dual-Track Decision System:
    - Track 1: Core KD strategy matrix
    - Track 2: Consecutive drop streak and 5 continuation risk rules
    """
    dual_res = evaluate_dual_track_system(stock_info, market_data)
    track1 = dual_res["track1"]
    track2 = dual_res["track2"]
    
    is_etf = valuation_info.get("is_etf", False)
    ratio = valuation_info.get("ratio", 0)
    
    strategy_label = dual_res["strategy_state"]
    base_recommendation = track1.get("recommendation", "中立")
    risk_control = dual_res["risk_control"]
    
    # News Sentiment Heuristics weighting
    news_titles = [n.get("title", "") for n in news_items]
    bull_keywords = ["營收", "新高", "大增", "看好", "看漲", "買進", "擴產", "獲利", "創高", "飆升", "利多"]
    bear_keywords = ["下修", "衰退", "砍單", "重挫", "看空", "賣出", "調降", "利空", "下跌", "暴跌", "警告"]
    
    bull_count = sum(1 for title in news_titles for kw in bull_keywords if kw in title)
    bear_count = sum(1 for title in news_titles for kw in bear_keywords if kw in title)
    
    reasons = [dual_res["integrated_reason"]]
    
    if is_etf and ratio is not None:
        if ratio > 1.0:
            reasons.append(f"⚠️ ETF 顯著溢價 (+{ratio:.2f}%)，警示追高風險")
        elif ratio < -0.5:
            reasons.append(f"💡 ETF 折價 ({ratio:.2f}%)，具價值吸引力")
            
    if bull_count > bear_count:
        reasons.append(f"最新新聞偏多 ({bull_count}則利多資訊)")
    elif bear_count > bull_count:
        reasons.append(f"最新新聞偏空 ({bear_count}則利空訊息)")
        
    if attachment_text:
        reasons.append("已整合上傳策略研報附件條件")
        
    # Standardize rating into main bucket considering dual tracks
    if track2.get("warning"):
        # If Track 2 triggers severe continuation warning, pull rating back to 中立 / 暫緩
        rating = "中立"
    elif "買進" in base_recommendation or "加碼" in base_recommendation:
        rating = "買進"
    elif "賣出" in base_recommendation:
        rating = "賣出"
    else:
        rating = "中立"
        
    summary_reason = "；".join(reasons)
    
    # Citations
    citations = []
    for n in news_items[:3]:
        citations.append({
            "title": n.get("title"),
            "published": n.get("published"),
            "link": n.get("link"),
            "source": n.get("source", "財經新聞")
        })
        
    return {
        "rating": rating,
        "strategy_state": strategy_label,
        "risk_control": risk_control,
        "risk_badge": dual_res["risk_badge"],
        "confidence": "高" if (bull_count != bear_count) else "中",
        "reason": summary_reason,
        "citations": citations,
        "engine": "雙軌決策規則引擎 (KD矩陣 + 連跌風控)",
        "track1": track1,
        "track2": track2,
        "drop_streak": dual_res["drop_streak"],
        "suggested_ratio": dual_res["suggested_ratio"]
    }

def analyze_stock_with_ai(
    stock_info: dict,
    valuation_info: dict,
    news_items: list,
    attachment_text: str = "",
    api_key: str = "",
    market_data: dict = None
) -> dict:
    """
    Analyze stock using Gemini LLM with Dual-Track Decision System.
    Synthesizes Track 1 (KD Matrix) + Track 2 (Drop Streak & Risk Rules) + News & Valuation.
    """
    effective_api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
    
    # Pre-calculate Dual-Track Strategy
    dual_res = evaluate_dual_track_system(stock_info, market_data)
    track1 = dual_res["track1"]
    track2 = dual_res["track2"]
    
    if not effective_api_key:
        return rule_based_fallback(stock_info, valuation_info, news_items, attachment_text, market_data)
        
    symbol = stock_info.get("symbol", "")
    name = stock_info.get("name", "")
    close = stock_info.get("latest_close", 0)
    change_pct = stock_info.get("change_pct", 0)
    signal_info = stock_info.get("signal_info", {})
    signal_text = signal_info.get("status_text", "")
    valuation_text = valuation_info.get("display_text", "")
    
    news_summary_lines = []
    for i, n in enumerate(news_items[:5], 1):
        news_summary_lines.append(f"{i}. 【{n.get('source')}】{n.get('title')} ({n.get('published')}) - URL: {n.get('link')}")
    news_context = "\n".join(news_summary_lines) if news_summary_lines else "近24-48小時無重大新聞。"
    
    prompt = f"""
你是一位專業的台股投資分析師與資產配置專家。本系統採用【雙軌決策系統】：
- 軌道一：保留原有 KD 策略核心邏輯（常規技術訊號，100% 採用 Yahoo 官方 KD）
- 軌道二：連跌分批與 5 項續跌風控判斷（左側加碼與防禦機制）

【當前標的雙軌演算結果】
- 股票代號/名稱: {symbol} ({name})
- 最新收盤價: ${close:.2f} (單日漲跌幅: {change_pct:+.2f}%)
- 9日 KD 數據: K值 = {track1['k']:.2f}, D值 = {track1['d']:.2f} ({signal_text})
- 軌道一 (KD策略建議): {track1['rule_name']} -> {dual_res['strategy_state']}
- 軌道二 (連跌與風控): 連跌天數 = {dual_res['drop_streak']} 天 -> {dual_res['risk_control']} (建議配置: {dual_res['suggested_ratio']})
- 折溢價比/估值評估: {valuation_text}

【近 24-48 小時財經新聞】
{news_context}

【研報/策略附件規則內容】
{attachment_text if attachment_text else "無附件內容。"}

【任務要求】
1. 同時闡釋【軌道一 KD 狀態】與【軌道二 連跌/風控策略】，若為連跌個股應特別說明左側加碼或暫緩防禦之考量；若為平盤/上漲個股應確認移動停利。
2. 權衡最新新聞事件與 ETF 折溢價/個股估值對決策的加減分效果。
3. 回應必須為嚴格 JSON 格式（不可添加任何多餘說明）：
{{
  "rating": "買進" | "中立" | "賣出",
  "strategy_state": "{dual_res['strategy_state']}",
  "risk_control": "{dual_res['risk_control']}",
  "confidence": "高" | "中" | "低",
  "reason": "綜合雙軌系統（軌道一KD與軌道二連跌風控）及新聞估值的精簡理由 (120字以內)",
  "cited_indices": [1, 2]  // 有引用的新聞編號 (1-based index)
}}
"""

    try:
        client = genai.Client(api_key=effective_api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
                top_p=0.9,
            )
        )
        
        raw_text = response.text.strip()
        cleaned_text = re.sub(r"^```json\s*", "", raw_text)
        cleaned_text = re.sub(r"^```\s*", "", cleaned_text)
        cleaned_text = re.sub(r"\s*```$", "", cleaned_text)
        
        parsed = json.loads(cleaned_text)
        
        rating = parsed.get("rating", track1["recommendation"])
        if track2.get("warning"):
            rating = "中立"
        elif rating not in ["買進", "中立", "賣出"]:
            rating = "買進" if "買進" in track1["recommendation"] else ("賣出" if "賣出" in track1["recommendation"] else "中立")
            
        strategy_state = parsed.get("strategy_state", dual_res["strategy_state"])
        risk_control = parsed.get("risk_control", dual_res["risk_control"])
        confidence = parsed.get("confidence", "高")
        reason = parsed.get("reason", dual_res["integrated_reason"])
        cited_indices = parsed.get("cited_indices", [])
        
        citations = []
        for idx in cited_indices:
            if isinstance(idx, int) and 1 <= idx <= len(news_items):
                n = news_items[idx - 1]
                citations.append({
                    "title": n.get("title"),
                    "published": n.get("published"),
                    "link": n.get("link"),
                    "source": n.get("source")
                })
                
        if not citations and news_items:
            for n in news_items[:2]:
                citations.append({
                    "title": n.get("title"),
                    "published": n.get("published"),
                    "link": n.get("link"),
                    "source": n.get("source")
                })
                
        return {
            "rating": rating,
            "strategy_state": strategy_state,
            "risk_control": risk_control,
            "risk_badge": dual_res["risk_badge"],
            "confidence": confidence,
            "reason": reason,
            "citations": citations,
            "engine": "Gemini 2.5 Flash (雙軌決策系統)",
            "track1": track1,
            "track2": track2,
            "drop_streak": dual_res["drop_streak"],
            "suggested_ratio": dual_res["suggested_ratio"]
        }
        
    except Exception as e:
        print(f"Gemini API Call failed: {e}. Using fallback engine.")
        res = rule_based_fallback(stock_info, valuation_info, news_items, attachment_text, market_data)
        res["engine"] += f" (LLM 呼叫異常後備方案)"
        return res
