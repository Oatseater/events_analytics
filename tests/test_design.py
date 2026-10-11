"""Design rules that are easy to break by accident."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STYLED = [ROOT / "assets" / "style.css", ROOT / "lib" / "theme.py",
          ROOT / "lib" / "charts.py", ROOT / ".streamlit" / "config.toml"]

HEX = re.compile(r"(?:#|%23)([0-9A-Fa-f]{6})\b")
RGB = re.compile(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)")


def test_palette_is_black_and_silver_only():
    # Warm near-black and brushed silver, no accent colour. "Warm" allows a
    # slight tint, so each colour's red, green and blue may differ by at most 8
    # (out of 255). Anything more saturated, such as a red, fails.
    for f in STYLED:
        text = f.read_text(encoding="utf-8")
        colours = [tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) for h in HEX.findall(text)]
        colours += [tuple(int(v) for v in m) for m in RGB.findall(text)]
        for rgb in colours:
            assert max(rgb) - min(rgb) <= 8, f"accent colour {rgb} in {f.name}"


def test_fonts_are_bundled_with_licences():
    fonts = ROOT / "static" / "fonts"
    for name in ["Archivo-Variable", "JetBrainsMono-Variable", "BodoniModa-Variable", "BodoniModa-Italic-Variable"]:
        assert (fonts / f"{name}.woff2").exists()
    assert len(list(fonts.glob("OFL-*.txt"))) == 3
    assert "googleapis" not in (ROOT / "assets" / "style.css").read_text()
