"""PhotoImportPage 用の圧縮設定 UI ビルダー。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGroupBox, QHBoxLayout, QLabel, QSlider, QSpinBox, QVBoxLayout


class PhotoImportCompressionControls:
    """圧縮設定 UI の生成と値参照をまとめる。

    このクラスは UI widget の組み立てに責務を限定し、画像変換アルゴリズム自体は
    `services.image_processor` 側へ委譲する。ここで重要なのは、ユーザーが見ている slider/spin の値と
    実際に import worker へ渡すパラメータを 1 箇所で対応づけることである。
    """

    def __init__(self, *, pngquant_available: bool) -> None:
        self.dpi_slider, self.dpi_spin = self._build_slider_spin_pair(72, 300, 150)
        self.jpeg_slider, self.jpeg_spin = self._build_slider_spin_pair(10, 100, 75)
        self.png_slider, self.png_spin = self._build_slider_spin_pair(10, 100, 75)
        self.png_label = QLabel("PNG品質:")

        if not pngquant_available:
            # pngquant が無い環境では品質帯指定がそのまま効かないため、UI からも明示的に見せ方を変える。
            self.png_slider.setEnabled(False)
            self.png_spin.setEnabled(False)
            self.png_label.setText("PNG品質 (Pillow減色):")

        layout = QVBoxLayout()
        layout.addLayout(self._build_row("DPI:", self.dpi_slider, self.dpi_spin))
        layout.addLayout(self._build_row("JPEG品質:", self.jpeg_slider, self.jpeg_spin))
        layout.addLayout(self._build_row(self.png_label, self.png_slider, self.png_spin))

        self.group_box = QGroupBox("圧縮設定")
        self.group_box.setLayout(layout)

    def dpi(self) -> int:
        """現在の DPI 設定を返す。"""
        return self.dpi_spin.value()

    def jpeg_quality(self) -> int:
        """現在の JPEG 品質設定を返す。"""
        return self.jpeg_spin.value()

    def png_quality_max(self) -> int:
        """現在の PNG 品質上限設定を返す。"""
        return self.png_spin.value()

    def _build_slider_spin_pair(
        self,
        minimum: int,
        maximum: int,
        initial: int,
    ) -> tuple[QSlider, QSpinBox]:
        """双方向同期された slider/spin の組を生成する。"""

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setValue(initial)

        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setValue(initial)

        # どちらを操作しても同じ値源を見ている感覚になるよう、相互接続で同期する。
        slider.valueChanged.connect(spin.setValue)
        spin.valueChanged.connect(slider.setValue)
        return slider, spin

    def _build_row(
        self,
        label: str | QLabel,
        slider: QSlider,
        spin: QSpinBox,
    ) -> QHBoxLayout:
        """ラベル + slider + spin の 1 行レイアウトを生成する。"""

        row = QHBoxLayout()
        row.addWidget(QLabel(label) if isinstance(label, str) else label)
        row.addWidget(slider, 1)
        row.addWidget(spin)
        return row