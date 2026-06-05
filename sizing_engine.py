"""Employee-confirmed carton sizing rules.

This module keeps process sizing separate from price estimation so every
material-area assumption can be tested and audited.
"""

from dataclasses import dataclass


FORMING_SINGLE_PAGE = "single_page"
FORMING_TWO_PAGE = "two_page"

LAYOUT_SINGLE = "single"
LAYOUT_DOUBLE = "double"

PAIR_LONG = "long"
PAIR_SHORT = "short"

UNKNOWN = "unknown"

FORMULA_VERSION = "employee-confirmed-2026-06-04"


@dataclass(frozen=True)
class Size2D:
    long_mm: int
    short_mm: int

    @property
    def area_m2(self) -> float:
        return self.long_mm * self.short_mm / 1_000_000


@dataclass(frozen=True)
class SizingResult:
    face_piece: Size2D
    board_piece: Size2D
    suggested_face_sheet: Size2D
    suggested_board_sheet: Size2D
    face_sheet: Size2D
    board_sheet: Size2D
    face_piece_count_per_carton: int
    face_pieces_per_sheet: int
    board_pieces_per_sheet: int
    face_sheets_per_carton: float
    board_sheets_per_carton: float
    face_area_per_carton_m2: float
    board_area_per_carton_m2: float
    long_allowance_mm: int
    short_allowance_mm: int
    board_delta_long_mm: int
    board_delta_short_mm: int
    formula_version: str
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class ProcessModes:
    forming_mode: str
    face_layout: str
    board_layout: str


def infer_process_modes(notes: object) -> ProcessModes:
    """Split legacy note text into forming and material-layout dimensions."""
    text = notes.strip() if isinstance(notes, str) else ""

    if "两页" in text or "双页" in text or "两面成型" in text:
        forming_mode = FORMING_TWO_PAGE
    elif "单页" in text or "单面成型" in text:
        forming_mode = FORMING_SINGLE_PAGE
    else:
        forming_mode = UNKNOWN

    board_single_explicit = "瓦楞纸板不双拼" in text or "瓦楞不双拼" in text
    face_single_explicit = "面纸不双拼" in text
    positive_pairing_text = (
        text.replace("瓦楞纸板不双拼", "")
        .replace("瓦楞不双拼", "")
        .replace("面纸不双拼", "")
    )
    has_positive_double_pairing = "双拼" in positive_pairing_text
    has_single_layout_evidence = "单拼" in text or forming_mode != UNKNOWN

    if face_single_explicit:
        face_layout = LAYOUT_SINGLE
    elif has_positive_double_pairing:
        face_layout = LAYOUT_DOUBLE
    elif has_single_layout_evidence:
        face_layout = LAYOUT_SINGLE
    else:
        face_layout = UNKNOWN

    if board_single_explicit:
        board_layout = LAYOUT_SINGLE
    elif has_positive_double_pairing:
        board_layout = LAYOUT_DOUBLE
    elif has_single_layout_evidence:
        board_layout = LAYOUT_SINGLE
    else:
        board_layout = UNKNOWN

    return ProcessModes(
        forming_mode=forming_mode,
        face_layout=face_layout,
        board_layout=board_layout,
    )


def _validate_positive(name: str, value: int) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")


def _layout_piece(
    piece: Size2D,
    layout: str,
    pair_direction: str,
    pair_reduction_mm: int,
) -> tuple[Size2D, int]:
    if layout == LAYOUT_SINGLE:
        return piece, 1
    if layout != LAYOUT_DOUBLE:
        raise ValueError(f"Unsupported layout: {layout}")
    if pair_direction not in {PAIR_LONG, PAIR_SHORT}:
        raise ValueError(f"Unsupported pair direction: {pair_direction}")
    if pair_reduction_mm < 0:
        raise ValueError("Pair reduction must not be negative")

    if pair_direction == PAIR_LONG:
        combined = 2 * piece.long_mm - pair_reduction_mm
        if combined <= 0:
            raise ValueError("Pair reduction is too large for the long direction")
        return Size2D(combined, piece.short_mm), 2

    combined = 2 * piece.short_mm - pair_reduction_mm
    if combined <= 0:
        raise ValueError("Pair reduction is too large for the short direction")
    return Size2D(piece.long_mm, combined), 2


def calculate_sizing(
    *,
    length_mm: int,
    width_mm: int,
    height_mm: int,
    forming_mode: str,
    face_layout: str = LAYOUT_SINGLE,
    board_layout: str = LAYOUT_SINGLE,
    long_allowance_mm: int = 45,
    short_allowance_mm: int | None = None,
    face_adjust_long_mm: int = 0,
    face_adjust_short_mm: int = 0,
    face_pair_direction: str = PAIR_SHORT,
    face_pair_reduction_mm: int = 20,
    board_pair_direction: str = PAIR_SHORT,
    board_pair_reduction_mm: int = 20,
    board_delta_long_mm: int = 5,
    board_delta_short_mm: int = 7,
    final_face_sheet: Size2D | None = None,
    final_board_sheet: Size2D | None = None,
) -> SizingResult:
    for name, value in (
        ("length_mm", length_mm),
        ("width_mm", width_mm),
        ("height_mm", height_mm),
    ):
        _validate_positive(name, value)

    if forming_mode not in {FORMING_SINGLE_PAGE, FORMING_TWO_PAGE}:
        raise ValueError(f"Unsupported forming mode: {forming_mode}")
    if long_allowance_mm < 0:
        raise ValueError("Long allowance must not be negative")
    if board_delta_long_mm < 0 or board_delta_short_mm < 0:
        raise ValueError("Board deltas must not be negative")

    default_short_allowance = 20 if forming_mode == FORMING_SINGLE_PAGE else 18
    effective_short_allowance = (
        default_short_allowance if short_allowance_mm is None else short_allowance_mm
    )
    if effective_short_allowance < 0:
        raise ValueError("Short allowance must not be negative")

    if forming_mode == FORMING_SINGLE_PAGE:
        face_long = 2 * (length_mm + width_mm) + long_allowance_mm
        piece_count = 1
    else:
        face_long = length_mm + width_mm + long_allowance_mm
        piece_count = 2

    face_piece = Size2D(
        long_mm=face_long + face_adjust_long_mm,
        short_mm=width_mm + height_mm + effective_short_allowance + face_adjust_short_mm,
    )
    board_piece = Size2D(
        long_mm=face_piece.long_mm - board_delta_long_mm,
        short_mm=face_piece.short_mm - board_delta_short_mm,
    )
    _validate_positive("board_piece.long_mm", board_piece.long_mm)
    _validate_positive("board_piece.short_mm", board_piece.short_mm)

    suggested_face_sheet, face_pieces_per_sheet = _layout_piece(
        face_piece, face_layout, face_pair_direction, face_pair_reduction_mm
    )
    suggested_board_sheet, board_pieces_per_sheet = _layout_piece(
        board_piece, board_layout, board_pair_direction, board_pair_reduction_mm
    )
    face_sheet = final_face_sheet or suggested_face_sheet
    board_sheet = final_board_sheet or suggested_board_sheet
    _validate_positive("face_sheet.long_mm", face_sheet.long_mm)
    _validate_positive("face_sheet.short_mm", face_sheet.short_mm)
    _validate_positive("board_sheet.long_mm", board_sheet.long_mm)
    _validate_positive("board_sheet.short_mm", board_sheet.short_mm)
    if final_board_sheet and (
        final_board_sheet.long_mm < suggested_board_sheet.long_mm
        or final_board_sheet.short_mm < suggested_board_sheet.short_mm
    ):
        raise ValueError("Final board sheet must not be smaller than the recommended minimum")
    face_sheets_per_carton = piece_count / face_pieces_per_sheet
    board_sheets_per_carton = piece_count / board_pieces_per_sheet

    warnings: list[str] = []
    if effective_short_allowance < default_short_allowance:
        warnings.append(
            f"{'单页' if forming_mode == FORMING_SINGLE_PAGE else '双页'}短边余量"
            f"低于常规{default_short_allowance}mm，需确认设备和版面"
        )
    if face_layout == LAYOUT_DOUBLE:
        warnings.append("面纸双拼方向和减量需按实际版面复核")
    if board_layout == LAYOUT_DOUBLE:
        warnings.append("瓦楞双拼尚缺员工实际案例，必须人工复核")
    if final_face_sheet:
        warnings.append("已使用人工最终面纸拼版尺寸，成本按人工尺寸计算")
    if final_board_sheet:
        warnings.append("已使用人工最终瓦楞下料尺寸，成本按人工尺寸计算")

    return SizingResult(
        face_piece=face_piece,
        board_piece=board_piece,
        suggested_face_sheet=suggested_face_sheet,
        suggested_board_sheet=suggested_board_sheet,
        face_sheet=face_sheet,
        board_sheet=board_sheet,
        face_piece_count_per_carton=piece_count,
        face_pieces_per_sheet=face_pieces_per_sheet,
        board_pieces_per_sheet=board_pieces_per_sheet,
        face_sheets_per_carton=face_sheets_per_carton,
        board_sheets_per_carton=board_sheets_per_carton,
        face_area_per_carton_m2=face_sheet.area_m2 * face_sheets_per_carton,
        board_area_per_carton_m2=board_sheet.area_m2 * board_sheets_per_carton,
        long_allowance_mm=long_allowance_mm,
        short_allowance_mm=effective_short_allowance,
        board_delta_long_mm=board_delta_long_mm,
        board_delta_short_mm=board_delta_short_mm,
        formula_version=FORMULA_VERSION,
        warnings=tuple(warnings),
    )
