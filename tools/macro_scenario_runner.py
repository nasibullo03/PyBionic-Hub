#!/usr/bin/env python3
"""
tools/macro_scenario_runner.py
Batch multi-step macro execution engine for high-velocity Android testing.
Executes complete test flows (navigation sweeps, button clicks, dialog verification,
text typing, gestures) without interactive round-trip delays, capturing screenshots
and hierarchy state at key milestones.
"""

import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent))
import adb_core
from ui_dump_engine import UIDumpEngine, UIElement
from long_screenshot_stitcher import capture_scrolling_view


@dataclass
class StepResult:
    step_number: int
    action_type: str
    target: str
    duration_ms: int
    success: bool
    screenshot_path: Optional[str] = None
    error_message: Optional[str] = None
    ui_elements_count: int = 0


@dataclass
class ScenarioReport:
    name: str
    total_steps: int
    passed_steps: int
    failed_steps: int
    total_duration_sec: float
    results: List[StepResult] = field(default_factory=list)
    output_dir: str = ""

    def is_successful(self) -> bool:
        return self.failed_steps == 0


class MacroScenarioRunner:
    """Executes batched sequence of test steps on Android device."""

    def __init__(self, scenario_name: str, device: Optional[str] = None, output_base: str = "tools/captures/scenarios"):
        self.name = scenario_name
        self.device = device
        self.out_dir = Path(output_base) / scenario_name
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.ui_engine = UIDumpEngine(device=device)
        self.step_counter = 0
        self.results: List[StepResult] = []

    def _save_step_screenshot(self, name: str) -> str:
        dest = self.out_dir / f"step_{self.step_counter:02d}_{name}.png"
        adb_core.capture_fast_screencap(str(dest), device=self.device)
        return str(dest)

    def tap(self, text_or_desc: str, retries: int = 2, wait_after_sec: float = 0.3) -> "MacroScenarioRunner":
        """Finds element by text/description and taps it."""
        self.step_counter += 1
        t0 = time.time()
        success = False
        err = None

        for attempt in range(retries):
            self.ui_engine.dump_hierarchy()
            el = self.ui_engine.find(text=text_or_desc, desc=text_or_desc)
            if el:
                success = self.ui_engine.tap(el)
                break
            time.sleep(0.3)

        if not success:
            err = f"Element with text/desc '{text_or_desc}' not found on screen"

        if wait_after_sec > 0:
            time.sleep(wait_after_sec)

        dur = int((time.time() - t0) * 1000)
        shot = self._save_step_screenshot(f"tap_{text_or_desc[:12].strip().replace(' ', '_')}")
        self.results.append(
            StepResult(
                step_number=self.step_counter,
                action_type="TAP",
                target=text_or_desc,
                duration_ms=dur,
                success=success,
                screenshot_path=shot,
                error_message=err,
                ui_elements_count=len(self.ui_engine.elements),
            )
        )
        return self

    def tap_coord(self, x: int, y: int, label: str = "coord", wait_after_sec: float = 0.3) -> "MacroScenarioRunner":
        """Taps precise screen coordinate."""
        self.step_counter += 1
        t0 = time.time()
        adb_core.run_shell(f"input tap {x} {y}", device=self.device)
        if wait_after_sec > 0:
            time.sleep(wait_after_sec)
        dur = int((time.time() - t0) * 1000)
        shot = self._save_step_screenshot(f"tap_{label}")
        self.results.append(
            StepResult(
                step_number=self.step_counter,
                action_type="TAP_COORD",
                target=f"({x}, {y}) - {label}",
                duration_ms=dur,
                success=True,
                screenshot_path=shot,
            )
        )
        return self

    def swipe(self, direction: str = "up", distance_ratio: float = 0.5, duration_ms: int = 400, wait_after_sec: float = 0.4) -> "MacroScenarioRunner":
        """Swipes screen up, down, left, or right."""
        self.step_counter += 1
        t0 = time.time()
        w, h = adb_core.get_device_resolution(device=self.device)
        cx = w // 2
        cy = h // 2

        if direction == "up":
            y1 = int(h * 0.75)
            y2 = int(y1 - (h * distance_ratio))
            adb_core.run_shell(f"input swipe {cx} {y1} {cx} {y2} {duration_ms}", device=self.device)
        elif direction == "down":
            y1 = int(h * 0.25)
            y2 = int(y1 + (h * distance_ratio))
            adb_core.run_shell(f"input swipe {cx} {y1} {cx} {y2} {duration_ms}", device=self.device)
        elif direction == "left":
            x1 = int(w * 0.8)
            x2 = int(x1 - (w * distance_ratio))
            adb_core.run_shell(f"input swipe {x1} cy {x2} cy {duration_ms}", device=self.device)
        elif direction == "right":
            x1 = int(w * 0.2)
            x2 = int(x1 + (w * distance_ratio))
            adb_core.run_shell(f"input swipe {x1} cy {x2} cy {duration_ms}", device=self.device)

        if wait_after_sec > 0:
            time.sleep(wait_after_sec)

        dur = int((time.time() - t0) * 1000)
        shot = self._save_step_screenshot(f"swipe_{direction}")
        self.results.append(
            StepResult(
                step_number=self.step_counter,
                action_type="SWIPE",
                target=direction,
                duration_ms=dur,
                success=True,
                screenshot_path=shot,
            )
        )
        return self

    def input_text(self, text: str, wait_after_sec: float = 0.3) -> "MacroScenarioRunner":
        """Enters text into focused input field."""
        self.step_counter += 1
        t0 = time.time()
        # Escape spaces for ADB input
        escaped = text.replace(" ", "%s")
        adb_core.run_shell(f"input text '{escaped}'", device=self.device)
        if wait_after_sec > 0:
            time.sleep(wait_after_sec)
        dur = int((time.time() - t0) * 1000)
        shot = self._save_step_screenshot("input_text")
        self.results.append(
            StepResult(
                step_number=self.step_counter,
                action_type="INPUT_TEXT",
                target=text,
                duration_ms=dur,
                success=True,
                screenshot_path=shot,
            )
        )
        return self

    def key(self, keycode: str, wait_after_sec: float = 0.3) -> "MacroScenarioRunner":
        """Sends key event (e.g. BACK, ENTER, TAB, HOME)."""
        self.step_counter += 1
        t0 = time.time()
        adb_core.run_shell(f"input keyevent KEYCODE_{keycode.upper()}", device=self.device)
        if wait_after_sec > 0:
            time.sleep(wait_after_sec)
        dur = int((time.time() - t0) * 1000)
        shot = self._save_step_screenshot(f"key_{keycode}")
        self.results.append(
            StepResult(
                step_number=self.step_counter,
                action_type="KEY",
                target=keycode,
                duration_ms=dur,
                success=True,
                screenshot_path=shot,
            )
        )
        return self

    def assert_visible(self, text: str) -> "MacroScenarioRunner":
        """Asserts that text is visible on the current screen."""
        self.step_counter += 1
        t0 = time.time()
        self.ui_engine.dump_hierarchy()
        el = self.ui_engine.find(text=text, desc=text)
        found = el is not None
        dur = int((time.time() - t0) * 1000)
        shot = self._save_step_screenshot(f"assert_{text[:10].strip().replace(' ', '_')}")
        self.results.append(
            StepResult(
                step_number=self.step_counter,
                action_type="ASSERT_VISIBLE",
                target=text,
                duration_ms=dur,
                success=found,
                screenshot_path=shot,
                error_message=None if found else f"Text '{text}' not found on screen",
                ui_elements_count=len(self.ui_engine.elements),
            )
        )
        return self

    def capture_full_scroll(self, name: str, max_swipes: int = 8) -> "MacroScenarioRunner":
        """Captures a scrolling stitched panoramic screenshot."""
        self.step_counter += 1
        t0 = time.time()
        dest = self.out_dir / f"step_{self.step_counter:02d}_{name}_long.png"
        stitched_path, _ = capture_scrolling_view(str(dest), max_swipes=max_swipes, device=self.device)
        dur = int((time.time() - t0) * 1000)
        self.results.append(
            StepResult(
                step_number=self.step_counter,
                action_type="CAPTURE_LONG_SCROLL",
                target=name,
                duration_ms=dur,
                success=bool(stitched_path),
                screenshot_path=stitched_path,
            )
        )
        return self

    def build_report(self) -> ScenarioReport:
        """Compiles scenario execution report and writes report.json."""
        passed = sum(1 for r in self.results if r.success)
        failed = sum(1 for r in self.results if not r.success)
        total_time = sum(r.duration_ms for r in self.results) / 1000.0

        rep = ScenarioReport(
            name=self.name,
            total_steps=len(self.results),
            passed_steps=passed,
            failed_steps=failed,
            total_duration_sec=total_time,
            results=self.results,
            output_dir=str(self.out_dir),
        )

        rep_file = self.out_dir / "report.json"
        with open(rep_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "name": rep.name,
                    "total_steps": rep.total_steps,
                    "passed": rep.passed_steps,
                    "failed": rep.failed_steps,
                    "duration_sec": round(rep.total_duration_sec, 2),
                    "steps": [asdict(r) for r in rep.results],
                },
                f,
                indent=2,
                ensure_ascii=False,
            )

        print(f"[MACRO] Scenario '{self.name}' finished: {passed}/{len(self.results)} passed ({total_time:.2f}s).")
        return rep


if __name__ == "__main__":
    print("Macro Scenario Runner module ready.")
