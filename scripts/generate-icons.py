#!/usr/bin/env python3
"""
Generate OpenDrop icon set.

Replaces the placeholder "colored dot" icons with a proper app icon
suitable for the system tray, app menu, and notifications.

Design:
- Rounded-square background (matches modern flat icon style).
- White paper-airplane glyph inside (universal "send" / file-share symbol).
- Three radiating arcs above the plane to suggest wireless transmission.
- Two color variants:
    active   — vibrant blue (#0a84ff, matches Apple's SF Blue accent)
    inactive — neutral gray (#8e8e93, system gray)

Outputs to opendrop/gui/resources/:
  - opendrop.png            512x512 master (used by .desktop / app menus)
  - icon_active.png         32x32 tray active
  - icon_inactive.png       32x32 tray inactive
  - hicolor/<size>/apps/    multiple sizes for the freedesktop icon theme

Run from the repo root:
    uv run python3 scripts/generate-icons.py
"""

from __future__ import annotations

from pathlib import Path
from typing import Tuple

from PIL import Image, ImageDraw, ImageFilter

# Colors (RGBA)
ACTIVE_BG = (10, 132, 255, 255)  # SF blue
INACTIVE_BG = (142, 142, 147, 255)  # SF gray
FG = (255, 255, 255, 255)  # opaque white
FG_DIM = (255, 255, 255, 130)  # semi-transparent white for outer arcs


def _rounded_square(size: int, color: Tuple[int, int, int, int]) -> Image.Image:
    """Solid rounded square (~22 % corner radius, modern app-icon style)."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    radius = int(size * 0.22)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=color)
    return img


def _draw_paper_plane(draw: ImageDraw.ImageDraw, size: int, color) -> None:
    """
    Stylized paper airplane, pointing up-right.

    Two triangles sharing an edge — the "fold" — and a tail wedge below.
    Sized to occupy roughly the bottom-right 60 % of the icon to leave room
    for the wireless arcs above.
    """
    s = size
    # Body: top vertex at upper-right, base extends down-left.
    plane = [
        (s * 0.82, s * 0.50),   # nose
        (s * 0.22, s * 0.78),   # tail-bottom
        (s * 0.45, s * 0.66),   # fold-bottom
        (s * 0.22, s * 0.54),   # tail-top
    ]
    draw.polygon(plane, fill=color)

    # Fold line (slight darker tint via outline)
    draw.line(
        [(s * 0.82, s * 0.50), (s * 0.45, s * 0.66)],
        fill=(0, 0, 0, 40),
        width=max(1, int(s * 0.008)),
    )


def _draw_signal_arcs(draw: ImageDraw.ImageDraw, size: int) -> None:
    """
    Three concentric arcs above and to the left of the plane, suggesting
    wireless transmission. The outer arc fades to give a sense of distance.
    """
    s = size
    cx, cy = int(s * 0.22), int(s * 0.50)  # arcs emanate from plane tail
    arcs = [
        (int(s * 0.22), FG, max(2, int(s * 0.045))),
        (int(s * 0.36), FG, max(2, int(s * 0.040))),
        (int(s * 0.50), FG_DIM, max(2, int(s * 0.035))),
    ]
    for radius, color, width in arcs:
        # Arc from -55° to -25° (upper-right quadrant relative to center).
        bbox = (cx - radius, cy - radius, cx + radius, cy + radius)
        draw.arc(bbox, start=-60, end=-10, fill=color, width=width)


def render_icon(size: int, bg: Tuple[int, int, int, int]) -> Image.Image:
    """Render the full composite icon at the given pixel size."""
    img = _rounded_square(size, bg)
    draw = ImageDraw.Draw(img)
    _draw_signal_arcs(draw, size)
    _draw_paper_plane(draw, size, FG)
    return img


def save_icon(img: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, optimize=True)
    print(f"  → {path} ({img.size[0]}×{img.size[1]})")


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    resources = repo_root / "opendrop" / "gui" / "resources"
    hicolor = resources / "hicolor"

    # System tray: small, must read well at 16-24 px. Use 32 as the canonical
    # tray size; modern desktops scale down from there.
    print("System-tray icons (32×32):")
    save_icon(render_icon(32, ACTIVE_BG), resources / "icon_active.png")
    save_icon(render_icon(32, INACTIVE_BG), resources / "icon_inactive.png")

    # App-menu / launcher icons in the standard hicolor sizes.
    print("Application icons (hicolor theme):")
    for sz in (16, 22, 24, 32, 48, 64, 96, 128, 256, 512):
        save_icon(
            render_icon(sz, ACTIVE_BG),
            hicolor / f"{sz}x{sz}" / "apps" / "opendrop.png",
        )

    # Master copy at 512 for packaging / Flatpak / web use.
    save_icon(render_icon(512, ACTIVE_BG), resources / "opendrop.png")

    print()
    print("Done.")


if __name__ == "__main__":
    main()
