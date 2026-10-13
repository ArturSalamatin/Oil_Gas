"""Регрессия BUG-004: кумулятивный баланс энергии на конфигах примеров.

Существующие тесты (test_val002.py::check_energy_balance) проверяют невязку
СЛАУ — она и до фикса была ~1e-12, потому что решатель самосогласован.
Физический баланс по сохранённой истории не был покрыт ничем, поэтому
BUG-004 прожил незамеченным: скрипт energy_balance.py считал запас энергии
как разность от t=0, а схема дискретизует приращение с множителем cap_j,
стоящим и в матрице, и в правой части. Разность двух выражений — дрейф
(rho cp)_eff, умноженный на абсолютную температуру; на табличном PVT он
систематичен и давал 20 % невязки, не убывающей с шагом по времени.

Конфиги укорочены до 6 ч и N = 25, чтобы тесты шли доли секунды.
"""

import copy
import json
from pathlib import Path

import numpy as np
import pytest

# Прототип radial_blackoil pytest берёт по pythonpath в pyproject.toml (DEBT-059).
# Ряды баланса собирает пакет (compute_energy_balance, DEBT-011); из examples/
# нужны только конфиги примеров.
_EXAMPLES = Path(__file__).resolve().parent.parent / "examples"

from gpn_multiphase_solver.energy.balance import compute_energy_balance  # noqa: E402

from gpn_multiphase_solver.io.config import _HISTORY_TIME_KEYS, load_config  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402


def _run_balance(example: str, p_wf: float | None = None) -> dict:
    """Укороченный прогон конфига примера + баланс энергии.

    6 ч вместо 72 ч и N = 25 вместо 50 — тест должен идти доли секунды.

    Конфиг примера содержит 72 интервала по 3600 с (DEBT-013), поэтому
    длительность задаётся усечением истории до одного интервала: правка
    history[0].dt без усечения укоротила бы только первый час из 72,
    и прогон остался бы 72-часовым — молча, без исключения.
    """
    config = load_config(_EXAMPLES / example / "config.json")
    config.grid.N = 25
    config.time.history = config.time.history[:1]
    config.time.history[0].dt = 21600.0        # 6 ч
    config.output.log_level = "WARNING"
    if p_wf is not None:
        config.time.history[0].p_wf = p_wf

    simulator, initial_state = SimulatorFactory.from_config(config)
    history = simulator.run(initial_state)
    # Длительность прогона — часть контракта теста: при неверном усечении
    # истории тест считал бы другой сценарий и всё равно был бы зелёным.
    assert history.times[-1] == pytest.approx(21600.0)
    return compute_energy_balance(history)


# Порог замыкания баланса. Дискретные уравнения схемы — тождество: если
# все члены выписаны на правильных слоях, баланс сходится точно, и остаются
# только округления. С DEBT-043 СЛАУ решается в отклонениях θ = T − T_ext,
# и на укороченном сценарии тестов (6 ч, N = 25) невязка 0…1.6e-16
# (замер DEBT-023, с теплопроводностью); до дефектного значения 9.6e-3 —
# десять порядков.
# Отдельный страж машинного уровня — TOL_MACHINE ниже.
#
# До BUG-007 здесь стояли 1e-2 и 2e-2: невязку считали ошибкой расщепления
# O(dt) и подгоняли порог под наблюдаемые ~1e-3. Ошибки расщепления в
# балансе нет (см. шапку gpn_multiphase_solver/energy/balance.py).
TOL_RESIDUAL = 1e-12


def test_energy_balance_table_pvt():
    """Табличный PVT + табличная ОФП: именно эта конфигурация давала 20 %.

    До фикса BUG-004 невязка была 0.204 на этом же setup, до BUG-007 —
    ~3.6e-3. Теперь это округления (с DEBT-043 — машинный уровень).
    """
    bal = _run_balance("04_table_table")
    assert abs(bal["rel_residual"][-1]) < TOL_RESIDUAL


def test_energy_balance_standing_pvt():
    """Standing + Corey: контрольная точка, что фикс не сломал рабочий путь.

    Прежде порог здесь был вдвое мягче остальных (2e-2 против 1e-2):
    невязка ~9.4e-3 считалась неустранимым остатком расщепления, и при
    пороге 1e-2 запас составлял 6 %. После BUG-007 выяснилось, что это был
    не остаток, а дефект: невязка упала до 4.0e-14, и отдельный порог
    больше не нужен.
    """
    bal = _run_balance("03_standing_corey")
    assert abs(bal["rel_residual"][-1]) < TOL_RESIDUAL


def test_energy_balance_no_degassing():
    """Табличный PVT при p_wf > p_b: газ не выделяется, Sg == 0, Rs == const.

    Отдельный режим, потому что в нём отсутствует разгазирование, но дефект
    накопления присутствовал в полной мере (0.209 до фикса BUG-004) — дрейф
    (rho cp)_eff идёт через rho_o, а не только через Sg.

    ВНИМАНИЕ: cum_deg здесь НЕ равен нулю и не должен — при Rs == const
    конвективная часть телескопируется в -L*rho_g_std*R*(G_o[N] - G_o[0]),
    то есть в поток растворённого газа, втекающего с нефтью через контур и
    уносимого через забой. Дегазации нет, а поток есть; проверять cum_deg
    на ноль было бы ошибкой (см. DEBT-009 и запись BUG-004 в реестре).
    """
    bal = _run_balance("04_table_table", p_wf=16e6)
    assert abs(bal["rel_residual"][-1]) < TOL_RESIDUAL


@pytest.mark.parametrize("example", ["03_standing_corey", "04_table_table"])
def test_balance_independent_of_history_structure(example):
    """Накопленные члены не зависят от того, как часто пишется история.

    Ключевой тест части B (DEBT-013). Раньше на этом месте стоял тест
    обратного смысла: compute_energy_balance ОТВЕРГАЛ разреженную историю, потому
    что суммировал приращения (T^n - T^{n-1}) по сохранённым шагам, и при
    пропуске шагов сумма занижалась. Теперь члены копятся на подшагах
    внутри решателя, поэтому структура истории на них не влияет вовсе.

    Один и тот же сценарий (6 ч, dt_integration из конфига) считается
    двумя способами: одной записью на весь прогон и шестью почасовыми.
    Суммируются одни и те же вклады подшагов, поэтому финальные значения
    обязаны совпасть с точностью до накопления ошибок сложения.
    """
    def run(n_intervals: int):
        config = load_config(_EXAMPLES / example / "config.json")
        config.grid.N = 25
        iv = copy.deepcopy(config.time.history[0])
        config.time.history = [copy.deepcopy(iv) for _ in range(n_intervals)]
        for h in config.time.history:
            h.dt = 21600.0 / n_intervals
        config.output.log_level = "WARNING"

        simulator, initial_state = SimulatorFactory.from_config(config)
        history = simulator.run(initial_state)
        assert history.n_saved == n_intervals + 1
        return compute_energy_balance(history)

    sparse = run(1)     # одна запись на весь прогон
    dense = run(6)      # почасовые записи

    for key in ("delta_E", "cum_adiab", "cum_conv",
                "cum_jt", "cum_deg", "cum_cond"):
        assert sparse[key][-1] == pytest.approx(dense[key][-1], rel=1e-10), key

    # Невязка проходит порог при обеих структурах — раньше разреженная
    # история давала на два-три порядка хуже.
    assert abs(sparse["rel_residual"][-1]) < TOL_RESIDUAL
    assert abs(dense["rel_residual"][-1]) < TOL_RESIDUAL


# ──────────────────────────────────────────────────────────────
# FEAT-018: ступенчатое расписание совпадает с равномерным
# ──────────────────────────────────────────────────────────────

# Шаг интегрирования теста делит все интервалы обоих расписаний (300 с
# и 3600 с), поэтому оба делают одни и те же 72 подшага по 300 с.
# С шагом конфигов 03/04 (3600 с) так не вышло бы: интервал записи 300 с
# сам измельчил бы интегрирование на старте
# (dt_actual = dt_hist / ceil(dt_hist / dt_integration) <= dt_hist),
# и тест сравнивал бы две разные схемы. Замер при планировании: при 3600 с
# та же пара расписаний на примере 03 расходится по T до 0.040 К.
_DT_INT_SCHEDULE = 300.0


def _run_schedule(example: str, tmp_path: Path, name: str, blocks: list[dict]):
    """Прогон конфига примера с подменённой историей (6 ч, N = 25).

    История записывается в JSON и проходит через load_config — проверяется
    вся цепочка: краткая форма → разворачивание → расчёт.
    """
    src = _EXAMPLES / example / "config.json"
    raw = json.loads(src.read_text(encoding="utf-8"))
    # Управление скважиной — из первого объекта истории примера (у 03 и 04
    # забойное давление постоянно на всей истории), время — из блоков теста.
    # Отбрасываются все ключи времени, а не только dt: история примеров
    # записана краткой формой {duration, dt_out} (DEBT-014), и её ключи
    # перекрыли бы блоки теста — равномерное расписание дало бы ValueError,
    # ступенчатое молча стало бы 144 интервалами по 3600 с
    control = {k: v for k, v in raw["time"]["history"][0].items()
               if k not in _HISTORY_TIME_KEYS}
    raw["time"]["history"] = [{**block, **control} for block in blocks]
    raw["time"]["dt_integration"] = _DT_INT_SCHEDULE
    path = tmp_path / f"{name}.json"
    path.write_text(json.dumps(raw), encoding="utf-8")

    config = load_config(path)
    # Таблицы PVT и ОФП (пример 04) фабрика ищет относительно конфига,
    # а JSON лежит во временном каталоге — возвращаем каталог примера.
    config.config_dir = src.parent
    config.grid.N = 25
    config.output.log_level = "WARNING"
    simulator, initial_state = SimulatorFactory.from_config(config)
    return simulator.run(initial_state)


@pytest.mark.parametrize("example", ["03_standing_corey", "04_table_table"])
def test_stepped_schedule_matches_uniform(example, tmp_path):
    """Ступенчатое расписание даёт то же решение, что равномерное (FEAT-018).

    Одни и те же 6 ч записываются двумя способами:
      равномерно — 72 записи по 300 с (форма dt + repeat);
      ступенчато — 12 записей по 300 с в первый час, затем 5 по 3600 с
                   (две формы duration + dt_out).
    Последовательность подшагов одна и та же (см. _DT_INT_SCHEDULE), на
    границе интервала решатель ничего не сбрасывает, поэтому на общих
    моментах записи состояние, данные скважины и накопленные балансы энергии
    и массы совпадают ПОБИТОВО. Допуска нет намеренно: расхождение хоть в одном
    бите значит, что структура истории влияет на расчёт, — это дефект,
    его надо искать, а не прятать допуском.
    """
    uniform = _run_schedule(example, tmp_path, "uniform",
                            [{"dt": 300.0, "repeat": 72}])
    stepped = _run_schedule(example, tmp_path, "stepped",
                            [{"duration": 3600.0, "dt_out": 300.0},
                             {"duration": 18000.0, "dt_out": 3600.0}])

    # Состав истории: начальное состояние + по записи на интервал
    assert uniform.n_saved == 1 + 72
    assert stepped.n_saved == 1 + 12 + 5
    # 72 сложения по 300.0 точны в двоичной арифметике
    assert stepped.times[-1] == uniform.times[-1] == 21600.0

    index = {t: k for k, t in enumerate(uniform.times)}
    for j, t in enumerate(stepped.times):
        k = index[t]        # KeyError — момент записи ступенчатой истории сдвинулся
        for name in ("p", "Sg", "Rs", "T", "regime"):
            assert np.array_equal(getattr(stepped.states[j], name),
                                  getattr(uniform.states[k], name)), (t, name)
        assert stepped.well_data[j] == uniform.well_data[k], t
        assert stepped.balance[j] == uniform.balance[k], t
        # Баланс массы (DEBT-039): интегралы — те же подшаги, запас — та же
        # функция побитово равных состояний
        assert stepped.mass_balance[j] == uniform.mass_balance[k], t


# ──────────────────────────────────────────────────────────────
# FEAT-019: структура истории не влияет на расчёт и через останов
# ──────────────────────────────────────────────────────────────

def test_stepped_schedule_matches_uniform_across_shut_in(tmp_path):
    """Ступенчатое расписание совпадает с равномерным и через смену режима (FEAT-019).

    Тест из записи FEAT-019 («скачок ГУ одним интервалом и половинными —
    решение на общем моменте совпадает»). test_stepped_schedule_matches_uniform
    проверяет то же при постоянном p_wf; здесь 2 ч добычи при 6 МПа, затем
    2 ч останова (q_oil = 0) — смена и вида управления, и знака изменения
    давления. Конфиг примера 16, N = 25, шаг интегрирования 300 с делит все
    интервалы обоих расписаний:
      равномерно — 48 записей по 300 с;
      ступенчато — в каждом режиме 6 записей по 300 с, затем 3 по 1800 с.
    Длительность — 2 + 2 ч, а не 6 + 6: тест без метки slow идёт в быстрый
    уровень, табличный PVT считается медленно (6 + 6 ч — 20 с).
    Смена управления в обоих расписаниях — на границе интервала, подшаги
    одни и те же, поэтому на общих моментах записи состояние, данные скважины
    и накопленные балансы энергии и массы совпадают ПОБИТОВО (допуска нет — как
    в тесте FEAT-018).
    """
    src = _EXAMPLES / "16_well_shut_in" / "config.json"
    raw = json.loads(src.read_text(encoding="utf-8"))
    prod = {"control": "pressure", "p_wf": 6.0e6}
    shut = {"control": "rate", "q_oil": 0.0, "min_bhp": 101325.0}

    def run(name, blocks):
        raw["time"]["history"] = blocks
        raw["time"]["dt_integration"] = _DT_INT_SCHEDULE
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        config = load_config(path)
        # Таблицы PVT и ОФП фабрика ищет относительно конфига — каталог примера
        config.config_dir = src.parent
        config.grid.N = 25
        config.output.log_level = "WARNING"
        simulator, initial_state = SimulatorFactory.from_config(config)
        return simulator.run(initial_state)

    uniform = run("uniform", [{"dt": 300.0, "repeat": 24, **prod},
                              {"dt": 300.0, "repeat": 24, **shut}])
    stepped = run("stepped", [{"duration": 1800.0, "dt_out": 300.0, **prod},
                              {"duration": 5400.0, "dt_out": 1800.0, **prod},
                              {"duration": 1800.0, "dt_out": 300.0, **shut},
                              {"duration": 5400.0, "dt_out": 1800.0, **shut}])

    assert uniform.n_saved == 1 + 48
    assert stepped.n_saved == 1 + 2 * (6 + 3)
    # Режимы действительно разные: на конце добычи (2 ч, запись 24) дебит
    # положителен и газ у забоя есть, на останове дебит — ноль
    # (q_o_std = -G_o[0], конвенция знаков)
    assert uniform.well_data[24].q_o_std > 0.0
    assert uniform.states[24].Sg.max() > 0.0
    assert uniform.well_data[-1].q_o_std == 0.0

    index = {t: k for k, t in enumerate(uniform.times)}
    for j, t in enumerate(stepped.times):
        k = index[t]        # KeyError — момент записи ступенчатой истории сдвинулся
        for name in ("p", "Sg", "Rs", "T", "regime"):
            assert np.array_equal(getattr(stepped.states[j], name),
                                  getattr(uniform.states[k], name)), (t, name)
        assert stepped.well_data[j] == uniform.well_data[k], t
        assert stepped.balance[j] == uniform.balance[k], t
        # Баланс массы (DEBT-039): интегралы — те же подшаги, запас — та же
        # функция побитово равных состояний
        assert stepped.mass_balance[j] == uniform.mass_balance[k], t


# ──────────────────────────────────────────────────────────────
# Регрессия BUG-007: конвективный член на слое T^{n+1}
# ──────────────────────────────────────────────────────────────


def test_convection_uses_implicit_temperature():
    """Баланс замыкается с машинной точностью на Standing-PVT.

    Прямой регрессор BUG-007. Схема НЕЯВНАЯ: Phi+/Phi- стоят в матрице
    СЛАУ при неизвестных T^{n+1}, а накопитель баланса умножал их на T^n.
    Ошибка ~Phi*(T^{n+1}-T^n)*dt за подшаг систематична, пока идёт
    охлаждение, поэтому копилась: 9.6e-3 против самосогласованности
    схемы 5.5e-13.

    На дефектном коде даёт ~9.6e-3 — мимо порога на восемь порядков
    (проверено откатом правки).
    """
    bal = _run_balance("03_standing_corey")
    assert abs(bal["rel_residual"][-1]) < TOL_RESIDUAL


def test_convection_implicit_table_pvt():
    """То же на табличном PVT — вторая ветвь по источнику свойств.

    Источник PVT был разделительной линией в BUG-004 (20 % на таблице
    против 1 % на Стендинге), поэтому обе ветви проверяются раздельно:
    дефект, проявляющийся только на одной из них, иначе прошёл бы мимо.
    """
    bal = _run_balance("04_table_table")
    assert abs(bal["rel_residual"][-1]) < TOL_RESIDUAL


# Страж θ-формы (DEBT-043): на укороченном сценарии решение в отклонениях
# замыкает баланс точно (03 и 04 — 0; замер DEBT-023, с теплопроводностью),
# решение в абсолютной T — 1.6e-13 (03) и 4.9e-13 (04) (замер DEBT-043,
# при λ = 0). Порог — на порядок ниже абсолютной формы.
TOL_MACHINE = 1e-14


@pytest.mark.parametrize("example", ["03_standing_corey", "04_table_table"])
def test_energy_balance_machine_precision(example):
    """Баланс энергии замыкается на машинном уровне — СЛАУ решается в отклонениях.

    Страж DEBT-043. В абсолютной температуре округления сборки и
    прогонки ~ε·cap·T (T ~ 350 K) давали на этом сценарии 1.6e-13 и
    4.9e-13, на полных конфигах — до 1.3e-10, и порог проверок лежал
    на уровне шума. В отклонениях θ = T − T_ext — 0 в обоих. Если
    решатель вернётся к абсолютной T или станет передавать накопителю
    записанную T вместо θ, тест упадёт: оба пути возвращают шум ε·cap·T
    (замер при планировании: накопитель по записанной T — 3.2e-14 и
    1.4e-13).
    """
    bal = _run_balance(example)
    assert abs(bal["rel_residual"][-1]) < TOL_MACHINE


def test_accumulation_without_substep_raises():
    """add_accumulation без парного add_substep обязана бросить RuntimeError.

    Контракт двухфазного накопления (DEBT-013): коэффициенты подшага
    приходят в первой фазе, применяются во второй. При рассогласовании фаз
    Phi остались бы от ПРЕДЫДУЩЕГО подшага, и конвективный вклад
    посчитался бы по чужим коэффициентам — молча, без признаков.

    Без явной проверки падение всё равно произошло бы, но с невнятным
    "TypeError: unsupported operand type(s) for *: 'NoneType' and 'float'"
    на гашеном _dt_substep. Явное сообщение называет причину.
    """
    import numpy as np

    from gpn_multiphase_solver.energy.balance import EnergyBalanceAccumulator
    from gpn_multiphase_solver.grid.log_radial import LogRadialGrid

    # Сетка-минимум: значения роли не играют, нужны лишь N и volumes.
    grid = LogRadialGrid(0.1, 100.0, 10.0, 5, 1e-14)
    acc = EnergyBalanceAccumulator(grid)

    T_new = np.full(5, 350.0)
    T_prev = np.full(5, 351.0)
    rho_cp_eff = np.full(5, 2.0e6)

    with pytest.raises(RuntimeError, match="add_substep"):
        acc.add_accumulation(T_new, T_prev, rho_cp_eff, dt=3600.0)

    # Состояние не тронуто: проверка стоит до любых накоплений, поэтому
    # прерванный вызов не оставляет накопитель частично обновлённым.
    assert acc.delta_E == 0.0
    assert acc.cum_cond == 0.0
