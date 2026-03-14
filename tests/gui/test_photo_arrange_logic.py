from work_report_maker.gui.pages.photo_arrange_logic import build_row_move_plan


def test_build_row_move_plan_moves_non_contiguous_rows_as_block() -> None:
    plan = build_row_move_plan([3, 1], 5, 5)

    assert plan.source_rows == [1, 3]
    assert plan.adjusted_insert_row == 3
    assert plan.destination_rows == [3, 4]
    assert plan.is_noop is False


def test_build_row_move_plan_is_noop_when_inserting_inside_selection_block() -> None:
    plan = build_row_move_plan([1, 2], 2, 5)

    assert plan.destination_rows == [1, 2]
    assert plan.is_noop is True


def test_build_row_move_plan_filters_invalid_rows_and_bounds_insert() -> None:
    plan = build_row_move_plan([-1, 1, 99], 99, 3)

    assert plan.source_rows == [1]
    assert plan.adjusted_insert_row == 2
    assert plan.destination_rows == [2]
    assert plan.is_noop is False