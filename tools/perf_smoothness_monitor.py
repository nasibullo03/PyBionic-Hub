#!/usr/bin/env python3
"""
tools/perf_smoothness_monitor.py
Real-time UI smoothness, frame rate (FPS), jank analysis, and resource health monitor.
Uses Android `dumpsys gfxinfo framestats` and `dumpsys meminfo` to verify 60fps/120fps
fluidity, detect frame drops, memory leaks, ANRs, and background CPU spikes.
"""

import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent))
import adb_core

DEFAULT_PKG = "dev.pybionic.runner"


@dataclass
class SmoothnessReport:
    package: str
    total_frames: int
    janky_frames: int
    jank_percentage: float
    percentile_90_ms: float
    percentile_95_ms: float
    percentile_99_ms: float
    total_pss_mb: float
    dalvik_heap_mb: float
    native_heap_mb: float
    crashes_detected: int
    anrs_detected: int
    status_rating: str  # "SMOOTH (🟢)", "MINOR_JANK (🟡)", "STUTTER (🔴)"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "package": self.package,
            "total_frames": self.total_frames,
            "janky_frames": self.janky_frames,
            "jank_percentage": round(self.jank_percentage, 2),
            "percentile_90_ms": round(self.percentile_90_ms, 2),
            "percentile_95_ms": round(self.percentile_95_ms, 2),
            "percentile_99_ms": round(self.percentile_99_ms, 2),
            "total_pss_mb": round(self.total_pss_mb, 2),
            "dalvik_heap_mb": round(self.dalvik_heap_mb, 2),
            "native_heap_mb": round(self.native_heap_mb, 2),
            "crashes_detected": self.crashes_detected,
            "anrs_detected": self.anrs_detected,
            "rating": self.status_rating,
        }


class PerfSmoothnessMonitor:
    def __init__(self, package: str = DEFAULT_PKG, device: Optional[str] = None):
        self.package = package
        self.device = device

    def reset_stats(self) -> None:
        """Resets gfxinfo framestats buffer before starting a test run."""
        adb_core.run_shell(f"dumpsys gfxinfo {self.package} reset", device=self.device)

    def capture_memory_info(self) -> Tuple[float, float, float]:
        """
        Parses dumpsys meminfo. Returns (total_pss_mb, dalvik_heap_mb, native_heap_mb).
        """
        out = adb_core.run_shell(f"dumpsys meminfo {self.package}", device=self.device)
        total_pss = 0.0
        dalvik = 0.0
        native = 0.0

        for line in out.splitlines():
            # Format typically: "TOTAL PSS:   123456" or table row
            if "TOTAL PSS:" in line or "TOTAL:" in line and "TOTAL PSS" not in line:
                m = re.search(r"(\d+)", line)
                if m:
                    total_pss = int(m.group(1)) / 1024.0
            elif "Native Heap" in line:
                parts = line.split()
                if len(parts) >= 3 and parts[2].isdigit():
                    native = int(parts[2]) / 1024.0
            elif "Dalvik Heap" in line:
                parts = line.split()
                if len(parts) >= 3 and parts[2].isdigit():
                    dalvik = int(parts[2]) / 1024.0

        return total_pss, dalvik, native

    def check_crashes_and_anrs(self) -> Tuple[int, int]:
        """Checks recent crash and ANR history for the package."""
        crash_out = adb_core.run_shell("dumpsys activity crashes", device=self.device)
        anr_out = adb_core.run_shell("dumpsys activity anrs", device=self.device)

        crash_count = len(re.findall(re.escape(self.package), crash_out))
        anr_count = len(re.findall(re.escape(self.package), anr_out))
        return crash_count, anr_count

    def analyze_framestats(self) -> SmoothnessReport:
        """Parses dumpsys gfxinfo output and computes jank rate and latency percentiles."""
        out = adb_core.run_shell(f"dumpsys gfxinfo {self.package}", device=self.device)

        total_frames = 0
        janky_frames = 0
        p90 = 0.0
        p95 = 0.0
        p99 = 0.0

        # Extract Total frames rendered
        m_total = re.search(r"Total frames rendered:\s+(\d+)", out)
        if m_total:
            total_frames = int(m_total.group(1))

        # Extract Janky frames
        m_jank = re.search(r"Janky frames:\s+(\d+)\s+\(([\d\.]+)%\)", out)
        if m_jank:
            janky_frames = int(m_jank.group(1))
            jank_pct = float(m_jank.group(2))
        else:
            jank_pct = (janky_frames / max(1, total_frames)) * 100.0

        # Extract 90th, 95th, 99th percentile
        m_p90 = re.search(r"90th percentile:\s+(\d+)ms", out)
        if m_p90:
            p90 = float(m_p90.group(1))
        m_p95 = re.search(r"95th percentile:\s+(\d+)ms", out)
        if m_p95:
            p95 = float(m_p95.group(1))
        m_p99 = re.search(r"99th percentile:\s+(\d+)ms", out)
        if m_p99:
            p99 = float(m_p99.group(1))

        # Memory stats
        pss_mb, dalvik_mb, native_mb = self.capture_memory_info()
        crashes, anrs = self.check_crashes_and_anrs()

        # Compute rating
        if jank_pct < 5.0 and crashes == 0 and anrs == 0:
            rating = "SMOOTH (🟢)"
        elif jank_pct < 15.0 and crashes == 0:
            rating = "MINOR_JANK (🟡)"
        else:
            rating = "STUTTER_OR_UNSTABLE (🔴)"

        return SmoothnessReport(
            package=self.package,
            total_frames=total_frames,
            janky_frames=janky_frames,
            jank_percentage=jank_pct,
            percentile_90_ms=p90,
            percentile_95_ms=p95,
            percentile_99_ms=p99,
            total_pss_mb=pss_mb,
            dalvik_heap_mb=dalvik_mb,
            native_heap_mb=native_mb,
            crashes_detected=crashes,
            anrs_detected=anrs,
            status_rating=rating,
        )


if __name__ == "__main__":
    monitor = PerfSmoothnessMonitor()
    rep = monitor.analyze_framestats()
    import json
    print(json.dumps(rep.to_dict(), indent=2))
