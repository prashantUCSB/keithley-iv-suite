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

    def list_resources_with_info(
        self, skip: "set[str] | None" = None
    ) -> list[dict]:
        """Return only physically reachable resources with IDN metadata.

        Parameters
        ----------
        skip : set of resource strings that are already open by connected drivers.
               Re-opening them causes VI_ERROR_NCIC; they are excluded from the
               scan probe but their rows remain in the UI from the initial connect.

        Resources that cannot be opened OR return an empty *IDN? response are
        silently dropped.  Serial ports (ASRL) are noisy false-positives and are
        always skipped.  The user can add any resource manually via the entry box.
        """
        skip = skip or set()
        all_resources = self.list_resources()
        log.info("VISA scan: probing %d resource(s): %s", len(all_resources), all_resources)
        results: list[dict] = []
        for rstr in all_resources:
            # Skip serial ports — they are never Keithley SMUs and always
            # time out on *IDN?, producing misleading log noise.
            if rstr.upper().startswith("ASRL"):
                log.debug("Skipping serial port: %s", rstr)
                continue

            # Skip resources already held open by our own connected drivers.
            if rstr in skip:
                log.debug("Skipping already-connected resource: %s", rstr)
                continue

            info = self._parse_resource_string(rstr)

            # Determine whether the USB vendor ID identifies this as Keithley
            # hardware.  This takes priority over the IDN-string check so that
            # is_smu stays True even when the IDN is garbled by stale buffer data.
            is_keithley_usb = False
            m = _USB_RE.match(rstr)
            if m:
                try:
                    is_keithley_usb = int(m.group(1), 16) == _KEITHLEY_VENDOR_ID
                except ValueError:
                    pass

            idn = ""
            try:
                res = self._rm.open_resource(  # type: ignore[union-attr]
                    rstr, open_timeout=3000
                )
                res.timeout = 3000
                res.read_termination  = "\n"
                res.write_termination = "\n"
                try:
                    # Clear the interface buffer before querying — for USBTMC
                    # this sends INITIATE_CLEAR which flushes stale measurement
                    # data that would otherwise be returned instead of the IDN.
                    try:
                        res.clear()
                    except Exception:
                        pass
                    idn = res.query("*IDN?").strip()
                except pyvisa.errors.VisaIOError as exc:
                    log.debug("IDN query failed for %s: %s", rstr, exc)
                    idn = ""
                except Exception as exc:
                    log.debug("IDN query error for %s: %s", rstr, exc)
                    idn = ""
                finally:
                    try:
                        res.close()
                    except Exception:
                        pass
            except pyvisa.errors.VisaIOError as exc:
                # VI_ERROR_NCIC: our own driver still holds this resource open.
                # Add the entry using hardware ID so the user can still see it.
                if "NCIC" in str(exc) and is_keithley_usb:
                    log.info(
                        "Resource %s is held by an existing session (NCIC) — "
                        "adding via USB vendor ID", rstr
                    )
                    info["idn"] = ""
                    info["friendly"] = self._friendly_name(rstr, "")
                    info["is_smu"] = True
                    results.append(info)
                else:
                    log.debug("Cannot open resource %s: %s", rstr, exc)
                continue
            except Exception as exc:
                log.debug("Skipping unreachable resource %s: %s", rstr, exc)
                continue

            if not idn:
                if is_keithley_usb:
                    # Hardware ID confirms Keithley device but IDN is empty
                    # (e.g. instrument is resetting) — add with product-ID name.
                    log.info("Keithley USB device responded without IDN: %s", rstr)
                    info["idn"] = ""
                    info["friendly"] = self._friendly_name(rstr, "")
                    info["is_smu"] = True
                    results.append(info)
                else:
                    log.debug("Skipping resource with no IDN response: %s", rstr)
                continue

            log.info("Found: %s  IDN=%r", rstr, idn)
            info["idn"] = idn
            info["friendly"] = self._friendly_name(rstr, idn)
            # is_smu: Keithley USB vendor ID takes priority over IDN content
            # so garbled IDN (stale measurement data) never hides the Connect button.
            info["is_smu"] = is_keithley_usb or any(
                k in idn.upper() for k in ("2400", "2401", "2410", "2420",
                                            "2450", "2460", "2470", "2601",
                                            "2602", "2604", "2611", "2612",
                                            "2614", "2634", "2636", "6430")
            )
            results.append(info)
        log.info("VISA scan complete: %d instrument(s) found", len(results))
        return results

    def open_resource(
        self,
        resource_string: str,
        timeout_ms: int = 5000,
        read_termination: str = "\n",
        write_termination: str = "\n",
    ) -> pyvisa.resources.Resource:
        res = self._rm.open_resource(  # type: ignore[union-attr]
            resource_string, open_timeout=timeout_ms
        )
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
