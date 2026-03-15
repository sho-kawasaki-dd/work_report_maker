"""建物プリセット管理ダイアログ。

保存済みの建物プリセット一覧を QListWidget で表示し、
ユーザーが「選択」「削除」「キャンセル」を操作できるダイアログ。

使い方:
    dlg = BuildingPresetDialog(parent)
    if dlg.exec() == QDialog.Accepted:
        building_name, recipient, address = dlg.selected_data()
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from work_report_maker.gui.preset_manager import (
    delete_building_preset,
    load_building_presets,
)


class BuildingPresetDialog(QDialog):
    """建物プリセット一覧から選択 or 削除するダイアログ。

    一覧には「建物名 (提出先名)」形式で表示される。
    ダブルクリックまたは「選択」ボタンで選択確定、「削除」ボタンで該当プリセットを削除する。

    この dialog 自体は JSON schema を知らず、preset_manager が返す辞書を「一覧表示」と
    「選択結果の返却」に変換することだけに責務を限定する。
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("建物プリセット読込")
        self.setMinimumWidth(420)

        # ダイアログ確定時に返すデータ (未選択なら None のまま)
        self._selected: dict[str, str] | None = None
        self._selected_building_name: str = ""

        # プリセット一覧リスト（ダブルクリックでも選択可能）
        self._list = QListWidget()
        self._list.itemDoubleClicked.connect(self._on_select)

        # 操作ボタン
        btn_select = QPushButton("選択")
        btn_select.clicked.connect(self._on_select)
        btn_delete = QPushButton("削除")
        btn_delete.clicked.connect(self._on_delete)
        btn_cancel = QPushButton("キャンセル")
        btn_cancel.clicked.connect(self.reject)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(btn_select)
        btn_layout.addWidget(btn_delete)
        btn_layout.addWidget(btn_cancel)

        layout = QVBoxLayout()
        layout.addWidget(self._list)
        layout.addLayout(btn_layout)
        self.setLayout(layout)

        # 初期表示時にプリセット一覧を読み込む
        self._refresh_list()

    def _refresh_list(self) -> None:
        """プリセット JSON を再読込して一覧を更新する。"""
        self._list.clear()
        presets = load_building_presets()
        for building_name, info in presets.items():
            # 表示テキスト: "建物名  (提出先名)" の形式
            label = f"{building_name}  ({info.get('recipient', '')})"
            item = QListWidgetItem(label)
            # Qt.UserRole (int=256) に建物名を格納し、選択時に取り出す
            item.setData(256, building_name)
            self._list.addItem(item)

    def _current_building_name(self) -> str | None:
        """現在選択中のリストアイテムから建物名を取得する。未選択なら None。"""
        item = self._list.currentItem()
        if item is None:
            return None
        return item.data(256)

    def _on_select(self) -> None:
        """「選択」ボタン押下 or ダブルクリック時の処理。

        選択中のプリセットデータを保持してダイアログを Accepted で閉じる。
        """
        name = self._current_building_name()
        if name is None:
            return
        presets = load_building_presets()
        info = presets.get(name)
        if info is None:
            return
        self._selected_building_name = name
        self._selected = info
        self.accept()

    def _on_delete(self) -> None:
        """「削除」ボタン押下時の処理。選択中のプリセットを JSON から削除し、一覧を更新する。"""
        name = self._current_building_name()
        if name is None:
            return
        # delete 後に再読込することで、永続化結果を source of truth とした一覧へ戻す。
        delete_building_preset(name)
        self._refresh_list()

    def selected_data(self) -> tuple[str, str, str] | None:
        """選択された (building_name, recipient, address) を返す。

        ダイアログが Accepted で閉じられた後に呼び出すこと。
        未選択（キャンセル）の場合は None を返す。
        """
        if self._selected is None:
            return None
        return (
            self._selected_building_name,
            self._selected.get("recipient", ""),
            self._selected.get("address", ""),
        )
