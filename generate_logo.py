"""
ILLUMINATI — Clean Symmetrical Mint/Teal Dot-Matrix LED Logo Generator
Generates:
  1. illuminati.png (White silhouette on black background)
  2. illuminati.svg (Transparent background, #33C09E mint/teal LED dots)
"""

from PIL import Image, ImageDraw
import os

# ── Settings ──────────────────────────────────────────────────────────────────
INPUT = "illuminati.png"
OUTPUT = "illuminati.svg"

DOT_SPACING = 6
DOT_RADIUS = 1.7
COLOR = "#33C09E"
BG = "#000000"

# Dimensions: 480 x 480 (80 x 80 dot grid, Center X = 240 is integer column 40)
WIDTH, HEIGHT = 480, 480
CX = 240
STROKE = 8  # >= DOT_SPACING to guarantee continuous dot sampling


def create_silhouette(path: str = INPUT) -> Image.Image:
    """Creates mathematically symmetrical Illuminati Eye of Providence silhouette."""
    img = Image.new("L", (WIDTH, HEIGHT), 0)
    draw = ImageDraw.Draw(img)

    # 1. Outer Pyramid (Triangle)
    apex = (CX, 48)
    foot_l = (72, 318)
    foot_r = (408, 318)

    draw.line([apex, foot_l], fill=255, width=STROKE)
    draw.line([apex, foot_r], fill=255, width=STROKE)

    # Double Base Line
    draw.line([(78, 300), (402, 300)], fill=255, width=STROKE)
    draw.line([(72, 312), (408, 312)], fill=255, width=STROKE)

    # 2. Inner Stepped Cross / Bracket
    # Eye Center = (CX, 180)
    cy = 180

    # Top horizontal bar
    draw.line([(CX - 42, 126), (CX + 42, 126)], fill=255, width=STROKE)
    # Vertical sides down to step
    draw.line([(CX - 42, 126), (CX - 42, 150)], fill=255, width=STROKE)
    draw.line([(CX + 42, 126), (CX + 42, 150)], fill=255, width=STROKE)

    # Horizontal step outwards
    draw.line([(CX - 78, 150), (CX - 42, 150)], fill=255, width=STROKE)
    draw.line([(CX + 42, 150), (CX + 78, 150)], fill=255, width=STROKE)

    # Outer vertical sides
    draw.line([(CX - 78, 150), (CX - 78, 210)], fill=255, width=STROKE)
    draw.line([(CX + 78, 150), (CX + 78, 210)], fill=255, width=STROKE)

    # Horizontal step inwards
    draw.line([(CX - 78, 210), (CX - 42, 210)], fill=255, width=STROKE)
    draw.line([(CX + 42, 210), (CX + 78, 210)], fill=255, width=STROKE)

    # Bottom vertical sides
    draw.line([(CX - 42, 210), (CX - 42, 234)], fill=255, width=STROKE)
    draw.line([(CX + 42, 210), (CX + 42, 234)], fill=255, width=STROKE)

    # Bottom horizontal bar
    draw.line([(CX - 42, 234), (CX + 42, 234)], fill=255, width=STROKE)

    # 3. Eye Features at cy = 180
    # Solid Pupil in center
    draw.ellipse([CX - 12, cy - 12, CX + 12, cy + 12], fill=255)

    # Inner eye brackets around pupil
    draw.arc([CX - 30, cy - 20, CX - 8, cy + 20], 90, 270, fill=255, width=STROKE)
    draw.arc([CX + 8, cy - 20, CX + 30, cy + 20], 270, 90, fill=255, width=STROKE)

    # Flanking Crescents
    draw.arc([CX - 110, cy - 16, CX - 94, cy + 16], 270, 90, fill=255, width=STROKE)
    draw.arc([CX + 94, cy - 16, CX + 110, cy + 16], 90, 270, fill=255, width=STROKE)

    img.save(path)
    print(f"Silhouette created: {path}")
    return img


def generate_svg(input_img: str = INPUT, output_svg: str = OUTPUT, transparent: bool = True):
    """Samples image pixels and generates golden dot-matrix SVG."""
    img = Image.open(input_img).convert("L")
    width, height = img.size

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" fill="none">',
        '  <!-- ILLUMINATI — Golden Dot-Matrix LED Eye of Providence -->'
    ]

    if not transparent:
        svg.append(f'  <rect width="100%" height="100%" fill="{BG}"/>')

    pixels = img.load()
    dots = 0

    for y in range(0, height, DOT_SPACING):
        for x in range(0, width, DOT_SPACING):
            brightness = pixels[x, y]
            if brightness > 40:
                intensity = brightness / 255.0
                radius = DOT_RADIUS * (0.7 + intensity * 0.3)
                opacity = 0.5 + intensity * 0.5
                svg.append(
                    f'  <circle cx="{x}" cy="{y}" r="{radius:.2f}" fill="{COLOR}" opacity="{opacity:.2f}"/>'
                )
                dots += 1

    svg.append("</svg>")

    with open(output_svg, "w", encoding="utf-8") as f:
        f.write("\n".join(svg))

    print(f"Logo created: {output_svg} ({dots} golden dots)")
    return dots


if __name__ == "__main__":
    create_silhouette(INPUT)
    generate_svg(INPUT, OUTPUT, transparent=True)
