"""Аудит FEAT-023, шаг 3 плана: правки example_runner на копии + тест флага.

Правки «До -> После» из плана применяются к тексту examples/example_runner.py
точной заменой строк (str.replace с проверкой, что «До» встречается ровно
один раз) — так проверяется, что Edit при реализации найдёт old_string.
Копия пишется в flag/example_runner.py; путь к прототипу в ней
перенаправляется на numerical_solver/ (иначе _SOLVER_ROOT указал бы на vault).
Затем тело test_steady_state_false_skips_steady_analytics из плана
выполняется на примере 05, и для контроля — путь по умолчанию.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\feat-023\\probes\\audit_flag.py
"""

import contextlib
import importlib.util
import io
import sys
import tempfile
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
SOLVER = HERE.parents[3] / "numerical_solver"
EX = SOLVER / "examples"
sys.path.insert(0, str(EX))

src = (EX / "example_runner.py").read_text(encoding="utf-8")

EDITS = [
    ("""def run_example(config_path: str | Path, output_dir: str | Path,
                title: str, overlays: dict | None = None,
                n_profiles: int | None = None) -> tuple:""",
     """def run_example(config_path: str | Path, output_dir: str | Path,
                title: str, overlays: dict | None = None,
                n_profiles: int | None = None,
                steady_state: bool = True) -> tuple:"""),
    ("""    FEAT-022. 13a задаёт 6: 0, 3, ..., 15 сут.
""",
     """    FEAT-022. 13a задаёт 6: 0, 3, ..., 15 сут.

    steady_state — строить ли стационарную аналитику: замкнутое решение
    на профилях p и S_g, его сверку report_closed и асимптотику
    температуры report_asymptotics. Все они — пределы t -> inf при
    удержании одного режима скважины. False снимает их (13b: режим
    меняется каждые сутки); явный overlay примера по-прежнему рисуется.
    Проверка R_s (наложение и report_rs) от флага не зависит.
"""),
    ("""    two_phase = config.initial_conditions.Rs0 > 0.0
    p_overlay = _pick_overlay(overlays, "p",
                              make_overlay_pressure(config) if two_phase else None)
    sg_overlay = _pick_overlay(overlays, "Sg",
                               make_overlay_saturation(config) if two_phase else None)""",
     """    two_phase = config.initial_conditions.Rs0 > 0.0
    # Стационарные наложения — только при steady_state: при смене режима
    # скважины на каждых сутках (13b) предела t -> inf у записей нет.
    steady = two_phase and steady_state
    p_overlay = _pick_overlay(overlays, "p",
                              make_overlay_pressure(config) if steady else None)
    sg_overlay = _pick_overlay(overlays, "Sg",
                               make_overlay_saturation(config) if steady else None)"""),
    ("""        report_rs(config, history, simulator._energy._pvt)
        print()
        report_closed(config, history, grid, simulator)""",
     """        report_rs(config, history, simulator._energy._pvt)
        if steady_state:
            print()
            report_closed(config, history, grid, simulator)"""),
    ("""    print()
    report_asymptotics(config, history, grid, simulator)""",
     """    print()
    if steady_state:
        report_asymptotics(config, history, grid, simulator)
    else:
        # Одна строка вместо двух отчётов: без неё пропажа сверок в
        # консоли выглядела бы как сбой подключения модулей.
        print("── Стационарная аналитика отключена (steady_state=False): "
              "замкнутое решение и асимптотика температуры не строятся ──")"""),
]

for old, new in EDITS:
    n = src.count(old)
    print(f"«До» найдено {n} раз: {old.splitlines()[0][:70]!r}")
    assert n == 1
    src = src.replace(old, new)

# Путь к прототипу — от numerical_solver, а не от папки копии
src = src.replace('_SOLVER_ROOT = Path(__file__).resolve().parents[1]',
                  f'_SOLVER_ROOT = Path(r"{SOLVER}")')
out = HERE / "flag"
out.mkdir(exist_ok=True)
(out / "example_runner.py").write_text(src, encoding="utf-8")
print("длина строк > 100:", [i + 1 for i, s in enumerate(src.splitlines()) if len(s) > 100])

spec = importlib.util.spec_from_file_location("example_runner", out / "example_runner.py")
example_runner = importlib.util.module_from_spec(spec)
sys.modules["example_runner"] = example_runner
spec.loader.exec_module(example_runner)

CFG = EX / "05_standing_table_rp" / "config.json"


def run(steady_state):
    called = []

    def spy(name):
        def f(*args, **kwargs):
            called.append(name)
            return None
        return f

    names = ("make_overlay_pressure", "make_overlay_saturation",
             "report_closed", "report_asymptotics", "report_rs")
    with contextlib.ExitStack() as st:
        for name in names:
            st.enter_context(mock.patch.object(example_runner, name, spy(name)))
        buf = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(buf):
            import time
            t0 = time.perf_counter()
            example_runner.run_example(config_path=CFG, output_dir=tmp,
                                       title="аудит steady_state",
                                       steady_state=steady_state)
            el = time.perf_counter() - t0
    return called, buf.getvalue(), el


called, text, el = run(False)
print(f"steady_state=False: вызваны {called}; пометка: "
      f"{'Стационарная аналитика отключена' in text}; {el:.1f} с")
assert called == ["report_rs"]
assert "Стационарная аналитика отключена" in text

called, text, el = run(True)
print(f"steady_state=True:  вызваны {called}; пометка: "
      f"{'Стационарная аналитика отключена' in text}; {el:.1f} с")
