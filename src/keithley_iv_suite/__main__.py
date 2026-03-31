"""Application entry point."""
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from keithley_iv_suite.ui.main_window import MainWindow


def main() -> int:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("Keithley IV Suite")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("prashantUCSB")

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
