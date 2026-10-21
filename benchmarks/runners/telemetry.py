"""Measured host/GPU telemetry, with unsupported counters represented by null."""
from __future__ import annotations

import csv
import ctypes
import io
import os
import platform
import shutil
import subprocess
import threading
import time
from datetime import datetime, timezone
from typing import Any

try:
    import psutil
except ImportError:  # CPU/RAM telemetry is optional; absence is explicit.
    psutil = None


def command(args: list[str], timeout: float = 10) -> dict[str, Any]:
    try:
        result = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return {"argv": args, "exit_code": result.returncode,
                "stdout": (result.stdout or "").strip(), "stderr": (result.stderr or "").strip()}
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"argv": args, "error": type(error).__name__}


def windows_file_version(path: str) -> dict[str, str] | None:
    """Read the installed executable's native VERSIONINFO without running it."""
    if os.name != "nt":
        return None
    try:
        version = ctypes.WinDLL("version", use_last_error=True)
        version.GetFileVersionInfoSizeW.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_uint32)]
        version.GetFileVersionInfoSizeW.restype = ctypes.c_uint32
        version.GetFileVersionInfoW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
        version.VerQueryValueW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_uint)]
        size = version.GetFileVersionInfoSizeW(path, None)
        if not 0 < size < 1_000_000:
            return None
        buffer = ctypes.create_string_buffer(size)
        if not version.GetFileVersionInfoW(path, 0, size, buffer):
            return None
        pointer, length = ctypes.c_void_p(), ctypes.c_uint()
        if not version.VerQueryValueW(buffer, "\\", ctypes.byref(pointer), ctypes.byref(length)) or length.value < 52:
            return None
        fixed = ctypes.cast(pointer, ctypes.POINTER(ctypes.c_uint32 * 13)).contents
        if fixed[0] != 0xFEEF04BD:
            return None
        def dotted(ms, ls):
            return f"{ms >> 16}.{ms & 65535}.{ls >> 16}.{ls & 65535}"
        return {"file_version": dotted(fixed[2], fixed[3]), "product_version": dotted(fixed[4], fixed[5])}
    except (OSError, ValueError, AttributeError):
        return None


def lm_studio_application() -> dict[str, Any]:
    if psutil:
        for process in psutil.process_iter(["name", "exe"]):
            try:
                if (process.info.get("name") or "").lower() == "lm studio.exe" and process.info.get("exe"):
                    path = process.info["exe"]
                    return {"executable": path, "version_info": windows_file_version(path),
                            "source": "running application Windows VERSIONINFO"}
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    return {"executable": None, "version_info": None, "source": "not observed; CLI version recorded separately"}


def inventory() -> dict[str, Any]:
    nvidia = shutil.which("nvidia-smi")
    lms = shutil.which("lms")
    return {"captured_at": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(),
            "python": platform.python_version(), "logical_cpu_count": os.cpu_count(),
            "psutil_available": psutil is not None,
            "lm_studio_application": lm_studio_application(),
            "physical_memory_bytes": psutil.virtual_memory().total if psutil else None,
            "available_memory_bytes": psutil.virtual_memory().available if psutil else None,
            "nvidia": command([nvidia, "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader,nounits"]) if nvidia else None,
            "lms_version": command([lms, "--version"]) if lms else None,
            "lms_loaded_models": command([lms, "ps", "--json"]) if lms else None}


class Telemetry:
    def __init__(self, interval: float = 1) -> None:
        self.interval = interval
        self.samples: list[dict[str, Any]] = []
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.nvidia = shutil.which("nvidia-smi")
        self.started = 0.0
        self.processes: list[Any] = []

    def sample(self) -> None:
        row: dict[str, Any] = {"seconds": round(time.perf_counter() - self.started, 4),
                               "gpu_used_mib": None, "gpu_utilization_percent": None,
                               "system_used_ram_bytes": None, "system_cpu_percent": None,
                               "lm_process_rss_bytes": None, "lm_process_cpu_percent": None}
        if psutil:
            memory = psutil.virtual_memory()
            row.update(system_used_ram_bytes=memory.total - memory.available,
                       system_cpu_percent=psutil.cpu_percent(interval=None))
            processes = []
            rss = 0
            cpu = 0.0
            for proc in self.processes:
                try:
                    rss += proc.memory_info().rss
                    cpu += proc.cpu_percent(interval=None)
                    processes.append(proc)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            row.update(lm_process_rss_bytes=rss if processes else None,
                       lm_process_cpu_percent=cpu if processes else None)
        if self.nvidia:
            data = command([self.nvidia, "--query-gpu=memory.used,utilization.gpu,utilization.memory,power.draw", "--format=csv,noheader,nounits"], timeout=5)
            try:
                values = next(csv.reader(io.StringIO(data.get("stdout", ""))))
                row.update(gpu_used_mib=float(values[0]), gpu_utilization_percent=float(values[1]),
                           gpu_memory_utilization_percent=float(values[2]), gpu_power_watts=float(values[3]))
            except (ValueError, IndexError, StopIteration):
                pass
        self.samples.append(row)

    def _loop(self) -> None:
        while not self.stop_event.wait(self.interval):
            self.sample()

    def __enter__(self):
        self.started = time.perf_counter()
        if psutil:
            for proc in psutil.process_iter(["name"]):
                name = (proc.info.get("name") or "").lower()
                if any(token in name for token in ("lm studio", "lmstudio", "llm", "llama")):
                    try:
                        proc.cpu_percent(interval=None)
                        self.processes.append(proc)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
        self.sample()
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=6)
        self.sample()

    def summary(self) -> dict[str, Any]:
        summary = {}
        for key in ("gpu_used_mib", "gpu_utilization_percent", "system_used_ram_bytes",
                    "system_cpu_percent", "lm_process_rss_bytes", "lm_process_cpu_percent"):
            values = [sample[key] for sample in self.samples if sample.get(key) is not None]
            summary[f"peak_{key}"] = max(values) if values else None
            summary[f"mean_{key}"] = sum(values) / len(values) if values else None
        return {"measurement": "sampled", "sample_interval_seconds": self.interval,
                "samples": len(self.samples), **summary}
