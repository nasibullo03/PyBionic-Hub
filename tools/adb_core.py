#!/usr/bin/env python3
"""
tools/adb_core.py
PyBionic Smart ADB Discovery & Low-Latency Bridge.
Provides automatic adb.exe location resolution, fast streaming screencap,
batch shell execution, and low-latency interaction.
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

POSSIBLE_ADB_PATHS = [
    r"C:\Users\User\AppData\Local\Android\Sdk\platform-tools\adb.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"),
    os.path.expandvars(r"%ANDROID_HOME%\platform-tools\adb.exe"),
    os.path.expandvars(r"%ANDROID_SDK_ROOT%\platform-tools\adb.exe"),
    "adb",  # system PATH fallback
]


def resolve_adb_path() -> str:
    """Finds the working adb executable path on the host system."""
    for path in POSSIBLE_ADB_PATHS:
        try:
            res = subprocess.run(
                [path, "version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            if res.returncode == 0:
                return path
        except Exception:
            continue
    return "adb"


ADB_BIN = resolve_adb_path()


def get_connected_devices() -> List[str]:
    """Returns list of active connected device serials."""
    try:
        res = subprocess.run(
            [ADB_BIN, "devices"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False
        )
        if res.returncode != 0:
            return []
        devices = []
        for line in res.stdout.strip().splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                devices.append(parts[0])
        return devices
    except Exception:
        return []


def get_default_device() -> Optional[str]:
    """Returns the primary active device serial or None."""
    devices = get_connected_devices()
    return devices[0] if devices else None


def run_adb(args: List[str], device: Optional[str] = None, check: bool = True) -> subprocess.CompletedProcess:
    """Runs an arbitrary ADB command with the resolved binary."""
    cmd = [ADB_BIN]
    if device:
        cmd += ["-s", device]
    cmd += args
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=check)


def run_shell(command: str, device: Optional[str] = None) -> str:
    """Executes a shell command on the device and returns stdout."""
    res = run_adb(["shell", command], device=device, check=False)
    return res.stdout


def run_batch_shell(commands: List[str], device: Optional[str] = None) -> str:
    """Executes multiple shell commands in a single pipeline."""
    combined = " && ".join(commands)
    return run_shell(combined, device=device)


def capture_fast_screencap(dest_path: str, device: Optional[str] = None) -> bool:
    """Captures screenshot directly to disk using ADB exec-out streaming (~0.2s)."""
    dest = Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [ADB_BIN]
    if device:
        cmd += ["-s", device]
    cmd += ["exec-out", "screencap", "-p"]

    try:
        with open(dest, "wb") as f:
            res = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, check=True)
        return dest.exists() and dest.stat().st_size > 1000
    except Exception as e:
        print(f"[ADB_CORE] Screencap failed: {e}", file=sys.stderr)
        return False


def get_device_resolution(device: Optional[str] = None) -> Tuple[int, int]:
    """Returns (width, height) of the physical or override display."""
    out = run_shell("wm size", device=device)
    # Output format: "Physical size: 1080x2400" or "Override size: ..."
    for line in out.splitlines():
        if "size:" in line:
            parts = line.split(":")[-1].strip().split("x")
            if len(parts) == 2:
                try:
                    return int(parts[0]), int(parts[1])
                except ValueError:
                    pass
    return 1080, 2400  # Default modern resolution fallback


if __name__ == "__main__":
    print(f"[ADB_CORE] Resolved ADB binary: {ADB_BIN}")
    devices = get_connected_devices()
    print(f"[ADB_CORE] Connected devices: {devices}")
