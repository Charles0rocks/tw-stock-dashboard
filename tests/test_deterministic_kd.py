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
from src.stock_data import evaluate_kd_strategy_rule, get_kd_signal

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

    def test_priority1_bond_low_zone(self):
        # 債券低檔金叉 (is_bond=True, K <= 30, K > D)
        res_gold = evaluate_deterministic_kd_state(k=15.0, d=10.0, is_bond=True)
        self.assertEqual(res_gold["label"], "【低檔轉強／鎖利加碼】")
        self.assertEqual(res_gold["light"], "🟢 加碼")
        self.assertIn("鎖利", res_gold["strategy_desc"])
        self.assertIn("加碼", res_gold["strategy_desc"])

        # 債券低檔死叉 (is_bond=True, K <= 30, K < D)
        res_dead = evaluate_deterministic_kd_state(k=8.0, d=16.0, is_bond=True)
        self.assertEqual(res_dead["label"], "【低檔鎖利／領息觀望】")
        self.assertEqual(res_dead["light"], "🟡 觀望")
        self.assertIn("安心領息", res_dead["strategy_desc"])

    def test_priority2_high_overbought(self):
        # 高檔超買鈍化/金叉 (K >= 80, K > D)
        res_high_gold = evaluate_deterministic_kd_state(k=85.0, d=80.0, is_bond=False)
        self.assertEqual(res_high_gold["label"], "【續抱不追高】")
        self.assertEqual(res_high_gold["light"], "🟢 續抱")

        # 高檔超買死叉 (K >= 80, K < D)
        res_high_dead = evaluate_deterministic_kd_state(k=82.0, d=86.0, is_bond=False)
        self.assertEqual(res_high_dead["label"], "【高檔減碼／獲利了結】")
        self.assertEqual(res_high_dead["light"], "🔴 減碼")

    def test_priority3_stock_low_zone(self):
        # 股票低檔超賣金叉 (is_bond=False, K <= 30, K > D)
        res_stock_gold = evaluate_deterministic_kd_state(k=18.0, d=12.0, is_bond=False)
        self.assertEqual(res_stock_gold["label"], "【低檔轉強／分批加碼】")
        self.assertEqual(res_stock_gold["light"], "🟢 加碼")

        # 股票低檔超賣死叉 (is_bond=False, K <= 30, K < D)
        # 建立破底測試資料
        dates = pd.date_range("2026-09-01", periods=10)
        df_break = pd.DataFrame({
            "Open": [100, 99, 98, 97, 96, 95, 94, 93, 92, 91],
            "High": [101, 100, 99, 98, 97, 96, 95, 94, 93, 91.2],
            "Low": [99, 98, 97, 96, 95, 94, 93, 92, 91, 89.0],
            "Close": [99, 98, 97, 96, 95, 94, 93, 92, 91, 89.0],
            "Volume": [1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 500]
        }, index=dates)

        res_stock_dead = evaluate_deterministic_kd_state(k=15.0, d=22.0, is_bond=False, df=df_break)
        self.assertEqual(res_stock_dead["label"], "【空方鈍化／禁止接刀】")
        self.assertEqual(res_stock_dead["light"], "🔴 警戒")
        self.assertIn("留意空方慣性破底", res_stock_dead["risk_warning"])

    def test_priority4_mid_oscillation(self):
        # 中軸偏多 (30 < K < 80, K > D)
        res_mid_bull = evaluate_deterministic_kd_state(k=55.0, d=45.0, is_bond=False)
        self.assertEqual(res_mid_bull["label"], "【偏多持股】")
        self.assertEqual(res_mid_bull["light"], "🟢 偏多")

        # 中軸偏空 (30 < K < 80, K < D)
        res_mid_bear = evaluate_deterministic_kd_state(k=45.0, d=55.0, is_bond=False)
        self.assertEqual(res_mid_bear["label"], "【持股觀望】")
        self.assertEqual(res_mid_bear["light"], "⚪ 中立")

    def test_dual_track_system_integration(self):
        # 測試 00720B 債券低檔金叉整合輸出
        bond_data = {
            "symbol": "00720B.TWO",
            "name": "元大投資級公司債",
            "k": 18.5,
            "d": 12.0,
            "latest_close": 32.5,
            "change_pct": 0.5,
            "df": None
        }
        res_bond = evaluate_dual_track_system(bond_data)
        self.assertEqual(res_bond["strategy_state"], "【低檔轉強／鎖利加碼】")
        self.assertIn("【低檔轉強／鎖利加碼】", res_bond["integrated_reason"])

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
        self.assertEqual(res_stock["strategy_state"], "【空方鈍化／禁止接刀】")

if __name__ == "__main__":
    unittest.main()
