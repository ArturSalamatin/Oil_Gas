"""Smoke-тесты для примеров из examples/ (FEAT-013).

Проверяет:
  A. Структура: каждая подпапка содержит config.json, main.py, README.md
  B. Конфиги: load_config проходит, CSV на месте, нет мёртвых полей
  C. Расчёт: все 10 сценариев считаются без NaN/Inf, Sg ∈ [0,1], p > 0, T > 0
  D. Физика по семействам: однофазные без газа, двухфазные с газом
  E. Суперпозиция тепловых вкладов: (T08-T07) + (T09-T07) = T04-T07
  F. Расщепление: термика не влияет на гидродинамику (побитово)
  G. README: обязательные разделы на месте

Расчёты кэшируются на уровне сессии (fixture EXAMPLE_RESULTS): каждый
сценарий считается один раз, около 1 с на сценарий.
"""

import json
from pathlib import Path

import numpy as np
import pytest

from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.io.config import load_config

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"

# Все сценарии по номерам папок.
ALL_EXAMPLES = [
    "01_single_phase_no_jt",
    "02_single_phase_jt",
    "03_standing_corey",
    "04_table_table",
    "05_standing_table_rp",
    "06_table_corey_rp",
    "07_degassing_adiabatic_only",
    "08_degassing_jt",
    "09_degassing_latent_heat",
    "10_deep_degassing",
]

# Семейство 1: Rs0 = 0 → газ не выделяется ни при каком давлении.
SINGLE_PHASE = ["01_single_phase_no_jt", "02_single_phase_jt"]

# Семейства 2 и 3: pwf < pb → разгазирование обязано произойти.
TWO_PHASE = [n for n in ALL_EXAMPLES if n not in SINGLE_PHASE]

# Сценарии с табличной ОФП (Sg мала) — им нужен раздел про увеличение Sg.
NEEDS_SG_SECTION = [
    "04_table_table", "06_table_corey_rp",
    "07_degassing_adiabatic_only", "08_degassing_jt",
    "09_degassing_latent_heat", "10_deep_degassing",
]


# ── Кэш расчётов ─────────────────────────────────────────────

def _run(name: str) -> dict:
    """Прогнать один пример, вернуть срез результатов."""
    cfg = load_config(EXAMPLES_DIR / name / "config.json")
    simulator, initial = SimulatorFactory.from_config(cfg)
    history = simulator.run(initial)
    final = history.states[-1]
    return {
        "history": history,
        "grid": simulator._grid,
        # config нужен балансу энергии: compute_balance(history, grid, config)
        # пересобирает по нему PVT и rock (FEAT-016).
        "config": cfg,
        "Rs0": cfg.initial_conditions.Rs0,
        "p": final.p,
        "T": final.T,
        "Sg": final.Sg,
        "Rs": final.Rs,
        "T_well": float(final.T[0]),
        "q_o": np.array([w.q_o_std for w in history.well_data]),
        "q_g": np.array([w.q_g_std for w in history.well_data]),
    }


@pytest.fixture(scope="session")
def results():
    """Все 10 сценариев, посчитанные один раз на сессию (~11 с суммарно)."""
    return {name: _run(name) for name in ALL_EXAMPLES}


# ═══════════════════════════════════════════════════════════
# A. Структура папок
# ═══════════════════════════════════════════════════════════

class TestStructure:
    @pytest.mark.parametrize("name", ALL_EXAMPLES)
    def test_required_files(self, name):
        """Каждый пример самодостаточен: конфиг, точка входа, описание."""
        folder = EXAMPLES_DIR / name
        for fname in ("config.json", "main.py", "README.md"):
            assert (folder / fname).is_file(), f"{name}: нет {fname}"

    def test_no_extra_example_folders(self):
        """Список ALL_EXAMPLES не отстал от содержимого examples/."""
        on_disk = sorted(
            d.name for d in EXAMPLES_DIR.iterdir()
            if d.is_dir() and d.name[0].isdigit()
        )
        assert on_disk == sorted(ALL_EXAMPLES)

    def test_runner_and_run_all_exist(self):
        """Инфраструктура на месте."""
        assert (EXAMPLES_DIR / "example_runner.py").is_file()
        assert (EXAMPLES_DIR / "run_all.py").is_file()
        assert (EXAMPLES_DIR / "README.md").is_file()


# ═══════════════════════════════════════════════════════════
# B. Конфиги
# ═══════════════════════════════════════════════════════════

class TestConfigs:
    @pytest.mark.parametrize("name", ALL_EXAMPLES)
    def test_load_config_passes(self, name):
        """Валидация конфига проходит (проверяет физические ограничения)."""
        cfg = load_config(EXAMPLES_DIR / name / "config.json")
        assert cfg.grid.N > 0

    @pytest.mark.parametrize("name", ALL_EXAMPLES)
    def test_referenced_csv_present(self, name):
        """CSV, на которые ссылается конфиг, лежат рядом с ним.

        Ловит рассинхрон: конфиг переключили на табличный PVT,
        а файлы скопировать забыли.
        """
        folder = EXAMPLES_DIR / name
        cfg = load_config(folder / "config.json")

        if cfg.pvt.model == "table":
            assert cfg.pvt.oil_pvt_file, f"{name}: pvt.model=table без oil_pvt_file"
            assert cfg.pvt.gas_pvt_file, f"{name}: pvt.model=table без gas_pvt_file"
            assert (folder / cfg.pvt.oil_pvt_file).is_file()
            assert (folder / cfg.pvt.gas_pvt_file).is_file()

        if cfg.relperm.model == "table":
            assert cfg.relperm.file, f"{name}: relperm.model=table без file"
            assert (folder / cfg.relperm.file).is_file()

    @pytest.mark.parametrize("name", ALL_EXAMPLES)
    def test_no_dead_output_format(self, name):
        """Поле output.format объявлено в io/config.py, но нигде не читается.

        В конфигах примеров его быть не должно — иначе пользователь решит,
        что оно переключает формат вывода (DEBT-008).
        """
        raw = json.loads((EXAMPLES_DIR / name / "config.json").read_text(encoding="utf-8"))
        assert "format" not in raw.get("output", {}), \
            f"{name}: мёртвое поле output.format в конфиге"


# ═══════════════════════════════════════════════════════════
# C. Расчёт: общие проверки для всех сценариев
# ═══════════════════════════════════════════════════════════

class TestRunAll:
    @pytest.mark.parametrize("name", ALL_EXAMPLES)
    def test_completes(self, results, name):
        """Расчёт дошёл до конца и сохранил шаги."""
        assert results[name]["history"].n_saved > 0

    @pytest.mark.parametrize("name", ALL_EXAMPLES)
    def test_no_nan_inf(self, results, name):
        """Ни одно поле не содержит NaN/Inf — базовый признак развала схемы."""
        r = results[name]
        for key in ("p", "T", "Sg", "Rs", "q_o", "q_g"):
            assert np.all(np.isfinite(r[key])), f"{name}: не-конечные значения в {key}"

    @pytest.mark.parametrize("name", ALL_EXAMPLES)
    def test_physical_bounds(self, results, name):
        """p > 0, T > 0, Sg ∈ [0, 1] — физически допустимые диапазоны."""
        r = results[name]
        assert np.all(r["p"] > 0.0), f"{name}: неположительное давление"
        assert np.all(r["T"] > 0.0), f"{name}: неположительная температура"
        assert np.all(r["Sg"] >= 0.0) and np.all(r["Sg"] <= 1.0), \
            f"{name}: Sg вне [0, 1]"

    @pytest.mark.parametrize("name", ALL_EXAMPLES)
    def test_oil_production(self, results, name):
        """Скважина добывает нефть: q_o > 0 на последнем шаге.

        Знак: q_o_std = -G_o[0], положителен при добыче (конвенция знаков).
        """
        assert results[name]["q_o"][-1] > 0.0


# ═══════════════════════════════════════════════════════════
# D. Физика по семействам
# ═══════════════════════════════════════════════════════════

class TestSinglePhase:
    """Семейство 1: Rs0 = 0 → pb < 0 → газ не выделяется никогда."""

    @pytest.mark.parametrize("name", SINGLE_PHASE)
    def test_no_free_gas(self, results, name):
        assert np.all(results[name]["Sg"] == 0.0), f"{name}: появился свободный газ"

    @pytest.mark.parametrize("name", SINGLE_PHASE)
    def test_no_gas_rate(self, results, name):
        assert np.all(results[name]["q_g"] == 0.0), f"{name}: ненулевой дебит газа"

    @pytest.mark.parametrize("name", SINGLE_PHASE)
    def test_rs_stays_zero(self, results, name):
        assert np.all(results[name]["Rs"] == 0.0)


class TestTwoPhase:
    """Семейства 2 и 3: pwf < pb → разгазирование обязано произойти."""

    @pytest.mark.parametrize("name", TWO_PHASE)
    def test_gas_appears(self, results, name):
        """Ключевой тест: ловит регрессию «pwf выше pb».

        При pwf > pb расчёт проходит без ошибок, но сценарий молча
        становится однофазным — Sg ≡ 0 вопреки замыслу.
        """
        assert results[name]["Sg"].max() > 0.0, \
            f"{name}: разгазирования не произошло — вероятно, pwf выше pb"

    @pytest.mark.parametrize("name", TWO_PHASE)
    def test_rs_decreased(self, results, name):
        """Газ действительно вышел из раствора: Rs упало ниже начального."""
        r = results[name]
        assert r["Rs"].min() < r["Rs0"], \
            f"{name}: Rs не уменьшилось относительно Rs0={r['Rs0']}"

    @pytest.mark.parametrize("name", TWO_PHASE)
    def test_gas_produced(self, results, name):
        """Дебит газа положителен — газ выносится в скважину."""
        assert results[name]["q_g"][-1] > 0.0


# ═══════════════════════════════════════════════════════════
# E. Суперпозиция тепловых вкладов (семейство 3)
# ═══════════════════════════════════════════════════════════

def test_thermal_superposition(results):
    """Вклады JT и скрытой теплоты складываются линейно.

    07 — опора (все тепловые скаляры = 0), 08 добавляет JT,
    09 добавляет скрытую теплоту, 04 — оба эффекта сразу.
    Ожидается: (T08 - T07) + (T09 - T07) = T04 - T07.

    Tolerance 1e-3 К: при измерении равенство выполняется с невязкой
    ~4e-13 К (машинная точность), запас оставлен на изменения дискретизации.
    """
    T07 = results["07_degassing_adiabatic_only"]["T_well"]
    T08 = results["08_degassing_jt"]["T_well"]
    T09 = results["09_degassing_latent_heat"]["T_well"]
    T04 = results["04_table_table"]["T_well"]

    contribution_jt = T08 - T07
    contribution_latent = T09 - T07
    contribution_both = T04 - T07

    assert contribution_jt + contribution_latent == pytest.approx(
        contribution_both, abs=1e-3), (
        f"суперпозиция нарушена: {contribution_jt:.4f} + {contribution_latent:.4f} "
        f"= {contribution_jt + contribution_latent:.4f} != {contribution_both:.4f}")


def test_thermal_effects_cool(results):
    """И JT, и скрытая теплота дают охлаждение относительно опоры 07."""
    T07 = results["07_degassing_adiabatic_only"]["T_well"]
    assert results["08_degassing_jt"]["T_well"] < T07
    assert results["09_degassing_latent_heat"]["T_well"] < T07


# ═══════════════════════════════════════════════════════════
# F. Расщепление: термика не влияет на гидродинамику
# ═══════════════════════════════════════════════════════════

@pytest.mark.parametrize("other", ["08_degassing_jt", "09_degassing_latent_heat"])
def test_thermal_does_not_affect_hydro(results, other):
    """Сценарии 07, 08, 09 различаются только секцией thermal.

    Из-за расщепления (operator splitting) HydroSolver не видит тепловых
    коэффициентов, а EnergySolver работает на замороженных p, Sg, Rs.
    Поэтому гидродинамика обязана совпасть ПОБИТОВО, а не приближённо.

    Тест ловит нарушение расщепления — если кто-то свяжет EnergySolver
    с гидродинамикой, равенство сломается.
    """
    base = results["07_degassing_adiabatic_only"]
    ref = results[other]

    for key in ("Sg", "p", "Rs", "q_o", "q_g"):
        assert np.array_equal(base[key], ref[key]), \
            f"{other}: поле {key} отличается от 07 — расщепление нарушено"


def test_thermal_actually_differs(results):
    """Контроль к предыдущему тесту: температура всё-таки различается.

    Без этой проверки test_thermal_does_not_affect_hydro прошёл бы
    и на вырожденной ситуации, где термика вообще не считается.
    """
    T07 = results["07_degassing_adiabatic_only"]["T"]
    T08 = results["08_degassing_jt"]["T"]
    assert not np.array_equal(T07, T08)


def test_01_02_differ_by_single_parameter():
    """README 02 обещает: от 01 отличается ровно одной строкой — mu_JT_oil.

    Раньше в 02 была вдобавок включена теплопроводность, из-за чего
    заявленная «изоляция вклада JT» не выполнялась, а аналитическая
    JT-асимптотика (main.py) смещалась на ~0.07 К. Тест фиксирует
    договорённость, чтобы расхождение конфига и README не вернулось.
    """
    cfg01 = json.loads(
        (EXAMPLES_DIR / "01_single_phase_no_jt" / "config.json").read_text("utf-8"))
    cfg02 = json.loads(
        (EXAMPLES_DIR / "02_single_phase_jt" / "config.json").read_text("utf-8"))

    # Плоский обход вложенных секций: "thermal.mu_JT_oil" → значение.
    def flatten(d, prefix=""):
        out = {}
        for k, v in d.items():
            key = f"{prefix}{k}"
            if isinstance(v, dict):
                out.update(flatten(v, key + "."))
            else:
                out[key] = v
        return out

    f01, f02 = flatten(cfg01), flatten(cfg02)
    assert f01.keys() == f02.keys(), "наборы полей конфигов 01 и 02 разошлись"

    diff = {k for k in f01 if f01[k] != f02[k]}
    assert diff == {"thermal.mu_JT_oil"}, \
        f"01 и 02 должны отличаться только mu_JT_oil, отличаются: {sorted(diff)}"


def test_02_relaxes_toward_jt_asymptote(results):
    """Пример 02 идёт к аналитической JT-асимптотике T = T_ext + mu_JT·(p - p_ext).

    При lambda = 0 стационарный энергобаланс rho·cp·u·dT/dr = rho·cp·mu_JT·u·dp/dr
    даёт dT/dr = mu_JT·dp/dr — скорость сокращается, профиль не зависит
    от дебита. Опорная точка — центр последней ячейки (там ГУ Дирихле
    задаёт T_ext), а не r = R_e.

    За 3 суток релаксация не завершается, поэтому проверяем не совпадение,
    а движение в нужную сторону: температура на забое монотонно падает
    и остаётся выше асимптотики (подходит сверху, не проскакивает).
    """
    res = results["02_single_phase_jt"]
    cfg = load_config(EXAMPLES_DIR / "02_single_phase_jt" / "config.json")
    mu_JT = cfg.thermal.mu_JT_oil
    T_ext = cfg.initial_conditions.T0

    p = res["p"]
    T = res["T"]
    T_asymp = T_ext + mu_JT * (p - p[-1])

    # Подход сверху: JT только охлаждает, ниже асимптотики уйти не может.
    # Приконтурная ячейка исключена: она служит опорной точкой асимптотики
    # (там T_asymp = T_ext по построению), но сама уже охлаждена
    # адиабатическим импульсом 1-го шага, поэтому лежит на ~0.01 К ниже.
    assert np.all(T[:-1] >= T_asymp[:-1] - 1e-9), \
        "температура проскочила ниже JT-асимптотики"

    # Но уже прошла заметную часть пути: у забоя полный размах ~2 К,
    # за 3 суток остаётся отставание меньше половины.
    gap_well = T[0] - T_asymp[0]
    full_swing = T_ext - T_asymp[0]
    assert 0.0 < gap_well < 0.5 * full_swing, \
        f"отставание у забоя {gap_well:.3f} К вне ожидаемого диапазона"

    # Динамика: температура на забое падает, а не восстанавливается
    # (отличие от 01, где после адиабатического импульса конвекция греет).
    T_well = np.array([s.T[0] for s in res["history"].states])
    assert T_well[-1] < T_well[1], \
        "T(r_w) должна падать под действием постоянного JT-стока"


# ═══════════════════════════════════════════════════════════
# G. README: обязательные разделы
# ═══════════════════════════════════════════════════════════

class TestReadme:
    @pytest.mark.parametrize("name", ALL_EXAMPLES)
    def test_has_modification_section(self, name):
        """Раздел «Как модифицировать» обязателен во всех README."""
        text = (EXAMPLES_DIR / name / "README.md").read_text(encoding="utf-8")
        assert "Как модифицировать" in text, f"{name}: нет раздела «Как модифицировать»"

    @pytest.mark.parametrize("name", NEEDS_SG_SECTION)
    def test_has_saturation_section(self, name):
        """Сценарии с малой Sg объясняют, как её увеличить.

        Иначе пользователь видит Sg ~ 1-2 % и решает, что расчёт неверен.
        """
        text = (EXAMPLES_DIR / name / "README.md").read_text(encoding="utf-8")
        assert "увеличить газонасыщенность" in text.lower(), \
            f"{name}: нет раздела про увеличение Sg"

    @pytest.mark.parametrize("name", ALL_EXAMPLES)
    def test_documents_module_combination(self, name):
        """README называет конкретные классы, которые создаёт Factory.

        Главная задача примеров — показать комбинации модулей.
        """
        text = (EXAMPLES_DIR / name / "README.md").read_text(encoding="utf-8")
        assert "PrototypeHydroAdapter" in text, f"{name}: не указан класс HydroSolver"
        assert "TridiagEnergySolver" in text, f"{name}: не указан класс EnergySolver"


# ═══════════════════════════════════════════════════════════
# H. Вывод: файлы создаются
# ═══════════════════════════════════════════════════════════

def test_pipeline_writes_output(tmp_path):
    """Полный pipeline example_runner создаёт все CSV и PNG.

    Проверяется на самом быстром сценарии (01), выходные файлы пишутся
    во временную папку, чтобы не трогать examples/*/output/.
    """
    import sys
    sys.path.insert(0, str(EXAMPLES_DIR))
    from example_runner import run_example

    run_example(
        config_path=EXAMPLES_DIR / "01_single_phase_no_jt" / "config.json",
        output_dir=tmp_path,
        title="тест pipeline",
    )

    expected = [
        "well_history.csv", "profiles.csv",
        "pressure_profiles.png", "temperature_profiles.png",
        "saturation_profiles.png", "well_rates.png", "wellbore_dynamics.png",
        # FEAT-016: баланс энергии подключён к run_example для всех примеров
        "energy_balance.png",
    ]
    for fname in expected:
        path = tmp_path / fname
        assert path.is_file(), f"не создан {fname}"
        assert path.stat().st_size > 0, f"пустой файл {fname}"


# ═══════════════════════════════════════════════════════════
# I. Общие проверки: баланс энергии у всех примеров (FEAT-016)
# ═══════════════════════════════════════════════════════════

# Модули проверок, вынесенные в examples/ (FEAT-016). Ни один из них не
# должен снова появиться в папке примера: копия в папке ПЕРЕКРЫВАЕТ общий
# модуль молча, без ошибки импорта (main.py делает sys.path.insert(0, ...)
# сначала для examples/, затем для папки примера, поэтому папка примера
# оказывается впереди). Именно так четыре копии energy_balance.py
# разошлись и породили BUG-004.
SHARED_CHECK_MODULES = [
    "energy_balance.py",
    "energy_balance_convergence.py",
    "temperature_asymptotics.py",
    "two_phase_analytics.py",
]


class TestSharedChecks:
    def test_energy_balance_all_examples(self, results):
        """Баланс энергии сходится у ВСЕХ десяти примеров.

        До BUG-004 невязка была 0.18-0.29 на шести конфигурациях из десяти,
        и на пяти из них это никем не проверялось: свой energy_balance.py
        имели только 01, 02, 03, 05. Порог 1e-2 отделяет ошибку расщепления
        O(dt) (~1e-3 на штатных конфигах) от пропущенного члена.
        """
        import sys
        sys.path.insert(0, str(EXAMPLES_DIR))
        from energy_balance import compute_balance

        bad = {}
        for name in ALL_EXAMPLES:
            r = results[name]
            bal = compute_balance(r["history"], r["grid"], r["config"])
            rel = abs(float(bal["rel_residual"][-1]))
            if rel >= 1e-2:
                bad[name] = rel
        assert not bad, f"невязка баланса >= 1e-2: {bad}"

    def test_conduction_term_always_computed(self, results):
        """Кондуктивный член считается безусловно, а не при lambda != 0.

        Ключевая защита FEAT-016. Пропуск члена у примера 10 (единственного
        с lambda != 0) маскировался девятью примерами с lambda = 0: у них он
        тождественно нулевой, поэтому отсутствие члена было незаметно.
        Проверяем ОБА случая: ключ присутствует всегда, при lambda = 0 член
        строго нулевой, при lambda != 0 — ненулевой.
        """
        import sys
        sys.path.insert(0, str(EXAMPLES_DIR))
        from energy_balance import compute_balance

        for name in ALL_EXAMPLES:
            r = results[name]
            cfg = r["config"]
            bal = compute_balance(r["history"], r["grid"], cfg)

            assert "cum_cond" in bal, f"{name}: нет ключа cum_cond"
            cond = bal["cum_cond"]
            assert np.all(np.isfinite(cond)), f"{name}: cum_cond не конечен"

            has_lambda = (cfg.rock.lambda_solid or cfg.rock.lambda_oil
                          or cfg.rock.lambda_gas)
            if has_lambda:
                # Пример 10: член реально считается, а не занулён ветвлением.
                assert abs(float(cond[-1])) > 0.0, (
                    f"{name}: lambda != 0, но cum_cond = 0 — член не считается")
            else:
                # Q_T_ext = geom * lambda_eff[-1] при lambda = 0 даёт ровно
                # 0.0, без NaN и inf (tridiag.py:179).
                assert np.all(cond == 0.0), (
                    f"{name}: lambda = 0, но cum_cond != 0: {cond[-1]}")

    def test_full_key_set_always_returned(self, results):
        """Набор ключей compute_balance полный независимо от конфига.

        Прежние копии для однофазных примеров не возвращали cum_jt (01) и
        cum_deg (01, 02) — отсутствующие ключи ломали бы вызывающий код.
        Физически отсутствующие члены приходят нулевыми массивами.
        """
        import sys
        sys.path.insert(0, str(EXAMPLES_DIR))
        from energy_balance import compute_balance

        required = {"t", "delta_E", "cum_adiab", "cum_conv", "cum_jt",
                    "cum_deg", "cum_cond", "total", "residual",
                    "rel_residual"}
        for name in ALL_EXAMPLES:
            r = results[name]
            bal = compute_balance(r["history"], r["grid"], r["config"])
            missing = required - set(bal)
            assert not missing, f"{name}: отсутствуют ключи {sorted(missing)}"

    @pytest.mark.parametrize("module", SHARED_CHECK_MODULES)
    def test_no_duplicate_helper_scripts(self, module):
        """Вынесенный модуль не вернулся копией в папку примера.

        Защита от того самого механизма, которым возникла FEAT-016: скрипт
        пишется под один пример, копируется в другой, копии правятся
        независимо и расходятся. Копия в папке примера при этом молча
        перекрывает общий модуль.
        """
        copies = sorted(
            p.parent.name for p in EXAMPLES_DIR.glob(f"*/{module}"))
        assert not copies, (
            f"{module} снова скопирован в папки примеров: {copies}. "
            f"Общий модуль examples/{module} будет молча перекрыт.")

    def test_shared_modules_exist(self):
        """Общие модули на месте — иначе примеры не считают проверки."""
        for module in SHARED_CHECK_MODULES + ["convergence.py"]:
            path = EXAMPLES_DIR / module
            assert path.is_file(), f"нет общего модуля examples/{module}"

    def test_energy_balance_reported_for_all_examples(self, tmp_path):
        """run_example печатает баланс энергии — проверка подключения.

        Отличается от test_energy_balance_all_examples: тот проверяет, что
        баланс СХОДИТСЯ, а этот — что он вообще ВЫЗЫВАЕТСЯ из run_example.
        Без этого общий модуль мог бы существовать, но не быть подключён, и
        примеры 06-10 снова остались бы без проверки.

        Берётся пример 10: у него lambda != 0, поэтому в выводе должна быть
        и ненулевая строка теплопроводности.
        """
        import contextlib
        import io
        import sys
        sys.path.insert(0, str(EXAMPLES_DIR))
        from example_runner import run_example

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            run_example(
                config_path=EXAMPLES_DIR / "10_deep_degassing" / "config.json",
                output_dir=tmp_path,
                title="тест подключения баланса",
            )
        out = buf.getvalue()

        assert "Невязка финал" in out, (
            "run_example не печатает невязку баланса энергии")
        assert "Теплопроводность" in out, (
            "в выводе баланса нет кондуктивного члена")
        assert (tmp_path / "energy_balance.png").is_file(), (
            "run_example не сохранил график баланса")
        # Асимптотика у примера 10 неприменима (lambda != 0) — должна быть
        # сказана причина, а не напечатано большое расхождение.
        assert "не проверяется" in out, (
            "асимптотика не сообщила о неприменимости при lambda != 0")
