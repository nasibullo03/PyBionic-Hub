#!/usr/bin/env python3
"""
tools/ui_dump_engine.py
Instant UI hierarchy dump and semantic element analyzer.
Parses on-screen UI components, state of switches (checked/unchecked),
buttons, texts, and bounding boxes for zero-latency automation without manual coordinate guesswork.
"""

import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent))
import adb_core


@dataclass
class UIElement:
    text: str
    content_desc: str
    resource_id: str
    class_name: str
    bounds: Tuple[int, int, int, int]  # (x1, y1, x2, y2)
    center: Tuple[int, int]  # (cx, cy)
    checked: bool
    enabled: bool
    clickable: bool
    scrollable: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "desc": self.content_desc,
            "id": self.resource_id,
            "class": self.class_name,
            "bounds": list(self.bounds),
            "center": list(self.center),
            "checked": self.checked,
            "enabled": self.enabled,
            "clickable": self.clickable,
            "scrollable": self.scrollable,
        }


class UIDumpEngine:
    """Manages dumping, parsing, querying, and interacting with on-screen UI elements."""

    def __init__(self, device: Optional[str] = None):
        self.device = device
        self.elements: List[UIElement] = []
        self.raw_xml: str = ""

    def dump_hierarchy(self) -> List[UIElement]:
        """Pulls and parses the live UI hierarchy from the device."""
        remote_path = "/data/local/tmp/pybionic_uidump.xml"
        adb_core.run_shell(f"uiautomator dump {remote_path}", device=self.device)
        self.raw_xml = adb_core.run_shell(f"cat {remote_path}", device=self.device)

        self.elements = []
        if not self.raw_xml.strip():
            return []

        try:
            root = ET.fromstring(self.raw_xml)
            for node in root.iter("node"):
                text = node.get("text", "")
                content_desc = node.get("content-desc", "")
                res_id = node.get("resource-id", "")
                cls_name = node.get("class", "").split(".")[-1]
                bounds_str = node.get("bounds", "")
                checked = node.get("checked", "false").lower() == "true"
                enabled = node.get("enabled", "true").lower() == "true"
                clickable = node.get("clickable", "false").lower() == "true"
                scrollable = node.get("scrollable", "false").lower() == "true"

                m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds_str)
                if m:
                    x1, y1, x2, y2 = map(int, m.groups())
                    cx = (x1 + x2) // 2
                    cy = (y1 + y2) // 2
                else:
                    x1 = y1 = x2 = y2 = cx = cy = 0

                # Filter out pure invisible container nodes with no metadata
                if text or content_desc or res_id or clickable or checked or scrollable:
                    self.elements.append(
                        UIElement(
                            text=text,
                            content_desc=content_desc,
                            resource_id=res_id,
                            class_name=cls_name,
                            bounds=(x1, y1, x2, y2),
                            center=(cx, cy),
                            checked=checked,
                            enabled=enabled,
                            clickable=clickable,
                            scrollable=scrollable,
                        )
                    )
        except Exception as e:
            print(f"[UI_ENGINE] Parse error: {e}", file=sys.stderr)

        return self.elements

    def find(self, text: Optional[str] = None, desc: Optional[str] = None, res_id: Optional[str] = None) -> Optional[UIElement]:
        """Finds the first UIElement matching the criteria (case-insensitive substring)."""
        for el in self.elements:
            if text and text.lower() in el.text.lower():
                return el
            if desc and desc.lower() in el.content_desc.lower():
                return el
            if res_id and res_id.lower() in el.resource_id.lower():
                return el
        return None

    def find_all(self, predicate: Callable[[UIElement], bool]) -> List[UIElement]:
        """Returns all elements matching the predicate."""
        return [el for el in self.elements if predicate(el)]

    def get_switches(self) -> List[UIElement]:
        """Finds all toggle switches or checkable controls on the current screen."""
        return [el for el in self.elements if el.class_name in ("Switch", "CheckBox", "RadioButton") or "switch" in el.class_name.lower()]

    def get_all_visible_texts(self) -> List[str]:
        """Returns ordered list of all non-empty textual strings on screen."""
        return [el.text for el in self.elements if el.text.strip()]

    def tap(self, target: Any) -> bool:
        """Taps element, coordinate tuple (x, y), or text string."""
        if isinstance(target, UIElement):
            cx, cy = target.center
        elif isinstance(target, (tuple, list)) and len(target) == 2:
            cx, cy = int(target[0]), int(target[1])
        elif isinstance(target, str):
            el = self.find(text=target, desc=target)
            if not el:
                return False
            cx, cy = el.center
        else:
            return False

        if cx > 0 and cy > 0:
            adb_core.run_shell(f"input tap {cx} {cy}", device=self.device)
            return True
        return False

    def tap_switch_for_label(self, label: str) -> bool:
        """
        Finds a switch horizontally aligned with a given setting label on screen and toggles it.
        """
        label_el = self.find(text=label, desc=label)
        if not label_el:
            return False

        _, ly1, _, ly2 = label_el.bounds
        switches = self.get_switches()

        # Find switch whose vertical bounds intersect or align with label bounds
        for sw in switches:
            _, sy1, _, sy2 = sw.bounds
            if max(ly1, sy1) <= min(ly2, sy2) + 30:  # overlapping or close vertical tolerance
                return self.tap(sw)

        # Fallback: tap right side of label row if switch node not tagged as separate class
        w, _ = adb_core.get_device_resolution(device=self.device)
        return self.tap((w - 80, (ly1 + ly2) // 2))

    def to_json(self) -> str:
        """Serializes current element hierarchy to structured JSON."""
        return json.dumps([el.to_dict() for el in self.elements], ensure_ascii=False, indent=2)


if __name__ == "__main__":
    engine = UIDumpEngine()
    elements = engine.dump_hierarchy()
    print(f"Dumped {len(elements)} elements. Texts:")
    for t in engine.get_all_visible_texts()[:15]:
        print(f"  • {t}")
