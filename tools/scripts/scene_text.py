#!/usr/bin/env python3
"""Compose exact Arabic copy onto a planned in-scene surface.

The image model draws an empty prop.  This module renders shaped Arabic onto a
transparent patch, projects it into the reviewed quadrilateral, and preserves
the raw image separately from the composited deliverable.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from textlayout import resolve_arabic_font, shape_arabic


class SceneTextError(RuntimeError):
    pass


TREATMENTS: dict[str, tuple[int, int, int, int]] = {
    "printed-ink": (30, 35, 38, 238),
    "chalk": (244, 239, 219, 232),
    "painted": (38, 48, 48, 235),
    "engraved": (76, 52, 35, 218),
    "stitched": (58, 43, 48, 235),
}


def _point(value: Any, label: str) -> tuple[float, float]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) != 2:
        raise SceneTextError(f"{label} must be [x, y]")
    try:
        x, y = float(value[0]), float(value[1])
    except (TypeError, ValueError) as exc:
        raise SceneTextError(f"{label} coordinates must be numbers") from exc
    if not (0 <= x <= 1 and 0 <= y <= 1):
        raise SceneTextError(f"{label} must use normalized 0..1 coordinates")
    return x, y


def validate_quad(value: Any) -> tuple[tuple[float, float], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) != 4:
        raise SceneTextError("resolvedQuad must contain [top-left, top-right, bottom-right, bottom-left]")
    points = tuple(_point(item, f"resolvedQuad[{index}]") for index, item in enumerate(value))
    area = 0.0
    for index, (x1, y1) in enumerate(points):
        x2, y2 = points[(index + 1) % 4]
        area += x1 * y2 - x2 * y1
    if abs(area) / 2 < 0.035:
        raise SceneTextError("resolvedQuad is too small for readable story text")
    signs: list[float] = []
    for index in range(4):
        a = points[index]
        b = points[(index + 1) % 4]
        c = points[(index + 2) % 4]
        signs.append((b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]))
    if not (all(value > 0 for value in signs) or all(value < 0 for value in signs)):
        raise SceneTextError("resolvedQuad must be convex and ordered around the surface")
    return points


def rect_quad(region: Mapping[str, Any]) -> list[list[float]]:
    try:
        x = float(region["x"])
        y = float(region["y"])
        width = float(region["width"])
        height = float(region["height"])
    except (KeyError, TypeError, ValueError) as exc:
        raise SceneTextError("plannedRegion requires x, y, width, height") from exc
    return [[x, y], [x + width, y], [x + width, y + height], [x, y + height]]


def _solve(matrix: list[list[float]], values: list[float]) -> list[float]:
    size = len(values)
    augmented = [row[:] + [values[index]] for index, row in enumerate(matrix)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) < 1e-10:
            raise SceneTextError("resolvedQuad perspective transform is singular")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        divisor = augmented[column][column]
        augmented[column] = [value / divisor for value in augmented[column]]
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            augmented[row] = [
                augmented[row][item] - factor * augmented[column][item]
                for item in range(size + 1)
            ]
    return [augmented[index][-1] for index in range(size)]


def _perspective_coefficients(
    output_points: Sequence[tuple[float, float]],
    source_points: Sequence[tuple[float, float]],
) -> list[float]:
    matrix: list[list[float]] = []
    values: list[float] = []
    for (x, y), (u, v) in zip(output_points, source_points):
        matrix.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        values.append(u)
        matrix.append([0, 0, 0, x, y, 1, -v * x, -v * y])
        values.append(v)
    return _solve(matrix, values)


def _wrap_logical(
    text: str,
    font: Any,
    draw: Any,
    max_width: int,
    max_lines: int,
) -> list[str] | None:
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join([*current, word])
        shaped = shape_arabic(candidate)
        bbox = draw.textbbox((0, 0), shaped, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current.append(word)
            continue
        if not current:
            return None
        lines.append(" ".join(current))
        current = [word]
    if current:
        lines.append(" ".join(current))
    if len(lines) > max_lines:
        return None
    return lines


def compose_scene_text(
    source: Path,
    destination: Path,
    *,
    text: str,
    integration: Mapping[str, Any],
    settings: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise SceneTextError("Pillow is required for scene-text composition") from exc
    if not text.strip():
        raise SceneTextError("Story text is empty")
    quad_value = integration.get("resolvedQuad")
    if quad_value is None:
        raise SceneTextError("Surface review must set resolvedQuad before composition")
    quad = validate_quad(quad_value)
    with Image.open(source) as opened:
        base = opened.convert("RGBA")
    width, height = base.size
    pixel_quad = tuple((x * width, y * height) for x, y in quad)
    top_width = math.dist(pixel_quad[0], pixel_quad[1])
    bottom_width = math.dist(pixel_quad[3], pixel_quad[2])
    left_height = math.dist(pixel_quad[0], pixel_quad[3])
    right_height = math.dist(pixel_quad[1], pixel_quad[2])
    patch_width = max(64, round(max(top_width, bottom_width)))
    patch_height = max(64, round(max(left_height, right_height)))
    patch = Image.new("RGBA", (patch_width, patch_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(patch)
    font_path = resolve_arabic_font(dict(settings or {}))
    minimum_pt = float(integration.get("minimumFontPt") or 12)
    minimum_px = max(12, round(minimum_pt * width / 842.0))
    max_lines = int(integration.get("maxLines") or 5)
    padding_x = max(10, round(patch_width * 0.08))
    padding_y = max(10, round(patch_height * 0.08))
    usable_width = patch_width - 2 * padding_x
    usable_height = patch_height - 2 * padding_y
    chosen_font = None
    logical_lines: list[str] | None = None
    line_height = 0
    for font_px in range(max(minimum_px, round(patch_height * 0.24)), minimum_px - 1, -1):
        font = ImageFont.truetype(str(font_path), font_px)
        lines = _wrap_logical(text, font, draw, usable_width, max_lines)
        if not lines:
            continue
        bbox = draw.textbbox((0, 0), "ابتج", font=font)
        candidate_height = max(1, bbox[3] - bbox[1])
        leading = round(candidate_height * 1.45)
        if leading * len(lines) <= usable_height:
            chosen_font = font
            logical_lines = lines
            line_height = leading
            break
    if chosen_font is None or logical_lines is None:
        raise SceneTextError(
            f"Full Arabic copy does not fit the reviewed surface at {minimum_pt:g}pt; "
            "regenerate with a larger carrier"
        )
    treatment = str(integration.get("treatment") or "printed-ink")
    fill = TREATMENTS.get(treatment, TREATMENTS["printed-ink"])
    total_height = line_height * len(logical_lines)
    y = padding_y + max(0, (usable_height - total_height) // 2)
    for logical in logical_lines:
        shaped = shape_arabic(logical)
        bbox = draw.textbbox((0, 0), shaped, font=chosen_font)
        line_width = bbox[2] - bbox[0]
        x = patch_width - padding_x - line_width
        if treatment == "chalk":
            draw.text((x + 1, y + 1), shaped, font=chosen_font, fill=(255, 255, 255, 42))
        elif treatment in {"engraved", "stitched"}:
            draw.text((x + 1, y + 1), shaped, font=chosen_font, fill=(255, 255, 255, 55))
        draw.text((x, y), shaped, font=chosen_font, fill=fill)
        y += line_height
    source_points = (
        (0.0, 0.0),
        (float(patch_width), 0.0),
        (float(patch_width), float(patch_height)),
        (0.0, float(patch_height)),
    )
    coeffs = _perspective_coefficients(pixel_quad, source_points)
    warped = patch.transform(
        (width, height),
        Image.Transform.PERSPECTIVE,
        coeffs,
        resample=Image.Resampling.BICUBIC,
    )
    composed = Image.alpha_composite(base, warped).convert("RGB")
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp = destination.with_name(f".{destination.name}.tmp")
    composed.save(tmp, format="PNG", optimize=True)
    tmp.replace(destination)
    return {
        "source": str(source),
        "destination": str(destination),
        "width": width,
        "height": height,
        "font": str(font_path),
        "fontPx": chosen_font.size,
        "lineCount": len(logical_lines),
        "text": text,
        "resolvedQuad": [list(point) for point in quad],
        "treatment": treatment,
    }

