import sys
if sys.stdout and getattr(sys.stdout, 'encoding', None) != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

import unittest
from src.strategy_engine import screen_kd_extremes

class TestKDScreener(unittest.TestCase):
    def test_screener_math_conditions(self):
        """測試極端值選股之嚴格數學不等式與標籤判定"""
        # 測試樣本資料
        test_quotes = [
            # 應符合超賣：K > D 且 K < 20
            {"symbol": "1101.TW", "name": "台泥", "k": 18.5, "d": 15.0, "change_pct": 1.2, "latest_close": 32.0, "volume_display": "1,000 張"},
            {"symbol": "2324.TW", "name": "仁寶", "k": 19.9, "d": 19.5, "change_pct": 0.5, "latest_close": 28.0, "volume_display": "2,000 張"},
            
            # 不符合超賣 (K < D 雖然 K < 20)
            {"symbol": "9999.TW", "name": "測試A", "k": 15.0, "d": 18.0, "change_pct": -1.0, "latest_close": 50.0, "volume_display": "500 張"},
            # 不符合超賣 (K >= 20 雖然 K > D)
            {"symbol": "9998.TW", "name": "測試B", "k": 20.1, "d": 18.0, "change_pct": 1.0, "latest_close": 50.0, "volume_display": "500 張"},

            # 應符合超買：K < D 且 K > 80
            {"symbol": "3605.TW", "name": "宏致", "k": 82.0, "d": 85.0, "change_pct": -2.0, "latest_close": 60.0, "volume_display": "3,000 張"},
            {"symbol": "2330.TW", "name": "台積電", "k": 80.5, "d": 81.0, "change_pct": -0.5, "latest_close": 1000.0, "volume_display": "10,000 張"},

            # 不符合超買 (K > D 雖然 K > 80)
            {"symbol": "9997.TW", "name": "測試C", "k": 85.0, "d": 82.0, "change_pct": 2.5, "latest_close": 120.0, "volume_display": "800 張"},
            # 不符合超買 (K <= 80 雖然 K < D)
            {"symbol": "9996.TW", "name": "測試D", "k": 79.9, "d": 82.0, "change_pct": -1.5, "latest_close": 90.0, "volume_display": "800 張"},

            # 中性區間
            {"symbol": "2317.TW", "name": "鴻海", "k": 55.0, "d": 52.0, "change_pct": 0.0, "latest_close": 180.0, "volume_display": "5,000 張"},
        ]

        from unittest.mock import patch
        with patch("src.stock_data.fetch_batch_quotes_kd", return_value=test_quotes):
            result = screen_kd_extremes(limit=50)

            oversold = result["oversold"]
            overbought = result["overbought"]

            # 驗證超賣組
            oversold_syms = [s["symbol"] for s in oversold]
            self.assertEqual(oversold_syms, ["1101.TW", "2324.TW"])
            for s in oversold:
                self.assertGreater(s["k"], s["d"])
                self.assertLess(s["k"], 20.0)
                self.assertEqual(s["tag"], "🟢【超賣區金叉 / 築底反轉】")

            # 驗證超買組
            overbought_syms = [s["symbol"] for s in overbought]
            self.assertEqual(set(overbought_syms), {"3605.TW", "2330.TW"})
            for s in overbought:
                self.assertLess(s["k"], s["d"])
                self.assertGreater(s["k"], 80.0)
                self.assertEqual(s["tag"], "🔴【高檔死叉 / 超買警戒】")

    def test_live_screener_execution_and_speed(self):
        """測試即時全市場快速選股執行時間 < 5.0 秒，且格式完備"""
        res = screen_kd_extremes(limit=100)
        self.assertLess(res["elapsed_seconds"], 5.0, f"選股執行耗時超過 5 秒: {res['elapsed_seconds']}s")
        self.assertGreater(res["total_scanned"], 0, "應至少掃描大於 0 檔股票")
        
        # 驗證超賣輸出格式與條件
        for s in res["oversold"]:
            self.assertGreater(s["k"], s["d"], f"{s['symbol']} K 應大於 D: {s['k']} vs {s['d']}")
            self.assertLess(s["k"], 20.0, f"{s['symbol']} K 應小於 20: {s['k']}")
            self.assertIn("🟢", s["tag"])

        # 驗證超買輸出格式與條件
        for s in res["overbought"]:
            self.assertLess(s["k"], s["d"], f"{s['symbol']} K 應小於 D: {s['k']} vs {s['d']}")
            self.assertGreater(s["k"], 80.0, f"{s['symbol']} K 應大於 80: {s['k']}")
            self.assertIn("🔴", s["tag"])

if __name__ == "__main__":
    unittest.main()
