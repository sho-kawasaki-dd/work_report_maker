from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGroupBox, QHBoxLayout, QLabel, QSlider, QSpinBox, QVBoxLayout


class PhotoImportCompressionControls:
    """圧縮設定 UI の生成と値参照をまとめる。"""

    def __init__(self, *, pngquant_available: bool) -> None:
        self.dpi_slider, self.dpi_spin = self._build_slider_spin_pair(72, 300, 150)
        self.jpeg_slider, self.jpeg_spin = self._build_slider_spin_pair(10, 100, 75)
        self.png_slider, self.png_spin = self._build_slider_spin_pair(10, 100, 75)
        self.png_label = QLabel("PNG品質:")

        if not pngquant_available:
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
        return self.dpi_spin.value()

    def jpeg_quality(self) -> int:
        return self.jpeg_spin.value()

    def png_quality_max(self) -> int:
        return self.png_spin.value()

    def _build_slider_spin_pair(
        self,
        minimum: int,
        maximum: int,
        initial: int,
    ) -> tuple[QSlider, QSpinBox]:
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setValue(initial)

        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setValue(initial)

        slider.valueChanged.connect(spin.setValue)
        spin.valueChanged.connect(slider.setValue)
        return slider, spin

    def _build_row(
        self,
        label: str | QLabel,
        slider: QSlider,
        spin: QSpinBox,
    ) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(QLabel(label) if isinstance(label, str) else label)
        row.addWidget(slider, 1)
        row.addWidget(spin)
        return row