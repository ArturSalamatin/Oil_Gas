"""BUG-024: консоль main.py примеров на копии examples/ — для сверки чисел README (по образцу DEBT-048).

Ограничение шага R_s в ступени 4 меняет истории примеров 16 (на уровне допуска) и 17. Числа README
взяты из консоли main.py, поэтому консоль сверяется: код базы против варианта.
Режимы:
  run <TAG> <вариант|code> <пример> ... — main.py на копии examples/ рядом со скриптом
                       (examples_copy_<TAG>/; после замера удалить — в git не идёт), чтобы не
                       перезаписать рисунки examples/*/output/. Вариант — подмена
                       RadialBlackOilModel._newton_switching (stage4_variants.py) на уровне класса.
                       Вывод: mains_<TAG>/<пример>.txt.
  diff <TAG_A> <TAG_B> — различающиеся строки консоли (пути, «Сохранён: …», время счёта отброшены).
                       Вывод: diff_mains_<TAG_A>_<TAG_B>.out.txt.
Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\bug-024\\probes\\run_mains.py run base code 16_well_shut_in 17_shut_in_strong_cooling
    .venv\\Scripts\\python ..\\vault\\issues\\bug-024\\probes\\run_mains.py run satrel satrel 16_well_shut_in 17_shut_in_strong_cooling
    .venv\\Scripts\\python ..\\vault\\issues\\bug-024\\probes\\run_mains.py diff base satrel
"""

import contextlib
import difflib
import io
import re
import runpy
import shutil
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOLVER = Path.cwd().resolve()   # запуск из numerical_solver проверяемого дерева
for p in (SOLVER, SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3", HERE):
    sys.path.insert(0, str(p))
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")
SKIP = re.compile(r"^(Сохранён:|Конфиг:)|\d+\.\d+ с\b|за \d+\.\d+ с|время")


def prepare_copy(copy):
    """Копия examples/ без output/, __pycache__ и рисунков; example_runner — на настоящий numerical_solver."""
    if copy.exists():
        shutil.rmtree(copy)
    shutil.copytree(SOLVER / "examples", copy,
                    ignore=shutil.ignore_patterns("output", "__pycache__", "*.png"))
    er = copy / "example_runner.py"
    old = "_SOLVER_ROOT = Path(__file__).resolve().parents[1]"
    text = er.read_text(encoding="utf-8")
    assert old in text, "example_runner.py изменился — поправить подмену пути"
    er.write_text(text.replace(old, f'_SOLVER_ROOT = Path(r"{SOLVER}")'), encoding="utf-8")


def run(tag, variant, names):
    import matplotlib
    matplotlib.use("Agg")
    if variant != "code":
        from radial_blackoil.blackoil import RadialBlackOilModel
        import stage4_variants
        fn = stage4_variants.make(variant)
        fn.__defaults__ = RadialBlackOilModel._newton_switching.__defaults__
        RadialBlackOilModel._newton_switching = fn
    copy = HERE / f"examples_copy_{tag}"
    prepare_copy(copy)
    out_dir = HERE / f"mains_{tag}"
    out_dir.mkdir(exist_ok=True)
    for name in names:
        buf = io.StringIO()
        t0 = time.perf_counter()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                runpy.run_path(str(copy / name / "main.py"), run_name="__main__")
            except BaseException:
                traceback.print_exc()
        (out_dir / f"{name}.txt").write_text(buf.getvalue(), encoding="utf-8")
        print(f"{name:<28} {time.perf_counter() - t0:6.1f} с", flush=True)


def norm(text):
    out = []
    for line in text.splitlines():
        line = re.sub(r"examples_copy[^\\/]*", "examples", line)
        if SKIP.search(line.strip()):
            continue
        out.append(line.rstrip())
    return out


def diff(a, b):
    lines = [f"=== консоль main.py: {a} против {b} (без путей, «Сохранён» и времени счёта)"]
    for fa in sorted((HERE / f"mains_{a}").glob("*.txt")):
        fb = HERE / f"mains_{b}" / fa.name
        if not fb.exists():
            lines.append(f"--- {fa.stem}: нет вывода {b}")
            continue
        la, lb = norm(fa.read_text(encoding="utf-8")), norm(fb.read_text(encoding="utf-8"))
        d = [x for x in difflib.unified_diff(la, lb, lineterm="", n=0)
             if not x.startswith(("---", "+++", "@@"))]
        lines.append(f"--- {fa.stem}: строк отличается {sum(x.startswith('-') for x in d)}")
        lines.extend("    " + x for x in d)
    text = "\n".join(lines)
    print(text)
    (HERE / f"diff_mains_{a}_{b}.out.txt").write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    if sys.argv[1] == "run":
        run(sys.argv[2], sys.argv[3], sys.argv[4:])
    else:
        diff(sys.argv[2], sys.argv[3])
