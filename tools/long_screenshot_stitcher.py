#!/usr/bin/env python3
"""
tools/long_screenshot_stitcher.py
High-velocity scrolling screenshot capture and seamless image stitcher.
Captures continuous scrollable views (e.g. 92 cards in SettingsScreen, logs, editor)
and merges them into a single high-resolution panoramic full-page PNG.
"""

import io
import math
import os
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple
from PIL import Image

# Import local adb core
sys.path.insert(0, str(Path(__file__).parent))
import adb_core


def find_vertical_overlap(img_top: Image.Image, img_bottom: Image.Image, search_range_ratio: float = 0.6) -> int:
    """
    Finds vertical overlap height between img_top and img_bottom in pixels.
    Uses fast grayscale line sampling for sub-millisecond alignment.
    """
    w, h = img_top.size
    gray_top = img_top.convert("L")
    gray_bot = img_bottom.convert("L")

    max_search = int(h * search_range_ratio)
    min_search = int(h * 0.1)

    # Sample central vertical strip to avoid scrollbars on the right edge
    x_start = int(w * 0.15)
    x_end = int(w * 0.85)

    best_overlap = 0
    best_diff = float("inf")

    # Sample every 2 pixels vertically for speed
    for overlap in range(min_search, max_search, 2):
        top_crop = gray_top.crop((x_start, h - overlap, x_end, h))
        bot_crop = gray_bot.crop((x_start, 0, x_end, overlap))

        # Sample 5 horizontal rows within the overlapping slice
        sample_step = max(1, overlap // 5)
        total_diff = 0
        pixels_sampled = 0

        for y in range(0, overlap, sample_step):
            row_top = [top_crop.getpixel((x, y)) for x in range(0, top_crop.width, 10)]
            row_bot = [bot_crop.getpixel((x, y)) for x in range(0, bot_crop.width, 10)]
            for p1, p2 in zip(row_top, row_bot):
                total_diff += abs(p1 - p2)
                pixels_sampled += 1

        avg_diff = total_diff / max(1, pixels_sampled)
        if avg_diff < best_diff:
            best_diff = avg_diff
            best_overlap = overlap

    # If match difference is small enough, return overlap
    if best_diff < 15.0:
        return best_overlap
    return 0


def stitch_images_vertically(images: List[Image.Image]) -> Image.Image:
    """Stitches a sequence of overlapping screenshots into a single continuous tall image."""
    if not images:
        raise ValueError("No images provided for stitching")
    if len(images) == 1:
        return images[0]

    stitched = images[0]
    for i in range(1, len(images)):
        curr = images[i]
        overlap = find_vertical_overlap(stitched, curr)

        # If overlap found, crop duplicate top portion of curr
        if overlap > 0:
            crop_top = curr.crop((0, overlap, curr.width, curr.height))
            new_w = max(stitched.width, crop_top.width)
            new_h = stitched.height + crop_top.height
            merged = Image.new("RGBA", (new_w, new_h))
            merged.paste(stitched, (0, 0))
            merged.paste(crop_top, (0, stitched.height))
            stitched = merged
        else:
            # Fallback direct stack if overlap couldn't be determined
            new_w = max(stitched.width, curr.width)
            new_h = stitched.height + curr.height
            merged = Image.new("RGBA", (new_w, new_h))
            merged.paste(stitched, (0, 0))
            merged.paste(curr, (0, stitched.height))
            stitched = merged

    return stitched


def create_contact_sheet(images: List[Image.Image], cols: int = 4, max_thumb_w: int = 240) -> Image.Image:
    """Creates a multi-column contact sheet / grid overview of all captured step screenshots."""
    if not images:
        raise ValueError("No images provided")

    thumbs = []
    for img in images:
        ratio = max_thumb_w / float(img.width)
        thumb_h = int(img.height * ratio)
        thumbs.append(img.resize((max_thumb_w, thumb_h), Image.Resampling.LANCZOS))

    rows = math.ceil(len(thumbs) / cols)
    thumb_w = max_thumb_w
    thumb_h = thumbs[0].height

    sheet_w = cols * (thumb_w + 10) + 10
    sheet_h = rows * (thumb_h + 10) + 10
    sheet = Image.new("RGBA", (sheet_w, sheet_h), (20, 24, 30, 255))

    for idx, thumb in enumerate(thumbs):
        c = idx % cols
        r = idx // cols
        x = 10 + c * (thumb_w + 10)
        y = 10 + r * (thumb_h + 10)
        sheet.paste(thumb, (x, y))

    return sheet


def capture_scrolling_view(
    output_png: str,
    max_swipes: int = 8,
    swipe_ratio: float = 0.55,
    swipe_speed_ms: int = 450,
    save_individual: bool = True,
    device: Optional[str] = None
) -> Tuple[str, List[str]]:
    """
    Automates scrolling down a view, taking screencaps, and creating a stitched full-page PNG.
    Returns (stitched_path, list_of_step_paths).
    """
    out_path = Path(output_png)
    out_dir = out_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    base_name = out_path.stem

    w, h = adb_core.get_device_resolution(device=device)
    center_x = w // 2
    # Start swipe from lower-middle to upper-middle to scroll content UP (view down)
    start_y = int(h * 0.75)
    end_y = int(start_y - (h * swipe_ratio))

    captured_images: List[Image.Image] = []
    step_paths: List[str] = []

    for step in range(1, max_swipes + 1):
        step_file = out_dir / f"{base_name}_step{step}.png"
        ok = adb_core.capture_fast_screencap(str(step_file), device=device)
        if not ok:
            print(f"[STITCHER] Failed screencap at step {step}", file=sys.stderr)
            break

        img = Image.open(step_file)
        # Check if identical to previous frame (hit bottom of scroll)
        if captured_images:
            overlap = find_vertical_overlap(captured_images[-1], img)
            # If 100% or nearly 100% overlap, we reached the bottom!
            if overlap >= (img.height * 0.95):
                print(f"[STITCHER] Bottom of scroll reached at step {step}.")
                if not save_individual:
                    step_file.unlink(missing_ok=True)
                break

        captured_images.append(img)
        step_paths.append(str(step_file))

        if not save_individual and len(step_paths) > 1:
            # remove old step file
            Path(step_paths[-2]).unlink(missing_ok=True)

        if step < max_swipes:
            # Perform scroll swipe
            adb_core.run_shell(f"input swipe {center_x} {start_y} {center_x} {end_y} {swipe_speed_ms}", device=device)
            # Short wait for momentum scroll animation to settle
            time.sleep(0.35)

    if not captured_images:
        return "", []

    print(f"[STITCHER] Stitching {len(captured_images)} frames...")
    stitched = stitch_images_vertically(captured_images)
    stitched.save(str(out_path), "PNG")
    print(f"[STITCHER] Saved long stitched screenshot: {out_path} ({stitched.width}x{stitched.height})")

    # Also save contact sheet overview
    contact_path = out_dir / f"{base_name}_overview.png"
    contact = create_contact_sheet(captured_images)
    contact.save(str(contact_path), "PNG")
    print(f"[STITCHER] Saved contact sheet overview: {contact_path}")

    return str(out_path), step_paths


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python long_screenshot_stitcher.py <output_stitched.png> [max_swipes]")
        sys.exit(1)
    out_file = sys.argv[1]
    swipes = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    capture_scrolling_view(out_file, max_swipes=swipes)
