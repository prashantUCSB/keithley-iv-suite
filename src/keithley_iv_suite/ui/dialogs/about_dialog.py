"""About dialog."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout

from .. import theme


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About Keithley IV Suite")
        self.setFixedSize(380, 220)
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 20, 24, 20)

        title = QLabel("Keithley IV Suite")
        title.setStyleSheet(
            f"font-size: 18pt; font-weight: 700; color: {theme.AMBER};"
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        sub = QLabel("Multi-SMU IV Characterization Platform")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet(f"color: {theme.TEXT_SECONDARY};")
        layout.addWidget(sub)

        info = QLabel(
            "Supports: Keithley 2400, 2401, 2602, 2614B\n"
            "VISA backends: NI-VISA, Keysight IO, pyvisa-py\n\n"
            "github.com/prashantUCSB/keithley-iv-suite"
        )
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 9pt;")
        layout.addWidget(info)

        ok_btn = QPushButton("OK")
        ok_btn.setProperty("role", "primary")
        ok_btn.clicked.connect(self.accept)
        layout.addWidget(ok_btn, alignment=Qt.AlignmentFlag.AlignCenter)
