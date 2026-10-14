from pathlib import Path

from PIL import Image


def convert_to_bmp(input_path: Path, output_path: Path) -> None:
    """Convert a JPG or PNG image to a 24-bit BMP, preserving its dimensions."""
    with Image.open(input_path) as source:
        if "A" in source.getbands() or "transparency" in source.info:
            rgba_image = source.convert("RGBA")
            background = Image.new("RGBA", rgba_image.size, (0, 0, 0, 255))
            rgb_image = Image.alpha_composite(background, rgba_image).convert("RGB")
        else:
            rgb_image = source.convert("RGB")

        rgb_image.save(output_path, format="BMP")
