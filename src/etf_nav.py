import requests
import re
import yfinance as yf

def is_etf(symbol: str, info: dict = None) -> bool:
    """Check if the stock symbol is a Taiwan ETF"""
    clean_symbol = symbol.split(".")[0]
    if clean_symbol.startswith("00"):
        return True
    if info and info.get("quoteType") == "ETF":
        return True
    return False

def fetch_etf_nav_fallback(symbol: str) -> float:
    """Fallback fetcher for ETF NAV using web scraping if yfinance navPrice is missing"""
    code = symbol.split(".")[0]
    # Try Yahoo Finance Taiwan ETF NAV page
    url = f"https://tw.stock.yahoo.com/quote/{code}.TW/real-time-nav"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            # Look for NAV price in HTML text e.g., "淨值" followed by digits
            matches = re.findall(r'"navPrice":\s*"([0-9\.]+)"', resp.text)
            if matches:
                return float(matches[0])
            matches_text = re.findall(r'淨值[^\d]*([0-9]+\.[0-9]+)', resp.text)
            if matches_text:
                return float(matches_text[0])
    except Exception:
        pass
    return None

def get_valuation_or_nav(symbol: str, current_price: float, info: dict = None) -> dict:
    """
    Calculate ETF Premium/Discount ratio (%) or Individual Stock PE ratio.
    Returns dict with value, formatted text, and type.
    """
    info = info or {}
    etf_flag = is_etf(symbol, info)
    
    if etf_flag:
        # ETF: Compute Premium / Discount Ratio
        nav_price = info.get("navPrice") or info.get("openNAV")
        if not nav_price or nav_price <= 0:
            # Try fallback web fetch
            nav_price = fetch_etf_nav_fallback(symbol)
            
        if nav_price and nav_price > 0:
            diff = current_price - nav_price
            ratio = (diff / nav_price) * 100.0
            
            if ratio > 0:
                text = f"溢價 +{ratio:.2f}% (淨值:{nav_price:.2f})"
                status = "premium"
            else:
                text = f"折價 {ratio:.2f}% (淨值:{nav_price:.2f})"
                status = "discount"
                
            return {
                "is_etf": True,
                "nav": nav_price,
                "current_price": current_price,
                "ratio": ratio,
                "display_text": text,
                "status": status
            }
        else:
            return {
                "is_etf": True,
                "nav": None,
                "current_price": current_price,
                "ratio": None,
                "display_text": "N/A (無淨值資料)",
                "status": "unknown"
            }
    else:
        # Individual stock: Return P/E or P/B valuation
        pe = info.get("trailingPE") or info.get("forwardPE")
        pb = info.get("priceToBook")
        
        parts = []
        if pe:
            parts.append(f"PE: {pe:.1f}x")
        if pb:
            parts.append(f"PB: {pb:.1f}x")
            
        val_str = ", ".join(parts) if parts else "估值合理"
        
        return {
            "is_etf": False,
            "pe": pe,
            "pb": pb,
            "ratio": None,
            "display_text": f"N/A ({val_str})",
            "status": "stock"
        }
