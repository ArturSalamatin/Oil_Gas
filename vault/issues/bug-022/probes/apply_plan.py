"""BUG-022, аудит: текст плана дословно — на копию numerical_solver/ (plan_tree/, в git не идёт).

Копирует из основного каталога gpn_multiphase_solver/, tests/, configs/, examples/ (без output/)
и HydroSolverPrototype/Prototype_1.0.3/ (без OUTPUT/) в plan_tree/numerical_solver/ и применяет
правки шагов 1–4 плана, беря блоки кода из файла плана по номерам (блоки ищутся по началу текста, вывод
--list — их перечень). Каждый якорь «до» обязан встретиться в файле ровно один раз — иначе Edit при
реализации не сработает; нарушение печатается и останавливает скрипт.
Запуск (из numerical_solver основного каталога):
    .venv\\Scripts\\python ..\\vault\\issues\\bug-022\\probes\\apply_plan.py [--list]
Потом — тесты из plan_tree\\numerical_solver: & $PY -m pytest tests/... (pytest берёт пакет копии).
После аудита plan_tree/ удалить.
"""

import re
import shutil
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SRC = ROOT / "numerical_solver"
DST = HERE / "plan_tree" / "numerical_solver"
PLAN = ROOT / "vault" / "plans" / "bug-022 newton-cell-relative-tolerance.md"
text = PLAN.read_text(encoding="utf-8")
blocks = []
for m in re.finditer(r"^( *)```(\w*)\n(.*?)^\1```", text, re.S | re.M):
    ind = len(m.group(1))
    blocks.append("\n".join(l[ind:] for l in m.group(3).split("\n")))
if "--list" in sys.argv:
    for i, b in enumerate(blocks):
        print(i, repr(b.strip().split("\n")[0][:100]))
    raise SystemExit


def B(prefix, k=0):
    """k-й блок плана, чей текст начинается с prefix (без последнего перевода строки).

    По началу текста, а не по номеру: правки плана добавляют блоки, номера сдвигаются.
    """
    found = [b for b in blocks if b.lstrip().startswith(prefix)]
    if len(found) <= k:
        raise SystemExit(f"✗ в плане нет блока #{k} с началом {prefix!r} (найдено {len(found)})")
    return found[k].rstrip("\n")


def edit(path, old, new, label):
    p = DST / path
    s = p.read_text(encoding="utf-8")
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"✗ {label}: якорь встречается {n} раз в {path}:\n{old[:200]}")
    p.write_text(s.replace(old, new), encoding="utf-8")
    print(f"✓ {label}")


# ── Копия дерева ──
if DST.exists():
    shutil.rmtree(DST)
ign = shutil.ignore_patterns("output", "OUTPUT", "__pycache__", "*.png", "*.emf", "*.svg", ".pytest_cache")
for d in ("gpn_multiphase_solver", "tests", "configs", "examples"):
    shutil.copytree(SRC / d, DST / d, ignore=ign)
shutil.copytree(SRC / "HydroSolverPrototype" / "Prototype_1.0.3", DST / "HydroSolverPrototype" / "Prototype_1.0.3", ignore=ign)
print("копия:", DST)

BO = "HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/blackoil.py"
CFG = "gpn_multiphase_solver/io/config.py"
FAC = "gpn_multiphase_solver/factory.py"

# ── Шаг 2: прототип ──
edit(BO, B("DEBT-040: under BHP"), B("DEBT-040: under BHP", 1), "шаг 2.1 docstring модуля")
edit(BO, B("jacobian_mode='grouped'"), B("jacobian_mode='grouped'", 1), "шаг 2.2 сигнатура конструктора")
ANCHOR_CTOR = "        self._upwind_frozen=None; self._upwind_left=None\n"
edit(BO, ANCHOR_CTOR + "\n    def set_bhp_control", ANCHOR_CTOR + B("# BUG-022: per-cell convergence test, off by default") + "\n\n    def set_bhp_control",
     "шаг 2.3 конец конструктора (якорь с контекстом — исходный встречается дважды)")
edit(BO, "    def _pressure_fd_step(", B("def _cell_weights") + "\n    def _pressure_fd_step(", "шаг 2.4 методы")
edit(BO, B("z=np.asarray(z0,float).copy()"), B("z=np.asarray(z0,float).copy()", 1), "шаг 2.5 начало _newton_fixed_active_set")
edit(BO, "        if nrm<=tol: return z,BlackOilNewtonReport(True,0,float(nrm))",
     "        if nrm<=tol and self._cells_converged(f,w): return z,BlackOilNewtonReport(True,0,float(nrm))", "шаг 2.5 :327")
edit(BO, "            if nrm<=tol: return z,BlackOilNewtonReport(True,it,float(nrm))",
     "            if nrm<=tol and self._cells_converged(f,w): return z,BlackOilNewtonReport(True,it,float(nrm))", "шаг 2.5 :346")
S507 = "        scale=max(np.linalg.norm(self.residual(z,state_old,dt_s,mask),np.inf),1e-9); tol=atol_sm3s+rtol*scale\n"
edit(BO, S507, S507 + B("# BUG-022: dt/PV_i of the per-cell test, None") + "\n", "шаг 2.6 веса ступени 4")
edit(BO, B("if nrm<=tol and switched==0:"), B("if nrm<=tol and switched==0:", 1), "шаг 2.6 проверка сходимости ступени 4")

# ── Шаг 3: конфиг и фабрика ──
edit(CFG, B('"""Параметры численного метода'), B('"""Параметры численного метода', 1), "шаг 3.1 докстринг NumericsConfig")
edit(CFG, "    max_retries: int = 9\n", "    max_retries: int = 9\n" + B("# Условие сходимости Ньютона по ячейке (BUG-022), безразмерное") + "\n", "шаг 3.2 поле")
VAL_END = "дробление до dt/2**20 бессмысленно.\")\n"
edit(CFG, VAL_END, VAL_END + B("# newton_cell_tol — порог условия сходимости") + "\n", "шаг 3.3 проверка")
edit(FAC, "        phase_switching_stage=True,\n", "        phase_switching_stage=True,\n" + B("# BUG-022: условие сходимости Ньютона по ячейке. У прототипа") + "\n", "шаг 3.4 фабрика")

# ── Шаг 1: тесты ──
NEW_TEST = B('"""BUG-022: условие сходимости Ньютона прототипа по ячейке') + "\n"
(DST / "tests" / "test_prototype_cell_tolerance.py").write_text(NEW_TEST, encoding="utf-8")
print("✓ шаг 1.1 новый файл тестов")
edit("tests/test_examples.py", "    def test_wellbore_warms_monotonically(self, results):",
     B("def test_wellbore_rs_never_decreases") + "\n\n    def test_wellbore_warms_monotonically(self, results):", "шаг 1.2 тест монотонности")
edit("tests/test_config.py", "class TestValidationThermal:", B("class TestNewtonCellTolValidation") + "\n\n\nclass TestValidationThermal:", "шаг 1.3 класс тестов")

if "--upto3" in sys.argv:   # состояние после шага 3: проверка «1 failed в быстром уровне»
    print("готово (шаги 1–3)")
    raise SystemExit

# ── Шаг 4: числа тестов ──
edit("tests/test_examples.py", "R_s застывает (79.51 у забоя)", "R_s застывает (79.54 у забоя)", "шаг 4.1 docstring")
edit("tests/test_examples.py", B("assert final.Rs[0] == pytest.approx(79.51"), B("# BUG-022: 79.5367"), "шаг 4.1 утверждение")
edit("tests/test_prototype_activation_cap.py", "        sim, init, dt = _sim(N=N)\n",
     "        sim, init, dt = _sim(N=N)\n" + B("# BUG-022: тест — про стартовую точку") + "\n", "шаг 4.2 выключение условия")
edit("tests/test_prototype_activation_cap.py", "    def test_without_cap_fails(self):",
     B("def test_first_day_with_cell_tol") + "\n\n    def test_without_cap_fails(self):", "шаг 4.2 новый тест")
PS = "tests/test_prototype_phase_switching.py"
for old, new in (("assert len(ok) == 60", "assert len(ok) == 70"), ("assert len(failed) == 34", "assert len(failed) == 41"),
                 ("approx(185.3065, abs=1e-3)", "approx(185.3236, abs=1e-3)"),
                 ("approx(397.8867, abs=1e-3)", "approx(397.8869, abs=1e-3)")):
    edit(PS, old, new, f"шаг 4.3 {new}")
edit(PS, B("Замер плана DEBT-015: 60 принятых"), B("Замер плана BUG-022: 70 принятых"), "шаг 4.3 docstring")
print("готово")
