"""PDF + QGIS control points → overlay PNG + 4 corner coordinates (PLAN.md §6 step 5, §11 M5).

How it works
------------
1. The map PDF page is rendered at ``RENDER_DPI`` (150, the same default GDAL/QGIS use when a
   PDF is opened directly, so points placed on either image line up).
2. The control points from the QGIS Georeferencer ``.points`` file are converted to Web
   Mercator (EPSG:3857) and an affine transform pixel → metres is fitted by least squares.
3. MapLibre draws an ``ImageSource`` by mapping the image onto the 4 corner coordinates in Web
   Mercator using two triangles, which reproduces an affine transform exactly. So no warping is
   needed: we keep the rendered image (downscaled, white made transparent) and publish the four
   transformed corners.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from opennaksha.models import Overlay

RENDER_DPI = 150
MAX_SIDE = 4096
EARTH_RADIUS = 6378137.0
WHITE_THRESHOLD = 235

Image.MAX_IMAGE_PIXELS = None  # TP map PDFs render to very large images on purpose


class GeorefError(Exception):
    pass


@dataclass(frozen=True)
class ControlPoint:
    map_x: float
    map_y: float
    pixel_x: float
    pixel_y: float


@dataclass(frozen=True)
class PointsFile:
    crs: str  # "EPSG:4326" or "EPSG:3857"
    points: list[ControlPoint]


@dataclass(frozen=True)
class Fit:
    matrix: np.ndarray  # 2x3, pixel (col, row, 1) → mercator (x, y)
    rms_m: float
    n_points: int


def parse_points(text: str) -> PointsFile:
    """Parse a QGIS Georeferencer .points file.

    Format: optional ``#CRS: <wkt>`` line, a header ``mapX,mapY,sourceX,sourceY,enable,...``,
    then one row per point. For an un-georeferenced image QGIS stores ``sourceY`` as a negative
    pixel row.
    """
    crs = "EPSG:4326"
    points: list[ControlPoint] = []
    header: list[str] | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            if line.upper().startswith("#CRS"):
                crs = _detect_crs(line)
            continue
        cols = [c.strip() for c in line.split(",")]
        if header is None and cols[0].lower() == "mapx":
            header = [c.lower() for c in cols]
            continue
        h = header or ["mapx", "mapy", "sourcex", "sourcey", "enable"]
        row = dict(zip(h, cols, strict=False))
        if row.get("enable", "1") in ("0", "false"):
            continue
        try:
            points.append(
                ControlPoint(
                    map_x=float(row["mapx"]),
                    map_y=float(row["mapy"]),
                    pixel_x=float(row["sourcex"]),
                    pixel_y=abs(float(row["sourcey"])),
                )
            )
        except (KeyError, ValueError) as e:
            raise GeorefError(f"bad control point row: {raw!r}") from e
    return PointsFile(crs=crs, points=points)


def _detect_crs(line: str) -> str:
    up = line.upper()
    # The outermost EPSG id in WKT2 (ID["EPSG",n]) / WKT1 (AUTHORITY["EPSG","n"]) is the last one.
    codes = re.findall(r'(?:ID|AUTHORITY)\[\s*"EPSG"\s*,\s*"?(\d+)"?\s*\]', up)
    if codes:
        code = codes[-1]
        if code in ("3857", "900913"):
            return "EPSG:3857"
        if code == "4326":
            return "EPSG:4326"
    elif "PSEUDO-MERCATOR" in up or "PSEUDO MERCATOR" in up:
        return "EPSG:3857"
    elif not up.lstrip("#CRS: ").startswith(("PROJCRS", "PROJCS")) and (
        "WGS 84" in up or "WGS84" in up
    ):
        return "EPSG:4326"
    raise GeorefError(
        f"unsupported CRS in points file ({line[:80]}...). Use EPSG:4326 or EPSG:3857 in QGIS."
    )


def lonlat_to_merc(lon: float, lat: float) -> tuple[float, float]:
    x = math.radians(lon) * EARTH_RADIUS
    y = math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)) * EARTH_RADIUS
    return x, y


def merc_to_lonlat(x: float, y: float) -> tuple[float, float]:
    lon = math.degrees(x / EARTH_RADIUS)
    lat = math.degrees(2 * math.atan(math.exp(y / EARTH_RADIUS)) - math.pi / 2)
    return lon, lat


def fit_affine(pf: PointsFile) -> Fit:
    if len(pf.points) < 3:
        raise GeorefError(f"need at least 3 enabled control points, got {len(pf.points)}")
    src = np.array([[p.pixel_x, p.pixel_y, 1.0] for p in pf.points])
    if pf.crs == "EPSG:4326":
        dst = np.array([lonlat_to_merc(p.map_x, p.map_y) for p in pf.points])
    else:
        dst = np.array([[p.map_x, p.map_y] for p in pf.points])
    if np.linalg.matrix_rank(src) < 3:
        raise GeorefError("control points are collinear; spread them across the map")
    sol, *_ = np.linalg.lstsq(src, dst, rcond=None)  # (3, 2)
    matrix = sol.T  # (2, 3)
    resid = src @ sol - dst
    # Mercator metres are stretched by 1/cos(lat); scale back to ground metres.
    lat = merc_to_lonlat(*dst.mean(axis=0))[1]
    rms = float(np.sqrt((resid**2).sum(axis=1).mean()) * math.cos(math.radians(lat)))
    return Fit(matrix=matrix, rms_m=rms, n_points=len(pf.points))


def image_corners(fit: Fit, width: int, height: int, left: int = 0, top: int = 0) -> tuple:
    """Lon/lat of the image corners: top-left, top-right, bottom-right, bottom-left.

    `left`/`top` offset a cropped image within the full rendered page.
    """
    out = []
    r, b = left + width, top + height
    for col, row in ((left, top), (r, top), (r, b), (left, b)):
        x, y = fit.matrix @ np.array([col, row, 1.0])
        lon, lat = merc_to_lonlat(float(x), float(y))
        out.append((round(lon, 7), round(lat, 7)))
    return tuple(out)


def render_pdf_page(pdf_path: Path, page: int = 0, dpi: int = RENDER_DPI) -> Image.Image:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        if page >= len(pdf):
            raise GeorefError(f"PDF has {len(pdf)} pages, asked for page {page}")
        bitmap = pdf[page].render(scale=dpi / 72.0)
        return bitmap.to_pil().convert("RGB")
    finally:
        pdf.close()


def make_overlay_png(img: Image.Image, out: Path, max_side: int = MAX_SIDE) -> None:
    """Downscale, make (near-)white transparent, palette-quantize and save an optimized PNG."""
    w, h = img.size
    scale = min(1.0, max_side / max(w, h))
    if scale < 1.0:
        img = img.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS)
    rgb = np.asarray(img.convert("RGB"))
    alpha = np.where((rgb >= WHITE_THRESHOLD).all(axis=2), 0, 255).astype(np.uint8)
    rgba = Image.fromarray(np.dstack([rgb, alpha]), "RGBA")
    quantized = rgba.quantize(colors=128, method=Image.Quantize.FASTOCTREE)
    out.parent.mkdir(parents=True, exist_ok=True)
    quantized.save(out, format="PNG", optimize=True)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass(frozen=True)
class GeorefOptions:
    """Optional sidecar ``{scheme_id}.json`` next to the .points file."""

    page: int = 0
    file_url: str | None = None  # which map file to use if a scheme has several
    # Optional [left, top, right, bottom] in rendered-page pixels: keep only the map area
    # (drops title block / legend from the overlay). Control points stay in full-page pixels.
    crop: tuple[int, int, int, int] | None = None

    @classmethod
    def load(cls, points_path: Path) -> GeorefOptions:
        side = points_path.with_suffix(".json")
        if not side.exists():
            return cls()
        data = json.loads(side.read_text(encoding="utf-8"))
        crop = data.get("crop")
        if crop is not None:
            if len(crop) != 4 or not (crop[0] < crop[2] and crop[1] < crop[3]):
                raise GeorefError(f"{side.name}: crop must be [left, top, right, bottom]")
            crop = tuple(int(v) for v in crop)
        return cls(page=int(data.get("page", 0)), file_url=data.get("file_url"), crop=crop)


def build_overlay(
    scheme_id: str,
    pdf_path: Path,
    points_path: Path,
    overlays_dir: Path,
    page: int = 0,
    crop: tuple[int, int, int, int] | None = None,
) -> Overlay:
    """Render, fit and write ``overlays_dir/{scheme_id}.png``. Returns the overlay record."""
    pf = parse_points(points_path.read_text(encoding="utf-8-sig"))
    fit = fit_affine(pf)
    img = render_pdf_page(pdf_path, page)
    left = top = 0
    if crop:
        w, h = img.size
        left, top = max(0, crop[0]), max(0, crop[1])
        img = img.crop((left, top, min(w, crop[2]), min(h, crop[3])))
    corners = image_corners(fit, *img.size, left=left, top=top)
    make_overlay_png(img, overlays_dir / f"{scheme_id}.png")
    return Overlay(
        status="done",
        url=f"overlays/{scheme_id}.png",
        corners=corners,
        source_sha256=sha256_file(pdf_path),
        accuracy_note=(
            f"Approximate: fitted from {fit.n_points} control points, "
            f"typical error about {max(1, round(fit.rms_m))} m."
        ),
        points_sha256=sha256_file(points_path),
    )


def safe_name(scheme_id: str) -> str:
    if not re.fullmatch(r"[a-z0-9-]+", scheme_id):
        raise GeorefError(f"invalid scheme id {scheme_id!r}")
    return scheme_id
