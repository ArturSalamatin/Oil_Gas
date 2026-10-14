"""PrototypeHydroAdapter — обёртка RadialBlackOilModel → HydroSolver.

Конвертирует:
  - давление: Па ↔ бар (на входе и выходе)
  - режим: gas_active ↔ regime
  - управление: PressureControl → set_bhp_control (Па → бар),
    RateControl → set_oil_rate_control (м³ст/с → м³ст/сут, Па → бар)
  - забойное давление: bhp_bar прототипа → HydroResult.p_wf (Па)

Q, u, m, Gm из потоков компонентов — общий шаг
fluxes.phase_fluxes_from_components, тот же, что у compute_fluxes
(DEBT-028): выбор ячейки выше по потоку — по перепаду давления, как
в прототипе.

НЕ конвертирует:
  - Rs, Sg (безразмерные)
  - Потоки G (м³ст/с — уже SI в прототипе)
  - dt (секунды)

Знаки: инверсия ТОЛЬКО well-потоков (прототип: outflow+, мы: outflow−).
Internal и outer — без инверсии.

Дробления нет: solve — один вызов advance. Не сошёлся —
HydroConvergenceError; шаг дробит Simulator (DEBT-015, P4-адаптивный-шаг.md).
См. P1-адаптер-единицы.md.

Память ступени 4 (DEBT-048): после STAGE4_MEMORY принятых подряд шагов, решённых
ступенью 4 advance, при том же управлении и на продолжении той же траектории шаг
решается сразу ступенью 4 (advance_fourth_stage). Её отказ — отказ шага без
ступеней 1-3; после STAGE4_MAX_FAILURES отказов подряд память сбрасывается.

Текст отказа (DEBT-054): прежний текст (dt, t, итерации, невязка) и хвост из отчёта
Ньютона — абсолютный допуск, мера условия по ячейке с порогом numerics.newton_cell_tol
и её предел округления (DEBT-055), причина выхода, какое условие сходимости не выполнено
(отказ на пределе округления — отдельной оговоркой) и чья это статистика (ступень 1
после подмены DEBT-030 или ступень 4 по памяти).
В конце (DEBT-069) — попытки ступеней advance по порядку из поля attempts отчёта:
ступень, ветка, причина выхода, итерации, проходы набора фаз, переключения, невязка.

Баланс массы (DEBT-039): component_inventories — запас компонентов
функцией прототипа; HydroResult.int_G_* — интегралы потоков через забой
и контур за шаг (подшаг один — dt·G того же состояния).

Выход за таблицы (DEBT-027): после каждого сошедшегося advance — pvt_range_warnings
прототипа, категория «кривая насыщения выше таблицы» — только по свободному газу
(FREE_GAS_SG); каждая категория — одна запись журнала за расчёт, с моментом первого
выхода. Начальное состояние проверяет фабрика тем же методом warn_table_range.
Только табличная PVT (check_table_range): у HydroPVTtoBlackOilAdapter нет таблицы gp.
"""

from dataclasses import replace

import numpy as np

from .base import HydroSolver, HydroConvergenceError
from ..state import SimulationState, HydroResult, BoundaryConditions
from ..grid.base import Grid
from ..pvt.base import HydroPVT
from ..bc import PressureControl, RateControl
from ..units import BAR_TO_PA, DAY_TO_S
from ..fluxes import phase_fluxes_from_components
from ..log import user_log

# Память ступени 4 (DEBT-048). Замер плана (vault/plans/debt-048
# shutin-remember-solving-stage.md, 1.2 и 1.9): вариант m2s — после BUG-024
# −80 % итераций Ньютона на останове конфига 20, −69 % в примере 17;
# 22 примера из 23 побитово.
STAGE4_MEMORY = 2         # принятых подряд шагов ступени 4, после которых шаг — сразу ею
STAGE4_MAX_FAILURES = 2   # отказов подряд ступени 4 по памяти, после которых память сброшена

# Свободный газ для проверки «кривая насыщения выше таблицы» (DEBT-027), доля порового
# объёма. Выше наибольшего p_b таблицы R_s^sat обрезан на последней ветви; это меняет
# решение только там, где есть газ, который мог бы раствориться. Ячейка фронта с флагом
# газа держит S_g на уровне округления Ньютона: до 1.2e-11 в табличных примерах (кроме
# 04a, где газ настоящий), до 3.6e-9 в эталонных кейсах прототипа (без условия по ячейке
# BUG-022); замерено на шагах до 1 ч. Настоящий газ выше p_b — сразу больше 1e-3 (пример
# 04a, 2 ч), до 0.08. Порог — в 280 раз выше шума и в 1000 раз ниже настоящего газа
# (vault/plans/debt-027 table-range-diagnostics.md, §2.4).
FREE_GAS_SG = 1e-6


# Причина выхода из Ньютона прототипа — поле exit_reason отчёта (DEBT-054). Неизвестный
# код печатается как есть: прототип может добавить причину раньше, чем адаптер — перевод.
_EXIT_REASONS = {
    "line_search": "линейный поиск не принял ни одной точки",
    "linear_solver": "отказ линейного решателя",
    "max_iter": "исчерпан лимит итераций",
    "nonfinite": "нечисловое приближение",
    "active_set": "набор фаз не установился",
    "sg_bound": "корень с S_g > 0.98",
    "branch": "ветвь скважины несогласована",
}

# Ветка скважины попытки ступени (DEBT-069) — поле branch записи StageAttempt прототипа
_BRANCHES = {"open": "открыта", "shut": "закрыта"}


def _failure_details(report, cell_tol: float | None, stage: int) -> str:
    """Хвост текста отказа: допуск, мера ячеек, предел округления, причина выхода, невыполненное условие (DEBT-054, DEBT-055)."""
    # Поля residual_tol, cell_measure, exit_reason несёт BlackOilNewtonReport с DEBT-054,
    # cell_floor — с DEBT-055. Подставные отчёты тестов (SimpleNamespace, отчёт без этих
    # полей) их не имеют — хвоста нет, текст прежний.
    tol = getattr(report, "residual_tol", None)
    measure = getattr(report, "cell_measure", None)
    floor = getattr(report, "cell_floor", None)
    reason = getattr(report, "exit_reason", "")
    if tol is None and measure is None and not reason:
        return ""
    text = ""
    if tol is not None:
        text += f" (допуск {tol:.2e})"
    if measure is not None:
        text += f", мера ячеек {measure:.2e}"
        if cell_tol is not None:
            text += f" (порог numerics.newton_cell_tol = {cell_tol:g})"
        # DEBT-055: предел округления меры на том же приближении — мера вектора |J|·ulp(z)
        # (eq:newton_cell_floor); есть только у отказа Ньютона с условием по ячейке
        if floor is not None:
            text += f", предел округления {floor:.2e}"
    if reason:
        text += f", выход: {_EXIT_REASONS.get(reason, reason)}"
    # Какое условие не выполнено — те же сравнения, что в Ньютоне прототипа
    # (||F||_inf <= residual_tol; мера <= cell_tol, BUG-022), поэтому это факт,
    # а не догадка. Только для отчёта о приближении Ньютона (есть допуск): у выхода
    # 'active_set' невязка — начального приближения нового набора фаз. «Оба
    # выполнены» при отказе — отказ не по условиям: ветвь скважины, S_g > 0.98,
    # у ступени 4 — переключения фаз или удержанные ячейки выше по потоку не
    # устоялись к лимиту итераций (причина выхода — рядом в тексте).
    if tol is not None:
        abs_ok = report.residual_inf <= tol
        if measure is None or cell_tol is None:
            text += " — абсолютное условие " + ("выполнено" if abs_ok else "не выполнено")
        else:
            text += " — " + {
                (True, False): "не выполнено только условие по ячейке",
                (False, True): "не выполнено только абсолютное условие",
                (False, False): "не выполнены оба условия сходимости",
                (True, True): "оба условия сходимости выполнены",
            }[(abs_ok, measure <= cell_tol)]
            # DEBT-055: только условие ячейки, и мера не выше предела округления — точнее
            # на этом шаге не решить; предел пропорционален шагу, дробление его снимает.
            # Сравнение — факт, как и классы выше (максимумы по сетке; в отказах на
            # пределе, замеренных планом, оно верно и поячеечно)
            if abs_ok and measure > cell_tol and floor is not None and measure <= floor:
                text += ", мера не выше предела округления (он пропорционален шагу)"
    # Чьи числа: при отказе advance — исходного алгоритма (подмена DEBT-030), у ступени 4
    # по памяти (DEBT-048) — её собственные
    return text + f"; числа — Ньютона ступени {stage}"


def _attempts_text(report) -> str:
    """Строка попыток ступеней advance по порядку: ступень, ветка, причина выхода, итерации, проходы, переключения, невязка (DEBT-069)."""
    # Поле attempts несёт BlackOilNewtonReport с DEBT-069: пусто, если шаг решила ступень 1.
    # Подставные отчёты тестов (SimpleNamespace) его не имеют — строки нет, текст прежний
    attempts = getattr(report, "attempts", ())
    if not attempts:
        return ""
    items = []
    for a in attempts:
        r = a.report
        head = f"{a.stage} {_BRANCHES.get(a.branch, a.branch)}" if a.branch else f"{a.stage}"
        if r.converged:
            # только у шага, принятого ступенями 2–4: последняя попытка
            items.append(f"{head} — сошлась (итераций {r.iterations})")
        elif r.exit_reason == "branch":
            # Ньютон сошёлся, но p[0] противоречит ветке: проходы, переключения и невязка
            # сошедшегося решения причину не объясняют; на старте добычи «закрыта»
            # «сходится» за 0 итераций на неизменном состоянии (DEBT-030)
            items.append(f"{head} — {_EXIT_REASONS['branch']} (итераций {r.iterations})")
        else:
            # Пустая причина — у подставных отчётов тестов; настоящий отказ её всегда имеет (DEBT-054)
            reason = _EXIT_REASONS.get(r.exit_reason, r.exit_reason) or "отказ"
            items.append(f"{head} — {reason} (итераций {r.iterations}, "
                         f"проходов {r.active_set_iterations}, "
                         f"переключений {r.phase_switches}, невязка {r.residual_inf:.2e})")
    return "; попытки ступеней: [" + "; ".join(items) + "]"


class PrototypeHydroAdapter(HydroSolver):
    """Adapter: RadialBlackOilModel (бар) → HydroSolver (Па)."""

    def __init__(self, model, grid: Grid, pvt: HydroPVT,
                 stage4_memory: int | None = STAGE4_MEMORY,
                 max_newton: int = 15, max_active_iter: int = 12,
                 check_table_range: bool = False):
        """
        model         — RadialBlackOilModel, уже сконфигурированный
        grid          — наш Grid (LogRadialGrid)
        pvt           — наш HydroPVT; фабрика передаёт тот же FullPVT, что решателю энергии (DEBT-006)
        stage4_memory — после стольких принятых подряд шагов ступени 4 шаг решается
                        сразу ею (DEBT-048); None — память выключена
        max_newton      — итераций Ньютона на одно решение при фиксированном наборе
                          фаз (numerics.newton_max_iter, DEBT-008)
        max_active_iter — проходов набора фаз с включением газа (numerics.max_active_set_iter, BUG-028)
        check_table_range — проверять выход принятых состояний за PVT- и ОФП-таблицы
                          (DEBT-027); фабрика включает только для табличной PVT
        """
        self._model = model
        self._grid = grid
        self._pvt = pvt
        # Память ступени 4 (DEBT-048): серия принятых подряд шагов, решённых
        # ступенью 4; отказы подряд ступени 4 по памяти; ключ продолжения —
        # (управление, t конца последнего принятого шага).
        self._stage4_memory = stage4_memory
        self._stage4_run = 0
        self._stage4_failures = 0
        self._stage4_key = None
        # Лимиты Ньютона прототипа (DEBT-008): передаются в каждый вызов advance и
        # advance_fourth_stage. Умолчания — умолчания advance (blackoil.py): адаптер,
        # созданный без них (тесты), считает как прежде. Ступень 4 (_newton_switching)
        # их не читает — у неё свой предел 40 итераций; передаются и ей, чтобы шаг по
        # памяти (DEBT-048) оставался побитово шагом advance после трёх отказов.
        self._max_newton = max_newton
        self._max_active_iter = max_active_iter
        # Выход за таблицы (DEBT-027): уже выведенные категории — на весь расчёт.
        # Адаптер живёт один расчёт (фабрика строит его заново): второй run того же
        # симулятора выведенные категории не повторит.
        self._check_table_range = check_table_range
        self._range_categories: set[str] = set()

    def warn_table_range(self, proto_state, t: float) -> None:
        """Выход состояния за PVT- и ОФП-таблицы — в журнал, одна запись на категорию за расчёт (DEBT-027)."""
        if not self._check_table_range:
            return
        from radial_blackoil.diagnostics import pvt_range_warnings, warning_category

        # Прототип берёт свойства за краями таблиц с краёв, без экстраполяции и молча;
        # его pvt_range_warnings называет категорию и значение. Категория — по
        # warning_category: в тексте о ветвях давления двоеточия нет, а числа меняются.
        for warning in pvt_range_warnings(self._model, proto_state,
                                          free_gas_sg=FREE_GAS_SG):
            category = warning_category(warning)
            if category in self._range_categories:
                continue
            self._range_categories.add(category)
            where = ("Начальное состояние" if t == 0.0
                     else f"Состояние при t = {t / DAY_TO_S:.4g} сут")
            user_log.warning(f"{where} вне таблиц: {warning}")

    def component_inventories(self, state: SimulationState) -> tuple[float, float]:
        """Запас компонентов функцией прототипа, м³ст. Ур. (eq:residual_oil), (eq:residual_gas)."""
        from radial_blackoil.state import BlackOilState

        # Запас берётся у прототипа, а не пересчитывается здесь: те же
        # пористость (rock.py), B_o, B_g и объёмы его сетки, что в невязке
        # Ньютона. Пересчёт своими формулами — механизм BUG-004: баланс
        # сверялся бы не со схемой, а с её копией.
        proto_state = BlackOilState(
            pressure_bar=state.p / BAR_TO_PA,
            rs_sm3_sm3=state.Rs.copy(),
            sg=state.Sg.copy(),
            gas_active=(state.regime == 1),
        )
        oil, gas = self._model.component_inventories(proto_state)
        return float(np.sum(oil)), float(np.sum(gas))

    def solve(self, state: SimulationState, dt: float,
              bc: BoundaryConditions) -> HydroResult:
        """Один шаг advance без дробления; не сошёлся — HydroConvergenceError (DEBT-015)."""
        from radial_blackoil.state import BlackOilState

        # ── Шаг 1: управление скважиной ──
        # Прототип ждёт бар и м³ст/сут; конфиг и WellControl — в СИ.
        well = bc.well
        if isinstance(well, PressureControl):
            self._model.set_bhp_control(well.p_wf / BAR_TO_PA)
        elif isinstance(well, RateControl):
            # Дебит нефти: p_bhp выражается из уравнения притока внутри
            # Ньютона (blackoil.py, _well_fluxes; eq:bc_rate_pwf); min_bhp —
            # нижняя граница, при p[0] <= min_bhp скважина закрыта.
            self._model.set_oil_rate_control(well.q_oil * DAY_TO_S,
                                             well.min_bhp / BAR_TO_PA)
        else:
            raise NotImplementedError(
                f"PrototypeHydroAdapter поддерживает PressureControl и RateControl, "
                f"получено {type(well).__name__}")

        # ── Шаг 2: SimulationState (Па) → BlackOilState (бар) ──
        proto_state = BlackOilState(
            pressure_bar=state.p / BAR_TO_PA,
            rs_sm3_sm3=state.Rs.copy(),
            sg=state.Sg.copy(),
            gas_active=(state.regime == 1),
        )

        # ── Шаг 3: advance ──
        # Память ступени 4 (DEBT-048). На останове из развитой газовой зоны почти
        # каждый шаг решает только ступень 4 advance (BUG-020), а ступени 1-3 перед
        # ней не сходятся: на непринятые решения уходило около 80 % итераций
        # Ньютона на останове. После STAGE4_MEMORY принятых подряд шагов ступени 4
        # шаг решается сразу ею: advance_fourth_stage побитово тот же, что advance
        # после трёх отказов. Её отказ — отказ шага, ступени 1-3 не пробуются:
        # замер плана — после её отказа они не решили ни одного шага из 2486.
        # Страховка от шага, который решили бы только они, — сброс памяти после
        # STAGE4_MAX_FAILURES отказов подряд. Одиночный шаг ступени 4 память не
        # включает: пример 16 (один такой шаг за расчёт) остаётся побитовым.
        # Память — только на продолжении той же траектории при том же управлении:
        # ключ — управление (атрибуты модели после set_*) и t конца последнего
        # принятого шага; повтор подшага после отказа идёт из того же состояния.
        m = self._model
        control = (m.control_mode, m.p_bhp_bar, m.oil_rate_target_sm3_day, m.min_bhp_bar)
        if (control, state.t) != self._stage4_key:
            self._stage4_run = self._stage4_failures = 0
        by_memory = (self._stage4_memory is not None
                     and self._stage4_run >= self._stage4_memory)
        limits = dict(max_active_iter=self._max_active_iter, max_newton=self._max_newton)
        if by_memory:
            new_proto, report = m.advance_fourth_stage(proto_state, dt, **limits)
        else:
            new_proto, report = m.advance(proto_state, dt, **limits)
        if not report.converged:
            # Отказ полного перебора серию не обнуляет: повтор того же подшага
            # меньшим шагом остаётся на той же траектории.
            if by_memory:
                self._stage4_failures += 1
                if self._stage4_failures >= STAGE4_MAX_FAILURES:
                    self._stage4_run = self._stage4_failures = 0
            # Дробит шаг Simulator (DEBT-015): делит пополам только этот
            # подшаг и повторяет его из того же состояния. Здесь — факты
            # отказа для журнала; текст для пользователя — в Simulator, он
            # дописывает этот текст в конец своего (DEBT-054). Хвост
            # _failure_details — после прежнего текста: тот остаётся началом.
            # Строка попыток ступеней (DEBT-069) — последней: прежний текст
            # и хвост DEBT-054 остаются началом.
            raise HydroConvergenceError(
                f"advance не сошёлся{' (ступень 4 по памяти)' if by_memory else ''}: "
                f"dt = {dt:.3e} с, "
                f"t = {state.t / DAY_TO_S:.4f} сут, итераций {report.iterations}, "
                f"невязка {report.residual_inf:.2e}"
                f"{_failure_details(report, m.cell_tol, 4 if by_memory else 1)}"
                f"{_attempts_text(report)}")
        self._stage4_run = self._stage4_run + 1 if report.phase_switching else 0
        self._stage4_failures = 0
        self._stage4_key = (control, state.t + dt)

        # Выход принятого состояния за таблицы (DEBT-027). Состояние принятое:
        # Simulator отвергает подшаг только по HydroConvergenceError выше, а отказ
        # проверки температуры после solve обрывает весь расчёт.
        self.warn_table_range(new_proto, state.t + dt)

        # ── Шаг 4: BlackOilState (бар) → SimulationState (Па) ──
        new_state = SimulationState(
            p=new_proto.pressure_bar * BAR_TO_PA,
            Sg=new_proto.sg.copy(),
            Rs=new_proto.rs_sm3_sm3.copy(),
            T=state.T.copy(),                # гидро не трогает T
            regime=np.where(new_proto.gas_active, 1, 2),
            t=state.t + dt,
        )

        # Интегралы потоков компонентов через забой и контур за шаг, м³ст
        # (DEBT-039). Потоки — на новом состоянии, как в невязке Ньютона
        # (неявная схема). Знаки: у прототипа отток к скважине положителен —
        # инверсия только на забое, как в _build_result: при добыче
        # int_*_well < 0, при притоке с контура int_*_ext < 0. Подшаг один,
        # поэтому интеграл равен dt·G того же состояния.
        f = self._model.face_component_fluxes_sm3s(new_proto)
        result = self._build_result(new_state, new_proto, bc)
        return replace(result,
                       int_G_o_well=dt * (-f['oil_well']),
                       int_G_o_ext=dt * f['oil_outer'],
                       int_G_g_well=dt * (-f['gas_component_well']),
                       int_G_g_ext=dt * f['gas_component_outer'])

    def _build_result(self, new_state: SimulationState,
                      new_proto, bc: BoundaryConditions) -> HydroResult:
        """Шаги 5–9: потоки компонентов из прототипа, Q, u, m, Gm — общим шагом fluxes.py."""
        N = self._grid.N

        # ── Шаг 5+6: потоки + согласование знаков ──
        fluxes = self._model.face_component_fluxes_sm3s(new_proto)

        # G_o: нефтяной компонент, м³ст/с
        # Инверсия ТОЛЬКО well (прототип: outflow+ = к скважине, мы: outflow− = к скважине)
        G_o = np.empty(N + 1)
        G_o[0] = -fluxes['oil_well']
        G_o[1:N] = fluxes['oil_internal']
        G_o[N] = fluxes['oil_outer']

        # G_g: полный газовый компонент (растворённый + свободный), м³ст/с
        G_g = np.empty(N + 1)
        G_g[0] = -fluxes['gas_component_well']
        G_g[1:N] = fluxes['gas_component_internal']
        G_g[N] = fluxes['gas_component_outer']

        # G_free_gas: только свободный газ, м³ст/с
        G_free_gas = np.empty(N + 1)
        G_free_gas[0] = -fluxes['free_gas_well']
        G_free_gas[1:N] = fluxes['free_gas_internal']
        G_free_gas[N] = fluxes['free_gas_outer']

        # ── Шаг 9: фактическое забойное давление ──
        # Результат шага при любом управлении: при OIL_RATE прототип
        # выражает p_bhp из уравнения притока (blackoil.py, _well_fluxes),
        # при BHP и p[0] <= уставки скважина закрыта и p_bhp = p[0].
        # well_rates считает на том же new_proto, что и потоки выше.
        p_wf = self._model.well_rates(new_proto)['bhp_bar'] * BAR_TO_PA

        # ── Шаги 7–8: Q, u, m, Gm — общий шаг с путём тестов (DEBT-028) ──
        # Тот же код, что у compute_fluxes: правило выбора ячейки выше по
        # потоку и формулы записаны в одном месте (fluxes.py).
        return phase_fluxes_from_components(G_o, G_g, G_free_gas,
                                            new_state, self._grid, self._pvt, bc,
                                            p_wf)
