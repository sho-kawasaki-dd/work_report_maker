"""PhotoArrangePage の行移動計画を計算する純粋関数群。

QStandardItemModel の並び替え処理自体は page 側で行うが、移動元行を一度取り除いた後に
挿入位置がどうずれるかはバグを埋め込みやすい。ここでは「移動前の insert row」と
「移動後に実際に挿入すべき row」を切り分け、GUI 実装からオフセット計算を分離する。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RowMovePlan:
    """複数行移動の結果を page 側へ返す計画オブジェクト。"""

    source_rows: list[int]
    insert_row: int
    adjusted_insert_row: int
    destination_rows: list[int]
    is_noop: bool


def build_row_move_plan(rows: list[int], insert_row: int, row_count: int) -> RowMovePlan:
    """選択行ブロックを別位置へ移すための計画を返す。

    ここでの `insert_row` は「元のモデルに対してユーザーが意図した挿入位置」であり、
    `adjusted_insert_row` は移動元行を取り除いた後のモデルに対する実際の挿入位置である。

    no-op 判定は、ドロップ先が選択ブロック内部または直後にあるケースをまとめて吸収する。
    これは Qt の D&D で頻出する「見た目上は少し動かしたが、実際には同じ位置」ケースを
    安定して扱うためである。
    """

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

    # 移動元より前にある行は先にモデルから抜かれるため、その件数だけ挿入先を左へ補正する。
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
