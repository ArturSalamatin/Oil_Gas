"""Проба FEAT-026: EMF -> PNG через Inkscape, чтобы глазами сравнить с исходным рисунком."""

import subprocess
from pathlib import Path

INKSCAPE = Path(r"C:\Program Files\Inkscape\bin\inkscape.com")
OUT = Path(__file__).resolve().parent / "out"

for name in ("fig_path", "fig_none"):
    emf = OUT / f"{name}.emf"
    png = OUT / f"{name}_roundtrip.png"
    subprocess.run([str(INKSCAPE), str(emf), "--export-type=png",
                    f"--export-filename={png}", "--export-dpi=60"],
                   check=True, capture_output=True)
    print(png, png.stat().st_size)
