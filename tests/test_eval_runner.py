import unittest

from eval_runner import predict_cost_full


class FullPriceModelTest(unittest.TestCase):
    def test_uses_independent_face_and_board_areas_when_provided(self):
        _, _, breakdown = predict_cost_full(
            {
                "board_area_m2": 1.0,
                "face_area_m2": 0.5,
                "qty": 10_000,
                "flute": "EB",
                "order_type": "内销",
                "print_colors": 2,
                "has_lam": False,
                "has_pad": False,
            },
            {"tier": "vip", "paper_gsm": 250, "paper_per_tonne": 3410},
        )

        self.assertEqual(breakdown["area_source"], "independent_sizing_engine_areas")
        self.assertAlmostEqual(breakdown["bc"], 1.5)
        self.assertAlmostEqual(breakdown["pc"], 0.426, places=3)


if __name__ == "__main__":
    unittest.main()
