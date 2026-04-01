"""VISA resource manager — auto-detects NI-VISA, Keysight IO, or pyvisa-py."""
from __future__ import annotations

import logging
import re
from typing import Optional

import pyvisa
import pyvisa.errors

log = logging.getLogger(__name__)

# Keithley USB vendor ID (decimal 1510 = 0x05E6)
_KEITHLEY_VENDOR_ID = 0x05E6

# USB product-ID → model string (integer keys, no string-matching ambiguity)
_KEITHLEY_USB_PRODUCTS: dict[int, str] = {
    0x2400: "2400",
    0x2401: "2401",
    0x2602: "2602",
    0x2612: "2612B",
    0x2614: "2614B",
    0x2634: "2634B",
    0x2636: "2636B",
}

# Pre-compiled pattern for USB VISA resource strings:
# USB[board]::0x<vendor>::0x<product>::<serial>::INSTR
_USB_RE = re.compile(
    r"USB\d*::0x([0-9A-Fa-f]+)::0x([0-9A-Fa-f]+)::",
    re.IGNORECASE,
)

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
                res = self._rm.open_resource(rstr, open_timeout=2000)  # type: ignore[union-attr]
                res.timeout = 2000  # 2 s — 2600-series can be slow to respond
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
            return {"resource_string": rstr, "interface": "GPIB", "address": f"GPIB · {addr}"}
        if upper.startswith("USB"):
            m = _USB_RE.match(rstr)
            short = f"USB · 0x{m.group(2).upper()}" if m else "USB"
            return {"resource_string": rstr, "interface": "USB", "address": short}
        if upper.startswith("TCPIP"):
            parts = rstr.split("::")
            ip = parts[1] if len(parts) > 1 else "?"
            return {"resource_string": rstr, "interface": "Ethernet", "address": f"LAN · {ip}"}
        return {"resource_string": rstr, "interface": "Unknown", "address": rstr}

    @staticmethod
    def _friendly_name(rstr: str, idn: str) -> str:
        # Prefer IDN field 2 — "MODEL 2614B" → "Keithley 2614B"
        if idn:
            parts = [p.strip() for p in idn.split(",")]
            if len(parts) >= 2:
                model = parts[1].upper().replace("MODEL", "").strip()
                if model:
                    return f"Keithley {model}"
        # Fall back to USB product-ID lookup (handles scan with no IDN)
        m = _USB_RE.match(rstr)
        if m:
            try:
                vendor  = int(m.group(1), 16)
                product = int(m.group(2), 16)
                if vendor == _KEITHLEY_VENDOR_ID:
                    model_str = _KEITHLEY_USB_PRODUCTS.get(product)
                    if model_str:
                        return f"Keithley {model_str}"
            except ValueError:
                pass
        return rstr
