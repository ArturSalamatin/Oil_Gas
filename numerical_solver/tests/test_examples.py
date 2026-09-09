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
    "04a_high_gas_saturation",
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
        # FEAT-017: свойства PVT — общий модуль для всех примеров
        "pvt.png",
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
    "pvt_plot.py",
]

# Баланс энергии суммирует ПРИРАЩЕНИЯ по сохранённым шагам, поэтому
# compute_balance требует save_every = 1 и бросает ValueError иначе
# (energy_balance.py:124). Пример 04a — первый в наборе с save_every = 12:
# его dt_integration = 300 даёт 864 подшага, и прореживание возвращает
# число сохранённых состояний к тем же 73, что у остальных. Список строим
# по конфигам, а не перечислением: следующий пример с прореживанием
# попадёт сюда сам, без правки теста.
BALANCE_EXAMPLES = [
    name for name in ALL_EXAMPLES
    if load_config(EXAMPLES_DIR / name / "config.json").output.save_every == 1
]


class TestSharedChecks:
    def test_energy_balance_all_examples(self, results):
        """Баланс энергии сходится у всех примеров с полной историей.

        До BUG-004 невязка была 0.18-0.29 на шести конфигурациях из десяти,
        и на пяти из них это никем не проверялось: свой energy_balance.py
        имели только 01, 02, 03, 05. Порог 1e-2 отделяет ошибку расщепления
        O(dt) (~1e-3 на штатных конфигах) от пропущенного члена.

        Идёт по BALANCE_EXAMPLES, а не по ALL_EXAMPLES: у 04a save_every = 12,
        и сумма приращений по прореженной истории заведомо неполна.
        """
        import sys
        sys.path.insert(0, str(EXAMPLES_DIR))
        from energy_balance import compute_balance

        bad = {}
        for name in BALANCE_EXAMPLES:
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

        BALANCE_EXAMPLES, а не ALL_EXAMPLES: compute_balance неприменим
        к 04a с его save_every = 12 (см. комментарий к списку).
        """
        import sys
        sys.path.insert(0, str(EXAMPLES_DIR))
        from energy_balance import compute_balance

        for name in BALANCE_EXAMPLES:
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

        BALANCE_EXAMPLES, а не ALL_EXAMPLES: compute_balance неприменим
        к 04a с его save_every = 12 (см. комментарий к списку).
        """
        import sys
        sys.path.insert(0, str(EXAMPLES_DIR))
        from energy_balance import compute_balance

        required = {"t", "delta_E", "cum_adiab", "cum_conv", "cum_jt",
                    "cum_deg", "cum_cond", "total", "residual",
                    "rel_residual"}
        for name in BALANCE_EXAMPLES:
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


# ═══════════════════════════════════════════════════════════
# J. Графики PVT: слой оформителя (FEAT-017)
# ═══════════════════════════════════════════════════════════

# Ключи, которые report_pvt обязан возвращать ВСЕГДА, независимо от конфига.
# У однофазных примеров значения вырождены (two_phase=False,
# nodes_in_range=0), но ключи присутствуют: отсутствующий ключ роняет
# вызывающий код ровно на тех сценариях, где он и не проверялся.
PVT_REPORT_KEYS = {
    "pb", "p_lo", "p_hi", "Rs0", "model", "two_phase", "nodes_in_range",
    "mu_o_lo", "mu_o_hi", "Bo_lo", "Bo_hi", "Rs_lo", "Rs_hi",
}

# PVT задан таблицами (узлы есть) против аналитических корреляций (узлов нет).
# Строится по конфигам, а не перечислением имён: перечисление молча
# относило бы новый табличный пример к аналитическим, и тест «узлов быть
# не может» падал бы с сообщением, не указывающим на причину.
TABLE_PVT = [
    name for name in ALL_EXAMPLES
    if load_config(EXAMPLES_DIR / name / "config.json").pvt.model == "table"
]
ANALYTIC_PVT = [n for n in ALL_EXAMPLES if n not in TABLE_PVT]


def _pvt_module():
    """Общий модуль examples/pvt_plot.py."""
    import sys
    sys.path.insert(0, str(EXAMPLES_DIR))
    import pvt_plot
    return pvt_plot


def _pvt_of_config(cfg):
    """PVT, собранный фабрикой по конфигу (эталон для сверки)."""
    from gpn_multiphase_solver.factory import _create_pvt
    return _create_pvt(cfg)


class TestPvtPlot:
    """Оформитель графика PVT: pvt.png, сводка, узлы таблиц.

    Приоритет по постановке задачи — вязкость mu_o и газосодержание Rs
    нефтяной фазы: первая входит в подвижность lambda_o = k*k_ro/mu_o,
    второе — в замыкание GOR = Rs0.
    """

    def test_plot_pvt_all_examples(self, results, tmp_path):
        """Модуль отрабатывает на всех десяти примерах и пишет непустой PNG.

        Покрывает обе PVT-модели (standing: 01, 02, 03, 05; table: 04,
        06-10) и оба режима (однофазный Rs0 = 0: 01, 02; двухфазный —
        остальные). Граничный случай Rs0 = 0 опасен: p_b = -0.176 МПа,
        и наивный код рисует вертикаль за пределами оси или падает.
        """
        pvt_plot = _pvt_module()
        for name in ALL_EXAMPLES:
            r = results[name]
            out = pvt_plot.plot_pvt(r["config"], r["history"],
                                    tmp_path / name, name, grid=r["grid"])
            assert out.is_file(), f"{name}: pvt.png не создан"
            assert out.stat().st_size > 0, f"{name}: pvt.png пустой"

    def test_report_pb_matches_pvt(self, results):
        """report_pvt сообщает то же p_b, что и сам объект PVT.

        Эталон — вызов pvt.pb(Rs0). Допуск 1e-6 Па: обе стороны обязаны
        считать ОДНИМ вызовом, а не своей формулой. Заодно покрывается
        ветка simulator=None (fallback на factory._create_pvt): fixture
        results симулятор не хранит.
        """
        pvt_plot = _pvt_module()
        for name in ALL_EXAMPLES:
            r = results[name]
            rep = pvt_plot.report_pvt(r["config"], r["history"])
            pb_ref = float(_pvt_of_config(r["config"]).pb(
                np.array([r["Rs0"]]))[0])
            assert abs(rep["pb"] - pb_ref) < 1e-6, (
                f"{name}: p_b сводки {rep['pb']} != {pb_ref} у PVT")

    def test_full_key_set_always_returned(self, results):
        """Набор ключей полный при любом конфиге — конвенция общих модулей.

        Ловушка «этот ключ не нужен, у нас однофазный сценарий» — ровно
        та, что дала BUG-004: девять примеров с lambda = 0 маскировали
        пропуск кондуктивного члена у десятого.
        """
        pvt_plot = _pvt_module()
        for name in ALL_EXAMPLES:
            r = results[name]
            rep = pvt_plot.report_pvt(r["config"], r["history"])
            assert PVT_REPORT_KEYS <= set(rep), (
                f"{name}: не хватает ключей "
                f"{PVT_REPORT_KEYS - set(rep)}")
            assert rep["two_phase"] == (name not in SINGLE_PHASE), (
                f"{name}: two_phase не соответствует Rs0")
            if name in ANALYTIC_PVT:
                assert rep["nodes_in_range"] == 0, (
                    f"{name}: у аналитического PVT узлов быть не может")

    def test_saturated_branch_hidden_when_single_phase(self, results,
                                                       tmp_path):
        """При Rs0 = 0 насыщенная ветвь не рисуется — иначе ось растянута.

        Измерено на 01: Rs_eq доходит до 138 м³ст/м³ст при физическом
        Rs ≡ 0. Если ветвь нарисовать, ось Rs растянется до 140, а
        физический ноль прижмётся к краю и станет нечитаем. Пометка
        «недостижимо» тут не помогает: масштаб задаёт сама кривая.
        """
        import matplotlib.pyplot as plt
        from gpn_multiphase_solver.io.output import plot_pvt_properties

        for name in SINGLE_PHASE:
            r = results[name]
            pvt = _pvt_of_config(r["config"])
            p = r["p"]
            fig, axes = plt.subplots(2, 3)
            plot_pvt_properties(pvt, 0.0, (float(p.min()), float(p.max())),
                                axes=axes)
            ylim = axes[0, 1].get_ylim()      # панель Rs
            plt.close(fig)
            assert ylim[1] < 1.0, (
                f"{name}: ось Rs растянута до {ylim[1]:.1f} — значит "
                f"нарисована нефизичная насыщенная ветвь")

    def test_physical_branch_matches_rs_analytics(self, results):
        """Физическая кривая совпадает с rs_analytics.rs_expected побитово.

        Обе стороны считают min(Rs_eq(p), Rs0). Расхождение двух
        реализаций одной формулы — тот самый класс дефектов, ради
        которого FEAT-016 сводил четыре копии energy_balance.py, поэтому
        допуск нулевой.
        """
        import sys
        sys.path.insert(0, str(EXAMPLES_DIR))
        from rs_analytics import rs_expected
        pvt_plot = _pvt_module()

        p = np.linspace(5e6, 25e6, 50)
        for name in TWO_PHASE:
            r = results[name]
            pvt = _pvt_of_config(r["config"])
            mine = pvt_plot._physical_rs(pvt, p, r["Rs0"])
            ref = rs_expected(r["config"], pvt, p)
            assert np.array_equal(mine, ref), (
                f"{name}: физическая кривая разошлась с rs_analytics")

    def test_rho_matches_formula(self, results):
        """Плотности сводки равны \\eqref{eq:rho_oil}, а не своей формуле.

        rho_o = (rho_o_ст + Rs*rho_g_ст)/Bo,  rho_g = rho_g_ст/Bg
        (problem_statement.tex, строки 1838-1840 и таблица обозначений).
        Проверка ловит попытку пересчитать плотность в модуле вместо
        вызова pvt.rho_o / pvt.rho_g.
        """
        pvt_plot = _pvt_module()
        for name in ALL_EXAMPLES:
            r = results[name]
            pvt = _pvt_of_config(r["config"])
            p_mid = np.array([0.5 * (float(r["p"].min())
                                     + float(r["p"].max()))])
            Rs = pvt_plot._physical_rs(pvt, p_mid, r["Rs0"])

            rho_o_ref = ((r["config"].pvt.rho_o_std
                          + Rs * r["config"].pvt.rho_g_std) / pvt.Bo(p_mid, Rs))
            rho_g_ref = r["config"].pvt.rho_g_std / pvt.Bg(p_mid)

            assert abs(float(pvt.rho_o(p_mid, Rs)[0])
                       - float(rho_o_ref[0])) < 1e-9, f"{name}: rho_o"
            assert abs(float(pvt.rho_g(p_mid)[0])
                       - float(rho_g_ref[0])) < 1e-9, f"{name}: rho_g"

    def test_nodes_units(self, results):
        """Узлы таблиц возвращаются в Па, а не в барах прототипа.

        В BlackOilPVT прототипа давления лежат в БАРАХ. Пропуск
        конвертации — ошибка в 1e5 раз; на графике узлы уедут за пределы
        оси и просто не отрисуются, поэтому глазами это не ловится.
        Эталон примера 04 известен точно: газовая таблица и нефтяные узлы
        стоят на 5, 15, 30 МПа, ветки заданы при Rs = 0 и 30 м³ст/м³ст.
        """
        pvt_plot = _pvt_module()
        r = results["04_table_table"]
        nodes = pvt_plot._pvt_table_nodes(_pvt_of_config(r["config"]),
                                          r["Rs0"])
        assert nodes is not None, "у табличного PVT узлы обязаны быть"
        assert np.allclose(nodes["p_gas"], [5e6, 15e6, 30e6])
        assert np.allclose(nodes["p_oil"], [5e6, 15e6, 30e6])
        assert np.allclose(nodes["rs_values"], [0.0, 30.0])

    def test_nodes_none_for_analytical_pvt(self, results):
        """У аналитического PVT узлов нет — маркеры вводили бы в заблуждение.

        Корреляция Стендинга гладкая, выделенных точек в ней не существует.
        """
        pvt_plot = _pvt_module()
        for name in ANALYTIC_PVT:
            r = results[name]
            nodes = pvt_plot._pvt_table_nodes(_pvt_of_config(r["config"]),
                                              r["Rs0"])
            assert nodes is None, f"{name}: у корреляции узлов быть не может"

    def test_table_nodes_in_working_range(self, results):
        """В рабочий диапазон примера 04 попадает ровно один узел.

        Демонстрационные таблицы грубы: рабочий диапазон 8.17…19.89 МПа,
        а узлы стоят на 5, 15 и 30 МПа — внутрь попадает только p_b = 15.
        Вся кривая между краями получена интерполяцией через две точки,
        и график обязан делать это видимым. Тест ловит и 0 (фильтр
        «внутри диапазона» слишком строг), и 3 (фильтра нет вовсе).
        """
        pvt_plot = _pvt_module()
        r = results["04_table_table"]
        rep = pvt_plot.report_pvt(r["config"], r["history"])
        assert rep["nodes_in_range"] == 1, (
            f"ожидался ровно один узел в диапазоне, получено "
            f"{rep['nodes_in_range']}")

    def test_single_phase_no_bubble_point_line(self, results, tmp_path):
        """При Rs0 = 0 p_b отрицательно и на график попасть не должно.

        Формула Стендинга при Rs = 0 даёт p_b = -0.176 МПа (скобка
        (Rs/gamma_g)^0.83 * 10^a - 1.4 обращается в -1.4). Это вне
        физической области; вертикаль там бессмысленна, а падения быть
        не должно — примеры 01 и 02 входят в штатный прогон run_all.py.
        """
        pvt_plot = _pvt_module()
        for name in SINGLE_PHASE:
            r = results[name]
            rep = pvt_plot.report_pvt(r["config"], r["history"])
            assert rep["pb"] < 0, f"{name}: ожидалось p_b < 0"
            assert rep["two_phase"] is False
            out = pvt_plot.plot_pvt(r["config"], r["history"],
                                    tmp_path / name, name, grid=r["grid"])
            assert out.is_file()

    def test_no_phantom_legend_entries(self, results):
        """Легенда не обещает кривых, которых на панели нет.

        У табличного PVT выше p_b выполняется Rs_eq == Rs0, поэтому
        насыщенная ветвь совпадает с физической ТОЖДЕСТВЕННО (измерено
        на 04: max|Bo_sat - Bo_phys| = 0.000e+00 против 2.341e-01 у
        Стендинга). Рисовать её нельзя — в легенде висела бы запись без
        линии, и график читался бы как дефект отрисовки.
        """
        import matplotlib.pyplot as plt
        from gpn_multiphase_solver.io.output import plot_pvt_properties

        n_entries = {}
        for name in ("03_standing_corey", "04_table_table"):
            r = results[name]
            pvt = _pvt_of_config(r["config"])
            p = r["p"]
            fig, axes = plt.subplots(2, 3)
            plot_pvt_properties(pvt, r["Rs0"],
                                (float(p.min()), float(p.max())), axes=axes)
            ax = axes[0, 2]                       # панель Bo
            labels = [t.get_text() for t in ax.get_legend().get_texts()]
            # Линии с >2 точками — настоящие кривые; axvline даёт 2 точки.
            curves = [ln for ln in ax.get_lines() if len(ln.get_xdata()) > 2]
            plt.close(fig)
            assert len(labels) <= len(curves), (
                f"{name}: записей легенды {len(labels)} при {len(curves)} "
                f"кривых — легенда обещает несуществующую линию")
            n_entries[name] = len(labels)

        assert n_entries["04_table_table"] < n_entries["03_standing_corey"], (
            "у табличного PVT насыщенная ветвь совпадает с физической и "
            "не должна попадать в легенду")

    def test_table_nodes_split_by_phase(self, results):
        """Узлы раздельны по фазам: газовые и нефтяные идут на разные панели.

        Наборы разные по природе: газовая таблица proto.gp против точек
        насыщения веток proto.pb вместе с узлами рисуемой ветки. Если
        подать их одним массивом, маркеры попадут не на те панели —
        в прототипе при аудите это дало пустые mu_o и Bo при заполненных
        mu_g и Bg.
        """
        pvt_plot = _pvt_module()
        r = results["04_table_table"]
        nodes = pvt_plot._pvt_table_nodes(_pvt_of_config(r["config"]),
                                          r["Rs0"])
        assert set(nodes) >= {"p_gas", "p_oil"}, "ключи должны быть раздельны"
        assert "p_all" not in nodes, (
            "объединение делает _nodes_in_range, а не сам сборщик узлов")

    def test_mu_o_spatial_localization(self, results):
        """Пространственная панель даёт верный радиус локализации вязкости.

        Величина, ради которой панель и вводится: у примера 03 ВСЯ
        вариация вязкости укладывается в r < 0.20 м при радиусе
        дренирования 47 м, то есть в 5 ячеек из 50. Панель mu_o(p) этого
        не показывает — она отвечает на другой вопрос.

        Заодно проверяется источник вязкости: mu_o берётся из состояния
        (p_j, Rs_j). Пересчёт по Rs_eq(p) вместо st.Rs дал бы другую
        кривую в зоне разгазирования.
        """
        # Ожидания измерены прогоном; допуск — соседняя ячейка
        # логарифмической сетки.
        expected = {
            "03_standing_corey": (0.20, 5, 1.09),
            "04_table_table": (2.11, 24, 1.68),
            "10_deep_degassing": (2.70, 26, 1.88),
        }
        for name, (r90_ref, k_ref, ratio_ref) in expected.items():
            r = results[name]
            pvt = _pvt_of_config(r["config"])
            st = r["history"].states[-1]
            rr = r["grid"].r_centers
            mu = pvt.mu_o(st.p, st.Rs)

            var = np.abs(np.diff(mu))
            tot = float(var.sum())
            assert tot > 0, f"{name}: вязкость обязана меняться"
            k90 = min(int(np.searchsorted(np.cumsum(var) / tot, 0.9)) + 1,
                      len(rr) - 1)
            assert abs(k90 - k_ref) <= 1, (
                f"{name}: 90 % вариации накоплено к ячейке {k90}, "
                f"ожидалось ~{k_ref}")
            assert rr[k90] == pytest.approx(r90_ref, rel=0.15), (
                f"{name}: радиус 90 % вариации {rr[k90]:.2f} м, "
                f"ожидалось ~{r90_ref} м")
            assert mu.max() / mu.min() == pytest.approx(ratio_ref, rel=0.05)

    def test_mu_o_spatial_single_phase(self, results, tmp_path):
        """На однофазных примерах панель не падает и не делит на ноль.

        Измерено: mu_o ≡ 2.4770e-03 Па·с во всех 50 ячейках, полная
        вариация ровно 0.000e+00, ячеек с p < p_b нет (p_b < 0). Обе
        защиты в _plot_mu_o_spatial (if tot > 0, if below.any()) написаны
        условиями именно поэтому: на двухфазных примерах эта ветка
        никогда не исполняется и осталась бы непроверенной.
        """
        pvt_plot = _pvt_module()
        for name in SINGLE_PHASE:
            r = results[name]
            pvt = _pvt_of_config(r["config"])
            st = r["history"].states[-1]
            mu = pvt.mu_o(st.p, st.Rs)
            assert float(mu.max() - mu.min()) == 0.0, (
                f"{name}: у однофазного примера вязкость обязана быть "
                f"постоянной")
            out = pvt_plot.plot_pvt(r["config"], r["history"],
                                    tmp_path / name, name, grid=r["grid"])
            assert out.is_file()

    def test_formatter_delegates_drawing_to_core(self):
        """Оформитель не дублирует построение, а вызывает ядро.

        Стоит построению расползтись обратно в examples/ — и ядерная
        функция перестанет отражать то, что видит пользователь пакета,
        а расслоение слоёв (FEAT-017, §4.0) потеряет смысл. Единственное,
        что оформитель рисует сам, — панель mu_o(r): ей нужны history
        и grid, которых ядро по контракту не знает.

        Порог различим надёжно: у relperm_plot.py, который рисует сам,
        таких вызовов 10; у rs_analytics.py, который лишь дорисовывает
        оверлей, — 1.
        """
        import ast

        src = EXAMPLES_DIR / "pvt_plot.py"
        tree = ast.parse(src.read_text(encoding="utf-8"))

        drawing = {"plot", "semilogx", "loglog", "scatter"}
        spatial = next(n for n in ast.walk(tree)
                       if isinstance(n, ast.FunctionDef)
                       and n.name == "_plot_mu_o_spatial")
        inside = {id(n) for n in ast.walk(spatial)}

        stray = []
        calls_core = False
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Name) and func.id == "plot_pvt_properties":
                calls_core = True
            if (isinstance(func, ast.Attribute) and func.attr in drawing
                    and id(node) not in inside):
                stray.append(func.attr)

        assert calls_core, "оформитель не вызывает ядерную plot_pvt_properties"
        assert not stray, (
            f"построение продублировано вне _plot_mu_o_spatial: {stray}")

    def test_module_signatures_follow_convention(self, results):
        """Сигнатуры следуют конвенции общих модулей, а не выбросу.

        Конвенция: config первым аргументом, simulator последним со
        значением по умолчанию, report_* печатает и возвращает dict.
        report_relperm возвращает None и является единственным выбросом
        среди шести общих модулей — копировать надо конвенцию.

        Ядро при этом не должно знать ни config, ни history, ни grid,
        ни simulator: подпись приходит готовой строкой в label.
        """
        import inspect
        from gpn_multiphase_solver.io.output import plot_pvt_properties
        pvt_plot = _pvt_module()

        pars = list(inspect.signature(pvt_plot.plot_pvt).parameters)
        assert pars[0] == "config", "config обязан быть первым аргументом"
        assert pars[:4] == ["config", "history", "output_dir", "title"]
        assert "simulator" in pars, "модуль обязан принимать simulator"
        sim_par = inspect.signature(pvt_plot.plot_pvt).parameters["simulator"]
        assert sim_par.default is None, "simulator — необязательный"

        rep_pars = list(inspect.signature(pvt_plot.report_pvt).parameters)
        assert rep_pars == ["config", "history", "simulator"]

        r = results["03_standing_corey"]
        assert isinstance(pvt_plot.report_pvt(r["config"], r["history"]), dict)

        core_pars = set(inspect.signature(plot_pvt_properties).parameters)
        forbidden = core_pars & {"config", "history", "grid", "simulator"}
        assert not forbidden, (
            f"ядро не должно знать про {forbidden} — оно принимает готовый "
            f"объект PVT")

    def test_density_panel_uses_twinx(self):
        """Панель плотностей — на двух осях.

        Измерено на примере 04: нефть 730…800, газ 40…140 кг/м³. На одной
        шкале газовая кривая прижата к низу и её форма нечитаема, а
        именно форма rho_g(p) различает PVT-модели.
        """
        import ast

        core = (Path(__file__).parent.parent / "gpn_multiphase_solver"
                / "io" / "output.py")
        tree = ast.parse(core.read_text(encoding="utf-8"))
        has_twinx = any(isinstance(n, ast.Call)
                        and isinstance(n.func, ast.Attribute)
                        and n.func.attr == "twinx"
                        for n in ast.walk(tree))
        assert has_twinx, (
            "панель плотностей обязана использовать twinx: нефть ~800, "
            "газ ~100 кг/м³, на одной оси газовая кривая нечитаема")


# ═══════════════════════════════════════════════════════════
# K. Сценарий 04a: высокая газонасыщенность (FEAT-015)
# ═══════════════════════════════════════════════════════════

HIGH_SG = "04a_high_gas_saturation"


class TestHighGasSaturation:
    """Обратное проектирование ОФП: k_rg^max подобрана так, чтобы Sg(r_w)=0.7.

    Смысл сценария — показать, что насыщенность управляется подвижностью газа.
    Если эти тесты падают, значит либо изменилась PVT-таблица, либо замыкание
    GOR = Rs0 перестало выполняться — и пример утратил смысл.
    """

    def test_target_saturation_reached(self, results):
        """Sg на забое достигает проектных 0.70.

        Значение вычислено обратной задачей из замыкания (README), а не
        подобрано. Допуск 0.01 покрывает округление k_rg^max 0.0013994 -> 0.0014
        и дискретизацию сетки.
        """
        Sg_well = float(results[HIGH_SG]["Sg"][0])
        assert 0.69 <= Sg_well <= 0.71, f"Sg(r_w) = {Sg_well}, ожидалось ~0.70"

    def test_gor_equals_Rs0(self, results):
        """Газовый фактор скважины равен Rs0 — то самое условие замыкания.

        На контуре свободного газа нет, весь газ приходит растворённым,
        поэтому в стационаре GOR = Rs0 = 30 тождественно. Прогон даёт 30.006
        (0.02 %); допуск 1 % с запасом на незавершённую релаксацию.
        """
        r = results[HIGH_SG]
        gor = float(r["q_g"][-1] / r["q_o"][-1])
        assert gor == pytest.approx(r["Rs0"], rel=1e-2), \
            f"GOR = {gor}, Rs0 = {r['Rs0']}"

    def test_full_degassing(self, results):
        """Ниже 5 МПа ветка Rs = 0 таблицы -> растворённого газа не остаётся.

        Именно полная дегазация даёт максимальный дефицит (Rs0 - Rs = 30)
        и выводит Sg на плато 0.70.
        """
        assert float(results[HIGH_SG]["Rs"].min()) == pytest.approx(0.0, abs=1e-9)

    def test_much_higher_than_example_04(self, results):
        """Sg в 04a на порядок с лишним выше, чем в 04 при том же PVT.

        Разница только в ОФП (Corey k_rg^max = 0.0014 против таблицы 04):
        менее подвижный газ накапливается сильнее. Это главный вывод примера.

        Порог 20x, а не 40x: измеренное отношение 47.6x (0.699965 / 0.014697),
        и порог 40 оставлял бы всего 19 % запаса — тест падал бы первым при
        любой правке демонстрационной relperm.csv примера 04, причём его
        сообщение не подсказывало бы причину. Качественный вывод («на порядок
        с лишним») держится с большим запасом.
        """
        sg_04a = float(results[HIGH_SG]["Sg"].max())
        sg_04 = float(results["04_table_table"]["Sg"].max())
        assert sg_04a > 20 * sg_04, f"04a: {sg_04a}, 04: {sg_04}"

    def test_corey_relperm_used(self):
        """Конфиг задаёт именно вычисленные параметры Кори.

        Ловит случайную правку k_rg^max: при другом значении Sg перестанет
        быть 0.70, и весь смысл обратного расчёта в README исчезнет.
        """
        cfg = load_config(EXAMPLES_DIR / HIGH_SG / "config.json")
        assert cfg.relperm.model == "corey"
        assert cfg.relperm.krg_max == pytest.approx(0.0014)
        assert cfg.relperm.n_o == pytest.approx(1.0)   # линейная k_ro -> точное табулирование
        assert cfg.relperm.n_g == pytest.approx(2.0)

    def test_matches_closure_at_well(self, results):
        """Численная Sg у забоя совпадает с корнем уравнения замыкания.

        Сверка ведётся ИМЕННО У ЗАБОЯ, а не по максимуму относительной ошибки:
        у фронта численная схема даёт малые ненулевые Sg в ячейках, где
        замыкание даёт строго 0 (размазывание корневой особенности
        Sg ~ sqrt(pb - p)), и относительная метрика там вырождается в 100 %
        при любой точности. Измерено: max|dSg| = 1.41e-2 по области, но у
        забоя 0.699965 против 0.699933 — согласие 0.005 %.

        Допуск 1 % с запасом на возможное измельчение сетки.
        """
        import sys
        sys.path.insert(0, str(EXAMPLES_DIR))
        from closed_form import Closure
        from gpn_multiphase_solver.factory import (
            SimulatorFactory, _create_relperm)

        cfg = load_config(EXAMPLES_DIR / HIGH_SG / "config.json")
        sim, _ = SimulatorFactory.from_config(cfg)
        # Closure принимает объект ОФП напрямую — работает и с CoreyRP.
        clo = Closure(sim._energy._pvt, _create_relperm(cfg),
                      cfg.initial_conditions.Rs0)

        p_well = float(results[HIGH_SG]["p"][0])
        Sg_well = float(results[HIGH_SG]["Sg"][0])
        assert clo.Sg(p_well) == pytest.approx(Sg_well, rel=1e-2)

    def test_saved_steps_match_other_examples(self, results):
        """Прореживание возвращает вывод к тем же 73 состояниям, что у 04.

        dt_integration = 300 даёт 864 подшага против 72 у остальных примеров,
        и при save_every = 1 это дало бы 865 состояний и profiles.csv на
        3.4 МБ вместо 0.28 МБ, а рекуррентная ОДУ-аналитика температуры
        (863 последовательных solve_ivp) перестала бы завершаться за
        разумное время. Множитель 12 выбран так, чтобы 864/12 = 72 подшага
        плюс начальное состояние — формат вывода 04a неотличим от прочих.
        """
        cfg = load_config(EXAMPLES_DIR / HIGH_SG / "config.json")
        assert cfg.output.save_every == 12
        n_04a = len(results[HIGH_SG]["history"].times)
        n_04 = len(results["04_table_table"]["history"].times)
        assert n_04a == n_04 == 73, f"04a: {n_04a}, 04: {n_04}"

    @pytest.mark.slow
    def test_dense_grid_converges_at_default_retries(self):
        """Сгущённая сетка N = 80 считается на ШТАТНОМ numerics.max_retries.

        Отложенный критерий BUG-003: до его исправления лимит дробления шага
        был жёстко зашит равным 5 (2^5 = 32 подшага), и этот сценарий при
        N >= 80 падал с RuntimeError. Здесь нужно 9 (512 подшагов), потому
        что при Sg ~ 0.7 обе фазы малоподвижны одновременно (kro = 0.30,
        krg = 6.9e-4) и якобиан плохо обусловлен по обеим переменным.
        Уменьшение dt_integration не помогает: A-retry дробит шаг внутри.

        Тест проверяет ровно то, что нельзя было проверить до создания 04a:
        значение по умолчанию 9 действительно достаточно для ЭТОГО класса
        задач (табличный PVT, высокая Sg), а не только для сценария с
        корреляциями Стендинга, на котором BUG-003 верифицировался косвенно.

        Отдельный прогон, а не фикстура results: сетка другая. ~60 с, отсюда
        маркер slow (pytest -m "not slow" его пропустит).
        """
        cfg = load_config(EXAMPLES_DIR / HIGH_SG / "config.json")
        cfg.grid.N = 80
        # Приватные поля НЕ трогаем: смысл теста в том, что штатного
        # значения из конфига достаточно.
        assert cfg.numerics.max_retries == 9, (
            "значение по умолчанию изменилось — пересмотреть BUG-003")

        sim, initial = SimulatorFactory.from_config(cfg)
        history = sim.run(initial)

        Sg_well = float(history.states[-1].Sg[0])
        assert Sg_well == pytest.approx(0.7000, abs=1e-3), (
            f"N = 80: Sg(r_w) = {Sg_well}, ожидалось 0.7000")

        # Дебит сходится по сетке: 4.9978e-3 при N = 50 против 4.9651e-3
        # при N = 80 — 0.65 %. Допуск 1 % по записи BUG-003.
        q_o = abs(float(history.hydro_results[-1].G_o[0]))
        assert q_o == pytest.approx(4.9651e-3, rel=1e-2), (
            f"N = 80: q_o = {q_o}, ожидалось 4.9651e-3")
