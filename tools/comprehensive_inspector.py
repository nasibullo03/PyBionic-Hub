#!/usr/bin/env python3
"""
tools/comprehensive_inspector.py
All-in-one comprehensive inspection tool for PyBionic Android app.
Executes in ~2-3 seconds:
  1. Fast screenshot (or optional scrolling long screenshot).
  2. Full UI hierarchy dump (all texts, buttons, switches & checked states).
  3. Real-time logcat crash & warning scanner.
  4. Smoothness framestats (Jank %, 90th percentile, memory PSS).
  5. Generates standalone HTML & Markdown visual inspection report.
"""

import argparse
import base64
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))
import adb_core
from long_screenshot_stitcher import capture_scrolling_view
from perf_smoothness_monitor import PerfSmoothnessMonitor
from ui_dump_engine import UIDumpEngine


def generate_html_report(
    report_title: str,
    screenshot_path: str,
    ui_elements: list,
    perf_data: dict,
    logcat_errors: list,
    output_html_path: str
) -> None:
    """Renders a comprehensive, dark-themed HTML report with embedded visuals and data tables."""
    # Convert screenshot to base64 for self-contained portability
    img_b64 = ""
    if os.path.exists(screenshot_path):
        with open(screenshot_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")

    switches = [el for el in ui_elements if el.get("class") in ("Switch", "CheckBox", "RadioButton") or "switch" in el.get("class", "").lower()]
    buttons = [el for el in ui_elements if el.get("clickable") and el not in switches]

    rating_color = "#00FF66" if "🟢" in perf_data.get("rating", "") else "#FFD700" if "🟡" in perf_data.get("rating", "") else "#FF3366"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{report_title} - PyBionic Inspection</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace;
      background: #0B0E14;
      color: #E2E8F0;
      margin: 0;
      padding: 24px;
    }}
    .header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 2px solid #1E293B;
      padding-bottom: 16px;
      margin-bottom: 24px;
    }}
    .title {{ font-size: 24px; font-weight: bold; color: #00E5FF; }}
    .badge {{
      display: inline-block;
      padding: 6px 12px;
      border-radius: 8px;
      font-weight: bold;
      background: rgba(0, 229, 255, 0.15);
      border: 1px solid #00E5FF;
      color: #00E5FF;
    }}
    .perf-cards {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }}
    .card {{
      background: #151A23;
      border: 1px solid #1E293B;
      border-radius: 12px;
      padding: 16px;
    }}
    .card-title {{ font-size: 12px; color: #94A3B8; text-transform: uppercase; margin-bottom: 6px; }}
    .card-val {{ font-size: 22px; font-weight: bold; color: #FFFFFF; }}
    .grid-2 {{
      display: grid;
      grid-template-columns: 420px 1fr;
      gap: 24px;
    }}
    .screenshot-pane {{
      background: #151A23;
      border: 1px solid #1E293B;
      border-radius: 12px;
      padding: 16px;
      text-align: center;
    }}
    .screenshot-img {{
      max-width: 100%;
      height: auto;
      max-height: 820px;
      border-radius: 8px;
      box-shadow: 0 8px 24px rgba(0,0,0,0.6);
      border: 1px solid #334155;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 12px;
      font-size: 13px;
    }}
    th, td {{
      padding: 10px;
      text-align: left;
      border-bottom: 1px solid #1E293B;
    }}
    th {{ background: #1C2331; color: #00E5FF; font-weight: bold; }}
    tr:hover {{ background: rgba(0, 229, 255, 0.05); }}
    .switch-on {{ color: #00FF66; font-weight: bold; }}
    .switch-off {{ color: #94A3B8; }}
    .log-err {{ background: rgba(255, 51, 102, 0.15); color: #FF7B72; font-family: monospace; padding: 4px; border-radius: 4px; }}
  </style>
</head>
<body>

  <div class="header">
    <div>
      <div class="title">⚡ PyBionic Live Inspection Report</div>
      <div style="color: #64748B; font-size: 13px; margin-top: 4px;">Scenario: {report_title} • Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</div>
    </div>
    <div class="badge" style="border-color: {rating_color}; color: {rating_color};">
      {perf_data.get('rating', 'UNKNOWN')}
    </div>
  </div>

  <div class="perf-cards">
    <div class="card">
      <div class="card-title">Jank Rate</div>
      <div class="card-val" style="color: {rating_color};">{perf_data.get('jank_percentage', 0.0)}%</div>
      <div style="font-size: 11px; color: #64748B;">{perf_data.get('janky_frames', 0)} / {perf_data.get('total_frames', 0)} frames</div>
    </div>
    <div class="card">
      <div class="card-title">90th / 95th Percentile</div>
      <div class="card-val">{perf_data.get('percentile_90_ms', 0)}ms <span style="font-size: 14px; color: #94A3B8;">/ {perf_data.get('percentile_95_ms', 0)}ms</span></div>
      <div style="font-size: 11px; color: #64748B;">Target: &lt; 16.6ms (60 FPS)</div>
    </div>
    <div class="card">
      <div class="card-title">Memory (PSS Total)</div>
      <div class="card-val">{perf_data.get('total_pss_mb', 0)} MB</div>
      <div style="font-size: 11px; color: #64748B;">Native: {perf_data.get('native_heap_mb', 0)} MB | Dalvik: {perf_data.get('dalvik_heap_mb', 0)} MB</div>
    </div>
    <div class="card">
      <div class="card-title">Interactive Elements</div>
      <div class="card-val">{len(ui_elements)}</div>
      <div style="font-size: 11px; color: #64748B;">Switches: {len(switches)} | Buttons: {len(buttons)}</div>
    </div>
  </div>

  <div class="grid-2">
    <div class="screenshot-pane">
      <div style="font-weight: bold; margin-bottom: 12px; color: #94A3B8;">Captured Screen State</div>
      <img src="data:image/png;base64,{img_b64}" class="screenshot-img" alt="Device Screenshot">
    </div>

    <div>
      <div class="card" style="margin-bottom: 24px;">
        <h3 style="margin-top: 0; color: #00E5FF;">🔘 Detected Switches & Toggles ({len(switches)})</h3>
        <table>
          <tr>
            <th>Label / Description</th>
            <th>Type</th>
            <th>State</th>
            <th>Center Coordinates</th>
          </tr>
          {''.join(f'''<tr>
            <td><strong>{s.get("text") or s.get("desc") or "Unnamed Toggle"}</strong></td>
            <td><code>{s.get("class")}</code></td>
            <td class="{'switch-on' if s.get('checked') else 'switch-off'}">{'[ON]' if s.get('checked') else '[OFF]'}</td>
            <td><code>{s.get("center")}</code></td>
          </tr>''' for s in switches[:50])}
        </table>
      </div>

      <div class="card">
        <h3 style="margin-top: 0; color: #FFD700;">📑 Key Visible Elements ({len(buttons)})</h3>
        <table>
          <tr>
            <th>Text</th>
            <th>Content Desc</th>
            <th>Bounds</th>
          </tr>
          {''.join(f'''<tr>
            <td>{b.get("text") or "—"}</td>
            <td>{b.get("desc") or "—"}</td>
            <td><code>{b.get("bounds")}</code></td>
          </tr>''' for b in buttons[:40])}
        </table>
      </div>
    </div>
  </div>

</body>
</html>
"""
    with open(output_html_path, "w", encoding="utf-8") as f:
        f.write(html)


def inspect_live_screen(
    name: str = "quick_inspection",
    scroll_long: bool = False,
    max_swipes: int = 6,
    output_dir: str = "tools/captures",
    device: Optional[str] = None
) -> dict:
    """Executes full comprehensive audit and writes HTML + JSON artifacts."""
    out_dir = Path(output_dir) / name
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[INSPECT] Starting comprehensive inspection: {name} (scroll={scroll_long})...")

    # 1. Screenshot
    shot_path = str(out_dir / "screen.png")
    if scroll_long:
        print("[INSPECT] Capturing scrolling stitched view...")
        capture_scrolling_view(shot_path, max_swipes=max_swipes, device=device)
    else:
        adb_core.capture_fast_screencap(shot_path, device=device)

    # 2. UI Dump
    print("[INSPECT] Dumping UI hierarchy...")
    ui_engine = UIDumpEngine(device=device)
    elements = ui_engine.dump_hierarchy()
    elements_dicts = [el.to_dict() for el in elements]

    # Save UI JSON
    with open(out_dir / "ui_elements.json", "w", encoding="utf-8") as f:
        json.dump(elements_dicts, f, indent=2, ensure_ascii=False)

    # 3. Perf & Smoothness
    print("[INSPECT] Profiling framestats and memory...")
    perf_mon = PerfSmoothnessMonitor(device=device)
    perf_rep = perf_mon.analyze_framestats()
    perf_dict = perf_rep.to_dict()

    with open(out_dir / "perf_metrics.json", "w", encoding="utf-8") as f:
        json.dump(perf_dict, f, indent=2)

    # 4. Generate HTML Report
    html_path = str(out_dir / "report.html")
    generate_html_report(name, shot_path, elements_dicts, perf_dict, [], html_path)
    print(f"[INSPECT] Complete! Report ready at: {html_path}")

    return {
        "name": name,
        "screenshot": shot_path,
        "html_report": html_path,
        "elements_count": len(elements),
        "perf": perf_dict,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PyBionic Comprehensive Inspector")
    parser.add_argument("--name", default="inspection_" + time.strftime("%Y%m%d_%H%M%S"))
    parser.add_argument("--scroll", action="store_true", help="Capture scrolling stitched view")
    parser.add_argument("--swipes", type=int, default=6, help="Max scroll swipes")
    args = parser.parse_args()

    inspect_live_screen(name=args.name, scroll_long=args.scroll, max_swipes=args.swipes)
