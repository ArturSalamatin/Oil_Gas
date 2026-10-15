"""BUG-029, аудит 1: блоки «До/После» плана на копии дерева — красное и зелёное состояние тестов."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

SOLVER = Path(__file__).resolve().parents[4] / "numerical_solver"
HERE = Path(__file__).resolve().parent
COPY = HERE / "plan_copy"
OUT = []


def log(s=""):
    print(s)
    OUT.append(str(s))


def replace(rel, old, new):
    """Замена ровно одного вхождения old в файле копии; иначе — остановка."""
    p = COPY / rel
    text = p.read_text(encoding="utf-8")
    n = text.count(old)
    if n != 1:
        log(f"!!! {rel}: вхождений «До» = {n}, ожидалось 1:\n{old[:200]}")
        raise SystemExit(1)
    p.write_text(text.replace(old, new), encoding="utf-8")


def pytest(*args):
    env = {**os.environ, "PYTHONPATH": str(COPY), "PYTHONDONTWRITEBYTECODE": "1",
           "PYTHONIOENCODING": "utf-8"}
    r = subprocess.run([sys.executable, "-m", "pytest", *args, "-q", "-p", "no:cacheprovider",
                        "--rootdir", str(COPY)], cwd=COPY, env=env, capture_output=True,
                       text=True, encoding="utf-8")
    tail = [ln for ln in r.stdout.splitlines() if ln.strip()][-12:]
    return "\n".join(tail)


# ── Копия: пакет, нужные тесты, конфиги, постановка, .py/.md примеров ──
if COPY.exists():
    shutil.rmtree(COPY)
shutil.copytree(SOLVER / "gpn_multiphase_solver", COPY / "gpn_multiphase_solver",
                ignore=shutil.ignore_patterns("__pycache__"))
(COPY / "tests").mkdir(parents=True)
for name in ("test_config.py", "conftest.py", "test_eq_references.py"):
    shutil.copy2(SOLVER / "tests" / name, COPY / "tests" / name)
shutil.copytree(SOLVER / "tests" / "data", COPY / "tests" / "data")
shutil.copytree(SOLVER / "configs", COPY / "configs")
(COPY / "doc").mkdir()
shutil.copy2(SOLVER / "doc" / "problem_statement.tex", COPY / "doc" / "problem_statement.tex")
for f in list((SOLVER / "examples").rglob("*.py")) + list((SOLVER / "examples").rglob("*.md")):
    dst = COPY / f.relative_to(SOLVER)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(f, dst)

env = {**os.environ, "PYTHONPATH": str(COPY)}
r = subprocess.run([sys.executable, "-c", "import gpn_multiphase_solver as g; print(g.__file__)"],
                   env=env, capture_output=True, text=True, cwd=COPY)
log(f"пакет копии: {r.stdout.strip()}")

log("=== База (копия без правок) ===")
log(pytest("tests/test_config.py", "-k", "TestValidationWell"))

# ── Шаг 1: тесты ──
T = "tests/test_config.py"
replace(T,
        "- Скважина: skin ≥ 0 (отказ с обходом через r_well), предупреждения при skin > 50\n"
        "  и при p_wf / min_bhp ≥ p0 в объекте истории (DEBT-056).\n",
        "- Скважина: skin ≥ 0 (отказ с обходом через r_well), предупреждения при skin > 50\n"
        "  и при p_wf / min_bhp ≥ p0 в объекте истории (DEBT-056); при skin > 0 —\n"
        "  скин не входит в уравнение энергии (BUG-029).\n")
replace(T,
        '        {"dt": 86400, "control": "pressure", "p_wf": 10e6}, second]\n'
        "    return raw\n\n\n",
        '        {"dt": 86400, "control": "pressure", "p_wf": 10e6}, second]\n'
        "    return raw\n\n\n"
        "# Признаки двух предупреждений о скине — фрагменты, которых нет в другом\n"
        "# сообщении: доля притока при s > 50 (DEBT-056) и скин вне уравнения\n"
        "# энергии при s > 0 (BUG-029)\n"
        '_INFLOW = "от притока без скина"\n'
        '_ENERGY = "В уравнении энергии его нет"\n\n\n')
replace(T,
        '    """Скин ≥ 0; предупреждения при skin > 50 и при p_wf, min_bhp ≥ p0 (DEBT-056)."""\n',
        '    """Скин ≥ 0; предупреждения при skin > 0 (BUG-029), > 50 и p_wf, min_bhp ≥ p0 (DEBT-056)."""\n')
replace(T, '''    # 50 — граница: предупреждение строго при s > 50 (решение пользователя)
    @pytest.mark.parametrize("skin", [0.0, 5.0, 50.0],
                             ids=["zero", "damaged", "threshold"])
    def test_skin_up_to_threshold_silent(self, tmp_path, caplog, skin):
        """0 ≤ s ≤ 50 — без отказа и без предупреждения."""
        raw = _minimal_raw()
        raw["numerics"] = {"skin": skin}
        with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
            cfg = load_config(_write_json(tmp_path, raw))
        assert cfg.numerics.skin == skin
        assert _warning_messages(caplog) == []
''', '''    def test_zero_skin_silent(self, tmp_path, caplog):
        """s = 0 (все конфиги проекта) — без отказа и без предупреждений."""
        raw = _minimal_raw()
        raw["numerics"] = {"skin": 0.0}
        with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
            cfg = load_config(_write_json(tmp_path, raw))
        assert cfg.numerics.skin == 0.0
        assert _warning_messages(caplog) == []

    # Скин входит только в гидродинамику (проводимость забойной грани); в
    # уравнении энергии забойная грань при добыче вклада не даёт (eq:QJT_disc,
    # eq:mdot_disc). Решение пользователя (BUG-029): предупреждать при любом
    # s > 0. О доле притока — строго при s > 50 (DEBT-056): здесь его нет
    @pytest.mark.parametrize("skin", [0.01, 5.0, 50.0],
                             ids=["small", "damaged", "threshold"])
    def test_positive_skin_warns_energy(self, tmp_path, caplog, skin):
        """0 < s ≤ 50 — одно предупреждение: скин не входит в уравнение энергии."""
        raw = _minimal_raw()
        raw["numerics"] = {"skin": skin}
        with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
            cfg = load_config(_write_json(tmp_path, raw))
        assert cfg.numerics.skin == skin
        msgs = _warning_messages(caplog)
        assert len(msgs) == 1
        assert _ENERGY in msgs[0]
        assert "numerics.skin" in msgs[0] and "T_wf" in msgs[0]

    # Установившийся однофазный приток: p_e − p_wf = qμ/(2πkh)·(ln(R_ext/r_w) + s),
    # из них qμ/(2πkh)·s — на скин-зоне; эта часть перепада в T не входит.
    # У _minimal_raw R_ext/r_w = 50/0.1 = 500, ln 500 = 6.2146
    def test_skin_energy_warning_gives_drawdown_share(self, tmp_path, caplog):
        """s = 2: доля депрессии на скин-зоне 2 / (ln 500 + 2) = 24.3 %."""
        raw = _minimal_raw()
        raw["numerics"] = {"skin": 2.0}
        with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
            load_config(_write_json(tmp_path, raw))
        energy = [m for m in _warning_messages(caplog) if _ENERGY in m]
        assert len(energy) == 1 and "24.3%" in energy[0]
''')
replace(T, '''        """s > 50 — предупреждение с именем поля; расчёт допускается."""
        raw = _minimal_raw()
        raw["numerics"] = {"skin": skin}
        with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
            cfg = load_config(_write_json(tmp_path, raw))
        assert cfg.numerics.skin == skin
        msgs = _warning_messages(caplog)
        assert len(msgs) == 1 and "numerics.skin" in msgs[0]
''', '''        """s > 50 — два предупреждения: о доле притока (DEBT-056) и о температуре (BUG-029)."""
        raw = _minimal_raw()
        raw["numerics"] = {"skin": skin}
        with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
            cfg = load_config(_write_json(tmp_path, raw))
        assert cfg.numerics.skin == skin
        msgs = _warning_messages(caplog)
        # По одному каждого вида, оба называют поле
        assert len(msgs) == 2
        assert sum(_INFLOW in m for m in msgs) == 1
        assert sum(_ENERGY in m for m in msgs) == 1
        assert all("numerics.skin" in m for m in msgs)
''')
replace(T, '''        assert "0.6%" in _warning_messages(caplog)[0]
''', '''        # Сообщение о притоке — по признаку, не по порядку: при s > 0 есть и второе
        inflow = [m for m in _warning_messages(caplog) if _INFLOW in m]
        assert len(inflow) == 1 and "0.6%" in inflow[0]
''')

log("=== Шаг 1: только тесты (ожидание: 7 failed, 17 passed) ===")
log(pytest("tests/test_config.py", "-k", "TestValidationWell"))
log("--- test_config.py целиком (ожидание: 7 failed, 312 passed) ---")
log(pytest("tests/test_config.py"))

# ── Шаг 2: io/config.py ──
C = "gpn_multiphase_solver/io/config.py"
replace(C,
        "    skin: float = 0.0                      # скин-фактор: ≥ 0, > 50 — предупреждение (DEBT-056)\n",
        "    # Скин-фактор: ≥ 0 (DEBT-056). Входит только в гидродинамику — сопротивлением\n"
        "    # забойной грани; в уравнение энергии не входит (BUG-029). Предупреждения:\n"
        "    # s > 0 — о температуре (BUG-029), s > 50 — о доле притока (DEBT-056)\n"
        "    skin: float = 0.0\n")
replace(C, "    _warn_large_skin(config)\n",
        "    _warn_large_skin(config)\n    _warn_skin_not_in_energy(config)\n")
replace(C, '''            f"Проверьте значение.")


def _warn_well_shut(''', '''            f"Проверьте значение.")


def _warn_skin_not_in_energy(cfg: SimulationConfig) -> None:
    """Предупреждение при s > 0: скин не входит в уравнение энергии (BUG-029). Ур. (eq:QJT_disc)."""
    # Скин в модели — только сопротивление забойной грани в гидродинамике:
    # проводимость 2πkh/(ln(r_1/r_w) + s) (прототип, well_transmissibility_m3).
    # В уравнении энергии забойная грань при добыче вклада не даёт: JT — с весом
    # Φ⁺ = 0 (eq:QJT_disc), перенос R_s — без состава за гранью (eq:mdot_disc).
    # Поэтому JT-нагрев нефти, охлаждение газа и теплота разгазирования на
    # перепаде скин-зоны в T не входят ни при каком N, и T_wf = T[0] их не
    # содержит (ssec:bc_disc). Знак потери без расчёта не известен: на
    # полуячейке у забоя примера 12 JT (+0.033 К) и дегазация (−0.032 К) почти
    # гасят друг друга (BUG-015). Модель не меняется — только предупреждение
    # (решение пользователя, BUG-029).
    # Доля депрессии на скин-зоне в установившемся однофазном притоке:
    # p_e − p_wf = qμ/(2πkh)·(ln(R_ext/r_w) + s), из них qμ/(2πkh)·s — на скин-зоне.
    s = cfg.numerics.skin
    if s > 0:
        g = cfg.geometry
        ln_re_rw = np.log(g.R_ext / g.r_well)
        share = s / (ln_re_rw + s)
        user_log.warning(
            f"numerics.skin = {s} > 0: скин учитывается только в гидродинамике "
            f"(сопротивление забойной грани). В уравнении энергии его нет: "
            f"дросселирование (эффект Джоуля–Томсона) и разгазирование на перепаде "
            f"давления скин-зоны в температуру не входят, и температура забоя T_wf "
            f"их не содержит. В установившемся однофазном притоке на скин-зону "
            f"приходится {share:.1%} депрессии (s / (ln(R_ext/r_w) + s), "
            f"ln(R_ext/r_w) = {ln_re_rw:.3g}).")


def _warn_well_shut(''')

log("=== Шаг 2: io/config.py (ожидание: 24 passed; test_config 319 passed) ===")
log(pytest("tests/test_config.py", "-k", "TestValidationWell"))
log(pytest("tests/test_config.py"))
log("--- test_eq_references.py ---")
log(pytest("tests/test_eq_references.py"))

# ── Шаг 3: state.py ──
replace("gpn_multiphase_solver/state.py",
        "    p_wf: float        # забойное давление, Па\n"
        "    T_wf: float        # забойная температура, К: T[0] — центр r_0 ячейки 0 (BUG-015)\n",
        "    p_wf: float        # забойное давление, Па\n"
        "    # При скине s > 0 T_wf не содержит дросселирования и разгазирования на\n"
        "    # перепаде скин-зоны: скин входит только в гидродинамику (BUG-029)\n"
        "    T_wf: float        # забойная температура, К: T[0] — центр r_0 ячейки 0 (BUG-015)\n")
log("=== Шаг 3: state.py ===")
log(pytest("tests/test_config.py", "tests/test_eq_references.py"))

# ── Проба шага 3 плана (текст из плана), запуск из корня копии ──
PROBE = '''"""BUG-029: предупреждение о скине видно при загрузке конфига в свежем процессе (без caplog)."""
import json
import os
import subprocess
import sys
from pathlib import Path

SOLVER = Path.cwd()  # запуск из numerical_solver/ worktree
HERE = Path(__file__).resolve().parent
base = json.loads((SOLVER / "configs" / "baseline.json").read_text(encoding="utf-8"))
# Дочерний процесс пишет stderr в UTF-8 — кириллица сообщения без порчи
env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
out = []

for s in (0.0, 2.0, 100.0):
    raw = {**base, "numerics": {**base.get("numerics", {}), "skin": s}}
    cfg = HERE / f"baseline_skin{s:g}.json"
    cfg.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    # Свежий процесс: обработчиков журнала нет (setup_logging — в фабрике),
    # запись WARNING печатает резервный обработчик logging в stderr
    code = ("import gpn_multiphase_solver as g; print(g.__file__); "
            "from gpn_multiphase_solver.io.config import load_config; "
            f"load_config(r'{cfg}')")
    r = subprocess.run([sys.executable, "-c", code], capture_output=True,
                       text=True, encoding="utf-8", env=env, cwd=SOLVER)
    out += [f"--- skin = {s:g}: код возврата {r.returncode}",
            f"stdout: {r.stdout.strip()}",
            f"stderr: {r.stderr.strip() or '(пусто)'}"]

# Вывод — файлом в UTF-8: конвейер PowerShell 5.1 портит кириллицу
(HERE / "warn_visible.out.txt").write_text("\\n".join(out) + "\\n", encoding="utf-8")
print(f"записано: {HERE / 'warn_visible.out.txt'}")
'''
(COPY / "warn_visible.py").write_text(PROBE, encoding="utf-8")
r = subprocess.run([sys.executable, str(COPY / "warn_visible.py")], cwd=COPY,
                   env={**os.environ, "PYTHONPATH": str(COPY)}, capture_output=True,
                   text=True, encoding="utf-8")
log("=== Проба шага 3 (warn_visible.py плана) ===")
log(f"код {r.returncode}; stderr: {r.stderr.strip() or '(пусто)'}")
log((COPY / "warn_visible.out.txt").read_text(encoding="utf-8")
    if (COPY / "warn_visible.out.txt").exists() else "(нет вывода)")

log("=== Длины изменённых строк > 100 ===")
for rel in (T, C, "gpn_multiphase_solver/state.py"):
    old = (SOLVER / rel).read_text(encoding="utf-8").splitlines()
    for i, ln in enumerate((COPY / rel).read_text(encoding="utf-8").splitlines(), 1):
        if len(ln) > 100 and ln not in old:
            log(f"{rel}:{i}: {len(ln)} симв.")
log("(конец списка)")

(HERE / "plan_check.out.txt").write_text("\n".join(OUT) + "\n", encoding="utf-8")
