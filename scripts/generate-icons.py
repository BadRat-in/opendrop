#!/usr/bin/env python3
"""
Generate OpenDrop system tray icons.

Creates two simple 32x32 PNG icons:
- icon_active.png: Green circle (OWL running)
- icon_inactive.png: Gray circle (OWL stopped)

These are used by the system tray icon in the GUI.
"""

from PIL import Image, ImageDraw
from pathlib import Path

def generate_icon(color: tuple, filename: str) -> None:
    """
    Generate a circular icon with the given color.

    Args:
        color: RGB tuple (r, g, b)
        filename: Output PNG filename
    """
    # Create 32x32 image with transparent background
    img = Image.new('RGBA', (32, 32), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Draw a circle from (4,4) to (28,28) with given color
    draw.ellipse(
        [(4, 4), (28, 28)],
        fill=color + (255,),  # Add alpha channel
        outline=None
    )

    # Save as PNG
    img.save(filename)
    print(f"Generated: {filename}")

def main() -> None:
    """Generate both icon files."""
    icons_dir = Path(__file__).parent.parent / "opendrop" / "gui" / "resources"
    icons_dir.mkdir(parents=True, exist_ok=True)

    # Active icon: bright green
    generate_icon((0, 200, 0), str(icons_dir / "icon_active.png"))

    # Inactive icon: gray
    generate_icon((128, 128, 128), str(icons_dir / "icon_inactive.png"))

    print("\nIcons generated successfully!")

if __name__ == "__main__":
    main()
