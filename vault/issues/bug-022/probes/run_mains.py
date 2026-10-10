"""BUG-022: консольный вывод main.py всех примеров на базе и на эмуляции плана — для сверки чисел README.

Числа README примеров взяты из консоли их main.py (балансы энергии и массы, проверка R_s,
замыкание GOR и т. д.). Скрипт запускает main.py на копии examples/ в этом каталоге
(examples_copy_<вариант>/; после замера удалить — в git не идёт), чтобы не перезаписать
рабочие рисунки examples/*/output/. Вариант 0 — код базы; иначе — эмуляция плана, как в
pytest_cell_tol.py (условие ячейки только у моделей фабрики GPN).
Вывод: mains_<вариант>/<пример>.txt; затем diff_mains.py сравнивает два варианта.
Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\bug-022\\probes\\run_mains.py 0
    .venv\\Scripts\\python ..\\vault\\issues\\bug-022\\probes\\run_mains.py pv1e-8
"""

import contextlib
import io
import os
import runpy
import shutil
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cell_tol  # noqa: E402  (ставит sys.path на numerical_solver и прототип)

import matplotlib  # noqa: E402
matplotlib.use("Agg")

COPY = None   # examples_copy_<вариант>: у каждого варианта своя копия — output/ не делятся


def prepare_copy():
    """Копия examples/ без output/ и __pycache__ (один раз)."""
    if COPY.exists():
        return
    shutil.copytree(cell_tol.SOLVER / "examples", COPY,
                    ignore=shutil.ignore_patterns("output", "__pycache__", "*.png"))
    # example_runner ищет прототип от своего каталога (parents[1]) — в копии указать настоящий
    er = COPY / "example_runner.py"
    old = "_SOLVER_ROOT = Path(__file__).resolve().parents[1]"
    text = er.read_text(encoding="utf-8")
    assert old in text, "example_runner.py изменился — поправить подмену пути"
    er.write_text(text.replace(old, f'_SOLVER_ROOT = Path(r"{cell_tol.SOLVER}")'), encoding="utf-8")


def install_emulation(variant):
    """Вариант 0 — код как есть; иначе — эмуляция плана: условие у моделей фабрики GPN."""
    if variant == "0":
        return
    from gpn_multiphase_solver import factory
    cell_tol.install(variant)
    cell_tol.CELL["require_mark"] = True
    orig = factory._create_prototype_hydro

    def create(*a, **k):
        hydro = orig(*a, **k)
        hydro._model._probe_cell = True
        return hydro

    factory._create_prototype_hydro = create


def main(variant, names):
    global COPY
    COPY = HERE / f"examples_copy_{variant}"
    prepare_copy()
    install_emulation(variant)
    out_dir = HERE / f"mains_{variant}"
    out_dir.mkdir(exist_ok=True)
    names = names or sorted(p.parent.name for p in COPY.glob("*/main.py"))
    for name in names:
        buf = io.StringIO()
        t0 = time.perf_counter()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                runpy.run_path(str(COPY / name / "main.py"), run_name="__main__")
            except BaseException:
                traceback.print_exc()
        (out_dir / f"{name}.txt").write_text(buf.getvalue(), encoding="utf-8")
        print(f"{name:<28} {time.perf_counter() - t0:6.1f} с", flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
