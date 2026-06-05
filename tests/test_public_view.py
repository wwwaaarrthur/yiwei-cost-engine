import unittest

import pandas as pd

from public_view import sanitize_precheck_costs_for_public, sanitize_process_sheets_for_public


class PublicViewSanitizationTest(unittest.TestCase):
    def test_process_sheet_public_view_generalizes_identity_fields(self):
        df = pd.DataFrame(
            [
                {
                    "client": "大型农化客户B",
                    "product": "真实品牌Alpha 1L*12瓶水剂纸箱P-365",
                    "batch_no": "YW-2026-02-02",
                    "box_l": 370,
                    "box_w": 280,
                    "box_h": 255,
                    "flute_normalized": "EB",
                    "board_material": "150gB瓦+115g皮芯纸+170gE瓦+230g牛卡里纸",
                    "paper_spec": "230g牛卡",
                    "padding_material": "真实垫片",
                    "padding_size": "100x200",
                    "grid_material": "真实格挡",
                    "print_qty_str": "客户原始印量",
                    "notes": "真实备注",
                    "file": "YW-2026-02-02剂预核单.xls",
                    "dirname": "真实目录",
                    "filepath": "/sensitive/source/YW-2026-02-02剂预核单.xls",
                }
            ]
        )

        safe = sanitize_process_sheets_for_public(df)

        self.assertNotIn("真实品牌Alpha", safe.loc[0, "product"])
        self.assertEqual(safe.loc[0, "file"], "PUBLIC_DEMO_ONLY")
        self.assertEqual(safe.loc[0, "dirname"], "PUBLIC_DEMO_ONLY")
        self.assertEqual(safe.loc[0, "filepath"], "PUBLIC_DEMO_ONLY")
        self.assertIn("脱敏纸板配置", safe.loc[0, "board_material"])
        self.assertEqual(safe.loc[0, "notes"], "PUBLIC_DEMO_REDACTED")

    def test_precheck_public_view_generalizes_row_level_cost_identity(self):
        cost_df = pd.DataFrame(
            [
                {
                    "product": "真实品牌Beta150",
                    "material": "130gE瓦+70g芯纸+150gB瓦+170g里纸",
                    "flute_type": "EB",
                    "file": "预核单工业品YW-2026-03-02.xls",
                    "qty": 2000,
                    "unit_cost": 1.33,
                    "contract_price": 4.3,
                }
            ]
        )

        safe = sanitize_precheck_costs_for_public(cost_df)

        self.assertNotIn("真实品牌Beta", safe.loc[0, "product"])
        self.assertNotIn("130gE瓦", safe.loc[0, "material"])
        self.assertTrue(safe.loc[0, "file"].startswith("PUBLIC_PRECHECK_"))
        self.assertEqual(safe.loc[0, "unit_cost"], 1.33)
        self.assertEqual(safe.loc[0, "contract_price"], 4.3)


if __name__ == "__main__":
    unittest.main()
