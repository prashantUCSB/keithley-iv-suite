"""VISA resource manager — auto-detects NI-VISA, Keysight IO, or pyvisa-py."""
from __future__ import annotations

import logging
from typing import Optional

import pyvisa
import pyvisa.errors

log = logging.getLogger(__name__)

# Known Keithley USB vendor/product IDs for friendly naming
_KEITHLEY_USB_IDS: dict[str, str] = {
    "05E6::2400": "Keithley 2400",
    "05E6::2401": "Keithley 2401",
    "05E6::2602": "Keithley 2602",
    "05E6::2602A": "Keithley 2602A",
    "05E6::2614": "Keithley 2614B",
    "05E6::2614B": "Keithley 2614B",
}

_BACKEND_CANDIDATES = [
    "",          # default (NI-VISA or Keysight, whichever is installed)
    "@py",       # pyvisa-py — pure Python fallback
]


class VISAManager:
    """Singleton-like VISA resource manager with auto-backend detection."""

    def __init__(self, backend: str = "") -> None:
        self._rm: Optional[pyvisa.ResourceManager] = None
        self._backend = backend
        self._connect()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _connect(self) -> None:
        candidates = [self._backend] if self._backend else _BACKEND_CANDIDATES
        for backend in candidates:
            try:
                self._rm = pyvisa.ResourceManager(backend) if backend else pyvisa.ResourceManager()
                log.info("VISA backend opened: %s", self._rm.visalib)
                return
            except Exception as exc:
                log.debug("Backend '%s' failed: %s", backend, exc)
        raise RuntimeError(
            "No VISA backend found. Install NI-VISA, Keysight IO Libraries, "
            "or run: pip install pyvisa-py"
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def resource_manager(self) -> pyvisa.ResourceManager:
        if self._rm is None:
            self._connect()
        return self._rm  # type: ignore[return-value]

    def list_resources(self) -> list[str]:
        """Return all VISA resource strings visible on this system."""
        try:
            return list(self._rm.list_resources())  # type: ignore[union-attr]
        except Exception as exc:
            log.error("list_resources failed: %s", exc)
            return []

    def list_resources_with_info(self) -> list[dict]:
        """Return resources with parsed metadata (type, address, friendly name)."""
        results: list[dict] = []
        for rstr in self.list_resources():
            info = self._parse_resource_string(rstr)
            try:
                res = self._rm.open_resource(rstr, open_timeout=500)  # type: ignore[union-attr]
                try:
                    idn = res.query("*IDN?").strip()
                except Exception:
                    idn = ""
                finally:
                    res.close()
                info["idn"] = idn
                info["friendly"] = self._friendly_name(rstr, idn)
            except Exception:
                info["idn"] = ""
                info["friendly"] = info.get("address", rstr)
            results.append(info)
        return results

    def open_resource(
        self,
        resource_string: str,
        timeout_ms: int = 5000,
        read_termination: str = "\n",
        write_termination: str = "\n",
    ) -> pyvisa.resources.Resource:
        res = self._rm.open_resource(resource_string)  # type: ignore[union-attr]
        res.timeout = timeout_ms
        res.read_termination = read_termination
        res.write_termination = write_termination
        return res

    def close(self) -> None:
        if self._rm:
            self._rm.close()
            self._rm = None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_resource_string(rstr: str) -> dict:
        upper = rstr.upper()
        if upper.startswith("GPIB"):
            parts = rstr.split("::")
            addr = parts[1] if len(parts) > 1 else "?"
            return {"resource_string": rstr, "interface": "GPIB", "address": f"GPIB::{addr}"}
        if upper.startswith("USB"):
            return {"resource_string": rstr, "interface": "USB", "address": rstr}
        if upper.startswith("TCPIP"):
            parts = rstr.split("::")
            ip = parts[1] if len(parts) > 1 else "?"
            return {"resource_string": rstr, "interface": "Ethernet", "address": ip}
        return {"resource_string": rstr, "interface": "Unknown", "address": rstr}

    @staticmethod
    def _friendly_name(rstr: str, idn: str) -> str:
        if idn:
            parts = idn.split(",")
            if len(parts) >= 2:
                return f"{parts[0].strip()} {parts[1].strip()}"
        for uid, name in _KEITHLEY_USB_IDS.items():
            if uid.replace(":", "::") in rstr or uid in rstr:
                return name
        return rstr
