"""FEAT-026: сценарии A–E модуля figure_io с настоящим Inkscape (аудит; повтор после реализации).

Запуск по одному сценарию, вывод в probes/audit_out/ (удалить после):
    numerical_solver\\.venv\\Scripts\\python probe_audit_scenarios.py A|B|C|D|E
E с PYTHONIOENCODING=cp1251 проверяет печать хвоста stderr Inkscape.
"""

import os
import sys
import time
from pathlib import Path

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
# На аудите здесь был код шага 1, извлечённый из плана; после реализации —
# настоящий модуль numerical_solver/examples/figure_io.py.
sys.path.insert(0, str(HERE.parents[3] / "numerical_solver" / "examples"))
import figure_io as fio

OUT = HERE / "audit_out" / "output"


def fig3():
    """Рисунок как wellbore_dynamics: 3 панели, кириллица, mathtext."""
    r = np.logspace(-1, np.log10(200), 350)
    fig, axes = plt.subplots(3, 1, sharex=True, figsize=(7, 8))
    for k, ax in enumerate(axes):
        for t in (0, 60, 150, 360):
            ax.semilogx(r, np.log(r + 1) * (k + 1) + t / 100, label=f"t = {t} сут")
        ax.set_ylabel(r"$T(r_w)$, К")
    axes[0].set_title("14: высокий газовый фактор\nДинамика на забое")
    axes[0].legend(fontsize=8)
    fig.tight_layout()
    return fig


def save(name):
    fig = fig3()
    fio.save_figure(fig, OUT / f"{name}.png", dpi=110)
    plt.close(fig)


def listing():
    emf = OUT / "emf"
    svg = sorted(p.stem for p in emf.glob("*.svg")) if emf.is_dir() else []
    em = sorted(p.stem for p in emf.glob("*.emf")) if emf.is_dir() else []
    return f"svg={svg} emf={em}"


def main():
    scenario = sys.argv[1]
    OUT.mkdir(parents=True, exist_ok=True)

    if scenario == "A":   # выключено: только PNG
        os.environ["GPN_EXAMPLES_EMF"] = "0"
        save("a")
        print("A:", (OUT / "a.png").is_file(), "emf/ есть:", (OUT / "emf").exists(),
              "export:", fio.export_emf(OUT))

    elif scenario == "B":  # 9 рисунков одним пакетом
        names = ["pressure_profiles", "temperature_profiles", "saturation_profiles",
                 "rs_profiles", "well_rates", "wellbore_dynamics", "relperm", "pvt",
                 "energy_balance"]
        for n in names:
            save(n)
        t0 = time.perf_counter()
        made = fio.export_emf(OUT)
        print(f"B: создано {len(made)} за {time.perf_counter() - t0:.1f} с; {listing()}")
        txt = (OUT / "emf" / "pvt.svg").read_text(encoding="utf-8")
        print("B: '<text' в SVG:", "<text" in txt)

    elif scenario == "C":  # перестройка двух рисунков -> второй пакет только из них
        before = {p.name: p.stat().st_mtime for p in (OUT / "emf").glob("*.emf")}
        save("pressure_profiles")
        save("temperature_profiles")
        made = fio.export_emf(OUT)
        after = {p.name: p.stat().st_mtime for p in (OUT / "emf").glob("*.emf")}
        changed = sorted(k for k in after if after[k] != before.get(k))
        print(f"C: конвертировано {[p.stem for p in made]}; изменились EMF: {changed}")

    elif scenario == "D":  # без Inkscape, затем доделка
        save("slopes")
        os.environ["INKSCAPE"] = r"C:\нет\inkscape.com"
        print("D1:", fio.export_emf(OUT), listing())
        del os.environ["INKSCAPE"]
        print("D2:", [p.stem for p in fio.export_emf(OUT)], listing())

    elif scenario == "E":  # битый SVG: Inkscape код 0, EMF нет -> хвост stderr
        (OUT / "emf" / "broken.svg").write_bytes(b"\xff\xfe not an svg \x80\x81")
        made = fio.export_emf(OUT)
        print("E: создано", [p.stem for p in made])


if __name__ == "__main__":
    main()
