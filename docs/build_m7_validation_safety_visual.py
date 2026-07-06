"""Build a concise, high-resolution M7 validation safety visual."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
OUT_PNG = ROOT / "m7_validation_safety_results_redesign.png"
OUT_SVG = ROOT / "m7_validation_safety_results_redesign.svg"

WIDTH = 2400
HEIGHT = 1450

FONT_REGULAR = Path("/System/Library/Fonts/Supplemental/Arial.ttf")
FONT_BOLD = Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf")

INK = "#17221d"
MUTED = "#5f6b63"
BG = "#f5faf7"
WHITE = "#ffffff"
LINE = "#dbe7df"
GREEN = "#1f9854"
GREEN_DARK = "#0b4f2a"
GREEN_SOFT = "#e6f6ec"
BLUE = "#2f72c9"
BLUE_SOFT = "#eaf2ff"
AMBER = "#cf8112"
RED = "#cf3f3f"
GRAY = "#93a0a8"
GRAY_SOFT = "#eef2f3"


@dataclass(frozen=True)
class CityRow:
    city: str
    candidates: int
    verified: int
    review: int
    rejected: int
    not_used: int
    precision: str


METRICS = [
    ("Precision", "1.00"),
    ("False verified", "0"),
    ("False approvals", "0"),
    ("Source failures", "0"),
]

CITY_ROWS = [
    CityRow("Burnaby R1", 144, 87, 57, 0, 0, "1.00"),
    CityRow("Calgary R-CG", 150, 29, 42, 27, 52, "1.00"),
    CityRow("Vancouver RS", 56, 10, 31, 15, 0, "1.00"),
]


def font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = FONT_BOLD if bold else FONT_REGULAR
    return ImageFont.truetype(str(path), size=size)


def text_size(draw: ImageDraw.ImageDraw, text: str, text_font: ImageFont.FreeTypeFont) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=text_font)
    return box[2] - box[0], box[3] - box[1]


def rounded_rect(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    radius: int,
    fill: str,
    outline: str | None = None,
    width: int = 1,
) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def soft_shadow(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], radius: int = 30) -> None:
    x1, y1, x2, y2 = box
    draw.rounded_rectangle((x1, y1 + 10, x2, y2 + 10), radius=radius, fill=(183, 196, 187, 42))


def draw_check(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int) -> None:
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=GREEN)
    draw.line((cx - 20, cy, cx - 7, cy + 14, cx + 23, cy - 19), fill=WHITE, width=10, joint="curve")


def draw_header(draw: ImageDraw.ImageDraw) -> None:
    draw.text((120, 96), "M7 Safety Check", font=font(82, bold=True), fill=INK)
    draw.text((124, 188), "AI suggests rules. Verification proves them. GIS exports only verified rules.", font=font(36), fill=MUTED)

    soft_shadow(draw, (1660, 82, 2280, 218), 34)
    rounded_rect(draw, (1660, 82, 2280, 218), 34, GREEN_SOFT, GREEN, 4)
    draw_check(draw, 1734, 150, 42)
    draw.text((1805, 130), "PASSED", font=font(50, bold=True), fill=GREEN_DARK)
    draw.text((1808, 178), "0 false approvals", font=font(30, bold=True), fill=INK)


def draw_metrics(draw: ImageDraw.ImageDraw) -> None:
    x0 = 120
    y = 292
    w = 510
    h = 190
    gap = 34
    for index, (label, value) in enumerate(METRICS):
        x = x0 + index * (w + gap)
        soft_shadow(draw, (x, y, x + w, y + h), 26)
        rounded_rect(draw, (x, y, x + w, y + h), 26, WHITE, LINE, 2)
        draw.text((x + 36, y + 45), label, font=font(31, bold=True), fill=GREEN_DARK)
        draw.text((x + 36, y + 100), value, font=font(74, bold=True), fill=GREEN)


def draw_arrow(draw: ImageDraw.ImageDraw, x1: int, y: int, x2: int) -> None:
    draw.line((x1, y, x2, y), fill=GREEN, width=7)
    draw.polygon([(x2, y), (x2 - 26, y - 17), (x2 - 26, y + 17)], fill=GREEN)


def draw_flow_step(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    w: int,
    title: str,
    caption: str,
    fill: str,
    outline: str,
    number: str,
) -> None:
    rounded_rect(draw, (x, y, x + w, y + 175), 28, fill, outline, 4)
    draw.ellipse((x + 36, y + 44, x + 92, y + 100), fill=outline)
    draw.text((x + 64, y + 81), number, font=font(28, bold=True), fill=WHITE, anchor="mm")
    draw.text((x + 120, y + 63), title, font=font(39, bold=True), fill=INK)
    draw.text((x + 120, y + 112), caption, font=font(28), fill=MUTED)


def draw_flow(draw: ImageDraw.ImageDraw) -> None:
    y = 560
    w = 610
    draw_flow_step(draw, 120, y, w, "Extract", "candidate rules", BLUE_SOFT, BLUE, "1")
    draw_arrow(draw, 760, y + 88, 835)
    draw_flow_step(draw, 870, y, w, "Verify", "source proof required", GREEN_SOFT, GREEN, "2")
    draw_arrow(draw, 1510, y + 88, 1585)
    draw_flow_step(draw, 1620, y, w, "Export", "verified rules only", GRAY_SOFT, INK, "3")


def draw_legend(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    items = [(GREEN, "Verified"), (AMBER, "Review"), (RED, "Rejected"), (GRAY, "Not used")]
    cursor = x
    for color, label in items:
        rounded_rect(draw, (cursor, y + 5, cursor + 30, y + 35), 7, color)
        draw.text((cursor + 42, y), label, font=font(27, bold=True), fill=MUTED)
        cursor += 42 + text_size(draw, label, font(27, bold=True))[0] + 44


def draw_segmented_bar(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    width: int,
    height: int,
    row: CityRow,
) -> None:
    rounded_rect(draw, (x, y, x + width, y + height), 18, "#edf2ef")
    segments = [
        (row.verified, GREEN),
        (row.review, AMBER),
        (row.rejected, RED),
        (row.not_used, GRAY),
    ]
    cursor = x
    remaining = width
    active_segments = [(count, color) for count, color in segments if count > 0]
    for index, (count, color) in enumerate(active_segments):
        seg_w = remaining if index == len(active_segments) - 1 else round(width * count / row.candidates)
        draw.rectangle((cursor, y, cursor + seg_w, y + height), fill=color)
        if seg_w >= 72:
            text = str(count)
            tw, th = text_size(draw, text, font(26, bold=True))
            draw.text((cursor + seg_w / 2 - tw / 2, y + height / 2 - th / 2 - 2), text, font=font(26, bold=True), fill=WHITE)
        cursor += seg_w
        remaining = x + width - cursor
    draw.rounded_rectangle((x, y, x + width, y + height), radius=18, outline="#d6dfda", width=2)


def draw_city_results(draw: ImageDraw.ImageDraw) -> None:
    x = 120
    y = 805
    w = 2160
    h = 470
    soft_shadow(draw, (x, y, x + w, y + h), 30)
    rounded_rect(draw, (x, y, x + w, y + h), 30, WHITE, LINE, 2)

    draw.text((x + 42, y + 58), "Per-city outcome", font=font(48, bold=True), fill=INK)
    draw_legend(draw, x + 600, y + 62)

    header_y = y + 128
    draw.text((x + 42, header_y), "City", font=font(26, bold=True), fill=MUTED)
    draw.text((x + 400, header_y), "Candidates", font=font(26, bold=True), fill=MUTED)
    draw.text((x + 635, header_y), "Split", font=font(26, bold=True), fill=MUTED)
    draw.text((x + 1845, header_y), "Precision", font=font(26, bold=True), fill=MUTED)
    draw.line((x + 40, header_y + 42, x + w - 40, header_y + 42), fill=LINE, width=2)

    row_y = y + 190
    for row in CITY_ROWS:
        draw.text((x + 42, row_y + 10), row.city, font=font(34, bold=True), fill=INK)
        draw.text((x + 430, row_y + 10), str(row.candidates), font=font(34, bold=True), fill=INK)
        draw_segmented_bar(draw, x + 635, row_y + 3, 1080, 56, row)
        rounded_rect(draw, (x + 1845, row_y, x + 1992, row_y + 62), 20, GREEN_SOFT, GREEN, 2)
        draw.text((x + 1880, row_y + 13), row.precision, font=font(32, bold=True), fill=GREEN_DARK)
        row_y += 80


def draw_footer(draw: ImageDraw.ImageDraw) -> None:
    draw.text((120, 1360), "Uncertain rule -> review. Uncertain proposal -> needs_review.", font=font(30, bold=True), fill=GREEN_DARK)


def build_png() -> None:
    image = Image.new("RGBA", (WIDTH, HEIGHT), WHITE)
    draw = ImageDraw.Draw(image)
    rounded_rect(draw, (44, 44, WIDTH - 44, HEIGHT - 44), 42, BG)
    rounded_rect(draw, (76, 66, WIDTH - 76, HEIGHT - 72), 34, WHITE, LINE, 2)
    draw_header(draw)
    draw_metrics(draw)
    draw_flow(draw)
    draw_city_results(draw)
    draw_footer(draw)
    image.convert("RGB").save(OUT_PNG, quality=95)


class Svg:
    def __init__(self) -> None:
        self.parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
            "<defs>",
            '<filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">',
            '<feDropShadow dx="0" dy="8" stdDeviation="7" flood-color="#b7c4bb" flood-opacity="0.35"/>',
            "</filter>",
            "</defs>",
        ]

    def rect(self, x: int, y: int, w: int, h: int, fill: str, stroke: str | None = None, rx: int = 0, sw: int = 1, shadow: bool = False) -> None:
        attrs = [f'x="{x}"', f'y="{y}"', f'width="{w}"', f'height="{h}"', f'rx="{rx}"', f'fill="{fill}"']
        if stroke:
            attrs.extend([f'stroke="{stroke}"', f'stroke-width="{sw}"'])
        if shadow:
            attrs.append('filter="url(#shadow)"')
        self.parts.append(f"<rect {' '.join(attrs)}/>")

    def circle(self, cx: int, cy: int, r: int, fill: str) -> None:
        self.parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}"/>')

    def line(self, x1: int, y1: int, x2: int, y2: int, stroke: str, sw: int = 2) -> None:
        self.parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round"/>')

    def text(self, x: int, y: int, value: str, size: int, fill: str = INK, weight: int = 400) -> None:
        self.parts.append(
            f'<text x="{x}" y="{y}" font-family="Arial, Helvetica, sans-serif" '
            f'font-size="{size}" font-weight="{weight}" fill="{fill}">{escape(value)}</text>'
        )

    def finish(self) -> str:
        self.parts.append("</svg>")
        return "\n".join(self.parts)


def svg_metric(svg: Svg, x: int, y: int, label: str, value: str) -> None:
    svg.rect(x, y, 510, 190, WHITE, LINE, 26, 2, True)
    svg.text(x + 36, y + 78, label, 31, GREEN_DARK, 700)
    svg.text(x + 36, y + 162, value, 74, GREEN, 700)


def svg_step(svg: Svg, x: int, y: int, w: int, title: str, caption: str, fill: str, outline: str, number: str) -> None:
    svg.rect(x, y, w, 175, fill, outline, 28, 4)
    svg.circle(x + 64, y + 72, 28, outline)
    svg.text(x + 55, y + 83, number, 28, WHITE, 700)
    svg.text(x + 120, y + 82, title, 39, INK, 700)
    svg.text(x + 120, y + 134, caption, 28, MUTED)


def svg_bar(svg: Svg, x: int, y: int, width: int, height: int, row: CityRow) -> None:
    cursor = x
    active = [(row.verified, GREEN), (row.review, AMBER), (row.rejected, RED), (row.not_used, GRAY)]
    active = [(count, color) for count, color in active if count > 0]
    remaining = width
    for index, (count, color) in enumerate(active):
        seg_w = remaining if index == len(active) - 1 else round(width * count / row.candidates)
        svg.rect(cursor, y, seg_w, height, color)
        if seg_w >= 72:
            svg.text(cursor + seg_w // 2 - 14, y + 38, str(count), 26, WHITE, 700)
        cursor += seg_w
        remaining = x + width - cursor
    svg.rect(x, y, width, height, "none", "#d6dfda", 18, 2)


def build_svg() -> None:
    svg = Svg()
    svg.rect(44, 44, WIDTH - 88, HEIGHT - 88, BG, None, 42)
    svg.rect(76, 66, WIDTH - 152, HEIGHT - 138, WHITE, LINE, 34, 2)
    svg.text(120, 174, "M7 Safety Check", 82, INK, 700)
    svg.text(124, 230, "AI suggests rules. Verification proves them. GIS exports only verified rules.", 36, MUTED)
    svg.rect(1660, 82, 620, 136, GREEN_SOFT, GREEN, 34, 4, True)
    svg.circle(1734, 150, 42, GREEN)
    svg.line(1714, 150, 1727, 164, WHITE, 10)
    svg.line(1727, 164, 1757, 131, WHITE, 10)
    svg.text(1805, 166, "PASSED", 50, GREEN_DARK, 700)
    svg.text(1808, 202, "0 false approvals", 30, INK, 700)
    for index, (label, value) in enumerate(METRICS):
        svg_metric(svg, 120 + index * (510 + 34), 292, label, value)

    svg_step(svg, 120, 560, 610, "Extract", "candidate rules", BLUE_SOFT, BLUE, "1")
    svg.line(760, 648, 835, 648, GREEN, 7)
    svg.parts.append(f'<polygon points="835,648 809,631 809,665" fill="{GREEN}"/>')
    svg_step(svg, 870, 560, 610, "Verify", "source proof required", GREEN_SOFT, GREEN, "2")
    svg.line(1510, 648, 1585, 648, GREEN, 7)
    svg.parts.append(f'<polygon points="1585,648 1559,631 1559,665" fill="{GREEN}"/>')
    svg_step(svg, 1620, 560, 610, "Export", "verified rules only", GRAY_SOFT, INK, "3")

    svg.rect(120, 805, 2160, 470, WHITE, LINE, 30, 2, True)
    svg.text(162, 863, "Per-city outcome", 48, INK, 700)
    legend_x = 720
    for color, label in ((GREEN, "Verified"), (AMBER, "Review"), (RED, "Rejected"), (GRAY, "Not used")):
        svg.rect(legend_x, 832, 30, 30, color, None, 7)
        svg.text(legend_x + 42, 861, label, 27, MUTED, 700)
        legend_x += 42 + len(label) * 17 + 44
    svg.text(162, 933, "City", 26, MUTED, 700)
    svg.text(520, 933, "Candidates", 26, MUTED, 700)
    svg.text(755, 933, "Split", 26, MUTED, 700)
    svg.text(1965, 933, "Precision", 26, MUTED, 700)
    svg.line(160, 975, 2240, 975, LINE, 2)

    y = 995
    for row in CITY_ROWS:
        svg.text(162, y + 43, row.city, 34, INK, 700)
        svg.text(550, y + 43, str(row.candidates), 34, INK, 700)
        svg_bar(svg, 755, y + 3, 1080, 56, row)
        svg.rect(1965, y, 147, 62, GREEN_SOFT, GREEN, 20, 2)
        svg.text(2000, y + 42, row.precision, 32, GREEN_DARK, 700)
        y += 80
    svg.text(120, 1394, "Uncertain rule -> review. Uncertain proposal -> needs_review.", 30, GREEN_DARK, 700)
    OUT_SVG.write_text(svg.finish(), encoding="utf-8")


def main() -> None:
    build_png()
    build_svg()
    print(f"Wrote {OUT_PNG}")
    print(f"Wrote {OUT_SVG}")


if __name__ == "__main__":
    main()
