"""Проба FEAT-026: matplotlib -> SVG -> Inkscape -> EMF. Время, размер, варианты передачи SVG."""

import subprocess
import time
from pathlib import Path

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

INKSCAPE = Path(r"C:\Program Files\Inkscape\bin\inkscape.com")
OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)


def make_fig():
    """Рисунок как у примеров: кириллица, mathtext, легенда, 3 подграфика."""
    r = np.logspace(-1, np.log10(200), 350)
    fig, axes = plt.subplots(3, 1, sharex=True, figsize=(7, 8))
    for k, ax in enumerate(axes):
        for t in (0, 60, 150, 360):
            ax.semilogx(r, np.log(r + 1) * (k + 1) + t / 100, label=f"t = {t} сут")
        ax.set_ylabel(r"$T(r_w)$, К  $\Delta T$, $\mu_{JT}$")
        ax.grid(True, alpha=0.3)
    axes[0].set_title("Пример 14 — высокий газовый фактор\nДинамика на забое")
    axes[0].legend(fontsize=8)
    axes[-1].set_xlabel("r, м")
    fig.tight_layout()
    return fig


def convert(svg: Path, emf: Path) -> float:
    t0 = time.perf_counter()
    subprocess.run([str(INKSCAPE), str(svg), "--export-type=emf",
                    f"--export-filename={emf}"],
                   check=True, capture_output=True)
    return time.perf_counter() - t0


def convert_pipe(svg_bytes: bytes, emf: Path) -> float:
    t0 = time.perf_counter()
    subprocess.run([str(INKSCAPE), "--pipe", "--export-type=emf",
                    f"--export-filename={emf}"],
                   input=svg_bytes, check=True, capture_output=True)
    return time.perf_counter() - t0


def main():
    import io

    for fonttype in ("path", "none"):
        matplotlib.rcParams["svg.fonttype"] = fonttype
        fig = make_fig()
        svg = OUT / f"fig_{fonttype}.svg"
        fig.savefig(svg)
        buf = io.BytesIO()
        fig.savefig(buf, format="svg")
        plt.close(fig)

        emf = OUT / f"fig_{fonttype}.emf"
        dt = convert(svg, emf)
        print(f"fonttype={fonttype:5s} файл : {dt:5.2f} с, SVG {svg.stat().st_size/1e3:7.1f} кБ,"
              f" EMF {emf.stat().st_size/1e3:7.1f} кБ, заголовок {emf.read_bytes()[40:44]!r}")

        emf2 = OUT / f"fig_{fonttype}_pipe.emf"
        dt = convert_pipe(buf.getvalue(), emf2)
        print(f"fonttype={fonttype:5s} pipe : {dt:5.2f} с, EMF {emf2.stat().st_size/1e3:7.1f} кБ")

    # Пакет: несколько SVG за один запуск Inkscape
    matplotlib.rcParams["svg.fonttype"] = "path"
    svgs = []
    for i in range(8):
        fig = make_fig()
        p = OUT / f"batch_{i}.svg"
        fig.savefig(p)
        plt.close(fig)
        svgs.append(p)
    t0 = time.perf_counter()
    subprocess.run([str(INKSCAPE), "--export-type=emf", *map(str, svgs)],
                   check=True, capture_output=True)
    dt = time.perf_counter() - t0
    made = [p.with_suffix(".emf") for p in svgs if p.with_suffix(".emf").is_file()]
    print(f"пакет 8 SVG за один запуск: {dt:5.2f} с, создано EMF: {len(made)}")


if __name__ == "__main__":
    main()
