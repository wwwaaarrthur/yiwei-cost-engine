import unittest

from sizing_engine import (
    FORMING_SINGLE_PAGE,
    FORMING_TWO_PAGE,
    LAYOUT_DOUBLE,
    LAYOUT_SINGLE,
    PAIR_SHORT,
    Size2D,
    UNKNOWN,
    calculate_sizing,
    infer_process_modes,
)


class SizingEngineTest(unittest.TestCase):
    def test_yw26_06_01_single_page_matches_employee_formula(self):
        result = calculate_sizing(
            length_mm=362,
            width_mm=288,
            height_mm=318,
            forming_mode=FORMING_SINGLE_PAGE,
            face_layout=LAYOUT_SINGLE,
            board_layout=LAYOUT_SINGLE,
        )

        self.assertEqual((result.face_piece.long_mm, result.face_piece.short_mm), (1345, 626))
        self.assertEqual((result.board_piece.long_mm, result.board_piece.short_mm), (1340, 619))
        self.assertEqual(result.face_piece_count_per_carton, 1)
        self.assertAlmostEqual(result.face_area_per_carton_m2, 1345 * 626 / 1_000_000)
        self.assertAlmostEqual(result.board_area_per_carton_m2, 1340 * 619 / 1_000_000)

    def test_yw26_06_02_two_page_uses_two_pieces_and_15mm_override(self):
        result = calculate_sizing(
            length_mm=370,
            width_mm=280,
            height_mm=232,
            forming_mode=FORMING_TWO_PAGE,
            short_allowance_mm=15,
            face_layout=LAYOUT_SINGLE,
            board_layout=LAYOUT_SINGLE,
        )

        self.assertEqual((result.face_piece.long_mm, result.face_piece.short_mm), (695, 527))
        self.assertEqual((result.board_piece.long_mm, result.board_piece.short_mm), (690, 520))
        self.assertEqual(result.face_piece_count_per_carton, 2)
        self.assertEqual(result.face_sheets_per_carton, 2)
        self.assertAlmostEqual(result.face_area_per_carton_m2, 695 * 527 * 2 / 1_000_000)
        self.assertAlmostEqual(result.board_area_per_carton_m2, 690 * 520 * 2 / 1_000_000)
        self.assertTrue(any("低于常规18mm" in warning for warning in result.warnings))

    def test_double_pairing_combines_two_pieces_and_divides_sheet_count(self):
        result = calculate_sizing(
            length_mm=460,
            width_mm=190,
            height_mm=280,
            forming_mode=FORMING_SINGLE_PAGE,
            face_layout=LAYOUT_DOUBLE,
            face_pair_direction=PAIR_SHORT,
            face_pair_reduction_mm=20,
            board_layout=LAYOUT_SINGLE,
        )

        self.assertEqual((result.face_piece.long_mm, result.face_piece.short_mm), (1345, 490))
        self.assertEqual((result.face_sheet.long_mm, result.face_sheet.short_mm), (1345, 960))
        self.assertEqual(result.face_pieces_per_sheet, 2)
        self.assertEqual(result.face_sheets_per_carton, 0.5)
        self.assertAlmostEqual(result.face_area_per_carton_m2, 1345 * 960 * 0.5 / 1_000_000)
        self.assertTrue(any("双拼" in warning for warning in result.warnings))

    def test_two_page_defaults_to_18mm_short_allowance(self):
        result = calculate_sizing(
            length_mm=370,
            width_mm=280,
            height_mm=232,
            forming_mode=FORMING_TWO_PAGE,
            face_layout=LAYOUT_SINGLE,
            board_layout=LAYOUT_SINGLE,
        )

        self.assertEqual(result.short_allowance_mm, 18)
        self.assertEqual(result.face_piece.short_mm, 530)

    def test_rejects_non_positive_box_dimensions(self):
        with self.assertRaisesRegex(ValueError, "greater than zero"):
            calculate_sizing(
                length_mm=0,
                width_mm=280,
                height_mm=232,
                forming_mode=FORMING_SINGLE_PAGE,
                face_layout=LAYOUT_SINGLE,
                board_layout=LAYOUT_SINGLE,
            )

    def test_manual_final_sheet_override_changes_cost_area_and_keeps_suggestion(self):
        result = calculate_sizing(
            length_mm=362,
            width_mm=288,
            height_mm=318,
            forming_mode=FORMING_SINGLE_PAGE,
            face_layout=LAYOUT_SINGLE,
            board_layout=LAYOUT_SINGLE,
            final_board_sheet=Size2D(1342, 621),
        )

        self.assertEqual((result.suggested_board_sheet.long_mm, result.suggested_board_sheet.short_mm), (1340, 619))
        self.assertEqual((result.board_sheet.long_mm, result.board_sheet.short_mm), (1342, 621))
        self.assertAlmostEqual(result.board_area_per_carton_m2, 1342 * 621 / 1_000_000)
        self.assertTrue(any("人工最终瓦楞" in warning for warning in result.warnings))

    def test_rejects_final_board_sheet_smaller_than_recommended_minimum(self):
        with self.assertRaisesRegex(ValueError, "must not be smaller"):
            calculate_sizing(
                length_mm=362,
                width_mm=288,
                height_mm=318,
                forming_mode=FORMING_SINGLE_PAGE,
                final_board_sheet=Size2D(1339, 619),
            )

    def test_infers_single_page_and_double_pairing_as_separate_modes(self):
        modes = infer_process_modes("单页成型，双拼")

        self.assertEqual(modes.forming_mode, FORMING_SINGLE_PAGE)
        self.assertEqual(modes.face_layout, LAYOUT_DOUBLE)
        self.assertEqual(modes.board_layout, LAYOUT_DOUBLE)

    def test_infers_two_page_without_double_pairing(self):
        modes = infer_process_modes("两页成型，印刷出血宽度要求小于10 mm")

        self.assertEqual(modes.forming_mode, FORMING_TWO_PAGE)
        self.assertEqual(modes.face_layout, LAYOUT_SINGLE)
        self.assertEqual(modes.board_layout, LAYOUT_SINGLE)

    def test_does_not_guess_forming_mode_when_only_face_paper_is_double_paired(self):
        modes = infer_process_modes("面纸双拼，瓦楞纸板不双拼，面纸彩印后需裁切")

        self.assertEqual(modes.forming_mode, UNKNOWN)
        self.assertEqual(modes.face_layout, LAYOUT_DOUBLE)
        self.assertEqual(modes.board_layout, LAYOUT_SINGLE)

    def test_empty_legacy_note_values_do_not_break_mode_inference(self):
        for note in (None, float("nan"), 0):
            with self.subTest(note=note):
                modes = infer_process_modes(note)
                self.assertEqual(modes.forming_mode, UNKNOWN)
                self.assertEqual(modes.face_layout, UNKNOWN)
                self.assertEqual(modes.board_layout, UNKNOWN)

    def test_unrelated_legacy_note_does_not_guess_layout(self):
        modes = infer_process_modes("印刷出血宽度要求小于10mm")

        self.assertEqual(modes.forming_mode, UNKNOWN)
        self.assertEqual(modes.face_layout, UNKNOWN)
        self.assertEqual(modes.board_layout, UNKNOWN)

    def test_board_not_double_paired_does_not_imply_face_is_double_paired(self):
        modes = infer_process_modes("瓦楞纸板不双拼")

        self.assertEqual(modes.forming_mode, UNKNOWN)
        self.assertEqual(modes.face_layout, UNKNOWN)
        self.assertEqual(modes.board_layout, LAYOUT_SINGLE)


if __name__ == "__main__":
    unittest.main()
