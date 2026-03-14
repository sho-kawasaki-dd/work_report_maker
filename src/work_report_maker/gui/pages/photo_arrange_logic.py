from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RowMovePlan:
    source_rows: list[int]
    insert_row: int
    adjusted_insert_row: int
    destination_rows: list[int]
    is_noop: bool


def build_row_move_plan(rows: list[int], insert_row: int, row_count: int) -> RowMovePlan:
    if row_count <= 0 or not rows:
        return RowMovePlan([], 0, 0, [], True)

    source_rows = sorted({row for row in rows if 0 <= row < row_count})
    if not source_rows:
        return RowMovePlan([], 0, 0, [], True)

    bounded_insert_row = max(0, min(insert_row, row_count))
    if source_rows[0] <= bounded_insert_row <= source_rows[-1] + 1:
        return RowMovePlan(
            source_rows=source_rows,
            insert_row=bounded_insert_row,
            adjusted_insert_row=bounded_insert_row,
            destination_rows=list(source_rows),
            is_noop=True,
        )

    adjusted_insert_row = bounded_insert_row - sum(1 for row in source_rows if row < bounded_insert_row)
    adjusted_insert_row = max(0, min(adjusted_insert_row, row_count - len(source_rows)))
    destination_rows = [adjusted_insert_row + index for index in range(len(source_rows))]
    return RowMovePlan(
        source_rows=source_rows,
        insert_row=bounded_insert_row,
        adjusted_insert_row=adjusted_insert_row,
        destination_rows=destination_rows,
        is_noop=False,
    )
