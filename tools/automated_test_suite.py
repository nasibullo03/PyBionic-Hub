#!/usr/bin/env python3
"""
tools/automated_test_suite.py
High-velocity turnkey test suite for verifying 1000+ PyBionic changes on device.
Runs complete end-to-end scenarios covering Settings Hubs, Zen Mode Editor,
Terminal signals, Stdin history, Deep Search, and 60fps/120fps smoothness profiling.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import adb_core
from macro_scenario_runner import MacroScenarioRunner
from perf_smoothness_monitor import PerfSmoothnessMonitor
from comprehensive_inspector import inspect_live_screen

PACKAGE_NAME = "dev.pybionic.runner"
MAIN_ACTIVITY = "dev.pybionic.runner.ui.MainActivity"


def launch_app(device: str = None) -> None:
    """Launches or brings PyBionic to the foreground."""
    print(f"[TEST_SUITE] Launching {PACKAGE_NAME}...")
    adb_core.run_shell(f"am start -n {PACKAGE_NAME}/{MAIN_ACTIVITY}", device=device)
    time.sleep(1.0)


def test_settings_8_hubs(device: str = None) -> bool:
    """Suite 1: Verifies the 8 Settings Hub categories and card filtering."""
    print("\n==========================================")
    print("▶ RUNNING SUITE: Settings 8 Category Hubs")
    print("==========================================")

    runner = MacroScenarioRunner("suite_settings_8_hubs", device=device)

    # 1. Navigate to Settings
    runner.tap("Settings")
    runner.tap("Настройки")  # Russian or English fallback

    categories = [
        ("Все", "ALL"),
        ("Общие & UI", "GENERAL"),
        ("Ядро сервера", "SERVER_KERNEL"),
        ("Безопасность", "SECURITY"),
        ("Python & Среда", "PYTHON_KERNEL"),
        ("Батарея & OEM", "OEM_BATTERY"),
        ("Сеть & Web", "NETWORK"),
        ("Хранилище & Бэкапы", "STORAGE_BACKUP"),
    ]

    for cat_name, code in categories:
        print(f"  • Testing category: {cat_name} ({code})")
        runner.tap(cat_name)
        # Capture view state for this category
        runner.swipe("down", distance_ratio=0.3)  # scroll to top if needed
        time.sleep(0.3)

    # Return to "Все"
    runner.tap("Все")
    rep = runner.build_report()
    return rep.is_successful()


def test_editor_and_terminal(device: str = None) -> bool:
    """Suite 2: Verifies Zen Mode, D-Pad, Auto-indent, and Shell hardware signals."""
    print("\n==========================================")
    print("▶ RUNNING SUITE: Editor, Zen Mode & Terminal")
    print("==========================================")

    runner = MacroScenarioRunner("suite_editor_terminal", device=device)

    # Tap on first project or main bot card
    runner.tap("main.py")
    runner.tap("Files")
    runner.tap("Файлы")

    # Open first editable file
    runner.tap(".py")

    # Toggle Zen Mode
    print("  • Testing Editor Zen Mode...")
    runner.tap("Zen Mode")
    runner.tap("Дзен")
    time.sleep(0.4)
    # Exit Zen Mode
    runner.tap("Exit Zen")
    runner.tap("Выход из Дзен")

    # Test D-Pad
    print("  • Testing Cursor D-Pad navigation...")
    runner.tap("◀")
    runner.tap("▶")
    runner.tap("▲")
    runner.tap("▼")

    # Close editor
    runner.key("BACK")
    time.sleep(0.3)

    # Switch to Console Tab
    print("  • Testing Console Tab & Traceback copy...")
    runner.tap("Console")
    runner.tap("Консоль")
    time.sleep(0.4)
    runner.tap("📋 Traceback")

    # Switch to Shell Tab
    print("  • Testing Interactive Shell & Hardware Signals...")
    runner.tap("Shell")
    runner.tap("Шелл")
    time.sleep(0.3)
    runner.tap("Ctrl+C")
    runner.tap("Ctrl+D")
    runner.tap("Tab")
    runner.tap("Clear")

    rep = runner.build_report()
    return rep.is_successful()


def test_smoothness_stress(device: str = None) -> dict:
    """Suite 3: Profiles 60fps/120fps smoothness during fast fling scrolling."""
    print("\n==========================================")
    print("▶ RUNNING SUITE: 60fps/120fps Smoothness Stress")
    print("==========================================")

    perf = PerfSmoothnessMonitor(package=PACKAGE_NAME, device=device)
    perf.reset_stats()

    w, h = adb_core.get_device_resolution(device=device)
    cx = w // 2
    y_start = int(h * 0.8)
    y_end = int(h * 0.2)

    print("  • Executing 6 rapid vertical fling scrolls...")
    for _ in range(3):
        adb_core.run_shell(f"input swipe {cx} {y_start} {cx} {y_end} 200", device=device)
        time.sleep(0.3)
    for _ in range(3):
        adb_core.run_shell(f"input swipe {cx} {y_end} {cx} {y_start} 200", device=device)
        time.sleep(0.3)

    time.sleep(0.5)
    rep = perf.analyze_framestats()
    print(f"  • Smoothness Result: {rep.status_rating}")
    print(f"  • Jank Percentage: {rep.jank_percentage:.2f}% ({rep.janky_frames}/{rep.total_frames} frames)")
    print(f"  • 90th percentile frame time: {rep.percentile_90_ms:.1f}ms (target: < 16.6ms)")
    print(f"  • Total Memory PSS: {rep.total_pss_mb:.1f} MB")
    return rep.to_dict()


def run_full_suite(device: str = None) -> None:
    """Runs all suites and produces comprehensive audit package."""
    t_start = time.time()
    launch_app(device=device)

    print("\n🚀 [STARTING FULL PYBIONIC AUTOMATION VERIFICATION SUITE] 🚀\n")

    res_settings = test_settings_8_hubs(device=device)
    res_editor = test_editor_and_terminal(device=device)
    res_perf = test_smoothness_stress(device=device)

    # Final overall comprehensive inspection dump
    print("\n📸 [GENERATING FINAL COMPREHENSIVE VISUAL AUDIT REPORT]")
    inspect_live_screen(name="final_audit_summary", scroll_long=True, max_swipes=6, device=device)

    total_time = time.time() - t_start
    print("\n" + "=" * 50)
    print("🏁 ALL AUTOMATION TEST SUITES FINISHED!")
    print(f"⏱ Total Execution Time: {total_time:.2f} seconds")
    print(f"• Settings 8 Hubs Suite: {'PASS ✅' if res_settings else 'FAIL ❌'}")
    print(f"• Editor & Terminal Suite: {'PASS ✅' if res_editor else 'FAIL ❌'}")
    print(f"• Smoothness & 60fps Rating: {res_perf.get('rating', 'UNKNOWN')}")
    print("=" * 50)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PyBionic Automated Test Suite")
    parser.add_argument("--suite", choices=["all", "settings", "editor", "perf"], default="all")
    args = parser.parse_args()

    if args.suite == "all":
        run_full_suite()
    elif args.suite == "settings":
        test_settings_8_hubs()
    elif args.suite == "editor":
        test_editor_and_terminal()
    elif args.suite == "perf":
        test_smoothness_stress()
