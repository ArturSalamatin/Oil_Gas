"""FEAT-032 (аудит): применить код плана к копии дерева probes/tree/numerical_solver.

Блоки кода берутся из текста плана (```python … ```) — проверяется сам план, а не
пересказ. Каждый «До» обязан встретиться в файле копии ровно один раз (иначе Edit
реализации не найдёт место). Вставки — после якоря, который тоже обязан быть
единственным. Печать: номер блока плана и первая строка — для сверки соответствия.

Копию скрипт создаёт сам: пакет, тесты, примеры (без output/), конфиги, doc,
pyproject.toml; прототип — ссылкой-junction на основной каталог (не копируется).
Прогоны в копии (из probes\\tree\\numerical_solver, python основного venv):
  pytest tests/ --collect-only -q          — 1806 (быстрый уровень 1533)
  pytest tests/ -m "not slow" -q           — 1533 passed (аудит 2026-10-13)
  <P>\\fingerprint_examples.py              — 0 расхождений из 23
Удаление копии — СНАЧАЛА ссылка, потом каталог (Remove-Item -Recurse через
junction в PowerShell 5.1 может удалить содержимое прототипа), и не из сессии,
стоящей внутри копии:
  cmd /c rmdir <probes>\\tree\\numerical_solver\\HydroSolverPrototype
  cmd /c rmdir /s /q <probes>\\tree

Запуск (из корня проекта): numerical_solver\\.venv\\Scripts\\python <этот файл>
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PLAN = ROOT / "vault" / "plans" / "feat-032 ramp-step-after-control-change.md"
SRC = ROOT / "numerical_solver"
TREE = HERE / "tree" / "numerical_solver"
for _s in (sys.stdout, sys.stderr):
    _s.reconfigure(encoding="utf-8", errors="replace")

# ── Копия дерева ──
if TREE.parent.exists():
    sys.exit(f"{TREE.parent} уже есть — удалите (порядок — в docstring) и запустите снова")
ignore = shutil.ignore_patterns("output", "__pycache__", ".pytest_cache", "*.pyc",
                                "*.png", "*.emf", "*.pdf", "*.aux", "*.log")
for d in ("gpn_multiphase_solver", "tests", "examples", "configs", "doc"):
    shutil.copytree(SRC / d, TREE / d, ignore=ignore)
shutil.copy2(SRC / "pyproject.toml", TREE / "pyproject.toml")
subprocess.run(["cmd", "/c", "mklink", "/J", str(TREE / "HydroSolverPrototype"),
                str(SRC / "HydroSolverPrototype")], check=True, capture_output=True)
print(f"копия: {TREE}")

text = PLAN.read_text(encoding="utf-8")
blocks = [m.group(1) for m in re.finditer(r"^[ ]*```python\n(.*?)^[ ]*```", text, re.S | re.M)]
print(f"блоков python в плане: {len(blocks)}")
for i, b in enumerate(blocks):
    first = next((ln for ln in b.splitlines() if ln.strip()), "")
    print(f"  [{i:2d}] {first.strip()[:90]}")


def B(i, starts):
    """Блок плана i; первая непустая строка обязана начинаться с starts — защита от сдвига нумерации."""
    b = blocks[i]
    first = next(ln for ln in b.splitlines() if ln.strip()).strip()
    assert first.startswith(starts), f"блок {i}: «{first[:60]}» не начинается с «{starts}»"
    return b


def edit(rel, old, new, count=1):
    """Заменить old на new в файле копии; old обязан встретиться ровно count раз."""
    p = TREE / rel
    s = p.read_text(encoding="utf-8")
    n = s.count(old)
    assert n == count, f"{rel}: «{old.strip()[:70]}…» встречается {n} раз, ожидалось {count}"
    p.write_text(s.replace(old, new), encoding="utf-8")
    print(f"  ок: {rel} — {old.strip().splitlines()[0][:70]}")


def insert_after(rel, anchor, new, count=1):
    edit(rel, anchor, anchor + new, count)


def insert_before(rel, anchor, new):
    edit(rel, anchor, new + anchor)


# ── Шаг 2: bc.py ──
P = "gpn_multiphase_solver/bc.py"
insert_after(P, '        """Забойное давление, Па."""\n        return self._p_wf\n',
             "\n" + B(0, "def __eq__"))
insert_after(P, '        """Минимальное забойное давление, Па."""\n        return self._min_bhp\n',
             "\n" + B(1, "def __eq__"))
T = "tests/test_rate_control.py"
insert_before(T, "# ═══════════════════════════════════════════════════════════\n# B. Фабрика",
              B(2, "class TestControlValueEquality") + "\n\n")
edit(T, "     дебиты прогона по давлению, повторяет его траекторию.\n",
     "     дебиты прогона по давлению, повторяет его траекторию.\n"
     "  D. Равенство управлений по значению (FEAT-032).\n")

# ── Шаг 3: config.py ──
C = "gpn_multiphase_solver/io/config.py"
edit(C, B(3, "@dataclass"), B(4, "@dataclass"))
insert_after(C, '        raise ValueError("history должна содержать хотя бы один интервал")\n',
             "\n" + B(5, "# dt_after_control_change"))
insert_before("tests/test_config.py", "class TestValidationThermal:",
              B(6, "class TestDtAfterControlChange") + "\n\n")

# ── Шаг 4: TimeSchedule, фабрика ──
S = "gpn_multiphase_solver/simulator.py"
edit(S, B(7, "def __init__"), B(8, "def __init__"))
insert_after(S, "        dt_actual = dt_hist / n_sub\n        return n_sub, dt_actual\n",
             "\n" + B(9, "def first_substep_depth"))
edit(S, "    Гарантия: n_sub · dt_actual = dt_hist точно (нет накопления ошибки округления).\n",
     "    Гарантия: n_sub · dt_actual = dt_hist точно (нет накопления ошибки округления).\n"
     "    Первый шаг интервала со сменой управления начинается с подшага dt/2**m (FEAT-032).\n")
edit("gpn_multiphase_solver/factory.py", B(10, "return TimeSchedule("), B(11, "return TimeSchedule("))
TS = "tests/test_simulator.py"
edit(TS, "from gpn_multiphase_solver.bc import PressureControl\n",
     "from gpn_multiphase_solver.bc import PressureControl, RateControl\n")
insert_after(TS, "    return TimeSchedule(dt_int, [ScheduleInterval(dt=dt_hist, bc=bc)])\n",
             "\n\n" + B(12, "def _schedule"))
insert_before(TS, "# ═══════════════════════════════════════════════════════════\n# B. Simulator.run()",
              B(13, "class TestFirstSubstepDepth") + "\n\n")
insert_after(TS, "        assert history.well_data[-1].q_o_std > 0\n", "\n" + B(14, "def test_dt_after"))

# ── Шаг 5: Simulator ──
edit(S, "  energy.solve → обновить state)\n\"\"\"",
     "  energy.solve → обновить state). Первый шаг интервала со сменой\n"
     "  управления начинается с подшага dt/2**m и растёт ×2 (FEAT-032)\n\"\"\"")
edit(S, B(15, "for k, interval"), B(16, "for k, interval"))
edit(S, B(17, "def _advance"), B(18, "def _advance"))
edit(S, B(19, "# Шаг dt в единицах"), B(20, "# Шаг dt в единицах"))
edit(S, B(21, "if size == 1:"), B(22, "if size == 1:"))
edit(S, B(23, "def _failure_message"), B(24, "def _failure_message"))
edit(S, B(25, "n_units = 2 ** self._max_retries"), B(26, "n_units = 2 ** (self._max_retries"))
edit(S, B(27, 'f"не сходится'), B(28, 'f"не сходится'))
insert_before(TS, "# ═══════════════════════════════════════════════════════════\n# G. Отказ при нефизичной",
              B(29, "def _ramp_run") + "\n\n")

# ── Шаг 6: test_val004 ──
V = "tests/test_val004.py"
insert_after(V, "    cfg.time.history = _shutin_history(cfg, k)\n", B(30, "# Шаги серии"), count=2)
insert_after(V, '    return {"end": hist.states[-1], "n_forced": len(forced), '
                '"n_records": len(hist.times)}\n', "\n\n" + B(31, "def _run_1h_shutin"))
p = TREE / V
p.write_text(p.read_text(encoding="utf-8").rstrip("\n") + "\n\n\n" + B(32, "@pytest.fixture"),
             encoding="utf-8")
print(f"  ок: {V} — фикстура и класс в конец")

# ── Шаг 7: конфиги и тесты 16/17 ──
for ex in ("16_well_shut_in", "17_shut_in_strong_cooling"):
    edit(f"examples/{ex}/config.json", '    "dt_integration": 3600,\n',
         '    "dt_integration": 3600,\n    "dt_after_control_change": 2.0,\n')

E = TREE / "tests/test_examples.py"
s = E.read_text(encoding="utf-8")
i16 = s.index("class TestWellShutIn:")
i17 = s.index("class TestShutInStrongCooling:")
iend = s.index("\n# ═", i17)
c16, c17 = s[i16:i17], s[i17:iend]
anchor = "        assert cfg.time.dt_integration == 3600.0\n"
assert c16.count(anchor) == 1 and c17.count(anchor) == 1
c16 = c16.replace(anchor, anchor + B(33, "# FEAT-032 (решение"))
c17 = c17.replace(anchor, anchor + B(35, "# FEAT-032 (решение"))


def replace_method(cls, name, new):
    a = cls.index(f"    def {name}(")
    b = cls.index("\n    def ", a + 1) + 1
    return cls[:a] + new.rstrip("\n") + "\n\n" + cls[b:]


c16 = replace_method(c16, "test_wellbore_heats_then_relaxes", B(34, "def test_wellbore_heats"))
for old, new in (("approx(24.5554e6, rel=1e-4)", "approx(25.4409e6, rel=1e-4)"),
                 ("approx(1.775e11, rel=2e-3)", "approx(1.776e11, rel=2e-3)"),
                 ("approx(3.962e10, rel=2e-3)", "approx(3.958e10, rel=2e-3)")):
    assert c17.count(old) == 1, old
    c17 = c17.replace(old, new)
old36 = B(36, "# BUG-022: 79.5367")
assert c17.count(old36) == 1, "блок 36 (До R_s 17) не найден"
c17 = c17.replace(old36, B(37, "# FEAT-032: 79.5875"))
c17 = replace_method(c17, "test_wellbore_warms_monotonically", B(38, "def test_wellbore_warms"))
E.write_text(s[:i16] + c16 + c17 + s[iend:], encoding="utf-8")
print("  ок: tests/test_examples.py — 16 и 17")
edit("tests/test_energy_matrix_examples.py", B(39, "# 16_well_shut_in не дробится"),
     B(40, "# 16_well_shut_in не дробится"))
print("ГОТОВО")
