import math

import numpy as np
import pytest
from PIL import Image

from opennaksha.georef.overlay import (
    GeorefError,
    build_overlay,
    fit_affine,
    image_corners,
    lonlat_to_merc,
    make_overlay_png,
    merc_to_lonlat,
    parse_points,
    render_pdf_page,
)

# A made-up affine map: 1 pixel = 2 m, rotated 5°, origin near Surat (synthetic test data).
ORIGIN = lonlat_to_merc(72.80, 21.20)
ANGLE = math.radians(5)


def true_merc(col, row):
    x = ORIGIN[0] + 2 * (col * math.cos(ANGLE) + row * math.sin(ANGLE))
    y = ORIGIN[1] + 2 * (col * math.sin(ANGLE) - row * math.cos(ANGLE))
    return x, y


def points_text(pixels, crs_line='#CRS: GEOGCRS["WGS 84",ID["EPSG",4326]]'):
    rows = [crs_line, "mapX,mapY,sourceX,sourceY,enable,dX,dY,residual"]
    for col, row in pixels:
        lon, lat = merc_to_lonlat(*true_merc(col, row))
        rows.append(f"{lon},{lat},{col},{-row},1,0,0,0")
    return "\n".join(rows)


def test_mercator_roundtrip():
    lon, lat = merc_to_lonlat(*lonlat_to_merc(72.83, 21.17))
    assert lon == pytest.approx(72.83) and lat == pytest.approx(21.17)


def test_parse_points_qgis_format():
    text = points_text([(0, 0), (100, 0), (0, 100)]) + "\n1,2,3,-4,0,0,0,0"
    pf = parse_points(text)
    assert pf.crs == "EPSG:4326"
    assert len(pf.points) == 3  # disabled row skipped
    assert pf.points[2].pixel_y == 100  # negative QGIS row → positive


def test_parse_points_mercator_crs():
    pf = parse_points(
        '#CRS: PROJCRS["WGS 84 / Pseudo-Mercator"]\nmapX,mapY,sourceX,sourceY,enable\n'
    )
    assert pf.crs == "EPSG:3857"


def test_unsupported_crs():
    with pytest.raises(GeorefError):
        parse_points('#CRS: PROJCRS["WGS 84 / UTM zone 43N",ID["EPSG",32643]]')


def test_affine_fit_recovers_corners():
    pf = parse_points(points_text([(10, 20), (900, 50), (450, 700), (880, 690), (30, 650)]))
    fit = fit_affine(pf)
    assert fit.rms_m < 0.01
    corners = image_corners(fit, 1000, 800)
    expected = [
        merc_to_lonlat(*true_merc(c, r)) for c, r in ((0, 0), (1000, 0), (1000, 800), (0, 800))
    ]
    for got, exp in zip(corners, expected, strict=True):
        assert got[0] == pytest.approx(exp[0], abs=1e-6)
        assert got[1] == pytest.approx(exp[1], abs=1e-6)


def test_fit_needs_three_non_collinear_points():
    with pytest.raises(GeorefError):
        fit_affine(parse_points(points_text([(0, 0), (10, 10)])))
    with pytest.raises(GeorefError):
        fit_affine(parse_points(points_text([(0, 0), (10, 10), (20, 20)])))


def test_overlay_png_is_downscaled_and_transparent(tmp_path):
    img = Image.new("RGB", (5000, 1000), "white")
    img.paste((200, 0, 0), (100, 100, 400, 400))
    out = tmp_path / "o.png"
    make_overlay_png(img, out, max_side=1000)
    res = Image.open(out).convert("RGBA")
    assert res.size == (1000, 200)
    px = np.asarray(res)
    assert px[0, 0, 3] == 0  # white → transparent
    assert px[50, 50, 3] == 255 and px[50, 50, 0] > 150


def tiny_pdf(path):
    """Write a minimal one-page PDF (200x100 pt) with a filled rectangle."""
    stream = b"0 0 1 rg 20 20 60 40 re f"
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 100] /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    path.write_bytes(bytes(out))


def test_render_and_build_overlay(tmp_path):
    pdf = tmp_path / "m.pdf"
    tiny_pdf(pdf)
    img = render_pdf_page(pdf)
    w, h = img.size  # 200x100 pt at 150 dpi ≈ 417x208 (renderer rounds up)
    assert abs(w - 417) <= 1 and abs(h - 208) <= 1
    points = tmp_path / "surat-tp-1.points"
    points.write_text(points_text([(0, 0), (400, 0), (0, 200), (400, 200)]), encoding="utf-8")
    ov = build_overlay("surat-tp-1", pdf, points, tmp_path / "overlays")
    assert ov.status == "done" and ov.url == "overlays/surat-tp-1.png"
    assert (tmp_path / "overlays" / "surat-tp-1.png").exists()
    assert ov.source_sha256 and ov.points_sha256 and len(ov.corners) == 4
    assert "control points" in ov.accuracy_note
