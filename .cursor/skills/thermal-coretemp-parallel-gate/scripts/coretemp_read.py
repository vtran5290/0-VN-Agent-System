"""
Read CPU temperatures from Core Temp via GetCoreTempInfo.dll (ALCPU SDK).

Prerequisites:
  - Core Temp is running (shared memory / DLL bridge).
  - GetCoreTempInfo.dll bitness matches this Python process (x64 Python needs x64 DLL).
  - Set CORE_TEMP_INFO_DLL to the full path of GetCoreTempInfo.dll, or place the DLL
    next to this script, or install under Program Files/Core Temp.

Reference: https://alcpu.com/CoreTemp/developers.html
"""

from __future__ import annotations

import argparse
import json
import os
from ctypes import CDLL, POINTER, Structure, WinDLL, byref, c_bool, c_char, c_float, c_uint, c_ubyte, sizeof
from ctypes import windll
from pathlib import Path


class CoreTempSharedDataEx(Structure):
    """Must match CoreTempSharedDataEx from Core Temp developers page (4-byte alignment)."""

    _pack_ = 4
    _fields_ = [
        ("uiLoad", c_uint * 256),
        ("uiTjMax", c_uint * 128),
        ("uiCoreCnt", c_uint),
        ("uiCPUCnt", c_uint),
        ("fTemp", c_float * 256),
        ("fVID", c_float),
        ("fCPUSpeed", c_float),
        ("fFSBSpeed", c_float),
        ("fMultiplier", c_float),
        ("sCPUName", c_char * 100),
        ("ucFahrenheit", c_ubyte),
        ("ucDeltaToTjMax", c_ubyte),
        ("ucTdpSupported", c_ubyte),
        ("ucPowerSupported", c_ubyte),
        ("uiStructVersion", c_uint),
        ("uiTdp", c_uint * 128),
        ("fPower", c_float * 128),
        ("fMultipliers", c_float * 256),
    ]


def _dll_candidates() -> list[Path]:
    env = os.environ.get("CORE_TEMP_INFO_DLL", "").strip()
    out: list[Path] = []
    if env:
        out.append(Path(env))
    here = Path(__file__).resolve().parent
    out.append(here / "GetCoreTempInfo.dll")
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    for base in (pf, pf86):
        out.append(Path(base) / "Core Temp" / "GetCoreTempInfo.dll")
    return out


def _zero_buf(buf: CoreTempSharedDataEx) -> None:
    CDLL("msvcrt").memset(byref(buf), 0, sizeof(buf))


def read_core_temp() -> dict:
    dll_path = next((p for p in _dll_candidates() if p.is_file()), None)
    if dll_path is None:
        return {
            "ok": False,
            "error": "GetCoreTempInfo.dll not found. Install Core Temp SDK DLL or set CORE_TEMP_INFO_DLL.",
            "candidates": [str(p) for p in _dll_candidates()],
        }

    buf = CoreTempSharedDataEx()
    _zero_buf(buf)

    dll = WinDLL(str(dll_path))
    fn = dll.fnGetCoreTempInfoAlt
    fn.argtypes = [POINTER(CoreTempSharedDataEx)]
    fn.restype = c_bool

    ok = bool(fn(byref(buf)))
    if not ok:
        err = int(windll.kernel32.GetLastError())
        return {"ok": False, "error": "fnGetCoreTempInfoAlt returned false", "winerror": err, "dll": str(dll_path)}

    n = int(buf.uiCoreCnt)
    if n <= 0 or n > 256:
        return {"ok": False, "error": "invalid uiCoreCnt", "uiCoreCnt": n, "dll": str(dll_path)}

    temps = [float(buf.fTemp[i]) for i in range(n)]
    fahrenheit = bool(buf.ucFahrenheit)
    unit = "F" if fahrenheit else "C"
    raw_name = bytes(buf.sCPUName).split(b"\x00", 1)[0]
    return {
        "ok": True,
        "dll": str(dll_path),
        "cpu_name": raw_name.decode("utf-8", errors="replace"),
        "uiCoreCnt": n,
        "uiCPUCnt": int(buf.uiCPUCnt),
        "uiStructVersion": int(buf.uiStructVersion),
        "fahrenheit": fahrenheit,
        "unit": unit,
        "temps": temps,
        "max_temp": max(temps),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="Print one JSON object on stdout.")
    args = ap.parse_args()
    data = read_core_temp()
    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print(data)
    return 0 if data.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
