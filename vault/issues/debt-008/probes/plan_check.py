r"""DEBT-008, аудит 2: блоки «До/После» плана, применённые дословно к копии дерева.

Запуск из numerical_solver/ основного каталога:
    .venv\Scripts\python ..\vault\issues\debt-008\probes\plan_check.py
Копия — vault/issues/debt-008/probes/plan_tree/ (gpn_multiphase_solver, tests, configs,
examples без output/, doc, pyproject.toml, HydroSolverPrototype). Удаляется в конце. Блоки кода берутся из плана по якорям
пунктов; каждая замена «До → После» обязана найти ровно одно вхождение. Прозаические
правки (шаг 3 п. 10, шаг 5) переписаны сюда дословно по тексту плана.
Состояния (после каждого — быстрый уровень pytest в копии):
  S1 — шаг 1 (тесты): ожидание 55 failed;  S2 — + шаг 2 (JSON, конвертер): 31;
  S3 — + шаг 3 (config.py): 8;  S4 — + шаг 4 (фабрика, адаптер): 1;  S5 — + шаг 5: 0;
  S6 — + шаг 6 (README): быстрый уровень целиком.
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

SOLVER = Path.cwd()
if not (SOLVER / "gpn_multiphase_solver").is_dir():
    sys.exit(f"Запускать из numerical_solver/, не из {SOLVER}")
ROOT = SOLVER.parent
PLAN = ROOT / "vault" / "plans" / "debt-008 dead-config-fields.md"
PROBES = Path(__file__).resolve().parent
TREE = PROBES / "plan_tree"
PY = sys.executable
TEXT = PLAN.read_text(encoding="utf-8")


# ── Разбор плана ──

def section(title: str) -> str:
    """Текст шага плана от заголовка «### <title>» до следующего «### »."""
    start = TEXT.index(f"### {title}")
    end = TEXT.find("\n### ", start + 4)
    return TEXT[start:end if end > 0 else len(TEXT)]


def blocks_after(text: str, anchor: str, count: int) -> list[str]:
    """count fenced-блоков после якоря; отступ пункта списка снимается по открывающей ```."""
    assert text.count(anchor) == 1, f"якорь не единственный ({text.count(anchor)}): {anchor}"
    lines = text[text.index(anchor):].splitlines()
    out, i = [], 0
    while len(out) < count:
        m = re.match(r"^( *)```", lines[i])
        if m:
            ind = len(m.group(1))
            body, i = [], i + 1
            while not re.match(r"^ *```\s*$", lines[i]):
                body.append(lines[i][ind:] if lines[i].strip() else "")
                i += 1
            out.append("\n".join(body) + "\n")
        i += 1
    return out


def inline_after(text: str, anchor: str, n: int = 1) -> str:
    """n-й фрагмент в обратных кавычках после якоря."""
    tail = text[text.index(anchor) + len(anchor):]
    return re.findall(r"`([^`]+)`", tail)[n - 1]


def once(text: str, old: str, new: str, what: str) -> str:
    n = text.count(old)
    assert n == 1, f"{what}: «До» найдено {n} раз"
    return text.replace(old, new)


def edit(rel: str, fn) -> None:
    p = TREE / rel
    p.write_text(fn(p.read_text(encoding="utf-8")), encoding="utf-8")


# ── Копия дерева ──

def make_tree() -> None:
    if TREE.exists():
        shutil.rmtree(TREE)
    ignore = shutil.ignore_patterns("output", "__pycache__", "*.emf", "*.svg", "*.png", "*.npz")
    # Прототип копируется целиком (~24 МБ): ссылка-каталог опасна — rmtree мог бы уйти в оригинал
    for d in ("gpn_multiphase_solver", "tests", "configs", "examples", "doc", "HydroSolverPrototype"):
        shutil.copytree(SOLVER / d, TREE / d,
                        ignore=shutil.ignore_patterns("__pycache__", "OUTPUT*")
                        if d == "HydroSolverPrototype" else ignore)
    shutil.copy2(SOLVER / "pyproject.toml", TREE / "pyproject.toml")
    # Страж: pytest копии обязан импортировать пакет копии, а не основного каталога
    with open(TREE / "tests" / "conftest.py", "a", encoding="utf-8") as f:
        f.write("\n\nimport gpn_multiphase_solver as _g_debt008\n"
                "from pathlib import Path as _P_debt008\n"
                "assert _P_debt008(_g_debt008.__file__).resolve().is_relative_to("
                "_P_debt008(__file__).resolve().parents[1]), _g_debt008.__file__\n")


def fast(tag: str, expect: int | None) -> list[str]:
    r = subprocess.run([PY, "-m", "pytest", "tests/", "-m", "not slow", "-q", "-rf",
                        "-p", "no:cacheprovider"], cwd=TREE, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    failed = [ln[7:].split(" - ")[0] for ln in r.stdout.splitlines() if ln.startswith("FAILED ")]
    errors = [ln for ln in r.stdout.splitlines() if ln.startswith("ERROR ")]
    last = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-500:]
    ok = expect is None or (len(failed) == expect and not errors and r.returncode in (0, 1)
                            and " passed" in last)
    print(f"{tag}: {last}  [ожидание {expect} failed — {'OK' if ok else 'РАСХОЖДЕНИЕ'}]")
    by_file: dict[str, int] = {}
    for t in failed:
        key = t.split("::")[0] + ("::" + t.split("::")[1] if "::" in t else "")
        key = re.sub(r"\[.*", "", key)
        by_file[key] = by_file.get(key, 0) + 1
    for k, v in sorted(by_file.items()):
        print(f"    {v:3d}  {k}")
    for e in errors:
        print("   ", e)
    if r.returncode not in (0, 1):
        print(r.stdout[-3000:], r.stderr[-3000:])
    return failed


# ── Шаг 1: тесты ──

def step1() -> None:
    s = section("Шаг 1:")
    hdr, = blocks_after(s, "1. `test_config.py`, шапка модуля", 1)
    new_sec, = blocks_after(s, "2. `test_config.py` — новый раздел", 1)
    frame = "# ═════════════════════════════════════════════════════════════\n# E. Мульти"

    def tc(t):
        t = once(t, "- Минимальный конфиг: только обязательные секции.\n",
                 "- Минимальный конфиг: только обязательные секции.\n" + hdr, "шапка test_config")
        return once(t, frame, new_sec + "\n\n" + frame, "раздел D2 test_config")
    edit("tests/test_config.py", tc)

    two, sup = blocks_after(s, "3. `test_factory_prototype.py`", 2)
    a1 = "        assert simulator._max_retries == 9\n\n"
    a2 = ("        config.initial_conditions.p0 = 15e6 - 1.0\n"
          "        SimulatorFactory.from_config(config)\n\n")
    edit("tests/test_factory_prototype.py",
         lambda t: once(once(t, a1, a1 + two + "\n", "после default_max_retries"),
                        a2, a2 + sup + "\n", "после p0_1pa"))

    adapter_tests, = blocks_after(s, "4. `test_prototype_adapter.py` — в конец файла", 1)
    edit("tests/test_prototype_adapter.py",
         lambda t: t.rstrip("\n") + "\n\n\n" + adapter_tests)

    repl, new_fn = blocks_after(s, "5. `test_rs_analytics.py`:", 2)

    def rs(t):
        t = once(t, "Rs <= Rs_eq(p) + RS_TOL —", "Rs <= Rs_eq(p) + rs_switch_tol —", "шапка rs")
        start = t.index("def test_supersaturation_within_solver_tolerance_is_accepted")
        end = t.index("\n\n\ndef ", start) + 1
        return t[:start] + repl + "\n\n" + new_fn + t[end:]
    edit("tests/test_rs_analytics.py", rs)

    ex, = blocks_after(s, "6. `test_examples.py`, `TestConfigs.test_no_dead_output_format`", 1)

    def te(t):
        start = t.index('    @pytest.mark.parametrize("name", ALL_EXAMPLES)\n'
                        "    def test_no_dead_output_format")
        end = t.index("\n\n", t.index("мёртвое поле output.format в конфиге", start)) + 1
        return t[:start] + ex + t[end:]
    edit("tests/test_examples.py", te)


# ── Шаг 2: JSON и конвертер ──

def step2() -> None:
    r = subprocess.run([PY, str(PROBES / "strip_removed_keys.py"), "--write"], cwd=TREE,
                       capture_output=True, text=True, encoding="utf-8")
    print("   strip:", r.stdout.strip().splitlines()[-1], r.stderr[-300:])
    s = section("Шаг 2:")
    old, new = blocks_after(s, "Конвертер `examples/18_prototype_input/prototype_input.py`", 2)
    edit("examples/18_prototype_input/prototype_input.py", lambda t: once(t, old, new, "конвертер"))


# ── Шаг 3: io/config.py ──

def step3() -> None:
    s = section("Шаг 3:")
    cfg = "gpn_multiphase_solver/io/config.py"

    def c(t):
        old1 = inline_after(s, "1. `GridConfig.type` (`:35`). До: ") + "\n"
        new1, = blocks_after(s, "1. `GridConfig.type`", 1)
        t = once(t, old1, new1, "GridConfig.type")
        old2, new2 = blocks_after(s, "2. `RockConfig`, конец", 2)
        t = once(t, old2, new2, "RockConfig")
        old3 = inline_after(s, "3. `TimeConfig` (`:134`): строку ") + "\n"
        t = once(t, old3, "", "TimeConfig.start_day")
        old4, new4, new4b = blocks_after(s, "4. `NumericsConfig` (`:141-155`)", 3)
        t = once(t, old4, new4, "NumericsConfig")
        old4b = inline_after(s, "последнюю строку комментария (`:179`). До: ") + "\n"
        t = once(t, old4b, new4b, "строка newton_cell_tol")
        old5, new5 = blocks_after(s, "5. `OutputConfig`", 2)
        t = once(t, old5, new5, "OutputConfig")
        consts, = blocks_after(s, "6. Перед заголовком `# ── Загрузка", 1)
        t = once(t, "# ── Загрузка ─", consts + "\n\n# ── Загрузка ─", "константы перед load_config")
        ins1, ins2 = blocks_after(s, "7. `load_config` (`:300-365`), две вставки", 2)
        a = ("            raise ValueError(f\"Отсутствует обязательная секция '{key}' в {path}\")\n")
        t = once(t, a, a + ins1, "вставка 1 load_config")
        b = "    _warn_large_skin(config)\n"
        t = once(t, b, ins2 + b, "вставка 2 load_config")
        g, = blocks_after(s, "8. `_validate` — после проверки `grid.N`", 1)
        n = '        raise ValueError(f"N должен быть ≥ 1, получено {cfg.grid.N}")\n'
        t = once(t, n, n + g, "grid.type в _validate")
        tail, = blocks_after(s, "9. `_validate` — в конец", 1)
        e = '            f"получено {ct!r}")\n'
        t = once(t, e, e + tail, "конец _validate")
        return t
    edit(cfg, c)

    # п. 10 — дословно по тексту плана
    def tc(t):
        t = once(t, "    def test_start_day(self, cfg):\n        assert cfg.time.start_day == 0.0\n\n",
                 "", "test_start_day")
        t = once(t, "    def test_dt_min(self, cfg):\n        assert cfg.numerics.dt_min == 1.0\n\n"
                    "    def test_dt_max_default(self, cfg):\n"
                    "        \"\"\"dt_max не задан в baseline → default = 86400.\"\"\"\n"
                    "        assert cfg.numerics.dt_max == 86400.0\n\n", "", "dt_min/dt_max")
        t = once(t, "    def test_format(self, cfg):\n        assert cfg.output.format == \"npz\"\n\n",
                 "", "test_format")
        t = once(t, "        assert cfg.numerics.dt_min == 1.0\n",
                 "        assert cfg.numerics.max_active_set_iter == 12\n", "no_numerics")
        t = once(t, "        assert cfg.output.format == \"npz\"\n", "", "no_output")
        t = once(t, "их не меньше 37.", "их не меньше 31.", "докстринг стража")
        t = once(t, "        assert len(_FLOAT_FIELDS) >= 37\n",
                 "        # 37 до DEBT-008: удалены p_ref, start_day, dt_min, dt_max, newton_rtol, "
                 "newton_atol\n        assert len(_FLOAT_FIELDS) >= 31\n", "порог стража")
        return t
    edit("tests/test_config.py", tc)


# ── Шаг 4: фабрика и адаптер ──

def step4() -> None:
    s = section("Шаг 4:")

    def f(t):
        old1 = inline_after(s, "1. `factory.py`, вызов (`:58`). До: ") + "\n"
        new1, = blocks_after(s, "1. `factory.py`, вызов", 1)
        t = once(t, old1, new1, "вызов _check_undersaturated_start")
        old2, new2 = blocks_after(s, "2. `factory.py`, константа и функция", 2)
        t = once(t, old2, new2, "константа и функция")
        t = once(t, "if ic.Rs0 > Rs_eq + _RS0_SUPERSAT_TOL:", "if ic.Rs0 > Rs_eq + rs_tol:", "условие")
        old3 = inline_after(s, "3. `factory.py`, `CompressibleRock` (`:410-415`). Комментарий ") + "\n"
        new3, = blocks_after(s, "3. `factory.py`, `CompressibleRock`", 1)
        t = once(t, old3, new3, "комментарий породы")
        ins4, = blocks_after(s, "4. `factory.py`, `RadialBlackOilModel(...)`", 1)
        t = once(t, "        skin=nc.skin,\n", "        skin=nc.skin,\n" + ins4, "rs/sg_switch_tol")
        old5, new5 = blocks_after(s, "5. `factory.py`, последняя строка", 2)
        return once(t, old5, new5, "return PrototypeHydroAdapter")
    edit("gpn_multiphase_solver/factory.py", f)

    def a(t):
        sig, doc, body = blocks_after(s, "6. `prototype_adapter.py`, конструктор", 3)
        t = once(t, "                 stage4_memory: int | None = STAGE4_MEMORY):\n", sig,
                 "сигнатура адаптера")
        d = "                        сразу ею (DEBT-048); None — память выключена\n"
        t = once(t, d, d + doc, "докстринг адаптера")
        k = "        self._stage4_key = None\n"
        t = once(t, k, k + body, "тело конструктора")
        old7, new7 = blocks_after(s, "7. `prototype_adapter.py`, `solve`", 2)
        return once(t, old7, new7, "вызовы advance")
    edit("gpn_multiphase_solver/hydro/prototype_adapter.py", a)


# ── Шаг 5: rs_analytics — дословно по тексту плана ──

def step5() -> None:
    s = section("Шаг 5:")

    def r(t):
        t = once(t, "до допуска решателя RS_TOL).", "до допуска решателя rs_switch_tol).", "шапка :10")
        t = once(t, "Rs > Rs_eq(p) + RS_TOL, а выключается", "Rs > Rs_eq(p) + rs_switch_tol, а выключается",
                 "шапка :28")
        start = t.index("# Допуск пересыщения ячейки без газа")
        end = t.index("RS_TOL = 1e-5\n") + len("RS_TOL = 1e-5\n")
        t = t[:start] + t[end:]
        old_doc, new_doc = blocks_after(s, "3. `rs_supersaturation`", 2)
        t = once(t, old_doc, new_doc, "rs_supersaturation")
        t = once(t, "excess > RS_TOL", "excess > tol", "excess > tol")
        st = "    st = history.states[-1]\n    d_abs, d_rel = rs_error(config, history, pvt)\n"
        t = once(t, st, "    st = history.states[-1]\n"
                        "    tol = config.numerics.rs_switch_tol      # допуск пересыщения решателя (DEBT-008)\n"
                        "    d_abs, d_rel = rs_error(config, history, pvt)\n", "tol в report_rs")
        t = once(t, "rs_supersaturation(history, pvt)\n", "rs_supersaturation(history, pvt, tol)\n",
                 "вызов rs_supersaturation")
        t = once(t, "st.Rs > Rs0 + RS_TOL", "st.Rs > Rs0 + tol", "n_above")
        t = once(t, "{RS_TOL:g}", "{tol:g}", "печать")
        assert "RS_TOL" not in t, "RS_TOL остался"
        return t
    edit("examples/rs_analytics.py", r)
    blank = re.search(r"SG_GAS = 1e-8\n(\n*)def rs_expected",
                      (TREE / "examples/rs_analytics.py").read_text(encoding="utf-8"))
    print(f"   пустых строк между SG_GAS и def rs_expected: {len(blank.group(1)) - 1}")


def step6() -> None:
    r = subprocess.run([PY, str(PROBES / "fix_readmes.py"), "--write"], cwd=TREE,
                       capture_output=True, text=True, encoding="utf-8")
    print("   fix_readmes:", r.stdout.strip().splitlines()[-1], r.stderr[-300:])


def main() -> None:
    # --probe: все шаги без прогонов pytest, затем проба red_state.py на итоговом дереве
    # (ожидания шага 8 плана); быстрее полного режима в ~20 раз
    probe_only = "--probe" in sys.argv[1:]
    run = (lambda *a: None) if probe_only else fast
    make_tree()
    try:
        step1(); run("S1 шаг 1", 55)
        step2(); run("S2 + шаг 2", 31)
        step3(); run("S3 + шаг 3", 8)
        step4(); run("S4 + шаг 4", 1)
        step5(); run("S5 + шаг 5", 0)
        step6(); run("S6 + шаг 6", 0)
        if probe_only:
            r = subprocess.run([PY, str(PROBES / "red_state.py")], cwd=TREE, capture_output=True,
                               text=True, encoding="utf-8", errors="replace")
            print(r.stdout, r.stderr[-2000:])
    finally:
        shutil.rmtree(TREE, ignore_errors=True)


if __name__ == "__main__":
    main()
