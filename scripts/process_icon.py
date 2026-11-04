#!/usr/bin/env python3
"""Turn a flat artwork PNG into a 156x156 theme icon.

Two common source shapes are supported:

  * opaque white background  -> alpha is derived from darkness
                                 (alpha = 255 - min(RGB))
  * transparent background   -> the existing alpha channel is used as-is

The artwork is cropped to its visible bounds, scaled to fit inside the inner
area, and centered on a rounded-square template (for example the iconback
image shipped by an icon pack). Without --template the artwork is centered on
a transparent square instead.

Example:
    py scripts/process_icon.py --input art.png --output out.png \\
        --template iconback1.png --inner 120
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import numpy as np
    from PIL import Image
except ImportError:  # pragma: no cover
    sys.exit("Pillow and numpy are required: py -m pip install pillow numpy")


def extract_artwork(im: Image.Image) -> Image.Image:
    im = im.convert("RGBA")
    arr = np.asarray(im)
    if arr[:, :, 3].min() < 250:
        art = im.crop(im.getbbox())
    else:
        luminance = arr[:, :, :3].min(axis=2)
        alpha = (255 - luminance).clip(0, 255).astype("uint8")
        art = Image.new("RGBA", im.size, (0, 0, 0, 0))
        art.putalpha(Image.fromarray(alpha))
        art = art.crop(art.getbbox())
    if art.width == 0 or art.height == 0:
        raise SystemExit("input image contains no visible artwork")
    return art


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--template", type=Path, help="rounded-square PNG to paste onto")
    ap.add_argument("--size", type=int, default=156)
    ap.add_argument("--inner", type=int, default=120, help="max artwork size inside the icon")
    args = ap.parse_args()

    art = extract_artwork(Image.open(args.input))
    scale = min(args.inner / art.width, args.inner / art.height)
    resample = getattr(Image, "Resampling", Image).LANCZOS
    art = art.resize(
        (max(1, round(art.width * scale)), max(1, round(art.height * scale))),
        resample,
    )

    if args.template:
        canvas = Image.open(args.template).convert("RGBA")
        if canvas.size != (args.size, args.size):
            canvas = canvas.resize((args.size, args.size), resample)
    else:
        canvas = Image.new("RGBA", (args.size, args.size), (0, 0, 0, 0))

    pos = ((args.size - art.width) // 2, (args.size - art.height) // 2)
    canvas.alpha_composite(art, pos)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(args.output)
    print(f"wrote {args.output} ({canvas.width}x{canvas.height})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
