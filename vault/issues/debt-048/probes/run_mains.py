"""DEBT-048: консоль main.py примеров на копии examples/ — для сверки чисел README (по образцу BUG-022).

Числа README примеров взяты из консоли их main.py: балансы энергии и массы, проверка R_s,
замыкание GOR и т. д. Память ступени 4 меняет историю примера 17 (план, 1.4), поэтому
перед правкой README консоль сверяется: база против эмуляции m2s (шаг 0) и база против
кода ветки (шаг 5).

Режимы:
  run <пример> ...   — main.py примеров на копии examples/ рядом со скриптом
                       (examples_copy<TAG>/; после замера удалить — в git не идёт), чтобы не
                       перезаписать рисунки examples/*/output/. Дерево кода — DEBT048_SOLVER
                       (как stage_memory.py). DEBT048_EMULATE=m2s — память на моделях фабрики
                       (подмена stage_memory.install), без неё — код дерева как есть.
                       Вывод: mains<TAG>/<пример>.txt.
  diff <TAG_A> <TAG_B> — строки консоли, которые различаются (пути копий, «Сохранён: …»
                       и время счёта отброшены). Вывод: diff_mains<TAG_A><TAG_B>.out.txt.

Запуск (из numerical_solver, PowerShell):
    $env:DEBT048_TAG = "_b22";      python ..\\vault\\issues\\debt-048\\probes\\run_mains.py run 16_well_shut_in 17_shut_in_strong_cooling
    $env:DEBT048_TAG = "_b22m2s"; $env:DEBT048_EMULATE = "m2s"; python ...\\run_mains.py run 16_well_shut_in 17_shut_in_strong_cooling
    python ..\\vault\\issues\\debt-048\\probes\\run_mains.py diff _b22 _b22m2s
"""

import contextlib
import difflib
import io
import os
import re
import runpy
import shutil
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import stage_memory as sm  # noqa: E402  (ставит sys.path на numerical_solver и прототип)

EMULATE = os.environ.get("DEBT048_EMULATE", "")
SKIP = re.compile(r"^(Сохранён:|Конфиг:)|\d+\.\d+ с\b|за \d+\.\d+ с|время")


def prepare_copy(copy):
    """Копия examples/ без output/, __pycache__ и рисунков; пакеты — из дерева SOLVER."""
    if copy.exists():
        shutil.rmtree(copy)
    shutil.copytree(sm.SOLVER / "examples", copy,
                    ignore=shutil.ignore_patterns("output", "__pycache__", "*.png"))
    # После DEBT-059 example_runner путей не добавляет: пакеты берутся из sys.path
    # процесса, а stage_memory при импорте ставит туда первыми numerical_solver и
    # прототип дерева SOLVER (вставка в sys.path[0] сильнее редактируемой установки
    # из основного каталога — проверено аудитом 3). До DEBT-059 example_runner сам
    # вставлял путь от своего каталога — в копии его надо было перенаправить.
    er = copy / "example_runner.py"
    old = "_SOLVER_ROOT = Path(__file__).resolve().parents[1]"
    text = er.read_text(encoding="utf-8")
    if old in text:
        er.write_text(text.replace(old, f'_SOLVER_ROOT = Path(r"{sm.SOLVER}")'), encoding="utf-8")


def install_emulation():
    """DEBT048_EMULATE=<вариант> — память на модели каждого адаптера, созданного фабрикой."""
    if not EMULATE:
        return
    from gpn_multiphase_solver import factory
    orig = factory._create_prototype_hydro

    def create(*a, **k):
        hydro = orig(*a, **k)
        sm.install(hydro._model, EMULATE)
        return hydro

    factory._create_prototype_hydro = create


def run(names):
    import matplotlib
    matplotlib.use("Agg")
    copy = HERE / f"examples_copy{sm.TAG}"
    prepare_copy(copy)
    install_emulation()
    out_dir = HERE / f"mains{sm.TAG}"
    out_dir.mkdir(exist_ok=True)
    print(sm.code_paths(), f"эмуляция: {EMULATE or 'нет'}", flush=True)
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
    for fa in sorted((HERE / f"mains{a}").glob("*.txt")):
        fb = HERE / f"mains{b}" / fa.name
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
    (HERE / f"diff_mains{a}{b}.out.txt").write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    if sys.argv[1] == "run":
        run(sys.argv[2:])
    else:
        diff(sys.argv[2], sys.argv[3])
