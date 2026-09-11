import sys
if sys.stdout and getattr(sys.stdout, 'encoding', None) != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

import pandas as pd
from src.stock_data import get_verified_stock_metrics

def run_test():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        
    print("==========================================================================")
    print("=== Yahoo 奇摩股市官方技術線 KD 與成交量驗證 (Official KD Test) ===")
    print("==========================================================================")
    
    test_symbols = ['00720B', '0056', '2308', '2330', '00878']
    
    for symbol in test_symbols:
        res = get_verified_stock_metrics(symbol)
        if res.get("success"):
            k_fmt = f"{res['k']:.2f}" if round(res['k'], 1) != round(res['k'], 2) else f"{res['k']:.1f}"
            d_fmt = f"{res['d']:.2f}" if round(res['d'], 1) != round(res['d'], 2) else f"{res['d']:.1f}"
            v_status = "✅ Yahoo官方源" if res['is_verified'] else "⚠️ 自算備援"
            
            print(f"標的: {res['symbol']:12s} ({res['name']:10s})")
            print(f"  - 資料日期:       {res['latest_date']}")
            print(f"  - 當日現價:       ${res['latest_close']:.2f} ({res['change_pct']:+.2f}%)")
            print(f"  - 官方直連指標:   9K = {k_fmt}, 9D = {d_fmt} ({v_status})")
            print(f"  - KD策略建議狀態: {res['signal_info']['rule_info']['label']}")
            print(f"  - 成交量 (張):    {res.get('volume_display', 'N/A')}")
            
            if symbol.startswith("00720B"):
                k_ok = (res['k'] == 7.91)
                d_ok = (res['d'] == 16.34)
                vol_ok = (res.get('volume_lots') == 1858)
                state_ok = ("超賣區" in res['signal_info']['rule_info']['label'] and "尋求築底" in res['signal_info']['rule_info']['label'])
                if k_ok and d_ok and vol_ok and state_ok:
                    print(f"\n  >>> 00720B 9K = {res['k']}, 9D = {res['d']}，成交量 {res['volume_lots']} 張，策略狀態正確。")
                else:
                    print(f"\n  >>> [00720B 校驗細節]: 9K={res['k']} (期待 7.91) | 9D={res['d']} (期待 16.34) | 量={res.get('volume_lots')} (期待 1858) | 狀態={res['signal_info']['rule_info']['label']}")
            elif symbol.startswith("0056"):
                print(f"  >>> [0056 檢驗結果]: 9K = {k_fmt}, 9D = {d_fmt}，成交量 = {res.get('volume_display')}")
                
            print("--------------------------------------------------------------------------")
        else:
            print(f"標的: {symbol} - 失敗: {res.get('error')}")

if __name__ == "__main__":
    run_test()
