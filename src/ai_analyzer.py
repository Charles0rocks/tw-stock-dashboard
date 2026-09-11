import os
import json
import re
from google import genai
from google.genai import types
from src.stock_data import evaluate_kd_strategy_rule

def rule_based_fallback(stock_info: dict, valuation_info: dict, news_items: list, attachment_text: str = "") -> dict:
    """
    Smart rule-based heuristic fallback engine when LLM API Key is not available.
    Adheres strictly to the mandatory 6 KD Strategy Rules as the core decision matrix.
    """
    k = stock_info.get("k", 50)
    d = stock_info.get("d", 50)
    signal_info = stock_info.get("signal_info", {})
    rule_info = signal_info.get("rule_info") or evaluate_kd_strategy_rule(k, d)
    
    is_etf = valuation_info.get("is_etf", False)
    ratio = valuation_info.get("ratio", 0)
    
    strategy_label = rule_info.get("label", "【觀望】")
    base_recommendation = rule_info.get("recommendation", "中立")
    strategy_desc = rule_info.get("strategy_desc", "")
    risk_control = rule_info.get("risk_control", "")
    
    # News Sentiment Heuristics weighting
    news_titles = [n.get("title", "") for n in news_items]
    bull_keywords = ["營收", "新高", "大增", "看好", "看漲", "買進", "擴產", "獲利", "創高", "飆升", "利多"]
    bear_keywords = ["下修", "衰退", "砍單", "重挫", "看空", "賣出", "調降", "利空", "下跌", "暴跌", "警告"]
    
    bull_count = sum(1 for title in news_titles for kw in bull_keywords if kw in title)
    bear_count = sum(1 for title in news_titles for kw in bear_keywords if kw in title)
    
    reasons = [f"核心KD矩陣：符合 {rule_info.get('rule_name')} -> {strategy_label}"]
    
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
        
    # Standardize rating into main bucket
    if "買進" in base_recommendation or "加碼" in base_recommendation:
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
        "confidence": "高" if (bull_count != bear_count) else "中",
        "reason": summary_reason,
        "citations": citations,
        "engine": "KD矩陣啟發式規則引擎"
    }

def analyze_stock_with_ai(
    stock_info: dict,
    valuation_info: dict,
    news_items: list,
    attachment_text: str = "",
    api_key: str = ""
) -> dict:
    """
    Analyze stock using Gemini LLM.
    Integrates the 6 KD Strategy Rules as the mandatory core foundation,
    synthesized with 24-48h news events and attachment rules.
    """
    effective_api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
    
    # Get pre-calculated KD Strategy Rule Matrix info
    k = stock_info.get("k", 50)
    d = stock_info.get("d", 50)
    signal_info = stock_info.get("signal_info", {})
    rule_info = signal_info.get("rule_info") or evaluate_kd_strategy_rule(k, d)
    
    if not effective_api_key:
        return rule_based_fallback(stock_info, valuation_info, news_items, attachment_text)
        
    symbol = stock_info.get("symbol", "")
    name = stock_info.get("name", "")
    close = stock_info.get("latest_close", 0)
    change_pct = stock_info.get("change_pct", 0)
    signal_text = signal_info.get("status_text", "")
    valuation_text = valuation_info.get("display_text", "")
    
    news_summary_lines = []
    for i, n in enumerate(news_items[:5], 1):
        news_summary_lines.append(f"{i}. 【{n.get('source')}】{n.get('title')} ({n.get('published')}) - URL: {n.get('link')}")
    news_context = "\n".join(news_summary_lines) if news_summary_lines else "近24-48小時無重大新聞。"
    
    prompt = f"""
你是一位專業的台股投資分析師與資產配置專家。請以以下【核心 KD 策略規則矩陣】為主要判斷基礎，結合新聞事件與附件研報進行權衡觀點分析。

【核心 KD 策略規則矩陣】
1. K > D 且 K < 20: 【買進】分批建倉 (超賣轉折；若折價>0.5%佳，溢價<0.3%) | 風控: 設9日低點停損
2. K > D 且 20 ≤ K ≤ 80: 【續抱 / 加碼買進】 (常態多頭；溢價<0.5%佳，溢價>1%暫停加碼) | 風控: 設移動停利(破10日線或死叉)
3. K > D 且 K > 80: 【續抱不追高】 (高檔強勢；常伴隨溢價>1%，禁止追買) | 風控: 設高檔移動停利，死叉即獲利了結
4. K < D 且 K > 80: 【賣出】獲利了結 (超買轉折高檔死叉；大幅溢價>1%加速出場) | 風控: 即刻分批停利獲利了結
5. K < D 且 20 ≤ K ≤ 80: 【觀望 / 減碼賣出】 (常態空頭；不以折價逆勢搶進) | 風控: 跌破重要均線/支撐線停損
6. K < D 且 K < 20: 【觀望】嚴禁買進 (低檔極弱趕底；折價>1%恐慌拋售未收斂，嚴禁猜底) | 風控: 嚴禁低檔摸底，靜待黃金交叉

【當前標的數據】
- 股票代號/名稱: {symbol} ({name})
- 最新收盤價: ${close:.2f} (單日漲跌幅: {change_pct:+.2f}%)
- 9日 KD 數據: K值 = {k:.2f}, D值 = {d:.2f} ({signal_text})
- 匹配的核心規則: {rule_info['rule_name']} -> {rule_info['label']}
- 風控停損/停利條款: {rule_info['risk_control']}
- 折溢價比/估值評估: {valuation_text}

【近 24-48 小時財經新聞】
{news_context}

【研報/策略附件規則內容】
{attachment_text if attachment_text else "無附件內容。"}

【任務要求】
1. 以匹配的核心 KD 策略規則矩陣為基準。
2. 權衡最新新聞事件與 ETF 折溢價/個股估值對決策的加減分效果。
3. 回應必須為嚴格 JSON 格式（不可添加任何多餘說明）：
{{
  "rating": "買進" | "中立" | "賣出",
  "strategy_state": "{rule_info['label']}",
  "risk_control": "{rule_info['risk_control']}",
  "confidence": "高" | "中" | "低",
  "reason": "以KD規則為基底，結合新聞與折溢價的綜合權衡理由 (100字以內)",
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
        
        rating = parsed.get("rating", rule_info["recommendation"])
        if rating not in ["買進", "中立", "賣出"]:
            rating = "買進" if "買進" in rule_info["recommendation"] else ("賣出" if "賣出" in rule_info["recommendation"] else "中立")
            
        strategy_state = parsed.get("strategy_state", rule_info["label"])
        risk_control = parsed.get("risk_control", rule_info["risk_control"])
        confidence = parsed.get("confidence", "高")
        reason = parsed.get("reason", f"遵循 KD 矩陣 {rule_info['label']} 策略，結合新聞面綜合評估。")
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
            "confidence": confidence,
            "reason": reason,
            "citations": citations,
            "engine": "Gemini 2.5 Flash (KD核心矩陣引擎)"
        }
        
    except Exception as e:
        print(f"Gemini API Call failed: {e}. Using fallback engine.")
        res = rule_based_fallback(stock_info, valuation_info, news_items, attachment_text)
        res["engine"] += f" (LLM 呼叫異常後備方案)"
        return res
