"""Application entry point."""
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from keithley_iv_suite.ui.main_window import MainWindow


def _apply_dpi_font_scale(app: QApplication) -> None:
    """Scale theme font sizes to match the primary screen DPI.

    Qt pt sizes are physical units (1/72 in) so they already map correctly to
    pixels.  However the constants in theme.py are tuned for 96 DPI.  On
    higher-DPI displays where the OS applies logical scaling, logical DPI can
    exceed 96, and bumping the base point size keeps UI text comfortably
    readable without requiring the OS high-DPI override.
    """
    from keithley_iv_suite.ui import theme
    screen = app.primaryScreen()
    if screen is None:
        return
    dpi = screen.logicalDotsPerInch()
    if dpi <= 120:
        return  # standard density — no adjustment needed
    scale = dpi / 96.0
    theme.FONT_SIZE_BASE  = round(theme.FONT_SIZE_BASE  * scale)
    theme.FONT_SIZE_SMALL = round(theme.FONT_SIZE_SMALL * scale)
    theme.FONT_SIZE_LARGE = round(theme.FONT_SIZE_LARGE * scale)
    theme.FONT_SIZE_TITLE = round(theme.FONT_SIZE_TITLE * scale)


def main() -> int:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("Keithley IV Suite")
    app.setApplicationVersion("1.1.0")
    app.setOrganizationName("prashantUCSB")

    _apply_dpi_font_scale(app)

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
