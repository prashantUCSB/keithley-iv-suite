"""Background export worker — writes CSV, PNG, and Excel without blocking the UI."""
from __future__ import annotations

import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal

from ...measurements.sweep_config import SweepConfig
from ...data.exporter import export_csv, append_excel_sheet

log = logging.getLogger(__name__)


class ExportWorker(QThread):
    """Runs file I/O (CSV, PNG, Excel) in a background thread.

    PNG bytes must be captured in the UI thread *before* creating this worker
    (QPixmap.grab() is not thread-safe).  Pass the raw bytes here; the worker
    writes them to disk.

    Signals
    -------
    export_done(folder)   — primary output folder path (CSV/PNG subfolder)
    export_error(message) — human-readable error description
    """

    export_done  = pyqtSignal(str)
    export_error = pyqtSignal(str)

    def __init__(
        self,
        result: dict,
        config: SweepConfig,
        output_dir: str,
        export_format: str,           # "csv", "excel", "both"
        png_bytes: Optional[bytes],
        excel_path: Optional[str],    # shared workbook path for this queue run
        excel_lock: threading.Lock,   # lock shared by all workers for this workbook
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._result       = result
        self._config       = config
        self._output_dir   = output_dir
        self._format       = export_format
        self._png_bytes    = png_bytes
        self._excel_path   = excel_path
        self._excel_lock   = excel_lock

    # ------------------------------------------------------------------

    def run(self) -> None:
        try:
            self._export()
        except Exception as exc:
            log.exception("ExportWorker: unhandled error")
            self.export_error.emit(str(exc))

    def _export(self) -> None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Sanitise label for use in filenames
        raw_label = self._config.label or self._config.measurement_type.name
        safe_label = "".join(
            c if c.isalnum() or c in ("-", "_") else "_" for c in raw_label
        ).strip("_") or "measurement"

        # ── CSV + PNG ─────────────────────────────────────────────────────
        if self._format in ("csv", "both"):
            subfolder = Path(self._output_dir) / ts
            subfolder.mkdir(parents=True, exist_ok=True)

            csv_path = subfolder / f"{safe_label}.csv"
            export_csv(self._result, csv_path, self._config)
            log.info("ExportWorker: CSV saved → %s", csv_path)

            if self._png_bytes:
                png_path = subfolder / f"{safe_label}.png"
                png_path.write_bytes(self._png_bytes)
                log.info("ExportWorker: PNG saved → %s", png_path)

            self.export_done.emit(str(subfolder))

        # ── Excel ─────────────────────────────────────────────────────────
        if self._format in ("excel", "both") and self._excel_path:
            append_excel_sheet(
                self._result,
                self._config,
                self._excel_path,
                self._excel_lock,
            )
            log.info("ExportWorker: Excel sheet appended → %s", self._excel_path)

            if self._format == "excel":
                # emit the workbook path when CSV wasn't written
                self.export_done.emit(str(Path(self._excel_path).parent))
