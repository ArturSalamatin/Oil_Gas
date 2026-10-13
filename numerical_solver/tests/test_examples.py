"""Smoke-тесты для примеров из examples/ (FEAT-013).

Проверяет:
  A. Структура: каждая подпапка содержит config.json, main.py, README.md
  B. Конфиги: load_config проходит, CSV на месте, нет мёртвых полей
  C. Расчёт: все сценарии ALL_EXAMPLES считаются без NaN/Inf, Sg ∈ [0,1], p > 0, T > 0
  D. Физика по семействам: однофазные без газа, двухфазные с газом
  E. Суперпозиция тепловых вкладов: (T08-T07) + (T09-T07) = T04-T07
  F. Расщепление: термика не влияет на гидродинамику (побитово)
  G. README: обязательные разделы на месте

Расчёты кэшируются на уровне сессии (фикстура results): каждый сценарий
считается один раз, при первом обращении; все 23 — около 5.5 мин.
Тесты на фикстуре помечены slow (хук в tests/conftest.py, DEBT-032).
"""

import json
from pathlib import Path

import numpy as np
import pytest

from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.io.config import NumericsConfig, load_config
from gpn_multiphase_solver.io.output import pvt_table_nodes, relperm_table_nodes

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
    "11_degassing_at_boundary",
    "12_large_drainage_radius",
    "13a_pwf_ramp_down",
    "13b_pwf_alternating",
    "14_high_gor_cooling",
    "15_oil_rate_ramp_up",
    "16_well_shut_in",
    "17_shut_in_strong_cooling",
    "18_prototype_input",
    "19_rs150_cooling",
    "20_rs300_cooling",
    "21_rs100_cooling",
]

# Семейство 1: Rs0 = 0 → газ не выделяется ни при каком давлении.
SINGLE_PHASE = ["01_single_phase_no_jt", "02_single_phase_jt"]

# Семейства 2 и 3: pwf < pb → разгазирование обязано произойти.
TWO_PHASE = [n for n in ALL_EXAMPLES if n not in SINGLE_PHASE]

# Сценарии, заканчивающиеся остановом скважины (FEAT-019, FEAT-029): на
# последней записи дебит нулевой. Утверждения «скважина добывает» и «газ
# выделяется» на последней записи для них неверны по смыслу (у 17 газ на
# финале есть — кольцо 3.6–24 м, — но дебит газа нулевой); у них то же
# проверяется на конце добычи — в классе сценария (TestWellShutIn,
# TestShutInStrongCooling).
ENDS_SHUT_IN = ["16_well_shut_in", "17_shut_in_strong_cooling"]
PRODUCING_AT_END = [n for n in ALL_EXAMPLES if n not in ENDS_SHUT_IN]
TWO_PHASE_AT_END = [n for n in TWO_PHASE if n not in ENDS_SHUT_IN]

# Сценарии с табличной ОФП (Sg мала) — им нужен раздел про увеличение Sg.
NEEDS_SG_SECTION = [
    "04_table_table", "06_table_corey_rp",
    "07_degassing_adiabatic_only", "08_degassing_jt",
    "09_degassing_latent_heat", "10_deep_degassing",
    "11_degassing_at_boundary", "12_large_drainage_radius",
    "13a_pwf_ramp_down", "13b_pwf_alternating", "14_high_gor_cooling", "15_oil_rate_ramp_up",
    "16_well_shut_in",
    "18_prototype_input",
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
        "grid": simulator.grid,
        # конфиг примера — для проверок, которым он нужен
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


class _LazyResults(dict):
    """Срезы результатов примеров по имени: расчёт при первом обращении (DEBT-032)."""

    # dict вызывает __missing__, когда ключа нет: results["03_standing_corey"]
    # считает пример, кладёт в словарь, следующие обращения берут готовое.
    # Расчёт запускает только results[name]; .get(), in и items() — нет.
    # Тесты обращаются к results только как results[name].
    def __init__(self) -> None:
        super().__init__()
        # Упавший расчёт запоминается: иначе каждый тест примера (до ~12)
        # пересчитывал бы его заново до той же ошибки. Прежняя фикстура
        # падала один раз — pytest кеширует исключение фикстуры с областью
        # «сессия».
        self._failed: dict[str, Exception] = {}

    def __missing__(self, name: str) -> dict:
        if name in self._failed:
            raise RuntimeError(
                f"{name}: расчёт примера уже упал в этой сессии") from self._failed[name]
        try:
            self[name] = _run(name)
        except Exception as exc:
            self._failed[name] = exc
            raise
        return self[name]


@pytest.fixture(scope="session")
def results():
    """Сценарии ALL_EXAMPLES: расчёт при первом обращении, один раз на сессию."""
    # Ленивый расчёт (DEBT-032): выборочный запуск теста на одном примере
    # стоит одного расчёта, а не двадцати трёх (~2.5 мин, замер 2026-10-11). Имя фикстуры читает
    # хук tests/conftest.py: тесты на ней получают метку slow.
    return _LazyResults()


def _output(name: str):
    """Секция output конфига примера (FEAT-030): состав штатного вывода."""
    return load_config(EXAMPLES_DIR / name / "config.json").output


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
    def test_no_removed_keys(self, name):
        """В конфигах примеров нет ключей, удалённых из схемы (DEBT-008).

        Загрузчик пропускает их с предупреждением; в примере такой ключ
        внушал бы, что поле на что-то влияет (до DEBT-008 — output.format,
        numerics.dt_min, dt_max, time.start_day: объявлены, но не читались).
        """
        raw = json.loads((EXAMPLES_DIR / name / "config.json").read_text(encoding="utf-8"))
        removed = {"rock": ("p_ref",), "time": ("start_day",),
                   "numerics": ("dt_min", "dt_max", "newton_rtol", "newton_atol"),
                   "output": ("format",)}
        for section, keys in removed.items():
            for key in keys:
                assert key not in raw.get(section, {}), f"{name}: {section}.{key}"

    def test_output_explicit(self):
        """У каждого примера заголовок и steady_state заданы в конфиге явно (FEAT-030).

        Умолчание steady_state сменилось с true (run_example) на false
        (решение пользователя 2026-10-13): пример без явного поля тихо
        потерял бы стационарную аналитику. Множество примеров с true —
        те, у кого до FEAT-030 main.py флаг не снимал.
        """
        steady = set()
        for name in ALL_EXAMPLES:
            out = json.loads((EXAMPLES_DIR / name / "config.json")
                             .read_text(encoding="utf-8"))["output"]
            assert isinstance(out.get("title"), str) and out["title"].strip(), (
                f"{name}: нет output.title")
            assert isinstance(out.get("steady_state"), bool), (
                f"{name}: нет явного output.steady_state")
            if out["steady_state"]:
                steady.add(name)
        assert steady == {
            "01_single_phase_no_jt", "02_single_phase_jt", "03_standing_corey",
            "04_table_table", "04a_high_gas_saturation", "05_standing_table_rp",
            "06_table_corey_rp", "07_degassing_adiabatic_only", "08_degassing_jt",
            "09_degassing_latent_heat", "10_deep_degassing",
            "11_degassing_at_boundary", "12_large_drainage_radius",
            "13a_pwf_ramp_down", "15_oil_rate_ramp_up"}


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

    @pytest.mark.parametrize("name", PRODUCING_AT_END)
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

    @pytest.mark.parametrize("name", TWO_PHASE_AT_END)
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

    @pytest.mark.parametrize("name", TWO_PHASE_AT_END)
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

    Теплопроводность у всех четырёх одинакова (1.5 / 0.14 / 0.04, DEBT-023)
    и равенства не нарушает: при замороженной гидродинамике уравнение
    энергии линейно по T, а lambda_eff зависит от S_g, не от T. Разные
    lambda у этих примеров сдвинули бы равенство на 1–2e-3 К — на уровне
    допуска, поэтому менять их только вместе.

    Tolerance 1e-3 К: при измерении равенство выполняется с невязкой
    0…6e-14 К (машинная точность; замер DEBT-023), запас оставлен на
    изменения дискретизации.
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


def test_thermal_effects_sign(results):
    """Знаки вкладов относительно опоры 07 (mu_JT = 0, L = 0).

    JT (08): mu_JT,o < 0 — нефть при дросселировании греется; газа мало
    (S_g ≲ 0.015), поэтому суммарный вклад — нагрев.
    Скрытая теплота (09): L > 0, газ выделяется — охлаждение.
    """
    T07 = results["07_degassing_adiabatic_only"]["T_well"]
    assert results["08_degassing_jt"]["T_well"] > T07
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


def _asymptotics_module():
    """Однофазная асимптотика — модуль пакета (DEBT-011)."""
    from gpn_multiphase_solver.diagnostics import temperature
    return temperature


def test_02_relaxes_toward_jt_asymptote(results):
    """Пример 02 идёт к аналитической JT-асимптотике T = T_ext + mu_JT·(p - p_0).

    При lambda = 0 стационарный энергобаланс rho·cp·u·dT/dr = rho·cp·mu_JT·u·dp/dr
    даёт dT/dr = mu_JT·dp/dr — скорость сокращается, профиль не зависит
    от дебита. Опорная точка — контур r = R_e: ГУ задаёт там T_ext при
    p = p_0 (factory.py). При mu_JT < 0 нефть греется уже на полуячейке
    между контуром и центром последней ячейки (compute_jt, перепад
    p_ext - p[N-1]), поэтому асимптота в ячейке N-1 равна
    T_ext - mu_JT·(p_0 - p[N-1]) > T_ext, а не T_ext (BUG-013).

    За 3 суток релаксация не завершается, поэтому проверяем не совпадение,
    а движение в нужную сторону: температура на забое растёт
    и остаётся ниже асимптотики (подходит снизу, не проскакивает).
    """
    res = results["02_single_phase_jt"]
    ta = _asymptotics_module()
    T_ext = res["config"].initial_conditions.T0

    T = res["T"]
    T_asymp = ta.single_phase_asymptote(res["config"], res["history"])

    # Подход снизу: JT нефти (mu_JT < 0) только греет, адиабатический
    # импульс 1-го шага (dp/dt < 0, множитель 1 + rho·cp·mu_JT ≈ 0.35 > 0)
    # охлаждает — оба удерживают T ниже асимптотики. Проверяются ВСЕ ячейки,
    # включая приконтурную: её асимптота выше T_ext на
    # |mu_JT|·(p_0 - p[N-1]) ≈ 0.0067 К. Прежний отсчёт от p[N-1] ставил
    # асимптоту этой ячейки в T_ext, и сдвиг оставался незамеченным.
    assert np.all(T <= T_asymp + 1e-9), \
        "температура проскочила выше JT-асимптотики"

    # Но уже прошла заметную часть пути: у забоя полный размах ~2 К,
    # за 3 суток остаётся отставание меньше половины.
    gap_well = T_asymp[0] - T[0]
    full_swing = T_asymp[0] - T_ext
    assert 0.0 < gap_well < 0.5 * full_swing, \
        f"отставание у забоя {gap_well:.3f} К вне ожидаемого диапазона"

    # Динамика: после адиабатического провала 1-го шага температура на
    # забое растёт под действием постоянного JT-источника и уходит выше T_ext.
    T_well = np.array([s.T[0] for s in res["history"].states])
    assert T_well[-1] > T_well[1], \
        "T(r_w) должна расти под действием постоянного JT-источника"
    assert T_well[-1] > T_ext, \
        "нефть при дросселировании (mu_JT < 0) должна нагреть забой"


def test_single_phase_asymptote_reference_is_contour(results):
    """Однофазная асимптотика отсчитывается от давления на контуре p_0 (BUG-013).

    ГУ задаёт T_ext при p = p_0 на контуре, а не в центре последней ячейки,
    поэтому асимптота в ячейке N-1 ниже T_ext на mu_JT·(p_0 - p[N-1]).
    Прежняя формула отсчитывала от p[N-1] и сдвигала асимптоту примера 02
    на ~0.0067 К по всей однофазной зоне.
    """
    res = results["02_single_phase_jt"]
    ta = _asymptotics_module()
    cfg = res["config"]
    T0 = cfg.initial_conditions.T0
    p0 = cfg.initial_conditions.p0
    mu = cfg.thermal.mu_JT_oil
    p = res["p"]

    T_as = ta.single_phase_asymptote(cfg, res["history"])

    # Та же формула, записанная независимо: отсчёт от p_0 на всей сетке.
    assert np.allclose(T_as, T0 + mu * (p - p0), rtol=0.0, atol=1e-12)

    # Приконтурная ячейка не опорная: её асимптота отличается от T0 ровно на
    # JT-перепад полуячейки; при mu_JT < 0 — выше T0. Допуск абсолютный:
    # |T0 - T_as[-1]| ~ 7e-3 К — разность чисел ~350 К, её относительная
    # ошибка округления ~1.5e-12, и rel=1e-12 давал бы ложное падение.
    assert T0 - T_as[-1] == pytest.approx(mu * (p0 - p[-1]), abs=1e-12)
    assert T_as[-1] - T0 > 0.0


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
        # DEBT-039: баланс массы компонентов — общий модуль для всех примеров
        "mass_balance.png",
        # FEAT-017: свойства PVT — общий модуль для всех примеров
        "pvt.png",
    ]
    for fname in expected:
        path = tmp_path / fname
        assert path.is_file(), f"не создан {fname}"
        assert path.stat().st_size > 0, f"пустой файл {fname}"


def test_profile_times_default_and_uniform():
    """Моменты профильных графиков: 4 опорных по умолчанию, N — равномерно.

    31 полусуточная запись (как у 13a). По умолчанию (n_profiles=None) —
    начало, 1/3, 2/3 и конец: индексы 0, 10, 20, 30; у остальных примеров
    так и остаётся. При n_profiles = 6 — моменты равномерно по времени
    на [0, 15 сут]: 0, 3, 6, 9, 12, 15 сут (решение пользователя
    2026-09-29 для 13a). N больше числа записей даёт каждую запись по
    одному разу; N = 1 эволюции не показывает — ValueError.
    """
    import sys
    sys.path.insert(0, str(EXAMPLES_DIR))
    from example_runner import _profile_times

    day = 86400.0
    times = [43200.0 * n for n in range(31)]
    assert _profile_times(times, n_profiles=None) == [
        times[0], times[10], times[20], times[30]]
    assert _profile_times(times, n_profiles=6) == [
        0.0, 3 * day, 6 * day, 9 * day, 12 * day, 15 * day]
    assert _profile_times(times, n_profiles=100) == times
    with pytest.raises(ValueError):
        _profile_times(times, n_profiles=1)


def test_pick_overlay_none_disables_default():
    """Наложение поля: нет ключа — умолчание; функция — она; None — без наложения.

    До FEAT-022 выбор шёл через `overlays.get(key) or умолчание`, и явный
    None молча заменялся умолчанием — отключить стационарное решение из
    примера было нельзя. 13a отключает его на профилях S_g (решение
    пользователя 2026-09-29): стационарное замыкание GOR = R_s0 при
    GOR = 54.9 на 15 сут вводит в заблуждение.
    """
    import sys
    sys.path.insert(0, str(EXAMPLES_DIR))
    from example_runner import _pick_overlay

    default, own = object(), object()
    assert _pick_overlay({}, "Sg", default) is default
    assert _pick_overlay({"T": own}, "Sg", default) is default
    assert _pick_overlay({"Sg": own}, "Sg", default) is own
    assert _pick_overlay({"Sg": None}, "Sg", default) is None


def test_steady_state_false_skips_steady_analytics(tmp_path, monkeypatch):
    """steady_state=False снимает стационарную аналитику, проверку R_s — нет.

    Решения пользователя: 2026-09-29 (FEAT-022, реш. 7) — стационарные
    наложения и сверки отключаются флагом run_example; 2026-09-30
    (FEAT-023) — проверка R_s остаётся. Стационар и асимптотика
    температуры — пределы t -> inf при удержании одного режима; у 13b
    режим меняется каждые сутки, и сверки печатали бы 7085 % и 0.94 К.

    Функции проверок подменяются шпионами: тест смотрит, что они НЕ
    вызываются, а не разбирает PNG. Пример 05 — самый быстрый двухфазный
    (~5 с). Путь по умолчанию (steady_state=True) покрыт
    test_energy_balance_reported_for_all_examples («Асимптотика
    температуры» в выводе).
    Ловит: флаг снимает не всё (наложение или один из отчётов остался)
    или снимает лишнее (report_rs).
    """
    import contextlib
    import io
    import sys
    sys.path.insert(0, str(EXAMPLES_DIR))
    import example_runner

    called = []

    def spy(name):
        def f(*args, **kwargs):
            called.append(name)
            # make_overlay_* вернули бы функцию рисования; None — «без наложения»
            return None
        return f

    for name in ("make_overlay_pressure", "make_overlay_saturation",
                 "report_closed", "report_asymptotics", "report_rs"):
        monkeypatch.setattr(example_runner, name, spy(name))

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        example_runner.run_example(
            config_path=EXAMPLES_DIR / "05_standing_table_rp" / "config.json",
            output_dir=tmp_path,
            title="тест steady_state",
            steady_state=False,
        )

    assert called == ["report_rs"], f"вызваны: {called}"
    assert "Стационарная аналитика отключена" in buf.getvalue()


# ═══════════════════════════════════════════════════════════
# I. Общие проверки: балансы энергии и массы у всех примеров (FEAT-016, DEBT-039)
# ═══════════════════════════════════════════════════════════

# Модули проверок, оставшиеся в examples/ после FEAT-030: печать и рисунки
# общих проверок — в пакете, gpn_multiphase_solver/report/.
# test_shared_modules_exist проверяет, что они на месте: без них примеры
# 03–05 и исследование сходимости баланса не работают.
SHARED_CHECK_MODULES = [
    "energy_balance_convergence.py",
    "two_phase_analytics.py",
]

# Все файлы верхнего уровня examples/ — общие модули и скрипты. Ни один из
# них не должен снова появиться в папке примера: исход у копии молчаливый
# при любом порядке sys.path.
#   - main.py 01, 02, 03, 05 и скрипты сходимости 04, 04a, 05 делают
#     sys.path.insert(0, ...) сначала для examples/, затем для папки
#     примера, и папка оказывается ВПЕРЕДИ. Копия ПЕРЕКРЫВАЕТ общий модуль
#     без ошибки импорта — и для всех, кто его импортирует: копия
#     figure_io.py подменит его и внутри example_runner.py.
#   - Остальные main.py вставляют только examples/, и он встаёт впереди
#     папки скрипта. Копия молча игнорируется: её правка ни на что не влияет.
# Именно так четыре копии energy_balance.py разошлись и породили BUG-004.
# Список строится по диску, а не вручную (DEBT-037): ручной список отстал —
# example_runner.py, figure_io.py и ещё четыре общих модуля в нём не
# значились. Новый файл в examples/ попадает под проверку сам.
SHARED_EXAMPLE_FILES = sorted(p.name for p in EXAMPLES_DIR.glob("*.py"))

# Прежде здесь стоял отдельный список BALANCE_EXAMPLES: баланс суммировал
# приращения по сохранённым шагам, поэтому пример 04a (save_every = 12,
# запись раз в 12 подшагов) из проверки выпадал. После DEBT-013 члены
# копятся на подшагах внутри решателя, баланс корректен при любой
# структуре истории, и проверка идёт по ALL_EXAMPLES — включая 04a.


class TestSharedChecks:
    def test_energy_balance_all_examples(self, results):
        """Баланс энергии замыкается у всех примеров с машинной точностью.

        До BUG-004 невязка была 0.18-0.29 на шести конфигурациях из десяти,
        и на пяти из них это никем не проверялось: свой energy_balance.py
        имели только 01, 02, 03, 05.

        Порог 1e-12, а не прежний 1e-2: дискретные уравнения схемы —
        тождество, они замыкаются при любом dt, если все члены выписаны на
        правильных слоях. Прежний порог подгонялся под наблюдаемые ~1e-3,
        которые считали ошибкой расщепления O(dt); после BUG-007 выяснилось,
        что это был дефект (конвекция на слое T^n вместо T^{n+1}), а
        расщепления в балансе нет вовсе.

        Затем стоял порог 1e-10, и он лежал на уровне шума: СЛАУ решалась в
        абсолютной T, и округления ~ε·cap·T давали до 1.3e-10 (16 после
        BUG-020). С DEBT-043 СЛАУ решается в отклонениях θ = T − T_ext:
        замер 2026-10-07 — 0…5.2e-15 у всех примеров (максимум по записям),
        запас ×190; наименьшая известная невязка дефекта (BUG-007) — 5.7e-4.

        Идёт по ALL_EXAMPLES, включая 04a: после DEBT-013 члены баланса
        копятся на подшагах, поэтому структура истории проверке не мешает.
        """
        from gpn_multiphase_solver.energy.balance import compute_energy_balance

        bad = {}
        for name in ALL_EXAMPLES:
            r = results[name]
            bal = compute_energy_balance(r["history"])
            rel = abs(float(bal["rel_residual"][-1]))
            # «not <»: NaN в невязке — тоже провал (прежнее «>=» его пропускало)
            if not rel < 1e-12:
                bad[name] = rel
        assert not bad, f"невязка баланса >= 1e-12: {bad}"

    def test_mass_balance_all_examples(self, results):
        """Баланс массы компонентов замыкается у всех примеров (DEBT-039).

        Порог 1e-6 на максимум относительной невязки по всем записям, нефть и
        газ. Уровень — допуск Ньютона прототипа, а не округления, как у
        баланса энергии: проверяется не физика (масса сохраняется невязкой
        Ньютона), а всё между невязкой и историей — допуск, накопленный по
        шагам; знаки потоков адаптера; учёт дробления шага. Замер при
        планировании (2026-10-06): 4.0e-13 ... 2.9e-8 (пример 15), запас к
        порогу — 35 раз; дефекты учёта дают 1e-3...1.
        """
        from gpn_multiphase_solver.mass_balance import compute_mass_balance

        bad = {}
        for name in ALL_EXAMPLES:
            bal = compute_mass_balance(results[name]["history"])
            assert bal is not None, f"{name}: баланс массы не считается"
            worst = max(float(np.max(bal["rel_residual_o"])),
                        float(np.max(bal["rel_residual_g"])))
            if worst >= 1e-6:
                bad[name] = worst
        assert not bad, f"невязка баланса массы >= 1e-6: {bad}"

    def test_conduction_term_always_computed(self, results):
        """Кондуктивный член считается безусловно, а не при lambda != 0.

        Ключевая защита FEAT-016. Пропуск члена у примера 10 (единственного
        с lambda != 0) маскировался девятью примерами с lambda = 0: у них он
        тождественно нулевой, поэтому отсутствие члена было незаметно.
        Проверяем ОБА случая: ключ присутствует всегда, при lambda = 0 член
        строго нулевой, при lambda != 0 — ненулевой.

        Идёт по ALL_EXAMPLES: после DEBT-013 баланс считается при любой
        структуре истории, отдельного списка исключений больше нет.
        """
        from gpn_multiphase_solver.energy.balance import compute_energy_balance

        for name in ALL_EXAMPLES:
            r = results[name]
            cfg = r["config"]
            bal = compute_energy_balance(r["history"])

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
                # Q_T[N] = geom * lambda_eff[-1] при lambda = 0 даёт ровно
                # 0.0, без NaN и inf (compute_conductive_transmissibility).
                assert np.all(cond == 0.0), (
                    f"{name}: lambda = 0, но cum_cond != 0: {cond[-1]}")

    def test_full_key_set_always_returned(self, results):
        """Набор ключей compute_energy_balance полный независимо от конфига.

        Прежние копии для однофазных примеров не возвращали cum_jt (01) и
        cum_deg (01, 02) — отсутствующие ключи ломали бы вызывающий код.
        Физически отсутствующие члены приходят нулевыми массивами.

        Идёт по ALL_EXAMPLES: после DEBT-013 баланс считается при любой
        структуре истории, отдельного списка исключений больше нет.
        """
        from gpn_multiphase_solver.energy.balance import compute_energy_balance

        required = {"t", "delta_E", "cum_adiab", "cum_conv", "cum_jt",
                    "cum_deg", "cum_cond", "total", "residual",
                    "rel_residual"}
        for name in ALL_EXAMPLES:
            r = results[name]
            bal = compute_energy_balance(r["history"])
            missing = required - set(bal)
            assert not missing, f"{name}: отсутствуют ключи {sorted(missing)}"

    @pytest.mark.parametrize("module", SHARED_EXAMPLE_FILES)
    def test_no_duplicate_helper_scripts(self, module):
        """Файл examples/ не вернулся копией в папку примера.

        Защита от того самого механизма, которым возникла FEAT-016: скрипт
        пишется под один пример, копируется в другой, копии правятся
        независимо и расходятся. Копия в папке примера при этом молча
        перекрывает общий модуль или молча игнорируется — в зависимости
        от порядка sys.path (комментарий у SHARED_EXAMPLE_FILES).
        """
        copies = sorted(
            p.parent.name for p in EXAMPLES_DIR.glob(f"*/{module}"))
        assert not copies, (
            f"{module} снова скопирован в папки примеров: {copies}. "
            f"Общий модуль examples/{module} будет молча перекрыт, "
            f"либо копия будет молча проигнорирована.")

    def test_shared_modules_exist(self):
        """Общие модули на месте — иначе примеры не считают проверки."""
        for module in SHARED_CHECK_MODULES + ["convergence.py"]:
            path = EXAMPLES_DIR / module
            assert path.is_file(), f"нет общего модуля examples/{module}"

    # Имена, которые скрипты examples/ берут из общих модулей, проверяет
    # tests/test_example_scripts.py (DEBT-046) — без исполнения скриптов.
    # Он заменил тест импорта convergence.py и его пользователей (DEBT-031).

    def test_energy_balance_reported_for_all_examples(self, tmp_path):
        """run_example печатает баланс энергии — проверка подключения.

        Отличается от test_energy_balance_all_examples: тот проверяет, что
        баланс СХОДИТСЯ, а этот — что он вообще ВЫЗЫВАЕТСЯ из run_example.
        Без этого общий модуль мог бы существовать, но не быть подключён, и
        примеры 06-10 снова остались бы без проверки.

        Берётся пример 10: у него lambda != 0, поэтому в выводе должна быть
        и ненулевая строка теплопроводности. Тот же прогон проверяет
        подключение баланса массы компонентов (DEBT-039).
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
        # DEBT-039: баланс массы подключён к тому же run_example
        assert "Баланс массы компонентов" in out, (
            "run_example не печатает баланс массы")
        assert (tmp_path / "mass_balance.png").is_file(), (
            "run_example не сохранил график баланса массы")
        # Асимптотика подключена и печатает заголовок. Прежде здесь
        # проверялось сообщение «не проверяется» при lambda != 0: условие
        # относилось к ТЕЛЕСКОПИЧЕСКОЙ формуле, которая удалена вместе со
        # всей двухфазной аналитикой (BUG-012). Однофазная асимптотика
        # T = T_ext + mu_JT·(p - p_ext) от теплопроводности не зависит и
        # считается при любом lambda.
        assert "Асимптотика температуры" in out, (
            "run_example не вызывает report_asymptotics")
        assert "двухфазная зона: аналитической проверки нет" in out, (
            "у примера 10 есть газ — отчёт должен сообщить, что "
            "двухфазной аналитики больше нет")

    def test_rs_check_all_two_phase_examples(self, results):
        """Проверка R_s проходит у всех примеров с газом, включая 12 и 13b (DEBT-026).

        Ячейки с газом (Sg > 1e-8): |Rs - Rs_eq(p)| <= 1e-10 (замер
        2026-10-03: 0 побитово у 03-10, 19-21, не больше 2.8e-14 у
        остальных). Ячейки без газа: пересыщенных (Rs > Rs_eq(p) + 1e-5)
        нет. У 12 и 13b на последней записи есть нефть без газа ниже p_b —
        недонасыщенная после восстановления давления (замер: 1 и 30).
        Прежняя проверка min(Rs_eq(p), Rs0) печатала на них «не совпадают»;
        условие >= 1 гарантирует, что тест действительно проходит через
        этот случай, а не только через падающее давление.
        Ловит: возврат к формуле min(...) во всех ячейках, задержку
        выделения газа и рассогласование PVT (ошибка в ячейках с газом),
        растворение газа сверх равновесия (пересыщение).
        """
        import contextlib
        import io
        from gpn_multiphase_solver.report.rs import report_rs

        reps = {}
        for name in TWO_PHASE:
            r = results[name]
            pvt = _pvt_of_config(r["config"])
            # report_rs печатает отчёт примера — в выводе теста он не нужен.
            with contextlib.redirect_stdout(io.StringIO()):
                reps[name] = report_rs(r["config"], r["history"], pvt)

        bad = {n: (rep["max_abs"], rep["n_supersaturated"])
               for n, rep in reps.items()
               if rep["max_abs"] > 1e-10 or rep["n_supersaturated"] > 0}
        assert not bad, f"проверка R_s не прошла (max_abs, пересыщенных): {bad}"

        for name in ("12_large_drainage_radius", "13b_pwf_alternating"):
            assert reps[name]["n_single_below_pb"] >= 1, (
                f"{name}: нет недонасыщенной нефти ниже p_b — тест больше не "
                f"проверяет случай восстановления давления")


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
    """Модуль пакета report/pvt.py (до FEAT-030 — examples/pvt_plot.py)."""
    from gpn_multiphase_solver.report import pvt as pvt_plot
    return pvt_plot


def _pvt_of_config(cfg):
    """PVT, собранный фабрикой по конфигу (эталон для сверки)."""
    from gpn_multiphase_solver.factory import create_pvt
    return create_pvt(cfg)


def _pvto_lines(ax, gid):
    """Кривые панели с разметкой gid (ядро размечает кривые PVTO через set_gid)."""
    return [ln for ln in ax.get_lines() if ln.get_gid() == gid]


def _table_pvto_axes(name, p_range):
    """Рисунок ядра по табличному PVT примера name без расчёта: (fig, axes, pvt, Rs0)."""
    import matplotlib.pyplot as plt
    from gpn_multiphase_solver.io.output import plot_pvt_properties
    cfg = load_config(EXAMPLES_DIR / name / "config.json")
    pvt = _pvt_of_config(cfg)
    Rs0 = float(cfg.initial_conditions.Rs0)
    fig, axes = plt.subplots(2, 3)
    plot_pvt_properties(pvt, Rs0, p_range, axes=axes,
                        table_nodes=pvt_table_nodes(pvt, Rs0))
    return fig, axes, pvt, Rs0


class TestPvtPlot:
    """Оформитель графика PVT: pvt.png, сводка, узлы таблиц.

    Приоритет по постановке задачи — вязкость mu_o и газосодержание Rs
    нефтяной фазы: первая входит в подвижность lambda_o = k*k_ro/mu_o,
    второе — в замыкание GOR = Rs0.
    """

    def test_plot_pvt_all_examples(self, results, tmp_path):
        """Модуль отрабатывает на всех примерах и пишет непустой PNG.

        Покрывает обе PVT-модели (standing: 01, 02, 03, 05; table: 04,
        06-10) и оба режима (однофазный Rs0 = 0: 01, 02; двухфазный —
        остальные). Граничный случай Rs0 = 0 опасен: p_b = -0.176 МПа,
        и наивный код рисует вертикаль за пределами оси или падает.
        """
        pvt_plot = _pvt_module()
        for name in ALL_EXAMPLES:
            r = results[name]
            out = pvt_plot.plot_pvt(r["config"], r["history"],
                                    tmp_path / name, name)
            assert out.is_file(), f"{name}: pvt.png не создан"
            assert out.stat().st_size > 0, f"{name}: pvt.png пустой"

    def test_report_pb_matches_pvt(self, results):
        """report_pvt сообщает то же p_b, что и сам объект PVT.

        Эталон — вызов pvt.pb(Rs0). Допуск 1e-6 Па: обе стороны обязаны
        считать ОДНИМ вызовом, а не своей формулой. Заодно покрывается
        ветка simulator=None (fallback на factory.create_pvt): fixture
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

    def test_physical_branch_matches_rs_analytics(self, results):
        """Физическое R_s сводки report_pvt совпадает с diagnostics.rs.rs_expected побитово.

        Обе стороны считают min(Rs_eq(p), Rs0). Расхождение двух
        реализаций одной формулы — тот самый класс дефектов, ради
        которого FEAT-016 сводил четыре копии energy_balance.py, поэтому
        допуск нулевой.
        """
        from gpn_multiphase_solver.diagnostics.rs import rs_expected
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
        (eq:rho_oil и таблица обозначений problem_statement.tex).
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
        nodes = pvt_table_nodes(_pvt_of_config(r["config"]),
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
            nodes = pvt_table_nodes(_pvt_of_config(r["config"]),
                                              r["Rs0"])
            assert nodes is None, f"{name}: у корреляции узлов быть не может"

    def test_table_nodes_in_working_range(self, results):
        """В рабочий диапазон примера 04 попадает ровно один узел.

        Демонстрационные таблицы грубы: рабочий диапазон 8.17…20.00 МПа
        (по всей истории: верх — начальное p_0, FEAT-019), а узлы стоят на
        5, 15 и 30 МПа — внутрь попадает только p_b = 15.
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
                                    tmp_path / name, name)
            assert out.is_file()

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
        nodes = pvt_table_nodes(_pvt_of_config(r["config"]),
                                          r["Rs0"])
        assert set(nodes) >= {"p_gas", "p_oil"}, "ключи должны быть раздельны"
        assert "p_all" not in nodes, (
            "объединение делает _nodes_in_range, а не сам сборщик узлов")

    def test_table_branches_are_pvto_rows(self):
        """Ветви табличного PVT — строки таблицы; легенда не растёт с их числом.

        Пример 14: строки 0, 10, …, 180; на оси 4.8…26.95 МПа (p_range
        6…24.5 МПа) видны все, кроме 180 (p_b = 27.63 МПа); 150 = R_s,0
        рисуется отдельно → 17 тонких ветвей + 1 жирная.
        """
        import matplotlib.pyplot as plt
        fig, axes, _, _ = _table_pvto_axes("14_high_gor_cooling", (6e6, 24.5e6))
        ax = axes[0, 0]
        n_thin, n_rs0 = (len(_pvto_lines(ax, "pvto_branch")),
                         len(_pvto_lines(ax, "pvto_rs0")))
        n_labels = len(ax.get_legend().get_texts())
        plt.close(fig)
        assert (n_thin, n_rs0) == (17, 1)
        assert n_labels <= 5, f"записей легенды {n_labels} при 17 ветвях"

    def test_table_extrapolation_dashed_outside_rows(self):
        """Насыщенная кривая вне [p_b(R_s,min), p_b(R_s,max)] — пунктир.

        Таблица 04: строки 0 и 30, p_b = 5 и 15 МПа. rs_sat прототипа —
        np.interp, за краями R_s^eq зажата: это экстраполяция, а не данные
        таблицы. На оси 3.2…22 МПа (p_range 4…20 МПа, как у 04a) — пунктир
        слева до 5 МПа и справа от 15 МПа, сплошная ровно 5…15 МПа.
        """
        import matplotlib.pyplot as plt
        fig, axes, _, _ = _table_pvto_axes("04_table_table", (4e6, 20e6))
        ext = _pvto_lines(axes[0, 0], "pvto_saturated_extrap")
        sol = _pvto_lines(axes[0, 0], "pvto_saturated")
        plt.close(fig)
        assert len(ext) == 2 and len(sol) == 1
        assert ext[0].get_xdata().max() == pytest.approx(5.0)
        assert ext[1].get_xdata().min() == pytest.approx(15.0)
        assert sol[0].get_xdata().min() == pytest.approx(5.0)
        assert sol[0].get_xdata().max() == pytest.approx(15.0)

    def test_table_start_nodes_on_own_branch(self):
        """Маркер начала строки PVTO стоит на своей ветви, а не на ветви R_s,0.

        Пример 14: p_b(160) = 25.0376 МПа > p_b(150). До FEAT-028 ординаты
        узлов считались по «физическому» R_s = min(R_s^eq, R_s,0) = 150, и
        маркер строки 160 стоял на mu_o(p_b, 150) = 5.1727e-4 Па·с вместо
        mu_o(p_b, 160) = 4.8926e-4 — на 5.4 % выше начала своей ветви.
        """
        import matplotlib.pyplot as plt
        fig, axes, pvt, _ = _table_pvto_axes("14_high_gor_cooling", (6e6, 24.5e6))
        pb160 = float(pvt.pb(np.array([160.0]))[0])
        starts = [ln for ln in axes[0, 0].get_lines()
                  if ln.get_marker() == "o" and ln.get_color() == "C3"]
        plt.close(fig)
        assert len(starts) == 1, "маркеры начал строк — одной серией"
        i = np.flatnonzero(np.isclose(starts[0].get_xdata(), pb160 / 1e6,
                                      rtol=0.0, atol=1e-9))
        assert i.size == 1
        mu160 = float(pvt.mu_o(np.array([pb160]), np.array([160.0]))[0])
        assert starts[0].get_ydata()[i[0]] == pytest.approx(mu160, rel=1e-12)

    def test_p_branch_follows_rs0_row(self):
        """Узлы ветви R_s,0 — только если R_s,0 совпадает со строкой таблицы.

        Таблица 04: строка 30 задана при 15 и 30 МПа. При R_s,0 = 20 (между
        строками 0 и 30) ветвь интерполирована прототипом по dp и собственных
        узлов не имеет — p_branch пуст. Сводку это не меняет: p_oil прежний.
        """
        cfg = load_config(EXAMPLES_DIR / "04_table_table" / "config.json")
        pvt = _pvt_of_config(cfg)
        nodes = pvt_table_nodes(pvt, 30.0)
        assert np.allclose(nodes["p_branch"], [15e6, 30e6])
        assert np.allclose(nodes["p_oil"], [5e6, 15e6, 30e6])
        assert pvt_table_nodes(pvt, 20.0)["p_branch"].size == 0

    def test_describe_mu_o_branch(self):
        """Подпись Стендинга перечисляет свойства, горизонтальные выше p_b (FEAT-027).

        B_o горизонтальна при c_o = 0, μ_o — без ветви Била. Без фикстуры
        results — быстрый уровень. Сочетания (0, none) и (>0, none) дают ту же
        подпись, что до FEAT-027: PNG примеров не меняются.
        """
        pvt_plot = _pvt_module()
        cfg = load_config(EXAMPLES_DIR / "03_standing_corey" / "config.json")
        only_rs = r"от $p$ — только через $R_s$"
        cases = {
            (0.0, "none"): (r"($B_o$, $\mu_o$ " + only_rs, None),
            (3.3e-9, "none"): (r"($\mu_o$ " + only_rs, None),
            (0.0, "beal"): (r"($B_o$ " + only_rs, "— Бил"),
            (3.3e-9, "beal"): (None, "— Бил"),
        }
        for (co, mu_model), (flat_text, beal_text) in cases.items():
            cfg.pvt.co_undersaturated = co
            cfg.pvt.mu_o_undersaturated = mu_model
            s = pvt_plot._describe(cfg)
            where = f"c_o = {co}, {mu_model}: {s!r}"
            if flat_text is None:
                assert "только через" not in s, where
            else:
                assert flat_text in s, where
            if beal_text is None:
                assert "Бил" not in s, where
            else:
                assert beal_text in s, where

    def test_formatter_delegates_drawing_to_core(self):
        """Оформитель не рисует сам — всё построение в ядре.

        Стоит построению расползтись обратно в оформитель (report/pvt.py,
        до FEAT-030 — examples/pvt_plot.py) — и ядерная функция перестанет
        отражать то, что видит пользователь своих рисунков, а расслоение
        слоёв (FEAT-017, §4.0) потеряет смысл. Панель mu_o(r), единственное,
        что оформитель рисовал сам, снята FEAT-028.
        """
        import ast

        src = Path(_pvt_module().__file__)
        tree = ast.parse(src.read_text(encoding="utf-8"))

        drawing = {"plot", "semilogx", "loglog", "scatter"}
        stray = []
        calls_core = False
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Name) and func.id == "plot_pvt_properties":
                calls_core = True
            if isinstance(func, ast.Attribute) and func.attr in drawing:
                stray.append(func.attr)

        assert calls_core, "оформитель не вызывает ядерную plot_pvt_properties"
        assert not stray, f"оформитель рисует сам: {stray}"

    def test_plot_pvt_layout_2x3(self, monkeypatch, tmp_path):
        """pvt.png — сетка 2x3 без панели mu_o(r); у plot_pvt нет параметра grid.

        Панель вязкости в ячейках снята во всех примерах (FEAT-028): она про
        решение, а не про модель PVT. Фигура — 6 панелей и правая ось
        плотности газа (twinx), всего 7 осей. Рисунок перехватывается до
        записи, history — заглушка с одним состоянием: тест без расчёта.
        """
        import inspect
        from types import SimpleNamespace

        pvt_plot = _pvt_module()
        assert "grid" not in inspect.signature(pvt_plot.plot_pvt).parameters
        assert not hasattr(pvt_plot, "_plot_mu_o_spatial")

        saved = {}
        monkeypatch.setattr(pvt_plot, "save_figure",
                            lambda fig, out, dpi: saved.setdefault("fig", fig))
        cfg = load_config(EXAMPLES_DIR / "03_standing_corey" / "config.json")
        history = SimpleNamespace(
            states=[SimpleNamespace(p=np.linspace(8e6, 20e6, 5))])
        pvt_plot.plot_pvt(cfg, history, tmp_path, "03")
        assert len(saved["fig"].axes) == 7

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
# J2. Рабочий диапазон рисунков — по всей истории (FEAT-019)
# ═══════════════════════════════════════════════════════════

def _relperm_module():
    """Модуль пакета report/relperm.py (до FEAT-030 — examples/relperm_plot.py)."""
    from gpn_multiphase_solver.report import relperm as relperm_plot
    return relperm_plot


def _shut_in_like_history():
    """Синтетическая история «добыча → останов»: газ и воронка есть только в середине.

    Записи: начальное состояние (p = 15.5 МПа, газа нет), конец добычи
    (воронка 6.1…15.4 МПа, S_g до 0.05 у забоя), конец останова (p = 15.5 МПа
    всюду, газ растворился). Расчёта нет — проверяется только охват.
    """
    from types import SimpleNamespace
    n = 50
    states = [
        SimpleNamespace(p=np.full(n, 15.5e6), Sg=np.zeros(n)),
        SimpleNamespace(p=np.linspace(6.1e6, 15.4e6, n),
                        Sg=np.linspace(0.05, 0.0, n)),
        SimpleNamespace(p=np.full(n, 15.5e6), Sg=np.zeros(n)),
    ]
    return SimpleNamespace(states=states)


class TestWorkingRange:
    """Рисунки PVT и ОФП берут рабочий диапазон по всем записям (FEAT-019).

    Прежде диапазон брался по последней записи. У примера 16 (останов
    после добычи) давление к концу выравнивается, газ растворяется, и
    relperm.png объявлял расчёт однофазным, а pvt.png сжимал диапазон в
    точку 15.5 МПа.
    """

    CFG = EXAMPLES_DIR / "12_large_drainage_radius" / "config.json"

    def test_pvt_range_spans_all_records(self):
        """_p_range — min/max по всем записям, а не по последней (там 15.5…15.5)."""
        lo, hi = _pvt_module()._p_range(_shut_in_like_history())
        assert lo == 6.1e6
        assert hi == 15.5e6

    def test_relperm_range_spans_all_records(self):
        """_sg_range — максимум S_g за всю историю (0.05), хотя на последней записи газа нет."""
        lo, hi = _relperm_module()._sg_range(_shut_in_like_history())
        assert lo == 0.0
        assert hi == pytest.approx(0.05, abs=1e-15)

    def test_report_relperm_not_single_phase_after_shut_in(self, capsys):
        """Сводка ОФП не объявляет расчёт однофазным, если газ был, а к концу растворился.

        Таблица ОФП примера 12; ожидается строка «рабочий диапазон: S_g =
        0.000000 … 0.050000» вместо «расчёт однофазный».
        """
        from gpn_multiphase_solver.factory import create_relperm
        cfg = load_config(self.CFG)
        _relperm_module().report_relperm(cfg, _shut_in_like_history(),
                                         create_relperm(cfg))
        out = capsys.readouterr().out
        assert "расчёт однофазный" not in out
        assert "рабочий диапазон: S_g = 0.000000 … 0.050000" in out

    def test_plot_relperm_two_panels_when_gas_only_in_past(self, monkeypatch, tmp_path):
        """relperm.png получает вторую панель (рабочий диапазон), а не пометку S_g ≡ 0.

        Число панелей задаёт вызов plt.subplots(1, n_panels): 2 у двухфазного
        расчёта, 1 у однофазного. Перехват вызова — тот же приём, что в
        test_plot_pvt_layout_2x3.
        """
        from gpn_multiphase_solver.factory import create_relperm
        rp_mod = _relperm_module()
        calls = []
        orig = rp_mod.plt.subplots

        def spy(*args, **kwargs):
            calls.append(args)
            return orig(*args, **kwargs)

        monkeypatch.setattr(rp_mod.plt, "subplots", spy)
        cfg = load_config(self.CFG)
        rp_mod.plot_relperm(cfg, _shut_in_like_history(), tmp_path, "16-синт",
                            create_relperm(cfg))
        assert calls[0][:2] == (1, 2), f"панелей: {calls[0][:2]}"


# ═══════════════════════════════════════════════════════════
# J3. Узлы таблиц на графиках — по классу модели (DEBT-006)
# ═══════════════════════════════════════════════════════════

class TestTableNodesByClass:
    """Скрипты графиков находят узлы таблиц по классу модели, а не по приватным полям.

    До DEBT-006 узлы ОФП (сейчас io/output.py::relperm_table_nodes, прежде
    _table_nodes в relperm_plot.py) тестов не имели, а узлы PVT проверяли
    в основном тесты на фикстуре results (метка slow). Здесь —
    быстрые проверки без расчёта.
    """

    def test_relperm_nodes_from_csv(self):
        """Табличная ОФП примера 04: узлы — ровно строки relperm.csv."""
        from gpn_multiphase_solver.factory import create_relperm, _read_relperm_csv
        cfg = load_config(EXAMPLES_DIR / "04_table_table" / "config.json")
        nodes = relperm_table_nodes(create_relperm(cfg))
        expected = _read_relperm_csv(cfg.config_dir / cfg.relperm.file)
        assert nodes is not None, "у табличной ОФП узлы обязаны быть"
        for got, exp in zip(nodes, expected):
            np.testing.assert_array_equal(got, exp)

    def test_relperm_nodes_none_for_corey(self):
        """Кори примера 03: выделенных точек нет — None."""
        from gpn_multiphase_solver.factory import create_relperm
        cfg = load_config(EXAMPLES_DIR / "03_standing_corey" / "config.json")
        assert relperm_table_nodes(create_relperm(cfg)) is None

    def test_pvt_nodes_none_for_standing(self):
        """Стендинг примера 03: узлов PVT нет — None (без фикстуры results, DEBT-006)."""
        cfg = load_config(EXAMPLES_DIR / "03_standing_corey" / "config.json")
        Rs0 = float(cfg.initial_conditions.Rs0)
        assert pvt_table_nodes(_pvt_of_config(cfg), Rs0) is None


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
        за фронтом (p >= pb) в расчёте остаётся газ из переходного процесса.
        В первый час изобара pb уходит до r ≈ 1.8 м, а когда она отступает,
        выделившийся газ не растворяется (таблица даёт Rs_eq = 30 = Rs0 при
        всех p >= 15 МПа) и почти неподвижен (krg ∝ Sg², при Sg ~ 0.01
        krg ~ 1e-7). Замыкание там даёт строго 0, и относительная метрика
        вырождается в 100 %. Измерено при N = 150: max|dSg| = 1.39e-2 — в
        пяти ячейках за фронтом, внутри двухфазной зоны до 1.0e-3, у забоя
        0.699965 против 0.699933 — согласие 0.005 %.

        Допуск 1 % с запасом на возможное измельчение сетки.
        """
        from gpn_multiphase_solver.diagnostics.closed_form import Closure
        from gpn_multiphase_solver.factory import (
            SimulatorFactory, create_relperm)

        cfg = load_config(EXAMPLES_DIR / HIGH_SG / "config.json")
        sim, _ = SimulatorFactory.from_config(cfg)
        # Closure принимает объект ОФП напрямую — работает и с CoreyRP.
        clo = Closure(sim.pvt, create_relperm(cfg),
                      cfg.initial_conditions.Rs0)

        p_well = float(results[HIGH_SG]["p"][0])
        Sg_well = float(results[HIGH_SG]["Sg"][0])
        assert clo.Sg(p_well) == pytest.approx(Sg_well, rel=1e-2)

    @pytest.mark.slow
    def test_dense_grid_converges_at_default_retries(self):
        """Сгущённая сетка N = 80 считается на ШТАТНОМ numerics.max_retries.

        Отложенный критерий BUG-003: до его исправления лимит дробления шага
        был жёстко зашит равным 5 (2^5 = 32 подшага), и этот сценарий при
        N >= 80 падал с RuntimeError. До BUG-016 здесь требовались все
        9 удвоений (512 подшагов, замер 2026-09-25): первый шаг — скачок
        p_wf 20 -> 4 МПа переводит под pb около половины ячеек разом (BUG-008).
        С третьей ступенью advance (BUG-016) шаг сходится без дробления; тест
        держит достаточность умолчания и для этого класса задач.

        Тест проверяет ровно то, что нельзя было проверить до создания 04a:
        значение по умолчанию 9 действительно достаточно для ЭТОГО класса
        задач (табличный PVT, высокая Sg), а не только для сценария с
        корреляциями Стендинга, на котором BUG-003 верифицировался косвенно.

        Источник значения — умолчание NumericsConfig, НЕ конфиг примера
        (BUG-011). Конфиг 04a задаёт 12 под свою штатную сетку N = 150, где
        до BUG-016 девяти хватало лишь впритык (BUG-008); здесь проверяется
        достаточность самого умолчания. Само умолчание = 9 контролируется
        в test_config.py:185.

        Штатную конфигурацию примера (N = 150, лимит 12) покрывает фикстура
        results — она считает каждый пример на его собственном конфиге.

        Отдельный прогон, а не фикстура results: сетка другая. ~50 с, отсюда
        маркер slow (pytest -m "not slow" его пропустит).
        """
        cfg = load_config(EXAMPLES_DIR / HIGH_SG / "config.json")
        cfg.grid.N = 80
        # Лимит дробления берём из УМОЛЧАНИЯ NumericsConfig, а не из конфига
        # 04a: там стоит 12 под штатную сетку примера N = 150, где до BUG-016
        # девяти хватало лишь впритык (BUG-008: требовалась attempt 9 из 9).
        # Здесь сетка другая (N = 80), и проверяется, что штатных девяти
        # удвоений достаточно.
        # Присваивание строго ДО SimulatorFactory.from_config: фабрика читает
        # max_retries один раз при сборке Simulator (SimulatorFactory.from_config).
        cfg.numerics.max_retries = NumericsConfig().max_retries

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


# ═══════════════════════════════════════════════════════════
# L. Сценарий 12: большая область дренирования (FEAT-021)
# ═══════════════════════════════════════════════════════════

class TestLargeDrainageRadius:
    """Сценарий 12: R_ext = 200 м, p0 = 15.5 МПа при p_b = 15 МПа, 15 сут.

    Зазор p0 - p_b = 0.5 МПа выбран так, чтобы контурная ячейка оставалась
    однофазной: давление на контуре задано на грани, а центр последней
    ячейки (185.36 м) лежит на полуячейку глубже, где давление ниже на
    0.05-0.08 МПа. При меньшем зазоре ячейка N-1 становится двухфазной по
    чисто сеточной причине (перепад на полуячейке ~1/N).

    За 15 сут режим нестационарен: лишний свободный газ, скопившийся в
    первые сутки, выносится к скважине, и газовый фактор убывает к R_s^0.
    """

    NAME = "12_large_drainage_radius"

    def test_boundary_cell_stays_single_phase(self, results):
        """Контурная ячейка однофазна на всей истории.

        Условия: штатный конфиг, 16 суточных записей.
        Ожидание: S_g[N-1] = 0 точно и R_s[N-1] = R_s^0 с машинной
        точностью на каждой записи (замер: max|R_s - R_s^0| = 5e-14).
        Ловит: опускание p0 к p_b, при котором двухфазность контурной
        ячейки определяется сеткой, а не физикой (при p0 = 15.05 МПа —
        с 62 ч).
        """
        r = results[self.NAME]
        for n, st in enumerate(r["history"].states):
            assert st.Sg[-1] == 0.0, \
                f"запись {n}: S_g[N-1] = {st.Sg[-1]:.3e}, контурная ячейка двухфазна"
            assert abs(st.Rs[-1] - r["Rs0"]) < 1e-10, \
                f"запись {n}: R_s[N-1] = {st.Rs[-1]} отличается от R_s^0 = {r['Rs0']}"

    def test_gor_relaxes_toward_Rs0_from_above(self, results):
        """Газовый фактор строго убывает и к концу ещё выше R_s^0.

        Условия: штатный конфиг, 15 суточных записей дебитов.
        Ожидание: GOR = q_g/q_o убывает на каждой записи (74.21 -> 36.67)
        и на 15 сут больше R_s^0 = 30. В стационаре GOR = R_s^0: газ
        входит через контур только растворённым. Превышение — вынос
        лишнего свободного газа из двухфазной зоны.
        Ловит: потерю нестационарного режима (GOR сразу около R_s^0) или
        смену характера подхода к стационару.
        """
        r = results[self.NAME]
        # Запись 0 — начальное состояние с нулевыми дебитами, пропускаем
        gor = r["q_g"][1:] / r["q_o"][1:]
        assert np.all(np.diff(gor) < 0.0), f"GOR не убывает монотонно: {gor}"
        assert gor[-1] > r["Rs0"], \
            f"GOR = {gor[-1]:.3f} на конце <= R_s0 = {r['Rs0']}: режим уже стационарен"


# ═══════════════════════════════════════════════════════════
# M. Сценарий 13a: ступенчатое снижение p_wf (FEAT-022)
# ═══════════════════════════════════════════════════════════

class TestPwfRampDown:
    """Сценарий 13a: конфиг 12, p_wf раз в сутки снижается на 0.6 МПа.

    Сутки k = 1..15: p_wf = 15 - 0.6·k МПа (14.4 -> 6.0), отсчёт от p_b.
    Запись каждые 0.5 сут: 30 интервалов, 31 запись; интервалы 2k-1 и 2k
    — сутки k. p_wf только снижается, поэтому p[0] > p_wf на всех
    подшагах и скважина не закрывается (к 13a не относится BUG-014).
    """

    NAME = "13a_pwf_ramp_down"

    def test_pwf_follows_schedule(self, results):
        """Заданное p_wf каждой записи совпадает с расписанием.

        Запись n = 1..30 — конец интервала n, сутки k = (n + 1) // 2.
        Ожидание: p_wf = 15 - 0.6·k МПа точно (целые Па в конфиге).
        Запись 0 — начальное состояние, там p_wf = p[0] (simulator.py:268).
        Ловит: сдвиг расписания на интервал, опечатку в конфиге.
        """
        wd = results[self.NAME]["history"].well_data
        assert len(wd) == 31
        for n in range(1, 31):
            k = (n + 1) // 2
            expected = 15.0e6 - 0.6e6 * k
            assert wd[n].p_wf == pytest.approx(expected, abs=1e-3), \
                f"запись {n}: p_wf = {wd[n].p_wf}, ожидалось {expected}"

    def test_boundary_cell_stays_single_phase(self, results):
        """Контурная ячейка однофазна на всей истории.

        Условия: p0 = 15.5 МПа при p_b = 15 МПа, 31 запись.
        Ожидание: S_g[N-1] = 0 точно, R_s[N-1] = R_s^0 с машинной точностью
        (замер: min_t p_{N-1} - p_b = +426.5 кПа, max|R_s - R_s^0| = 7.8e-14).
        Ловит: опускание p0 к p_b, при котором двухфазность контурной
        ячейки задаётся сеткой, а не физикой.
        """
        r = results[self.NAME]
        for n, st in enumerate(r["history"].states):
            assert st.Sg[-1] == 0.0, \
                f"запись {n}: S_g[N-1] = {st.Sg[-1]:.3e}, контурная ячейка двухфазна"
            assert abs(st.Rs[-1] - r["Rs0"]) < 1e-10, \
                f"запись {n}: R_s[N-1] = {st.Rs[-1]} отличается от R_s^0 = {r['Rs0']}"

    def test_oil_rate_steps_up_daily_and_relaxes_within_day(self, results):
        """Дебит нефти растёт от суток к суткам и спадает внутри суток.

        Физика: каждая ступень увеличивает депрессию на 0.6 МПа, поэтому
        дебит в конце суток k+1 выше, чем в конце суток k (замер:
        4.99e-4 -> 3.157e-3 м³ст/с). Внутри суток после скачка воронка
        депрессии расширяется и дебит убывает: запись середины суток
        (2k-1) выше записи конца суток (2k). Замер: на всех 15 сутках.
        Ловит: потерю ступенчатого режима (p_wf не меняется между
        интервалами) или неверный знак отклика на скачок ГУ.
        """
        q = results[self.NAME]["q_o"]      # запись 0 — нулевой дебит
        day_end = q[2::2]                   # записи 2, 4, ..., 30
        mid_day = q[1::2]                   # записи 1, 3, ..., 29
        assert np.all(np.diff(day_end) > 0.0), f"q_o концов суток не растёт: {day_end}"
        assert np.all(mid_day > day_end), \
            f"q_o внутри суток не спадает: середины {mid_day}, концы {day_end}"

    def test_closed_form_uses_last_interval_pwf(self, results):
        """Замкнутое решение строится при p_wf последнего интервала (6 МПа).

        До FEAT-022 closed_form брал history[0].p_wf — у 13a это 14.4 МПа,
        и пунктир на графиках описывал бы режим первых суток (q_o =
        4.98e-4). Теперь — предел t -> inf при удержании последнего режима.
        Ожидание: q_o = 3.2827e-3 м³ст/с (замер 2026-09-29: 3.282724e-3).
        Ловит: возврат к history[0].
        """
        from gpn_multiphase_solver.diagnostics.closed_form import solve_closed
        from gpn_multiphase_solver.factory import create_relperm

        r = results[self.NAME]
        cfg = r["config"]
        cl = solve_closed(cfg, _pvt_of_config(cfg), create_relperm(cfg),
                          r["grid"].r_centers)
        assert cl["q_o"] == pytest.approx(3.2827e-3, rel=1e-4)

    def test_config_plots_six_moments(self):
        """Конфиг 13a: профили на 6 моментах — 0, 3, ..., 15 сут (output.n_profiles).

        Решение пользователя 2026-09-29: 31 кривая (каждая запись) нечитаема —
        10 цветов цикла повторяются трижды, легенда не помещается.
        """
        assert _output(self.NAME).n_profiles == 6

    def test_config_disables_saturation_overlay(self):
        """Конфиг 13a: стационарное решение не рисуется на профилях S_g (output.closed_form_overlays).

        Решение пользователя 2026-09-29: замыкание GOR = R_s0 на 15 сут
        (GOR = 54.9) даёт S_g почти вдвое ниже численной — на графике это
        выглядит как ошибка. Пунктир стационара на профилях p остаётся.
        """
        out = _output(self.NAME)
        assert out.steady_state is True
        assert out.closed_form_overlays == ["p"]


# ═══════════════════════════════════════════════════════════
# N. Замкнутое решение при управлении по дебиту (FEAT-020)
# ═══════════════════════════════════════════════════════════

def _closed_form():
    """Наложения и сверка — модуль пакета report/closed_form.py (FEAT-030)."""
    from gpn_multiphase_solver.report import closed_form
    return closed_form


def _closed_form_core():
    """Замкнутое решение — модуль пакета (DEBT-011)."""
    from gpn_multiphase_solver.diagnostics import closed_form
    return closed_form


@pytest.fixture(scope="module")
def stationary_base():
    """Конфиг примера 12, его PVT, ОФП и сетка (r центров ячеек)."""
    from gpn_multiphase_solver.factory import create_relperm
    from gpn_multiphase_solver.grid.log_radial import LogRadialGrid
    cfg = load_config(EXAMPLES_DIR / "12_large_drainage_radius" / "config.json")
    g = cfg.geometry
    grid = LogRadialGrid(r_well=g.r_well, R_ext=g.R_ext, h=g.h,
                         N=cfg.grid.N, k=cfg.rock.permeability)
    return cfg, _pvt_of_config(cfg), create_relperm(cfg), grid.r_centers


class TestStationaryPwf:
    """p_wf стационара — предел t -> inf при удержании последнего интервала.

    При управлении по давлению — уставка последнего интервала (FEAT-022),
    при управлении по дебиту — обращение квадратуры (3) closed_form по дебиту
    (FEAT-020). Обращение стоит 1.2–4 с, поэтому PVT, ОФП и сетка — общие
    (фикстура stationary_base уровня модуля), а solve_closed зовётся не чаще
    раза на тест.
    """

    @staticmethod
    def _rate_config(cfg, q_oil_sm3_day):
        """Копия конфига с одним интервалом управления по дебиту, min_bhp = 1 атм."""
        import copy
        from gpn_multiphase_solver.io.config import HistoryInterval
        c = copy.deepcopy(cfg)
        c.time.history = [HistoryInterval(dt=86400.0, control="rate",
                                          q_oil=q_oil_sm3_day / 86400.0,
                                          min_bhp=101325.0)]
        return c

    def test_pressure_control_uses_last_interval(self):
        """Управление по давлению: уставка последнего интервала (13a — 6 МПа)."""
        cfg = load_config(EXAMPLES_DIR / "13a_pwf_ramp_down" / "config.json")
        assert _closed_form_core().stationary_pwf(cfg, None, None) == 6.0e6

    def test_rate_control_inverts_last_rate(self, stationary_base):
        """Дебит 270 м³ст/сут: p_wf* = 6.59493 МПа, q_o решения = заданному.

        Только solve_closed: внутри — одно обращение, отдельный вызов
        stationary_pwf удвоил бы стоимость. Порог по дебиту: brentq с
        xtol = 1 Па даёт |Δq|/q ≲ 1 Па / (p_e − p_wf*) ≈ 1.1e-7, замер
        аудита 1.96e-8. Ловит: неверное обращение, возврат к p_wf из конфига.
        """
        cfg, pvt, rp, r = stationary_base
        cl = _closed_form_core().solve_closed(self._rate_config(cfg, 270.0), pvt, rp, r)
        assert cl["p_wf"] == pytest.approx(6.59493e6, rel=1e-5)
        assert cl["q_o"] == pytest.approx(270.0 / 86400.0, rel=1e-6)

    def test_unreachable_rate_gives_min_bhp(self, stationary_base):
        """Дебит 1000 м³ст/сут выше стационарного максимума (412 при 1 атм):
        стационар при min_bhp — ограничение активно."""
        cfg, pvt, rp, _ = stationary_base
        pw = _closed_form_core().stationary_pwf(self._rate_config(cfg, 1000.0), pvt, rp)
        assert pw == 101325.0

    def test_zero_rate_gives_contour_pressure(self, stationary_base):
        """Нулевой дебит: депрессии нет, p_wf* = p_e."""
        cfg, pvt, rp, _ = stationary_base
        pw = _closed_form_core().stationary_pwf(self._rate_config(cfg, 0.0), pvt, rp)
        assert pw == cfg.initial_conditions.p0


# ═══════════════════════════════════════════════════════════
# O. Сценарий 15: пуск с линейно растущим дебитом нефти (FEAT-020)
# ═══════════════════════════════════════════════════════════

class TestOilRateRampUp:
    """Сценарий 15: конфиг 12, скважина управляется по дебиту нефти.

    Сутки k = 1..15: q_oil = 18·k м³ст/сут (0 → 270 по записям), min_bhp =
    1 атм. Сутки разбиты на 24 часовых интервала с одним дебитом: 360
    интервалов, 361 запись (запись n — момент n ч). p_wf — результат
    расчёта: выражается из уравнения притока (eq:bc_rate_pwf).
    """

    NAME = "15_oil_rate_ramp_up"

    def test_config_is_rate_controlled(self, results):
        """Конфиг: 360 часовых интервалов по дебиту, p_wf не задан.

        Интервал i (с 0) относится к суткам k = i // 24 + 1. Ловит: возврат
        к суточной записи (на графике пропадает пила T), опечатку в дебите,
        потерю полей управления.
        """
        hist = results[self.NAME]["config"].time.history
        assert len(hist) == 360
        for i, h in enumerate(hist):
            k = i // 24 + 1
            assert h.control == "rate"
            assert h.dt == 3600.0
            assert h.min_bhp == 101325.0
            assert h.p_wf is None
            assert h.q_oil == pytest.approx(18.0 * k / 86400.0, rel=1e-15)

    def test_rate_follows_schedule(self, results):
        """Дебит записей совпадает с расписанием (замер: точно).

        Запись 0 — начальное состояние с нулевым дебитом; запись n ≥ 1 —
        конец n-го часа, сутки k = ceil(n / 24). Ловит: сдвиг расписания на
        интервал, ошибку единиц м³ст/с ↔ м³ст/сут.
        """
        q = results[self.NAME]["q_o"]
        assert len(q) == 361
        assert q[0] == 0.0
        for n in range(1, 361):
            k = (n - 1) // 24 + 1
            assert q[n] == pytest.approx(18.0 * k / 86400.0, rel=1e-12), \
                f"запись {n}: q_o = {q[n] * 86400:.6f} м³ст/сут, ожидалось {18 * k}"

    def test_temperature_sawtooth(self, results):
        """T(r_w) идёт пилой: провал в первые часы после ступени дебита.

        Физика: на ступени давление у забоя за первый час падает на 350–540
        кПа (2/3 суточного падения) — адиабатическое охлаждение, со 2-х
        суток ещё и разгазирование; за остаток суток дросселирование нефти
        (mu_JT,o < 0) прогревает забой на 24–30 мК (на 2-е сутки — 12 мК).
        Замер: на сутках 2..15 минимум внутри суток ниже значения на конце
        предыдущих на 21–51 мК; минимум расчёта 349.9489 К на записи 338
        (14 сут + 2 ч). Ловит: возврат к суточной записи (минимума не
        видно), потерю адиабатического члена.
        """
        T = np.array([st.T[0] for st in results[self.NAME]["history"].states])
        for k in range(2, 16):
            day = T[24 * (k - 1) + 1: 24 * k + 1]   # записи внутри суток k
            dip = T[24 * (k - 1)] - day.min()
            assert dip > 0.02, f"сутки {k}: провал {dip * 1e3:.1f} мК"
        assert int(np.argmin(T)) == 338
        assert T.min() == pytest.approx(349.9489, abs=2e-4)

    def test_pwf_decreases_and_stays_above_min_bhp(self, results):
        """p_wf строго убывает по записям и не доходит до min_bhp.

        Физика: дебит растёт, а пласт истощается — депрессия нарастает.
        Строго и по часовым записям внутри суток (наименьший шаг −90 Па).
        Ожидание (замер плана FEAT-020): 15.5 МПа (запись 0 — p[0]) →
        6.12991 МПа на 15 сут; ограничение 1 атм не срабатывает.
        Ловит: срабатывание ограничения, запись уставки вместо p_wf шага.
        """
        pwf = np.array([w.p_wf for w in results[self.NAME]["history"].well_data])
        assert np.all(np.diff(pwf) < 0.0), f"p_wf не убывает: {pwf}"
        assert np.all(pwf > 101325.0)
        assert pwf[-1] == pytest.approx(6.12991e6, rel=1e-4)

    def test_boundary_cell_stays_single_phase(self, results):
        """Контурная ячейка однофазна на всей истории.

        Замер плана FEAT-020: min_t p_{N-1} − p_b = +428.9 кПа.
        """
        r = results[self.NAME]
        for n, st in enumerate(r["history"].states):
            assert st.Sg[-1] == 0.0, \
                f"запись {n}: S_g[N-1] = {st.Sg[-1]:.3e}, контурная ячейка двухфазна"
            assert abs(st.Rs[-1] - r["Rs0"]) < 1e-10

    def test_closed_form_hooks_run_for_rate_control(self, results):
        """Постобработка примера при управлении по дебиту не падает.

        Прежде closed_form брал p_wf последнего интервала из конфига — при
        управлении по дебиту там None. Теперь стационар строится обращением
        по дебиту 270 м³ст/сут: p_wf* = 6.5949 МПа (замер плана FEAT-020).
        Наложение давления и report_closed зовут solve_closed с одним
        ключом кэша — обращение считается один раз (≤ 4 с).
        """
        import contextlib
        import io
        import types
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        cf = _closed_form()

        r = results[self.NAME]
        cfg, history, grid = r["config"], r["history"], r["grid"]
        # closed_form берёт PVT и ОФП как simulator.pvt, simulator.relperm (_prepare)
        from gpn_multiphase_solver.factory import create_relperm
        sim = types.SimpleNamespace(pvt=_pvt_of_config(cfg),
                                    relperm=create_relperm(cfg))

        fig, ax = plt.subplots()
        try:
            cf.make_overlay_pressure(cfg)(ax, history, grid, sim)
        finally:
            plt.close(fig)

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cf.report_closed(cfg, history, grid, sim)
        out = buf.getvalue()
        assert "дебит задан" in out
        assert "6.5949" in out

    def test_config_plots_six_moments(self):
        """Конфиг 15: профили на 6 моментах — 0, 3, ..., 15 сут, как 13a (output.n_profiles)."""
        assert _output(self.NAME).n_profiles == 6

    def test_config_disables_closed_form_overlays(self):
        """Конфиг 15: стационар не рисуется на профилях давления и S_g (output.closed_form_overlays = []).

        На 15 сут у забоя избыток свободного газа (GOR 58.1 против Rs0 = 30,
        S_g^max 0.038 против 0.018 у замыкания GOR = Rs0), давление ниже
        стационарного на 464 кПа — на графике это выглядит как ошибка.
        Сверка остаётся в консоли (report_closed): steady_state = true.
        """
        out = _output(self.NAME)
        assert out.steady_state is True
        assert out.closed_form_overlays == []


# ═══════════════════════════════════════════════════════════
# P. Сценарий 14: высокий газовый фактор, охлаждение забоя (FEAT-024)
# ═══════════════════════════════════════════════════════════

class TestHighGorCooling:
    """Сценарий 14: R_s0 = 150 (p_b = 23.72 МПа), S_gc = 0.1, 12 × 30 сут.

    Конфиг 12, в котором p0 = 24.5 МПа, R_s0 = 150, таблица PVT нефти по
    корреляциям (19 веток), ОФП Кори n_g = 3 с порогом S_gc = 0.1 (таблица
    с шагом 0.01), N = 350, шаг интегрирования 1 сут. Забой охлаждается на
    9.64-10.43 К: теплота выделения газа и расширение газа сильнее нагрева
    нефти при дросселировании (mu_JT,o < 0).
    """

    NAME = "14_high_gor_cooling"

    def test_wellbore_cools_by_5_to_11_K(self, results):
        """На каждой записи 1..12 забой холоднее T0 на 5-11 К.

        Смысл примера (запрос руководителя: охлаждение на 5-10 К). Граница
        расширена до 11 К (решение пользователя 2026-10-01): при c_p,g = 2850
        и L = 230 кДж/кг ΔT с 90 сут за -10 К. Замер 2026-10-01: -9.635 К на
        30 сут, -10.434 К на 360 сут, T(r_w) = 339.566 К. Ловит: смену знака
        mu_JT, потерю скрытой теплоты, регрессию схемы энергии на суточном шаге.
        """
        r = results[self.NAME]
        T0 = r["config"].initial_conditions.T0
        dT = np.array([st.T[0] - T0 for st in r["history"].states[1:]])
        assert np.all(dT < -5.0) and np.all(dT > -11.0), f"ΔT(r_w) = {dT}"
        assert r["T_well"] == pytest.approx(339.566, abs=2e-3)

    def test_gor_below_Rs0_and_rising(self, results):
        """GOR ниже R_s0 и строго растёт: свободный газ копится в пласте.

        Замер: 138.80 (30 сут) -> 149.24 (360 сут) при R_s0 = 150. При малой
        S_g газ малоподвижен (k_rg кубическая и нулевая до S_gc = 0.1), он
        копится, пока S_g не выйдет на стационарный профиль, и газа
        добывается меньше, чем входит через контур растворённым.
        Ловит: смену характера подхода к стационару (GOR сверху, как при
        газе, подвижном с малых S_g) и скачки GOR от излома k_rg (линейная
        k_rg над порогом: 139-148 немонотонно). Потерю самого порога этот
        тест НЕ ловит (при S_gc = 0 GOR тоже растёт снизу: 144.18 -> 149.67),
        её ловит test_well_saturation_matches_relperm. Числа для линейной
        k_rg и S_gc = 0 — замер на исходной конфигурации FEAT-024 (N = 50,
        таблица PVT из трёх веток).
        """
        r = results[self.NAME]
        # Запись 0 — начальное состояние с нулевыми дебитами, пропускаем
        gor = r["q_g"][1:] / r["q_o"][1:]
        assert np.all(np.diff(gor) > 0.0), f"GOR не растёт монотонно: {gor}"
        assert np.all(gor < r["Rs0"]), f"GOR >= R_s0: {gor}"

    def test_well_saturation_matches_relperm(self, results):
        """S_g у забоя на 360 сут = 0.2595 — её задаёт форма k_rg над порогом.

        Тождество Дарси на забойной грани: k_rg/k_ro(S_g) = (GOR - R_s)·
        mu_g·B_g/(mu_o·B_o) ≈ 0.0185; корень определяется k_rg сразу над
        S_gc. Замер 2026-10-01: 0.2595 (Кори n_g = 3, S_gc = 0.1, таблица с
        шагом 0.01) — совпадает с корнем тождества. Корни при той же правой
        части: при S_gc = 0 — 0.194, при линейной k_rg над порогом — 0.113.
        Ловит: потерю порога S_gc или смену формы k_rg в relperm.csv.
        """
        # results[...]["Sg"] — поле последней записи (360 сут), [0] — ячейка у забоя
        Sg_w = float(results[self.NAME]["Sg"][0])
        assert Sg_w == pytest.approx(0.2595, abs=1e-3), f"S_g(r_w) = {Sg_w:.4f}"

    def test_boundary_cell_stays_single_phase(self, results):
        """Контурная ячейка однофазна на всей истории.

        Замер 2026-10-01: min_t p_{N-1} - p_b = +764.2 кПа.
        """
        r = results[self.NAME]
        for n, st in enumerate(r["history"].states):
            assert st.Sg[-1] == 0.0, \
                f"запись {n}: S_g[N-1] = {st.Sg[-1]:.3e}, контурная ячейка двухфазна"
            assert abs(st.Rs[-1] - r["Rs0"]) < 1e-10

    def test_gas_active_cells_match_pressure(self, results):
        """Ниже p_b газ есть всегда; выше p_b — только заметный, не шум.

        Три проверки на каждой записи:
        1) газ есть ровно в двухфазных ячейках (S_g > 0 <=> regime = 1);
        2) p < p_b(R_s0) => ячейка двухфазна: ниже давления насыщения газ
           обязан выделиться;
        3) двухфазная ячейка при p >= p_b допустима только с S_g > 1e-8.
        Обратная к 2) импликация (двухфазна => p < p_b) неверна: дебит
        падает, давление на краю двухфазной зоны растёт, а выделившийся газ
        поднимает собственное давление насыщения ячейки выше p_b(R_s0).
        Замер 2026-10-01: ячейка на 105.4 м на 90 сут — p - p_b = +2.7 кПа,
        S_g = 2.8e-3; к 150 сут газ растворяется (321 двухфазная ячейка
        при 320 ячейках с p < p_b на 90 и 120 сут).
        Без веток PVT выше R_s0 R_s_sat при p > p_b берётся на краю таблицы
        (= R_s0), и ячейки, помеченные двухфазными на первом суточном шаге,
        остаются такими с S_g ~ 1e-16 — шум округления. Замер 2026-10-01
        (таблица без веток 160-180, 30 сут): 13 ячеек на 21-339 кПа выше
        p_b, S_g = 6e-17...5e-16; проверка 3) падает, 1) и 2) проходят.
        Ловит: удаление веток выше R_s0 из oil_pvt.csv, отсутствие газа
        ниже p_b, рассогласование regime и S_g.
        """
        # Порог шума округления: артефакт без веток выше R_s0 даёт S_g ~ 1e-16,
        # настоящий газ у фронта при повышении давления — S_g ~ 1e-3.
        SG_NOISE = 1e-8
        r = results[self.NAME]
        pvt = _pvt_of_config(r["config"])
        pb = float(pvt.pb(np.array([r["Rs0"]]))[0])
        for n, st in enumerate(r["history"].states):
            below = st.p < pb
            two_phase = st.regime == 1
            # 1) Газ — только в двухфазных ячейках, и в каждой из них
            assert np.array_equal(st.Sg > 0.0, two_phase), \
                f"запись {n}: S_g > 0 не совпадает с regime = 1"
            # 2) Ниже p_b однофазных ячеек нет
            assert np.all(two_phase[below]), \
                f"запись {n}: однофазная ячейка при p < p_b"
            # 3) Выше p_b двухфазность допустима только с заметным газом
            above = two_phase & ~below
            assert np.all(st.Sg[above] > SG_NOISE), \
                (f"запись {n}: двухфазная ячейка выше p_b с "
                 f"S_g = {st.Sg[above].min():.3e} — шум округления")

    def test_config_disables_steady_state(self):
        """Конфиг 14 отключает стационарную аналитику целиком (output.steady_state = false).

        Решение пользователя 2026-10-01: снимает пунктир стационара с
        профилей p и S_g, сверку report_closed и асимптотику температуры.
        За 360 сут стационар не достигнут (GOR < R_s0, газ у фронта ещё
        копится), сравнение с пределом t -> inf точность расчёта не
        характеризует. Ловит: возврат стационарных наложений.
        """
        assert _output(self.NAME).steady_state is False


# ═══════════════════════════════════════════════════════════
# Q. Сценарий 13b: чередование p_wf 6 <-> 10.75 МПа (FEAT-023)
# ═══════════════════════════════════════════════════════════

class TestPwfAlternating:
    """Сценарий 13b: конфиг 12, p_wf по суткам 6 / 10.75 МПа, 30 сут.

    Сутки d = 1..30: нечётные 6 МПа, чётные 10.75 МПа = (6 + 15.5)/2.
    Запись каждые 0.5 сут: 60 интервалов, 61 запись; запись n >= 1 —
    конец интервала n, сутки d = (n + 1) // 2; середина суток d —
    запись 2d - 1, конец — 2d. Скачок вверх поднимает p_wf выше давления
    у забоя (6.13 МПа): прототип закрывает скважину (обратный клапан,
    eq:bc_pwf_shutin), но закрытие длится 2-3 мин и при шаге 3600 с на
    принятых шагах не видно (замер FEAT-023).
    """

    NAME = "13b_pwf_alternating"

    @staticmethod
    def _pwf_of_day(d):
        """Заданное p_wf суток d, Па: нечётные 6 МПа, чётные 10.75 МПа."""
        return 6.0e6 if d % 2 == 1 else 10.75e6

    def test_pwf_follows_schedule(self, results):
        """Фактическое p_wf каждой записи совпадает с расписанием.

        WellData.p_wf — фактическое давление шага (FEAT-020): у закрытой
        скважины оно равно p[0] и ниже заданного. Совпадение на всех 60
        записях значит заодно, что на моментах записи скважина открыта.
        Замер: отклонение 0 Па.
        Ловит: сдвиг расписания на интервал, опечатку в конфиге, закрытую
        скважину на конце интервала.
        """
        wd = results[self.NAME]["history"].well_data
        assert len(wd) == 61
        for n in range(1, 61):
            expected = self._pwf_of_day((n + 1) // 2)
            assert wd[n].p_wf == pytest.approx(expected, abs=1e-3), \
                f"запись {n}: p_wf = {wd[n].p_wf}, ожидалось {expected}"

    def test_high_pwf_days_produce_less(self, results):
        """Конец суток при 10.75 МПа: q_o и S_g(r_w) ниже, чем в конце предыдущих при 6 МПа.

        Физика: депрессия 4.75 МПа против 9.5 — приток меньше, давление у
        забоя выше, газа выделяется меньше и часть его растворяется
        обратно. Пары k = 1..15: конец суток 2k-1 — запись 4k-2, конец
        суток 2k — запись 4k. Замер: q_o 1.73-1.86e-3 против 3.18-3.35e-3
        м³ст/с, S_g(r_w) 0.0029-0.0174 против 0.0247-0.0483.
        Ловит: потерю чередования режимов (p_wf не меняется).
        """
        r = results[self.NAME]
        q = r["q_o"]
        sg_w = np.array([st.Sg[0] for st in r["history"].states])
        for k in range(1, 16):
            lo, hi = 4 * k - 2, 4 * k
            assert q[hi] < q[lo], f"пара {k}: q_o {q[hi]:.4e} >= {q[lo]:.4e}"
            assert sg_w[hi] < sg_w[lo], \
                f"пара {k}: S_g(r_w) {sg_w[hi]:.4f} >= {sg_w[lo]:.4f}"

    def test_rate_approaches_regime_from_opposite_sides(self, results):
        """Внутри суток дебит спадает после скачка вниз и растёт после скачка вверх.

        После скачка 10.75 -> 6 МПа перепад у забоя максимален, воронка
        расширяется, дебит убывает к режиму 6 МПа сверху. После скачка
        6 -> 10.75 МПа профиль, сложившийся при 6 МПа, заполняется
        притоком от контура, перепад p[0] - p_wf растёт, дебит растёт к
        режиму 10.75 МПа снизу. Замер: на всех 30 сутках (сутки 1:
        3.383 -> 3.235e-3; сутки 2: 1.698 -> 1.746e-3 м³ст/с).
        Ловит: неверный знак отклика на скачок ГУ.
        """
        q = results[self.NAME]["q_o"]
        for d in range(1, 31):
            mid, end = q[2 * d - 1], q[2 * d]
            if d % 2 == 1:
                assert mid > end, f"сутки {d} (6 МПа): q_o не спадает: {mid:.4e} -> {end:.4e}"
            else:
                assert mid < end, f"сутки {d} (10.75 МПа): q_o не растёт: {mid:.4e} -> {end:.4e}"

    def test_repressurization_leaves_undersaturated_oil(self, results):
        """Обратное растворение газа ограничено его запасом.

        Финал (30 сут, 10.75 МПа): есть однофазные ячейки ниже p_b — нефть
        недонасыщена, R_s < R_s^eq(p) (замер: 30 ячеек на 0.9-74 м, зазор
        0.18-2.44 м³ст/м³ст). В двухфазных ячейках R_s = R_s^eq(p) —
        равновесие Black Oil (замер 1e-13). Концы суток при 6 МПа (записи
        2, 6, ..., 58): однофазных ячеек ниже p_b нет — давление ниже
        прежнего, газ снова выделился всюду.
        Отбор по regime, а не по S_g == 0: прототип обнуляет крошечную
        отрицательную S_g, оставляя ячейку двухфазной (blackoil.py:275).
        Ловит: мгновенное пересыщение нефти газом «из ниоткуда» или
        залипание ячеек в двухфазном режиме при росте давления.
        """
        r = results[self.NAME]
        pvt = _pvt_of_config(r["config"])
        pb = float(pvt.pb(np.array([r["Rs0"]]))[0])
        states = r["history"].states

        final = states[-1]
        rs_eq = pvt.Rs_eq(final.p)
        under = (final.regime == 2) & (final.p < pb)
        assert np.count_nonzero(under) > 0, "на финале нет недонасыщенной нефти ниже p_b"
        assert np.all(final.Rs[under] < rs_eq[under] - 1e-6), \
            "однофазная ячейка ниже p_b с R_s >= R_s^eq(p)"
        two = final.regime == 1
        np.testing.assert_allclose(final.Rs[two], rs_eq[two], rtol=0.0, atol=1e-10)

        for n in range(2, 61, 4):
            st = states[n]
            bad = (st.regime == 2) & (st.p < pb)
            assert not np.any(bad), (
                f"запись {n} (конец суток при 6 МПа): "
                f"{np.count_nonzero(bad)} однофазных ячеек ниже p_b")

    def test_config_plots_seven_moments(self):
        """Конфиг 13b: профили на 7 моментах — 0, 5, ..., 30 сут (output.n_profiles).

        Решение пользователя 2026-09-30: 5, 15, 25 сут — концы суток при
        6 МПа, 10, 20, 30 сут — при 10.75 МПа.
        """
        assert _output(self.NAME).n_profiles == 7

    def test_config_disables_steady_state(self):
        """Конфиг 13b отключает стационарную аналитику (решение 2026-09-29; output.steady_state)."""
        assert _output(self.NAME).steady_state is False


# ═══════════════════════════════════════════════════════════
# Q2. Сценарий 16: останов скважины после добычи (FEAT-019)
# ═══════════════════════════════════════════════════════════

class TestWellShutIn:
    """Сценарий 16: конфиг 12, 15 сут добычи при 6 МПа, затем 15 сут останова.

    Останов — управление по дебиту q_oil = 0 (eq:bc_rate_well): потоки
    компонентов через забой нулевые, p_wf = p[0] (eq:bc_rate_pwf при q = 0).
    Записи: 0 — начальное состояние; 1..15 — концы суток добычи; 16..39 —
    часы первых суток останова (запись 15 + k — момент 15 сут + k ч);
    40..53 — концы суток 17..30. Числа — замер плана FEAT-019
    (vault/issues/feat-019/probes/plan_numbers.out.txt). Первый час останова —
    от подшага 1.76 с с удвоением (time.dt_after_control_change = 2 с, FEAT-032);
    числа останова — замер плана FEAT-032
    (vault/issues/feat-032/probes/readme_numbers_h2.out.txt).
    """

    NAME = "16_well_shut_in"
    END_PROD = 15        # запись конца добычи (15 сут)

    def test_config_follows_decisions(self):
        """Расписание: 15 суточных интервалов при 6 МПа, 24 часовых и 14 суточных с q_oil = 0.

        Решения пользователя 2026-10-03: останов — по дебиту, min_bhp = 1 атм
        (обязателен по конфигу, при q = 0 не действует). Нарастание шага после
        останова — time.dt_after_control_change = 2 с (FEAT-032). Ловит: возврат к
        управлению по давлению, потерю часовой записи первых суток останова
        (на графиках пропадёт восстановление давления).
        """
        cfg = load_config(EXAMPLES_DIR / self.NAME / "config.json")
        hist = cfg.time.history
        assert len(hist) == 15 + 24 + 14
        assert cfg.time.dt_integration == 3600.0
        # FEAT-032 (решение пользователя 2026-10-11): первый час останова — от
        # подшага 3600/2**11 = 1.76 с с удвоением, а не одним шагом
        assert cfg.time.dt_after_control_change == 2.0
        for h in hist[:15]:
            assert (h.control, h.dt, h.p_wf) == ("pressure", 86400.0, 6.0e6)
        for k, h in enumerate(hist[15:]):
            assert h.control == "rate" and h.q_oil == 0.0
            assert h.min_bhp == 101325.0 and h.p_wf is None
            assert h.dt == (3600.0 if k < 24 else 86400.0)

    def test_production_phase_degasses(self, results):
        """На конце добычи скважина добывает нефть и газ, газ выделился в пласте.

        Утверждения общих тестов test_oil_production, test_gas_appears,
        test_gas_produced — на записи 15 вместо последней (16 исключён из
        них списком ENDS_SHUT_IN). Замер: q_o = 3.2365e-3, q_g = 0.11871
        м³ст/с, S_g(r_w) = 0.02394, R_s мин 3.373 < R_s0 = 30.
        """
        r = results[self.NAME]
        st = r["history"].states[self.END_PROD]
        assert r["q_o"][self.END_PROD] == pytest.approx(3.2365e-3, rel=1e-4)
        assert r["q_g"][self.END_PROD] > 0.0
        assert st.Sg.max() > 0.0
        assert st.Rs.min() < r["Rs0"]

    def test_shut_in_stops_flow_through_well(self, results):
        """На всех записях останова q_o = q_g = 0 точно, фактическое p_wf = p[0].

        Знак: q_o_std = -G_o[0]; при q_oil = 0 прототип ставит потоки забоя
        ровно 0 (blackoil.py, _well_fluxes, ветка OIL_RATE: bhp = p0).
        Замер: max|p_wf - p[0]| = 0 Па. Ловит: утечку через забой (закачку
        или отбор) при останове, запись уставки вместо фактического p_wf.
        """
        r = results[self.NAME]
        h = r["history"]
        for n in range(self.END_PROD + 1, len(h.states)):
            assert r["q_o"][n] == 0.0 and r["q_g"][n] == 0.0, f"запись {n}"
            assert h.well_data[n].p_wf == h.states[n].p[0], f"запись {n}"

    def test_pressure_builds_up_past_pb(self, results):
        """p(r_w) не убывает после останова, выше p_b — с 12 ч, на финале p = p_ext.

        Замер: 6.1242 МПа (15 сут) → 13.024 (1 ч) → 15.0324 (запись 27,
        15.5 сут — первая выше p_b = 15 МПа) → 15.4206 (16 сут); финал
        max|p - p_ext| = 0.014 Па. Ловит: потерю притока через контур,
        «залипание» давления у забоя.
        """
        r = results[self.NAME]
        states = r["history"].states
        pw = np.array([s.p[0] for s in states])
        assert np.all(np.diff(pw[self.END_PROD:]) >= 0.0)
        pb = float(_pvt_of_config(r["config"]).pb(np.array([r["Rs0"]]))[0])
        above = [n for n in range(self.END_PROD, len(pw)) if pw[n] > pb]
        assert above[0] == 27, f"выше p_b с записи {above[0]}"
        p_ext = r["config"].initial_conditions.p0
        assert np.max(np.abs(states[-1].p - p_ext)) < 1.0

    def test_gas_redissolves_and_rs_freezes(self, results):
        """Свободный газ растворяется за 7 ч, R_s застывает неоднородным и ниже равновесного.

        Физика: давление поднимается, газ растворяется в пределах своего
        запаса; когда газ кончается, нефть остаётся недонасыщенной. Течения
        после выравнивания давления нет, диффузии в модели нет — профиль R_s
        больше не меняется и к R_s0 не возвращается.
        Замер: двухфазных ячеек нет с записи 22 (15 сут + 7 ч, p(r_w) =
        14.48 МПа < p_b); финал R_s(r_w) = 4.792, max(R_s - R_s^eq(p)) =
        6.0e-14; max|R_s(20 сут) - R_s(30 сут)| = 1.0e-6.
        Ловит: пересыщение нефти «из ниоткуда», возврат R_s к R_s0 (утечку
        газа через контур или забой), залипание ячеек в двухфазном режиме.
        """
        r = results[self.NAME]
        states = r["history"].states
        for n in range(22, len(states)):
            assert np.all(states[n].regime == 2), f"запись {n}: есть двухфазные"
            assert np.all(states[n].Sg == 0.0), f"запись {n}: есть газ"
        assert np.count_nonzero(states[21].regime == 1) > 0   # на 6 ч газ ещё есть
        final = states[-1]
        rs_eq = _pvt_of_config(r["config"]).Rs_eq(final.p)
        assert np.max(final.Rs - rs_eq) <= 1e-10
        assert final.Rs[0] == pytest.approx(4.792, abs=1e-3)
        assert np.max(np.abs(states[43].Rs - final.Rs)) < 1e-3   # 20 сут против 30

    def test_wellbore_heats_then_relaxes(self, results):
        """T(r_w) скачком растёт при останове (сжатие), пик на 1 ч, дальше монотонно убывает.

        Физика: давление у забоя за первый час растёт на 6.9 МПа — адиабатическое
        сжатие (за первые сутки останова +4.86e10 Дж из ΔE = +5.17e10 Дж),
        растворение газа добавляет +2.9e9 Дж. Конвекции через забой нет,
        дальше тепло уходит теплопроводностью. Замер (план FEAT-032, первый час —
        от подшага 1.76 с с удвоением): 350.3507 (15 сут) → 350.6723 (запись 16,
        максимум) → 350.3169 К (30 сут). Одним шагом 3600 с пик был на 2 ч
        (350.6596 К): первый шаг занижал нагрев первого часа.
        Ловит: потерю адиабатического члена (нагрева не будет), остаток
        конвекции через забой при останове (релаксация пойдёт иначе), выключенное
        нарастание (пик сдвинется на запись 17).
        """
        T = np.array([s.T[0] for s in results[self.NAME]["history"].states])
        k = self.END_PROD + int(np.argmax(T[self.END_PROD:]))
        assert k == 16
        assert T[k] == pytest.approx(350.6723, abs=2e-4)
        assert T[k] - T[self.END_PROD] > 0.25
        assert np.all(np.diff(T[k:]) < 0.0)
        assert T[-1] == pytest.approx(350.3169, abs=2e-4)

    def test_plots_cover_production_phase(self, results):
        """pvt.png и relperm.png 16 показывают диапазон добычи, а не только останов.

        На последней записи p = 15.5 МПа всюду и S_g ≡ 0. По всей истории:
        p 6.1224…15.5 МПа (p_b = 15 МПа внутри, один узел таблицы), S_g до
        0.048261 (запись 1). Ловит возврат к диапазону по последней записи.
        """
        r = results[self.NAME]
        rep = _pvt_module().report_pvt(r["config"], r["history"])
        assert rep["p_lo"] == pytest.approx(6.1224e6, rel=1e-4)
        assert rep["p_lo"] < rep["pb"] < rep["p_hi"]
        assert rep["nodes_in_range"] == 1
        _lo, hi = _relperm_module()._sg_range(r["history"])
        assert hi == pytest.approx(0.048261, rel=1e-4)
        assert r["Sg"].max() == 0.0        # на последней записи газа нет

    def test_config_settings(self):
        """Конфиг 16: 7 моментов профилей, без стационарной аналитики, наложения штатные.

        Решения пользователя 2026-10-03 (5, 6): профили равномерно; наложение
        R_s не отключается — после DEBT-026 на финале без газа кружков нет.
        """
        out = _output(self.NAME)
        assert out.n_profiles == 7
        assert out.steady_state is False
        assert out.closed_form_overlays == ["p", "Sg"]


# ═══════════════════════════════════════════════════════════
# R. Сценарии 19–21: охлаждение забоя на корреляциях (FEAT-025)
# ═══════════════════════════════════════════════════════════

# Замер: 19, 21 — 2026-10-01 (vault/issues/feat-025/probes/plan_numbers.py),
# 20 — 2026-10-03 (vault/issues/debt-034/probes/plan_numbers.py); N = 350.
# dT_lo/dT_hi — границы ΔT(r_w) на всех записях после начальной с запасом
# ~0.5-1 К к замеру; T_well, Sg_w — на 30 сут. Остальное — решения
# пользователя: L (19, 21 — по Клапейрону; 20 — 170 кДж/кг, выбор
# пользователя), k = 10 мД, co — сжимаемость недонасыщенной нефти, 1/Па
# (20 — Васкес–Беггс: p0 на 2.71 МПа выше p_b, без неё при нулевой
# rock.compressibility однофазная зона несжимаема), steps — история после
# развёртки кратких форм: пары (число интервалов, длина интервала, с),
# dp0 — окно p0 - p_b, Па.
STANDING_COREY_COOLING = {
    # замер ΔT: -3.466 ... -3.631 К
    "19_rs150_cooling": dict(dT_lo=-4.2, dT_hi=-3.0, T_well=396.369,
                             Sg_w=0.4432, L=202000.0, k=1e-14, co=0.0,
                             steps=((30, 86400.0),), dp0=(0.4e6, 0.6e6)),
    # замер ΔT: -12.201 (1 ч) ... -15.518 К (30 сут); p0 - p_b = 2.708 МПа;
    # 48 интервалов по 1 ч, затем 28 по 1 сут (краткая форма FEAT-018)
    "20_rs300_cooling": dict(dT_lo=-16.5, dT_hi=-11.5, T_well=364.482,
                             Sg_w=0.4521, L=170000.0, k=1e-14, co=3.3e-9,
                             steps=((48, 3600.0), (28, 86400.0)),
                             dp0=(2.6e6, 2.8e6)),
    # замер ΔT: -2.368 ... -2.479 К
    "21_rs100_cooling": dict(dT_lo=-3.0, dT_hi=-2.0, T_well=397.521,
                             Sg_w=0.4083, L=227000.0, k=1e-14, co=0.0,
                             steps=((30, 86400.0),), dp0=(0.4e6, 0.6e6)),
}


class TestStandingCoreyCooling:
    """Сценарии 19–21: PVT Стендинга, ОФП Кори, R_s0 = 150 / 300 / 100, 30 сут.

    Нефть добывается при p_wf глубоко ниже p_b (3 / 5 / 3 МПа при
    p_b = 24.18 / 30.29 / 17.22 МПа). Забой охлаждается: теплота выделения
    газа сильнее нагрева нефти при дросселировании (mu_JT,o < 0); в 20 без
    неё забой греется (+0.49 К на 30 сут). В 19 и 21 тепловые константы
    согласованы с флюидом (mu_JT,g и c_p,g — уравнение состояния,
    L — Клапейрон); в 20 L = 170 кДж/кг задана пользователем, mu_JT,g и
    c_p,g взяты от R_s0 = 500 и не пересчитаны. Газ неподвижен
    до S_g = S_gc = 0.1 и копится в пласте: GOR ниже R_s0 и растёт.
    """

    @pytest.mark.parametrize("name", list(STANDING_COREY_COOLING))
    def test_wellbore_cools(self, results, name):
        """На каждой записи после начальной забой холоднее T0 в пределах полосы замера.

        Записи: 19, 21 — 30 суточных; 20 — 76 (48 часовых, 28 суточных).
        Смысл примеров — охлаждение забоя. Оценка по изоэнтальпийному
        балансу (модель М.3, GOR = R_s0): -4.11 / -15.88 / -2.73 К; расчёт
        на 30 сут — 88 / 98 / 91 % оценки (газ ещё копится в пласте).
        Ловит: смену знака mu_JT, потерю скрытой теплоты, регрессию схемы
        энергии на суточном шаге, смену тепловых констант конфига.
        """
        e = STANDING_COREY_COOLING[name]
        r = results[name]
        T0 = r["config"].initial_conditions.T0
        dT = np.array([st.T[0] - T0 for st in r["history"].states[1:]])
        assert np.all(dT < e["dT_hi"]) and np.all(dT > e["dT_lo"]), \
            f"{name}: ΔT(r_w) = {dT}"
        assert r["T_well"] == pytest.approx(e["T_well"], abs=2e-3)

    @pytest.mark.parametrize("name", list(STANDING_COREY_COOLING))
    def test_gor_below_Rs0_and_rising(self, results, name):
        """GOR ниже R_s0 и строго растёт: свободный газ копится в пласте.

        Замер: 121.41 -> 128.70 (19), 246.31 (1 ч) -> 278.63 (20),
        81.96 -> 85.78 (21); наименьший прирост между записями 0.132 /
        0.035 (часовые записи) / 0.060. q_o и q_g в тест не заложены:
        q_g немонотонен в 19 и 20.
        Ловит: потерю порога подвижности (газ уходит в скважину сразу),
        скачки GOR от излома k_rg.
        """
        r = results[name]
        # Запись 0 — начальное состояние с нулевыми дебитами, пропускаем
        gor = r["q_g"][1:] / r["q_o"][1:]
        assert np.all(np.diff(gor) > 0.0), f"{name}: GOR не растёт монотонно: {gor}"
        assert np.all(gor < r["Rs0"]), f"{name}: GOR >= R_s0: {gor}"

    @pytest.mark.parametrize("name", list(STANDING_COREY_COOLING))
    def test_well_saturation_matches_relperm(self, results, name):
        """S_g у забоя на 30 сут — её задаёт форма Кори над порогом S_gc.

        Тождество Дарси на забойной грани: k_rg/k_ro(S_g) = (GOR - R_s)·
        mu_g·B_g/(mu_o·B_o); корень определяется k_rg = 0.8·S*^3,
        S* = (S_g - 0.1)/(1 - 0.05 - 0.1). Замер: 0.4432 / 0.4521 / 0.4083
        (19, 21 — 2026-10-01; 20 — 2026-10-03).
        Ловит: смену S_gc, S_or или показателей Кори в конфиге.
        """
        Sg_w = float(results[name]["Sg"][0])
        assert Sg_w == pytest.approx(STANDING_COREY_COOLING[name]["Sg_w"], abs=1e-3), \
            f"{name}: S_g(r_w) = {Sg_w:.4f}"

    @pytest.mark.parametrize("name", list(STANDING_COREY_COOLING))
    def test_boundary_cell_stays_single_phase(self, results, name):
        """Контурная ячейка однофазна на всей истории.

        Замер: min_t (p_{N-1} - p_b) = +499.3 / +2685.6 / +465.5 кПа (20 — 2026-10-03).
        Ловит: p0 вплотную к p_b (тогда разгазирование доходит до контура).
        """
        r = results[name]
        for n, st in enumerate(r["history"].states):
            assert st.Sg[-1] == 0.0, \
                f"{name}, запись {n}: S_g[N-1] = {st.Sg[-1]:.3e}, контурная ячейка двухфазна"
            assert abs(st.Rs[-1] - r["Rs0"]) < 1e-10

    @pytest.mark.parametrize("name", list(STANDING_COREY_COOLING))
    def test_gas_active_cells_match_pressure(self, results, name):
        """Ниже p_b газ есть всегда; выше p_b — только заметный, не шум.

        Три проверки на каждой записи (та же логика, что у примера 14):
        1) газ есть ровно в двухфазных ячейках (S_g > 0 <=> regime = 1);
        2) p < p_b(R_s0) => ячейка двухфазна;
        3) двухфазная ячейка при p >= p_b допустима только с S_g > 1e-8.
        Такие ячейки возможны: давление у края двухфазной зоны растёт вслед
        за падением дебита, а выделившийся раньше газ остаётся при p >= p_b.
        Замер (19, 21 — 2026-10-01; 20 — 2026-10-03): в 19–21 их нет.
        Ловит: отсутствие газа ниже p_b, рассогласование regime и S_g.
        """
        SG_NOISE = 1e-8
        r = results[name]
        pvt = _pvt_of_config(r["config"])
        pb = float(pvt.pb(np.array([r["Rs0"]]))[0])
        for n, st in enumerate(r["history"].states):
            below = st.p < pb
            two_phase = st.regime == 1
            assert np.array_equal(st.Sg > 0.0, two_phase), \
                f"{name}, запись {n}: S_g > 0 не совпадает с regime = 1"
            assert np.all(two_phase[below]), \
                f"{name}, запись {n}: однофазная ячейка при p < p_b"
            above = two_phase & ~below
            assert np.all(st.Sg[above] > SG_NOISE), \
                (f"{name}, запись {n}: двухфазная ячейка выше p_b с "
                 f"S_g = {st.Sg[above].min():.3e} — шум округления")

    @pytest.mark.parametrize("name", list(STANDING_COREY_COOLING))
    def test_config_follows_decisions(self, name):
        """Конфиг — корреляции и решения пользователя (19, 21 — 2026-10-01; 20 — 2026-10-03).

        Общее: PVT standing и ОФП corey (без CSV); S_gc = 0.1 (газ подвижен
        после 0.1), S_or = 0.05 (выбор FEAT-025; вводился как обход BUG-018,
        ошибка исправлена), N = 350, 30 сут при постоянном p_wf, k = 10 мД.
        Своё (словарь STANDING_COREY_COOLING): история — 19, 21: 30 × 1 сут,
        20: 48 × 1 ч + 28 × 1 сут; L — 19, 21: Клапейрон, 20: 170 кДж/кг;
        co — 20: 3.3e-9 1/Па, 19, 21: 0; p0 - p_b — 19, 21: 0.4-0.6 МПа,
        20: 2.71 МПа.
        Ловит: случайный возврат к табличным данным; смену решений по
        конфигу.
        """
        e = STANDING_COREY_COOLING[name]
        cfg = load_config(EXAMPLES_DIR / name / "config.json")
        assert cfg.pvt.model == "standing" and cfg.relperm.model == "corey"
        assert cfg.relperm.S_gc == 0.1 and cfg.relperm.S_or == 0.05
        assert cfg.grid.N == 350
        # load_config разворачивает краткие формы истории ({dt, repeat},
        # {duration, dt_out}) в список интервалов; длина интервала
        # {duration, dt_out} — ровно dt_out, сравнение точное
        hist = cfg.time.history
        expected = [dt for n, dt in e["steps"] for _ in range(n)]
        assert [h.dt for h in hist] == expected
        assert sum(expected) == 30 * 86400.0
        assert len({h.p_wf for h in hist}) == 1
        assert cfg.thermal.L_degas == e["L"]
        assert cfg.rock.permeability == e["k"]
        assert cfg.pvt.co_undersaturated == e["co"]
        pb = float(_pvt_of_config(cfg).pb(np.array([cfg.initial_conditions.Rs0]))[0])
        lo, hi = e["dp0"]
        assert lo < cfg.initial_conditions.p0 - pb < hi

    @pytest.mark.parametrize("name", list(STANDING_COREY_COOLING))
    def test_config_disables_steady_state(self, name):
        """Конфиг отключает стационарную аналитику целиком (output.steady_state = false).

        Как у 14: за 30 сут GOR < R_s0, газ ещё копится — сравнение с
        пределом t -> inf точность расчёта не характеризует.
        Ловит: возврат стационарных наложений.
        """
        assert _output(name).steady_state is False


# ═══════════════════════════════════════════════════════════
# S. Сценарий 17: останов после сильного охлаждения забоя (FEAT-029)
# ═══════════════════════════════════════════════════════════

class TestShutInStrongCooling:
    """Сценарий 17: конфиг 20 на N = 200; 15 сут добычи при 5 МПа, затем 15 сут останова.

    Останов — управление по дебиту q_oil = 0 (eq:bc_rate_well): потоки
    компонентов через забой нулевые, p_wf = p[0] (eq:bc_rate_pwf при q = 0).
    Записи: 0 — начальное состояние; 1..15 — концы суток добычи; 16..39 —
    часы первых суток останова (запись 15 + k — момент 15 сут + k ч);
    40..53 — концы суток 17..30. Числа — замер плана FEAT-029
    (vault/issues/feat-029/probes/plan_numbers.out.txt, 2026-10-07). Первый час
    останова — от подшага 1.76 с с удвоением (time.dt_after_control_change = 2 с,
    FEAT-032); числа останова — замер плана FEAT-032
    (vault/issues/feat-032/probes/readme_numbers_h2.out.txt).
    """

    NAME = "17_shut_in_strong_cooling"
    END_PROD = 15        # запись конца добычи (15 сут)

    def test_config_follows_decisions(self):
        """Конфиг 20 на N = 200; расписание 15 × 1 сут при 5 МПа, 24 × 1 ч и 14 × 1 сут с q_oil = 0.

        Решения пользователя 2026-10-07: конфиг примера 20, 15 + 15 сут,
        N = 200. dt_integration = 3600 с — решение пользователя 2026-10-07
        (скорость; замер FEAT-029 до DEBT-015, при равномерном дроблении:
        суточный шаг у 17 вдвое дольше — 200 с против 104 с, T(r_w) на
        30 сут отличается на 0.04 К). После DEBT-015 (локальное дробление)
        суточный шаг на останове сходится, 3600 с — выбор, а не требование;
        после BUG-024 — без единого отказа (~12 с против ~70 с при 3600 с).
        Ловит: возврат к суточному шагу, потерю часовой записи первых суток
        останова, подмену флюида, ОФП или тепловых констант.
        """
        cfg = load_config(EXAMPLES_DIR / self.NAME / "config.json")
        assert cfg.grid.N == 200
        assert cfg.time.dt_integration == 3600.0
        # FEAT-032 (решение пользователя 2026-10-11): первый час останова — от 1.76 с с удвоением
        assert cfg.time.dt_after_control_change == 2.0
        ic = cfg.initial_conditions
        assert (ic.p0, ic.T0, ic.Rs0) == (33.0e6, 380.0, 300.0)
        assert cfg.pvt.model == "standing" and cfg.relperm.model == "corey"
        assert cfg.relperm.S_gc == 0.1 and cfg.relperm.S_or == 0.05
        assert cfg.pvt.co_undersaturated == 3.3e-9
        assert cfg.rock.permeability == 1e-14
        assert cfg.thermal.L_degas == 170000.0
        hist = cfg.time.history
        assert len(hist) == 15 + 24 + 14
        for h in hist[:15]:
            assert (h.control, h.dt, h.p_wf) == ("pressure", 86400.0, 5.0e6)
        for k, h in enumerate(hist[15:]):
            assert h.control == "rate" and h.q_oil == 0.0
            assert h.min_bhp == 101325.0 and h.p_wf is None
            assert h.dt == (3600.0 if k < 24 else 86400.0)

    def test_production_cools_and_degasses(self, results):
        """На конце добычи забой охлаждён на 15 К, газ выделился, скважина добывает нефть и газ.

        Утверждения общих тестов test_oil_production, test_gas_appears,
        test_gas_produced — на записи 15 вместо последней (17 исключён из
        них списком ENDS_SHUT_IN). Охлаждение — теплота выделения газа.
        Замер: T(r_w) = 365.0166 К (ΔT = -14.983 К), q_o = 3.33438e-3
        м³ст/с, GOR = 271.85 < R_s0 = 300 (газ копится в пласте до порога
        S_gc), S_g(r_w) = 0.4490, газ в 165 ячейках из 200 (до 51.9 м).
        Ловит: потерю скрытой теплоты, смену знака mu_JT, подмену ОФП.
        """
        r = results[self.NAME]
        st = r["history"].states[self.END_PROD]
        assert st.T[0] == pytest.approx(365.0166, abs=2e-3)
        assert r["q_o"][self.END_PROD] == pytest.approx(3.33438e-3, rel=1e-4)
        gor = r["q_g"][self.END_PROD] / r["q_o"][self.END_PROD]
        assert 0.0 < gor < r["Rs0"]
        assert st.Sg[0] == pytest.approx(0.4490, abs=1e-3)
        assert np.count_nonzero(st.Sg > 0.0) == 165

    def test_shut_in_stops_flow_through_well(self, results):
        """На всех записях останова q_o = q_g = 0 точно, фактическое p_wf = p[0].

        Знак: q_o_std = -G_o[0]; при q_oil = 0 прототип ставит потоки забоя
        ровно 0 (ветка OIL_RATE: bhp = p0). Замер: max|p_wf - p[0]| = 0 Па.
        Ловит: утечку через забой при останове, запись уставки вместо
        фактического p_wf.
        """
        r = results[self.NAME]
        h = r["history"]
        for n in range(self.END_PROD + 1, len(h.states)):
            assert r["q_o"][n] == 0.0 and r["q_g"][n] == 0.0, f"запись {n}"
            assert h.well_data[n].p_wf == h.states[n].p[0], f"запись {n}"

    def test_pressure_builds_up_past_pb(self, results):
        """p(r_w) не убывает после останова; выше p_b — около 12 ч; на финале p = p0.

        Замер: 5.1545 МПа (15 сут) -> 25.4409 (1 ч) -> 30.4249 (запись 27,
        15.5 сут — первая выше p_b = 30.2921 МПа) -> 31.6345 (16 сут) ->
        33.0000 (27 сут); наименьшее приращение между записями 3.7 Па;
        финал max|p - p0| = 2.4 Па. Допуск ±1 запись: граница хрупкая — на
        записи 26 до p_b не хватает 31.6 кПа, а до BUG-024 (часы останова
        дробились) запись 26 была уже выше p_b на 3.8 кПа.
        Ловит: потерю притока через контур, «залипание» давления у забоя.
        """
        r = results[self.NAME]
        states = r["history"].states
        pw = np.array([s.p[0] for s in states])
        assert np.all(np.diff(pw[self.END_PROD:]) >= 0.0)
        assert pw[self.END_PROD + 1] == pytest.approx(25.4409e6, rel=1e-4)
        pb = float(_pvt_of_config(r["config"]).pb(np.array([r["Rs0"]]))[0])
        above = [n for n in range(self.END_PROD, len(pw)) if pw[n] > pb]
        assert abs(above[0] - 27) <= 1, f"выше p_b с записи {above[0]}"
        p0 = r["config"].initial_conditions.p0
        assert np.max(np.abs(states[-1].p - p0)) < 10.0

    def test_gas_dissolves_at_well_and_ring_remains(self, results):
        """У забоя газ растворяется за первый час; кольцо газа 3.6–24 м остаётся до конца.

        Физика: у забоя при 5 МПа газ занимает 45 % пор, но по массе его
        мало (B_g = 0.026); при сжатии он растворяется весь, нефть остаётся
        недонасыщенной, R_s застывает (79.59 у забоя). На 3.6–24 м газа за
        добычу скопилось больше, чем нефть растворяет и при p0: там газ
        остаётся (S_g до 0.062), нефть насыщена сверх R_s0 —
        R_s = R_s,eq(33 МПа) = 332.41. Течения после выравнивания давления
        нет, диффузии в модели нет.
        Замер: ячеек с газом 165 (15 сут) -> 112 (1 ч) -> 67 (16 сут) -> 51
        (с 21 сут, 3.63–24.27 м); ячейка 0 без газа с записи 16.
        Ловит: залипание ячеек в двухфазном режиме, утечку газа через забой,
        растворение сверх равновесия.
        """
        r = results[self.NAME]
        states = r["history"].states
        rr = r["grid"].r_centers
        assert all(s.Sg[0] == 0.0 for s in states[self.END_PROD + 1:])
        n_gas = [int(np.count_nonzero(s.Sg > 0.0)) for s in states]
        assert np.all(np.diff(n_gas[self.END_PROD:]) <= 0), n_gas
        final = states[-1]
        gas = final.Sg > 0.0
        assert np.count_nonzero(gas) == 51
        assert 3.5 < rr[gas].min() and rr[gas].max() < 25.0
        rs_eq = _pvt_of_config(r["config"]).Rs_eq(final.p)
        assert np.max(np.abs(final.Rs[gas] - rs_eq[gas])) <= 1e-10
        assert final.Rs[gas].min() > r["Rs0"]           # 332.41 > 300
        assert np.max(final.Rs - rs_eq) <= 1e-10        # пересыщенных нет
        # FEAT-032: 79.5875 — первый час останова от подшага 1.76 с; одним шагом
        # 3600 с было 79.5368 (R_s у забоя задаёт первый подшаг, BUG-026).
        # Чувствительность к допускам Ньютона замерена BUG-022 при шаге 3600 с:
        # 79.5364–79.5368 при atol = 1e-14, newton_cell_tol = 1e-8…1e-10.
        assert final.Rs[0] == pytest.approx(79.5875, abs=1e-3)

    def test_wellbore_rs_never_decreases(self, results):
        """R_s(r_w) на останове не убывает: забойная ячейка получает нефть только из ячейки 1.

        Физика: скважина закрыта, поток через забой нулевой; недонасыщенная забойная
        ячейка получает нефть только из ячейки 1 (R_s = 93.11 против 79.59 у забоя), и в
        неявной схеме с ячейкой выше по потоку новое R_s — выпуклая комбинация старого
        и притекающего: R_s(r_w) растёт или стоит. Убывание допускается только на уровне
        допуска Ньютона: условие по ячейке (numerics.newton_cell_tol = 1e-8, BUG-022) даёт
        оценку ошибки R_s забоя за шаг eps*B_o*(gas_residual_scale + R_s) = 4.6e-6 — за сутки
        из 24 шагов по 1 ч худший случай 1.1e-4 (подшагов при дроблении больше). Порог -1e-4
        — с запасом ×5 к замеру BUG-022: наименьшее изменение между записями 16..53 —
        -2.0e-5 (сейчас +1.6e-7, план FEAT-032); без условия — -1.84e-2 (6 убываний,
        шум абсолютного допуска).
        Ловит: возврат к одному абсолютному критерию сходимости (BUG-022).
        """
        rs = np.array([s.Rs[0] for s in results[self.NAME]["history"].states])
        assert np.min(np.diff(rs[self.END_PROD + 1:])) >= -1e-4

    def test_wellbore_warms_monotonically(self, results):
        """T(r_w) на останове строго растёт: +4.24 К за 1 ч, к 30 сут недогрев 2.65 К.

        Физика (члены схемы по ячейкам зоны r < 1 м, план FEAT-032, zone_budget.py):
        в первый час зона греется растворением своего газа (53 %) и сжатием (43 %);
        дальше газа у забоя нет, и тепло приходит теплопроводностью из
        зоны, где газ ещё растворяется (сутки 2–15: 97 % нагрева зоны).
        Конвекции через забой нет. Замер: 365.0166 (15 сут) -> 369.2582
        (1 ч) -> 373.7368 (16 сут) -> 377.3505 К (30 сут); наименьшее
        приращение между записями 0.0645 К. Первый час — 12 подшагов от 1.76 с
        с удвоением (FEAT-032); второй час дробится на 2 × 1800 с (отказ ступени 4
        по памяти, DEBT-048), остальные часы — одним шагом.
        Ловит: потерю адиабатического члена или теплоты растворения,
        конвекцию через закрытый забой, выключенное нарастание (T на 1 ч ниже на 0.48 К).
        """
        T = np.array([s.T[0] for s in results[self.NAME]["history"].states])
        E = self.END_PROD
        assert np.all(np.diff(T[E:]) > 0.0)
        assert T[E + 1] == pytest.approx(369.2582, abs=2e-3)
        assert T[39] == pytest.approx(373.7368, abs=2e-3)
        assert T[-1] == pytest.approx(377.3505, abs=2e-3)

    def test_gas_ring_warmer_than_T0(self, results):
        """На финале кольцо газа теплее T0: max ΔT = +0.22 К на 22.5 м.

        Физика: в кольце газ растворялся при росте давления — теплота
        растворения и сжатие нагрели его выше пластовой температуры, а
        теплопроводность за 15 сут тепло не отвела. Профиль T немонотонен:
        у забоя -2.65 К, на 10 м -0.04 К, на 22.5 м +0.22 К, у контура
        +0.001 К. Замер: max ΔT = +0.2212 К.
        Ловит: потерю члена растворения, неверный знак теплоты дегазации.
        """
        r = results[self.NAME]
        final = r["history"].states[-1]
        dT = final.T - r["config"].initial_conditions.T0
        k = int(np.argmax(dT))
        assert dT[k] == pytest.approx(0.2212, abs=2e-3)
        rr = r["grid"].r_centers
        gas = final.Sg > 0.0
        assert rr[gas].min() <= rr[k] <= rr[gas].max()

    def test_shut_in_heating_sources(self, results):
        """На останове пласт греют сжатие (77 %) и растворение газа (22 %).

        Приращения членов баланса энергии по области от конца добычи до
        30 сут (energy.balance.compute_energy_balance), Дж: ΔE = +1.776e11,
        адиабатический +1.371e11, дегазация (здесь — растворение)
        +3.958e10, Джоуль–Томсон +6.8e8, конвекция +2.0e8. За добычу член
        дегазации отрицателен (-2.226e11): газ выделялся и охлаждал.
        Ловит: смену знака члена дегазации при растворении, потерю
        адиабатического члена.
        """
        from gpn_multiphase_solver.energy.balance import compute_energy_balance

        r = results[self.NAME]
        bal = compute_energy_balance(r["history"])
        E = self.END_PROD
        d = {k: float(bal[k][-1] - bal[k][E])
             for k in ("delta_E", "cum_adiab", "cum_deg", "cum_jt", "cum_conv")}
        assert d["delta_E"] == pytest.approx(1.776e11, rel=2e-3)
        assert d["cum_adiab"] == pytest.approx(1.371e11, rel=2e-3)
        assert d["cum_deg"] == pytest.approx(3.958e10, rel=2e-3)
        assert bal["cum_deg"][E] < 0.0   # добыча: выделение газа охлаждает
        assert abs(d["cum_jt"]) + abs(d["cum_conv"]) < 0.01 * d["delta_E"]

    def test_plots_cover_production_phase(self, results):
        """pvt.png и relperm.png 17 показывают диапазон добычи, а не только останов.

        На последней записи p = 33 МПа почти всюду и S_g <= 0.0625 (кольцо).
        По всей истории: p 5.1545…33 МПа (p_b = 30.29 МПа внутри), S_g до
        0.44899 (запись 15). Ловит возврат к диапазону по последней записи.
        """
        r = results[self.NAME]
        rep = _pvt_module().report_pvt(r["config"], r["history"])
        assert rep["p_lo"] == pytest.approx(5.1545e6, rel=1e-4)
        assert rep["p_lo"] < rep["pb"] < rep["p_hi"]
        _lo, hi = _relperm_module()._sg_range(r["history"])
        assert hi == pytest.approx(0.44899, abs=1e-4)

    def test_config_settings(self):
        """Конфиг 17: 7 моментов профилей, без стационарной аналитики, наложения штатные.

        Как у 16 (решение FEAT-019): профили равномерно 0, 5, …, 30 сут;
        стационар последнего интервала (q = 0) тривиален — p = p0 всюду.
        """
        out = _output(self.NAME)
        assert out.n_profiles == 7
        assert out.steady_state is False
        assert out.closed_form_overlays == ["p", "Sg"]


# ═══════════════════════════════════════════════════════════
# T. Сценарий 18: вход прототипа — книга INPUT_TEMPLATE.xlsx (VAL-005)
# ═══════════════════════════════════════════════════════════

def _prototype_input_module():
    """Модуль examples/18_prototype_input/prototype_input.py, загруженный по пути файла."""
    # Папку примера в sys.path не кладём: в ней main.py, он перекрыл бы
    # одноимённые модули других тестов. Модуль импортирует пакет, прототип
    # (путь — pythonpath в pyproject.toml), numpy; io.figures — лениво, только для рисунков.
    import importlib.util
    path = EXAMPLES_DIR / "18_prototype_input" / "prototype_input.py"
    spec = importlib.util.spec_from_file_location("prototype_input_18", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def prototype_18(tmp_path_factory):
    """Прототип на книге примера 18 штатным путём run_workbook (~12 с): профили и дебиты по отметкам."""
    pi = _prototype_input_module()
    out = tmp_path_factory.mktemp("prototype_18")
    pi.run_prototype(pi.BOOK, out)
    return pi.load_prototype(out)


class TestPrototypeInput:
    """Сценарий 18: книга прототипа INPUT_TEMPLATE.xlsx → конфиг; сверка с прототипом и CMG IMEX T07.

    Гидродинамику считает Ньютон прототипа (PrototypeHydroAdapter), табличное
    PVT от T не зависит: сверка проверяет перевод книги, адаптер и наш шаг по
    времени, а не физику фильтрации (её авторы прототипа сверили с IMEX сами).
    Записи: 0 — начальное состояние; 1..22 — строки SCHEDULE книги: 1 мин;
    1, 2, 4, 5 сут; 5 сут + 10…60 с; 6, 14, 15 сут; 15 сут + 10…60 с; 16,
    30 сут. Числа — замер плана VAL-005
    (vault/issues/val-005/probes/plan_numbers_dt3600.out.txt, 2026-10-08).
    """

    NAME = "18_prototype_input"

    def test_files_reproduce_conversion(self, tmp_path):
        """config.json и три CSV папки — ровно то, что даёт конвертация книги.

        Ловит: ручную правку файлов примера в обход книги; правку конвертера
        без перегенерации файлов. Сравнение построчное, не побайтное:
        окончания строк в рабочей копии зависят от настроек git.
        """
        pi = _prototype_input_module()
        pi.convert(pi.BOOK, tmp_path)
        for name in ("config.json", "oil_pvt.csv", "gas_pvt.csv", "relperm.csv"):
            got = (tmp_path / name).read_text(encoding="utf-8").splitlines()
            ref = (EXAMPLES_DIR / self.NAME / name).read_text(encoding="utf-8").splitlines()
            assert got == ref, f"{name}: файл примера расходится с конвертацией книги"

    def test_config_follows_decisions(self):
        """Конфиг: геометрия и пласт книги, шаг = DTMAX, теплофизика примера 14, режимы 150/120/100 бар.

        dt_integration = 3600 с = DTMAX книги: против прототипа max|Δp| 0.0054
        бар, суточный шаг — 1.93 бар и 9 % по q_o против IMEX, шаг 600 с —
        71 с расчёта вместо 13 без выигрыша (замер плана). Теплофизика и
        плотности — не из книги (прототип изотермический), решение
        пользователя 2026-10-08: значения примера 14. Ловит: смену шага,
        подмену тепловых констант, сдвиг смены режима.
        """
        cfg = load_config(EXAMPLES_DIR / self.NAME / "config.json")
        assert cfg.time.dt_integration == 3600.0
        assert cfg.grid.N == 100
        g = cfg.geometry
        assert (g.r_well, g.R_ext, g.h) == (0.1, 100.0, 10.0)
        assert cfg.rock.permeability == 9.869233e-16 and cfg.rock.porosity == 0.2
        ic = cfg.initial_conditions
        assert (ic.p0, ic.T0, ic.Rs0) == (200e5, 350.0, 50.0)
        assert (cfg.pvt.rho_o_std, cfg.pvt.rho_g_std) == (850.0, 0.85)
        th = cfg.thermal
        assert (th.c_p_oil, th.c_p_gas, th.mu_JT_oil, th.mu_JT_gas, th.L_degas) == \
            (2000.0, 2850.0, -4e-7, 4e-6, 230000.0)
        hist = cfg.time.history
        assert len(hist) == 22
        # Начала интервалов, сут: смена режима — ровно на 5 и 15 сут
        t = np.cumsum([0.0] + [h.dt for h in hist]) / 86400.0
        for k, h in enumerate(hist):
            expected = 150e5 if t[k] < 5.0 else (120e5 if t[k] < 15.0 else 100e5)
            assert h.control == "pressure" and h.p_wf == expected, f"интервал {k}"
        assert t[-1] == pytest.approx(30.0, abs=1e-9)

    def test_imex_reference_applies(self):
        """Эталон IMEX T07 применим к шаблону и к самой T07, но не к книгам с другим MODEL, таблицами или режимами.

        T01 — те же MODEL и таблицы, режим 100 бар с начала; T06 — другое p0;
        T08c — расширенная PVTO и подъём p_wf. Ловит: сверку с IMEX на книге,
        для которой эталона нет.
        """
        pi = _prototype_input_module()
        inputs = pi.PROTO_ROOT / "regression" / "inputs"
        assert pi.imex_applicable(pi.BOOK)
        assert pi.imex_applicable(inputs / "T07.xlsx")
        for case in ("T01", "T06", "T08c"):
            assert not pi.imex_applicable(inputs / f"{case}.xlsx"), case

    def test_main_settings(self):
        """18: 6 моментов профилей и без стационарной аналитики (конфиг); main.py вызывает сверку с прототипом и IMEX."""
        out = _output(self.NAME)
        assert out.n_profiles == 6
        assert out.steady_state is False
        text = (EXAMPLES_DIR / self.NAME / "main.py").read_text(encoding="utf-8")
        assert "report_and_plot(" in text

    def test_conversion_rate_book(self, tmp_path):
        """Книга с управлением по дебиту (T09 прототипа): OIL_RATE → control="rate", сутки → секунды, Minimum BHP → min_bhp.

        T09: 2 м³ст/сут нефти при Minimum BHP 100 бар, 7 интервалов. Шаблон
        эту ветку конвертера не задействует. Ловит: потерю перевода суток в
        секунды, подмену min_bhp другим давлением, отказ проверки конфига.
        """
        pi = _prototype_input_module()
        pi.convert(pi.PROTO_ROOT / "regression" / "inputs" / "T09.xlsx", tmp_path)
        hist = load_config(tmp_path / "config.json").time.history
        assert len(hist) == 7
        for h in hist:
            assert (h.control, h.q_oil, h.min_bhp, h.p_wf) == ("rate", 2.0 / 86400.0, 100e5, None)

    def test_conversion_refuses_unsupported_book(self, tmp_path, monkeypatch):
        """Книгу, которую решатель молча поставил бы иначе, конвертер отвергает с именем параметра.

        Решатель держит на контуре p0 и берёт опорное давление породы равным
        p0 (factory.py, CompressibleRock); у управления по дебиту нижняя
        граница p_wf обязательна. Листы подменяются в памяти (_read_book),
        файл книги не меняется. Ловит: молчаливую подмену p_e, p_ref и
        min_bhp.
        """
        import copy
        pi = _prototype_input_module()
        base = pi._read_book(pi.BOOK)

        def edited(sheet, key_col, key, changes):
            """Копия листов книги с правкой первой строки листа sheet, где key_col == key."""
            sheets = copy.deepcopy(base)
            rows = [list(r) for r in sheets[sheet]]
            h = [str(x).strip() if x is not None else "" for x in rows[0]]
            for r in rows[1:]:
                if r[h.index(key_col)] == key:
                    for col, value in changes.items():
                        r[h.index(col)] = value
                    break
            sheets[sheet] = rows
            return sheets

        cases = {
            "Reference pressure": edited("MODEL", "Parameter", "Reference pressure",
                                         {"Value": 190.0}),
            "Outer-boundary pressure": edited("MODEL", "Parameter", "Outer-boundary pressure",
                                              {"Value": 210.0}),
            # Первая строка SCHEDULE (0 сут) — OIL_RATE без нижней границы p_wf
            "Minimum BHP": edited("SCHEDULE", "Time, day", 0.0,
                                  {"Control mode": "OIL_RATE",
                                   "Oil-rate target, Sm3/day": 2.0,
                                   "Minimum BHP, bar(a)": None}),
        }
        for what, sheets in cases.items():
            monkeypatch.setattr(pi, "_read_book", lambda book, _s=sheets: _s)
            with pytest.raises(ValueError, match=what):
                pi.convert(pi.BOOK, tmp_path / what.replace(" ", "_"))

    def test_matches_prototype(self, results, prototype_18):
        """Расчёт совпадает с прототипом на той же книге на всех 22 отметках SCHEDULE.

        Различие — только последовательность шагов по времени: у нас 3600 с,
        у прототипа 1 мин с ростом до 60 мин. Замер: max|Δp| 0.0054 бар,
        |ΔS_g| 3.1e-4, |ΔR_s| 1.7e-3, q_o 0.006 %, q_g 0.068 %, GOR 0.067 %;
        p_wf совпадает точно. Допуски TOL_PROTOTYPE — запас ~3 раза. Ловит
        ошибку перевода книги (k на 1 % — q_o 0.94 %; c_r = 0 — 1.38 бар;
        скин 0.1 — 7.4 бар), суточный шаг (1.93 бар), потерю отметки
        SCHEDULE в истории (compare падает с именем отметки).
        """
        pi = _prototype_input_module()
        days = sorted(t for t in prototype_18 if t > 0.0)
        assert len(days) == 22
        worst = pi.compare(results[self.NAME]["history"], prototype_18, days)
        bad = {k: worst[k] for k, lim in pi.TOL_PROTOTYPE.items() if not worst[k] <= lim}
        assert not bad, f"расхождение с прототипом вне допуска: {bad}"

    def test_matches_imex_t07(self, results):
        """Против CMG IMEX T07 — на уровне приёмки прототипа авторами (запас ~10 %).

        Отметки 1, 2, 4, 5, 6, 14, 15, 16, 30 сут (отметки «+1 мин» авторы
        исключили). Авторы: Δp 0.1374 бар, ΔS_g 0.0046, RMSE 0.00227, ΔR_s
        0.0445, q_o 0.51 %, q_g 2.52 %, GOR 2.56 %; замер плана — 0.1373 /
        0.0046 / 0.00227 / 0.0445 / 0.51 / 2.59 / 2.62. Ловит то же, что
        сверка с прототипом, грубее: k на 1 % — q_o 1.41 %, Δp 0.168 бар.
        """
        pi = _prototype_input_module()
        worst = pi.compare(results[self.NAME]["history"], pi.load_imex(), pi.STABLE_DAYS)
        bad = {k: worst[k] for k, lim in pi.TOL_IMEX.items() if not worst[k] <= lim}
        assert not bad, f"расхождение с IMEX вне допуска: {bad}"

    def test_wellbore_cools(self, results):
        """Забой холоднее T0 на всех записях после пуска: на 0.20…0.64 К.

        Охлаждение — адиабатическое расширение и теплота выделения газа
        (баланс энергии за 30 сут: −1.19e10 и −8.9e8 Дж против +4.6e8 Дж
        Джоуля–Томсона). После каждого снижения p_wf забой за минуту
        охлаждается на ~0.4 К и затем прогревается. Замер: от −0.6431 К
        (запись 20, 15 сут + 60 с) до −0.1994 К (запись 5, 5 сут); на 30 сут
        −0.4892 К. Ловит: смену знака теплового эффекта, ошибку единиц
        тепловых констант.
        """
        h = results[self.NAME]["history"]
        dT = np.array([s.T[0] for s in h.states[1:]]) - 350.0
        assert np.all((dT > -1.0) & (dT < -0.1)), dT
        assert dT.min() == pytest.approx(-0.6431, abs=2e-3)
        assert dT[-1] == pytest.approx(-0.4892, abs=2e-3)
