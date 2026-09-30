import sys
if sys.stdout and getattr(sys.stdout, 'encoding', None) != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

import unittest
import pandas as pd
import numpy as np

from src.strategy_engine import (
    check_is_bond,
    check_bottom_break_risk,
    evaluate_deterministic_kd_state,
    evaluate_track1_kd,
    evaluate_dual_track_system
)

class TestDeterministicKD(unittest.TestCase):
    def test_check_is_bond(self):
        # 債券代碼結尾帶 B
        self.assertTrue(check_is_bond("00720B"))
        self.assertTrue(check_is_bond("00720B.TWO"))
        self.assertTrue(check_is_bond("00679B.TW"))
        self.assertTrue(check_is_bond("00687B"))
        self.assertTrue(check_is_bond("00937B.TWO"))

        # 債券關鍵字
        self.assertTrue(check_is_bond("00720B", "元大投資級公司債"))
        self.assertTrue(check_is_bond("00679B", "元大美債20年"))
        self.assertTrue(check_is_bond("00724B", "群益10年IG金融債"))
        self.assertTrue(check_is_bond("TEST", "富邦特選美債"))

        # 一般股票與股票型 ETF
        self.assertFalse(check_is_bond("2330.TW", "台積電"))
        self.assertFalse(check_is_bond("2317.TW", "鴻海"))
        self.assertFalse(check_is_bond("2454.TW", "聯發科"))
        self.assertFalse(check_is_bond("0050.TW", "元大台灣50"))
        self.assertFalse(check_is_bond("0056.TW", "元大高股息"))
        self.assertFalse(check_is_bond("00878.TW", "國泰永續高股息"))

    def test_bond_mandatory_clause(self):
        # 驗證 00720B（K=30.4, D=47.5）：命中債券條款 -> 【低檔鎖利／蓋牌領息觀望】，評級為「中立」
        res_00720b = evaluate_deterministic_kd_state(k=30.4, d=47.5, is_bond=True)
        self.assertEqual(res_00720b["label"], "【低檔鎖利／蓋牌領息觀望】")
        self.assertEqual(res_00720b["action_type"], "中立")
        self.assertEqual(res_00720b["recommendation"], "中立")
        self.assertEqual(res_00720b["light"], "🟡 觀望")
        self.assertIn("切勿砍在阿呆谷", res_00720b["strategy_desc"])

        # 債券低檔金叉 (is_bond=True, K <= 30, K > D)
        res_gold = evaluate_deterministic_kd_state(k=15.0, d=10.0, is_bond=True)
        self.assertEqual(res_gold["label"], "【低檔轉強／鎖利加碼】")
        self.assertEqual(res_gold["action_type"], "買進")
        self.assertEqual(res_gold["light"], "🟢 加碼")

    def test_dimension1_bullish_k_over_d(self):
        # K >= 80: 【續抱不追高】 (買進)
        res_80 = evaluate_deterministic_kd_state(k=85.0, d=80.0, is_bond=False)
        self.assertEqual(res_80["label"], "【續抱不追高】")
        self.assertEqual(res_80["action_type"], "買進")
        self.assertEqual(res_80["light"], "🟢 續抱")

        # 60 <= K < 80: 【順勢偏多／輕倉試單】 (買進)
        res_60 = evaluate_deterministic_kd_state(k=72.0, d=68.0, is_bond=False)
        self.assertEqual(res_60["label"], "【順勢偏多／輕倉試單】")
        self.assertEqual(res_60["action_type"], "買進")
        self.assertEqual(res_60["light"], "🟢 偏多")

        # 20 < K < 60: 【多頭復甦／持股觀望】 (中立)
        res_mid = evaluate_deterministic_kd_state(k=55.0, d=45.0, is_bond=False)
        self.assertEqual(res_mid["label"], "【多頭復甦／持股觀望】")
        self.assertEqual(res_mid["action_type"], "中立")
        self.assertEqual(res_mid["light"], "⚪ 觀望")

        # K <= 20: 【低檔黃金交叉／分批佈局】 (買進)
        res_low = evaluate_deterministic_kd_state(k=18.0, d=12.0, is_bond=False)
        self.assertEqual(res_low["label"], "【低檔黃金交叉／分批佈局】")
        self.assertEqual(res_low["action_type"], "買進")
        self.assertEqual(res_low["light"], "🟢 佈局")

    def test_dimension2_bearish_k_under_d(self):
        # K >= 80: 【高檔死叉／獲利了結】 (賣出)
        res_80 = evaluate_deterministic_kd_state(k=82.0, d=86.0, is_bond=False)
        self.assertEqual(res_80["label"], "【高檔死叉／獲利了結】")
        self.assertEqual(res_80["action_type"], "賣出")
        self.assertEqual(res_80["light"], "🔴 賣出")

        # 60 <= K < 80 (如 0056 K=66.4, D=69.1): 【持股觀望／停止加碼】 (中立)
        res_0056 = evaluate_deterministic_kd_state(k=66.4, d=69.1, is_bond=False)
        self.assertEqual(res_0056["label"], "【持股觀望／停止加碼】")
        self.assertEqual(res_0056["action_type"], "中立")
        self.assertEqual(res_0056["recommendation"], "中立")
        self.assertEqual(res_0056["light"], "⚪ 觀望")

        # 20 < K < 60: 【持股觀望／禁止加碼】 (中立)
        res_mid = evaluate_deterministic_kd_state(k=45.0, d=55.0, is_bond=False)
        self.assertEqual(res_mid["label"], "【持股觀望／禁止加碼】")
        self.assertEqual(res_mid["action_type"], "中立")
        self.assertEqual(res_mid["light"], "⚪ 觀望")

        # K <= 20: 【低檔觀望／嚴禁殺低】 (中立)
        dates = pd.date_range("2026-09-01", periods=10)
        df_break = pd.DataFrame({
            "Open": [100, 99, 98, 97, 96, 95, 94, 93, 92, 91],
            "High": [101, 100, 99, 98, 97, 96, 95, 94, 93, 91.2],
            "Low": [99, 98, 97, 96, 95, 94, 93, 92, 91, 89.0],
            "Close": [99, 98, 97, 96, 95, 94, 93, 92, 91, 89.0],
            "Volume": [1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 500]
        }, index=dates)

        res_low = evaluate_deterministic_kd_state(k=15.0, d=22.0, is_bond=False, df=df_break)
        self.assertEqual(res_low["label"], "【低檔觀望／嚴禁殺低】")
        self.assertEqual(res_low["action_type"], "中立")
        self.assertEqual(res_low["light"], "🟡 觀望")
        self.assertIn("留意空方慣性破底", res_low["risk_warning"])

    def test_dual_track_system_integration(self):
        # 測試 00720B 債券低檔鎖利觀望整合輸出
        bond_data = {
            "symbol": "00720B.TWO",
            "name": "元大投資級公司債",
            "k": 30.4,
            "d": 47.5,
            "latest_close": 30.85,
            "change_pct": -0.16,
            "df": None
        }
        res_bond = evaluate_dual_track_system(bond_data)
        self.assertEqual(res_bond["strategy_state"], "【低檔鎖利／蓋牌領息觀望】")
        self.assertEqual(res_bond["action_type"], "中立")
        self.assertIn("【低檔鎖利／蓋牌領息觀望】", res_bond["integrated_reason"])

        # 測試 0056 中高檔死叉持股觀望整合輸出
        etf_0056 = {
            "symbol": "0056.TW",
            "name": "元大高股息",
            "k": 66.4,
            "d": 69.1,
            "latest_close": 38.5,
            "change_pct": -0.3,
            "df": None
        }
        res_0056 = evaluate_dual_track_system(etf_0056)
        self.assertEqual(res_0056["strategy_state"], "【持股觀望／停止加碼】")
        self.assertEqual(res_0056["action_type"], "中立")

        # 測試弱勢個股低檔死叉整合輸出
        weak_stock = {
            "symbol": "2324.TW",
            "name": "仁寶",
            "k": 15.0,
            "d": 25.0,
            "latest_close": 30.0,
            "change_pct": -1.5,
            "df": None
        }
        res_stock = evaluate_dual_track_system(weak_stock)
        self.assertEqual(res_stock["strategy_state"], "【低檔觀望／嚴禁殺低】")
        self.assertEqual(res_stock["action_type"], "中立")

if __name__ == "__main__":
    unittest.main()
