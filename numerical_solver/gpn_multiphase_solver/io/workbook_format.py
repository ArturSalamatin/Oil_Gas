"""Формат книги ввода Excel, версия 1: листы, строки, единицы, допустимые значения (FEAT-033).

Одна таблица на генератор шаблона (io/workbook_template.py) и на перевод книги
в конфиг (FEAT-035). Подписи, единицы и комментарии книги правятся здесь:
правки, сделанные командой в самой книге, переносятся сюда вручную, а
gpn-solver template пишет книгу заново.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..units import BAR_TO_PA, DAY_TO_S, HOUR_TO_S, MD_TO_M2, PA_S_TO_CP

# Версия формата — ячейка format_version листа MODEL. В книге все строки
# обязательны (умолчаний нет), поэтому новое поле или другая единица — новая
# версия: книга прежней версии получает отказ перевода.
FORMAT_VERSION = 1

# Заголовки листов «параметр–значение», столбцы A…F. Комментарий — на двух
# языках: Comment по-английски, «Комментарии» по-русски (решение 66 плана)
PARAM_HEADER = ("Key", "Parameter", "Value", "Unit", "Comment", "Комментарии")


@dataclass(frozen=True)
class Limit:
    """Допустимые значения числовой ячейки: границы, целое, больше значения другой строки."""
    lo: float | None = None        # нижняя граница; None — нет
    lo_strict: bool = False        # True: v > lo; False: v >= lo
    hi: float | None = None        # v <= hi; None — нет
    integer: bool = False          # целое; Excel хранит 100 как 100.0 — оно целое
    above_key: str | None = None   # v > значения строки с этим ключом на том же листе

    def accepts(self, v, above: float | None = None) -> bool:
        """Допустимо ли число v; above — значение строки above_key."""
        # bool — подкласс int: логическое значение в числовой ячейке — не число
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not np.isfinite(v):
            return False
        if self.integer and v != np.floor(v):
            return False
        if self.lo is not None and (v <= self.lo if self.lo_strict else v < self.lo):
            return False
        if self.hi is not None and v > self.hi:
            return False
        return self.above_key is None or v > above


# Пределы — как у программы (_validate, _validate_interval в io/config.py;
# пределы столбцов CSV в factory.py): проверка книги не строже JSON (решение 50)
POSITIVE = Limit(lo=0.0, lo_strict=True)              # > 0
NON_NEGATIVE = Limit(lo=0.0)                           # >= 0
ANY = Limit()                                          # любое конечное число
FRACTION = Limit(lo=0.0, hi=1.0)                       # [0, 1]
POROSITY = Limit(lo=0.0, lo_strict=True, hi=1.0)       # (0, 1]
COUNT = Limit(lo=1.0, integer=True)                    # целое >= 1


@dataclass(frozen=True)
class Param:
    """Строка листа «параметр–значение»: ключ, подпись, единица, демо-значение, пределы."""
    key: str                    # путь поля конфига (rock.permeability) или ключ книги (rock.p_ref)
    label: str                  # столбец Parameter: «Название (символ)»
    unit: str                   # столбец Unit, ASCII; перевод в СИ — UNIT_TO_SI
    demo: float | int | str     # значение книги генератора, в единицах книги
    comment: str                # столбец Comment, по-английски
    comment_ru: str             # столбец «Комментарии», по-русски
    limit: Limit | None = None  # None — у постоянной строки (fixed)
    # Постоянное значение: ячейка Value заблокирована, перевод принимает только
    # demo (версия формата; якобиан и решатель СЛАУ — решение 65 плана)
    fixed: bool = False

    def accepts(self, v, above: float | None = None) -> bool:
        """Допустимо ли значение ячейки Value."""
        if self.fixed:
            return v == self.demo
        return self.limit.accepts(v, above)


@dataclass(frozen=True)
class Column:
    """Столбец табличного листа: заголовок с единицей, назначение, пределы."""
    header: str                 # строка 1 листа; перевод сверяет её точно
    unit: str                   # «-» — безразмерная
    target: str                 # столбец CSV (factory.py) или поле HistoryInterval; «t» — момент
    limit: Limit | None = None  # None — выбор из choices
    choices: tuple[str, ...] = ()


# ── MODEL: пласт, флюид, начальные условия, скважина ──
MODEL = (
    Param("format_version", "Format version", "-", FORMAT_VERSION,
          "Workbook format; written by gpn-solver template, do not change.",
          "Версия формата книги. Её записывает gpn-solver template, значение не меняется.",
          fixed=True),
    Param("geometry.r_well", "Wellbore radius (rw)", "m", 0.1,
          "Inner boundary of the radial model.",
          "Внутренняя граница расчётной области: стенка скважины.", POSITIVE),
    Param("geometry.R_ext", "Drainage radius (re)", "m", 100.0,
          "Outer boundary of the radial model; greater than rw.",
          "Внешняя граница расчётной области, контур питания; больше rw.",
          Limit(above_key="geometry.r_well")),
    Param("geometry.h", "Formation thickness (h)", "m", 10.0,
          "Thickness of the formation open to flow.",
          "Толщина пласта, по которой идёт приток.", POSITIVE),
    Param("rock.permeability", "Absolute permeability (k)", "mD", 1.0,
          "Uniform and isotropic.",
          "Одинакова по всему пласту и во всех направлениях.", POSITIVE),
    # Пара (φ_ref, p_ref), как ROCK в Eclipse/OPM: пористость керна часто
    # известна не при пластовом давлении (решение 49). Перевод считает
    # porosity = φ_ref·exp(c_r·(p0 − p_ref)) — точно для закона решателя
    Param("rock.porosity_ref", "Reference porosity (φref)", "-", 0.2,
          "Porosity at the reference pressure pref; at pi it is φref·exp(cr·(pi - pref)).",
          "Пористость при опорном давлении pref. При начальном давлении pi пористость "
          "равна φref·exp(cr·(pi - pref)).", POROSITY),
    # Абсолютное давление > 0 — своя проверка книги: в конфиге поля нет
    Param("rock.p_ref", "Reference pressure (pref)", "bar(a)", 200.0,
          "Pressure at which φref is given.",
          "Давление, при котором задана пористость φref.", POSITIVE),
    Param("rock.compressibility", "Pore volume compressibility (cr)", "1/bar", 4.5e-5,
          "φ(p) = φi·exp(cr·(p - pi)); 0: incompressible pore volume.",
          "Пористость меняется с давлением как φ(p) = φi·exp(cr·(p - pi)); при нуле "
          "поровый объём не сжимается.", NON_NEGATIVE),
    # У программы предела плотностей нет (DEBT-076); книга требует > 0 (решение 54)
    Param("pvt.rho_o_std", "Oil density at standard conditions (ρo,sc)", "kg/m3", 800.0,
          "Stock-tank oil; used by the energy equation.",
          "Дегазированная нефть при стандартных условиях; нужна уравнению энергии.",
          POSITIVE),
    Param("pvt.rho_g_std", "Gas density at standard conditions (ρg,sc)", "kg/m3", 0.727,
          "Used by the energy equation.",
          "Нужна уравнению энергии.", POSITIVE),
    # Контур питания держит p0, T0, R_s0 (factory._create_schedule): p_ext, T_ext, Rs_ext
    Param("initial_conditions.p0", "Initial reservoir pressure (pi)", "bar(a)", 200.0,
          "Uniform at t = 0; also held constant at the drainage radius re.",
          "Одинаково по всему пласту в начальный момент; на контуре питания re "
          "поддерживается постоянным.", POSITIVE),
    Param("initial_conditions.Rs0", "Initial solution gas-oil ratio (Rsi)", "Sm3/Sm3", 50.0,
          "Uniform at t = 0 and in the inflow at re; within the Rs range of OIL_PVT, "
          "pi not below Pb(Rsi).",
          "Одинаково по всему пласту в начальный момент и в притоке через контур re. "
          "Лежит в диапазоне Rs таблицы OIL_PVT; начальное давление pi не ниже "
          "давления насыщения Pb(Rsi).", NON_NEGATIVE),
    Param("initial_conditions.T0", "Initial reservoir temperature (Ti)", "K", 350.0,
          "Uniform at t = 0; also held constant at the drainage radius re.",
          "Одинакова по всему пласту в начальный момент; на контуре питания re "
          "поддерживается постоянной.", POSITIVE),
    # Скин — только гидродинамика (BUG-029), отрицательный не предусмотрен (DEBT-056)
    Param("numerics.skin", "Skin factor (S)", "-", 0.0,
          "Well inflow resistance (hydraulics only); not included in the energy equation.",
          "Дополнительное сопротивление притоку у скважины. Учитывается только в "
          "гидродинамике, в уравнение энергии не входит.", NON_NEGATIVE),
)

# ── THERMAL: тепловые свойства скелета и фаз ──
# Скелет — сплошная твёрдая фаза: ρ_ma·c_ma и λ_ma входят в уравнение энергии
# с весом 1 − φ0 (определение под eq:main_rhocpeff; eq:lambda_eff). Перевод
# считает rock.rho_cp_solid = ρ_ma·c_ma.
THERMAL = (
    Param("rock.rho_solid", "Rock matrix density (ρma)", "kg/m3", 2650.0,
          "Solid grains, pore space excluded (quartz: 2650).",
          "Плотность минеральных зёрен без учёта пор (кварц: 2650).", POSITIVE),
    Param("rock.c_solid", "Rock matrix specific heat capacity (cma)", "J/(kg*K)", 820.0,
          "Solid grains (quartz at 350 K: 820). The energy equation uses ρma·cma.",
          "Теплоёмкость минеральных зёрен (кварц при 350 K: 820). В уравнение энергии "
          "входит произведение ρma·cma.", POSITIVE),
    # λ = 0 допустимо — так отключают теплопроводность (_validate, DEBT-047)
    Param("rock.lambda_solid", "Rock matrix thermal conductivity (λma)", "W/(m*K)", 2.5,
          "λeff = (1 - φi)·λma + φi·(So·λo + Sg·λg) is an upper (parallel) bound: "
          "choose λma so that λeff matches the measured conductivity of the saturated rock.",
          "Эффективная теплопроводность считается как λeff = (1 - φi)·λma + "
          "φi·(So·λo + Sg·λg); такое осреднение даёт оценку сверху. λma подбирается так, "
          "чтобы λeff совпала с измеренной теплопроводностью насыщенной породы.",
          NON_NEGATIVE),
    Param("rock.lambda_oil", "Oil phase thermal conductivity (λo)", "W/(m*K)", 0.13,
          "Reservoir oil.",
          "Пластовая нефть.", NON_NEGATIVE),
    Param("rock.lambda_gas", "Gas phase thermal conductivity (λg)", "W/(m*K)", 0.05,
          "Free gas at reservoir conditions.",
          "Свободный газ в пластовых условиях.", NON_NEGATIVE),
    Param("thermal.c_p_oil", "Oil phase specific heat capacity (cp,o)", "J/(kg*K)", 2365.0,
          "Reservoir oil with dissolved gas; constant.",
          "Пластовая нефть с растворённым газом; принята постоянной.", POSITIVE),
    Param("thermal.c_p_gas", "Gas phase specific heat capacity (cp,g)", "J/(kg*K)", 2800.0,
          "Free gas at reservoir conditions; constant.",
          "Свободный газ в пластовых условиях; принята постоянной.", POSITIVE),
    # Знак любой (eq:muJT_def): у нефти μ_JT < 0, у газа ниже давления инверсии > 0;
    # μ_JT,o > 0 и L < 0 — предупреждения _validate, не отказ
    Param("thermal.mu_JT_oil", "Oil Joule–Thomson coefficient (μJT,o)", "K/MPa", -0.4,
          "(∂T/∂p) at constant enthalpy; negative for oil: oil heats up when throttled.",
          "Изменение температуры с давлением при постоянной энтальпии. У нефти "
          "отрицательный: при дросселировании нефть нагревается.", ANY),
    Param("thermal.mu_JT_gas", "Gas Joule–Thomson coefficient (μJT,g)", "K/MPa", 2.05,
          "Positive below the inversion pressure: gas cools when throttled.",
          "Ниже давления инверсии положительный: при дросселировании газ охлаждается.", ANY),
    Param("thermal.L_degas", "Heat of gas liberation from oil (L)", "kJ/kg", 230.0,
          "Per kg of liberated gas; positive: liberation absorbs heat (cooling).",
          "На килограмм выделившегося газа. Положительное значение: выделение газа "
          "поглощает тепло, пласт охлаждается.", ANY),
)

# ── NUMERICS: все численные поля конфига (решение 17); шаги — в часах (решение 18) ──
NUMERICS = (
    Param("grid.N", "Grid cells (N)", "-", 100,
          "Logarithmic radial grid from rw to re: cells are finer near the well.",
          "Ячейки сгущаются к скважине: сетка равномерна по ln r от rw до re.", COUNT),
    Param("time.dt_integration", "Integration time step (Δt)", "h", 1.0,
          "Each SCHEDULE interval is split into equal substeps not longer than Δt.",
          "Каждый интервал SCHEDULE делится на равные подшаги не длиннее Δt.", POSITIVE),
    # 0.11 с — как в примерах 16, 17 (BUG-026); число, а не формула (П2 плана);
    # 0.11/3600 ч с 15 значащими цифрами (решение 63) — 0.11000000000000017 с.
    # Слова «выключено» нет (решение 64): h0 >= подшага интервала даёт полный
    # первый шаг (TimeSchedule.first_substep_depth возвращает 0)
    Param("time.dt_after_control_change", "First substep after control change (h0)", "h",
          3.05555555555556e-05,
          "After a change of well control (not at t = 0) the first substep shrinks to h0, "
          "rounded down to substep/2^m, then doubles. A value not less than Δt switches "
          "this off. 3.0556E-05 h = 0.11 s.",
          "После смены режима скважины (кроме момента t = 0) первый подшаг уменьшается "
          "до h0, округлённого вниз до подшага/2^m, и дальше удваивается. Значение не "
          "меньше Δt отключает уменьшение. 3.0556E-05 ч = 0,11 с.", POSITIVE),
    Param("numerics.max_retries", "Max step halvings", "-", 9,
          "A substep where Newton fails is halved; the smallest substep is Δt/2^max_retries.",
          "Если Ньютон на подшаге не сошёлся, подшаг делится пополам; самый короткий "
          "подшаг равен Δt/2^max_retries.", Limit(lo=0.0, hi=20.0, integer=True)),
    Param("numerics.newton_max_iter", "Newton max iterations", "-", 15,
          "Limit of Newton iterations while the set of cells with free gas is fixed.",
          "Предел итераций Ньютона, пока набор ячеек со свободным газом не меняется.",
          COUNT),
    # Проходы набора фаз прототипа: проходы, где газ только снимается, не
    # считаются (BUG-028), всего проходов не больше max_active_set_iter + N
    Param("numerics.max_active_set_iter", "Max phase-set passes", "-", 12,
          "After Newton converges, cells where free gas appeared or vanished are switched "
          "and Newton is repeated. This limits the repeats that switch gas on; repeats "
          "that only remove gas are not counted.",
          "После сходимости Ньютона проверяется, где свободный газ появился или исчез; "
          "если состав фаз в ячейках изменился, Ньютон повторяется. Параметр ограничивает "
          "число повторов, в которых газ появляется хотя бы в одной ячейке; повторы, где "
          "газ только исчезает, не считаются.", COUNT),
    # Условие по ячейке (BUG-022): max|F|·Δt/V_p <= tol; «выключено» в книге нет (решение 64)
    Param("numerics.newton_cell_tol", "Newton cell tolerance", "-", 1e-8,
          "Newton has converged only if in every cell the mass residual of the step is "
          "below this fraction of the cell pore volume.",
          "Ньютон считается сошедшимся, только если в каждой ячейке невязка массы за шаг "
          "меньше этой доли порового объёма ячейки.", POSITIVE),
    Param("numerics.rs_switch_tol", "Gas appearance tolerance", "Sm3/Sm3", 1e-5,
          "Free gas appears in a cell when Rs exceeds the saturated Rs at the cell pressure "
          "by more than this value.",
          "Свободный газ появляется в ячейке, когда газосодержание Rs превышает равновесное "
          "при давлении ячейки больше чем на это значение.", POSITIVE),
    Param("numerics.sg_switch_tol", "Gas disappearance tolerance", "-", 1e-9,
          "Free gas is removed from a cell when its computed saturation Sg becomes negative "
          "by more than this value; smaller negative Sg is treated as round-off.",
          "Свободный газ в ячейке исчезает, когда расчётная насыщенность Sg становится "
          "отрицательной и по модулю больше этого значения. Меньшая по модулю "
          "отрицательная Sg считается погрешностью счёта.", POSITIVE),
    # Постоянные (решение 65): заказчику нужны только grouped и sparse; reference
    # и dense прототипа — для проверок разработчиками, в JSON они остаются
    Param("numerics.jacobian_mode", "Jacobian mode", "-", "grouped",
          "Fixed: the Jacobian is computed by finite differences over groups of columns.",
          "Значение постоянное: якобиан считается конечными разностями по группам "
          "столбцов.", fixed=True),
    Param("numerics.linear_solver", "Linear solver", "-", "sparse",
          "Fixed: sparse LU factorization.",
          "Значение постоянное: LU-разложение разреженной матрицы.", fixed=True),
)

PARAM_SHEETS = {"MODEL": MODEL, "THERMAL": THERMAL, "NUMERICS": NUMERICS}

# ── SCHEDULE: строка k — момент t_k и режим на [t_k, t_{k+1}] ──
# Первая строка — t = 0, последняя — только момент завершения, её режим не
# читается (решения 9, 32, 40). Ячейки, которые режим строки не использует,
# не читаются (решение 61). Каждая строка — момент записи (решение 30).
SCHEDULE = (
    Column("Time, day", "day", "t", NON_NEGATIVE),
    Column("Control mode", "-", "control", choices=("BHP", "OIL_RATE")),
    Column("BHP target, bar(a)", "bar(a)", "p_wf", POSITIVE),
    Column("Oil-rate target, Sm3/day", "Sm3/day", "q_oil", NON_NEGATIVE),
    Column("Minimum BHP, bar(a)", "bar(a)", "min_bhp", POSITIVE),
)
# Режим книги → control конфига и поля HistoryInterval, которые режим читает
CONTROL_MODES = {"BHP": ("pressure", ("p_wf",)),
                 "OIL_RATE": ("rate", ("q_oil", "min_bhp"))}

# ── Таблицы PVT и ОФП: столбцы CSV и их пределы — factory.py (DEBT-042, DEBT-044) ──
OIL_PVT = (
    Column("Rs, Sm3/Sm3", "Sm3/Sm3", "Rs_sm3_sm3", NON_NEGATIVE),
    Column("Pressure, bar(a)", "bar(a)", "pressure_Pa", POSITIVE),
    Column("Bo, rm3/Sm3", "rm3/Sm3", "Bo", POSITIVE),
    Column("mu_o, cP", "cP", "mu_o_Pa_s", POSITIVE),
)
GAS_PVT = (
    Column("Pressure, bar(a)", "bar(a)", "pressure_Pa", POSITIVE),
    Column("Bg, rm3/Sm3", "rm3/Sm3", "Bg", POSITIVE),
    Column("mu_g, cP", "cP", "mu_g_Pa_s", POSITIVE),
)
RELPERM = (
    Column("Sg", "-", "Sg", FRACTION),
    Column("kro", "-", "kro", FRACTION),
    Column("krg", "-", "krg", FRACTION),
)
# Первая и последняя строки RELPERM обязательны (решение 68): (Sg, kro, krg),
# None — ячейка, которую задаёт инженер. Число — постоянное, ячейка заблокирована.
# k_rg = 0 при S_g = 0 и k_ro = 0 в последней строке требует и фабрика
# (_check_relperm_table: DEBT-079, DEBT-073)
RELPERM_FIRST_ROW = (0.0, None, 0.0)
RELPERM_LAST_ROW = (1.0, 0.0, None)

TABLE_SHEETS = {"SCHEDULE": SCHEDULE, "OIL_PVT": OIL_PVT, "GAS_PVT": GAS_PVT,
                "RELPERM": RELPERM}
SHEET_ORDER = (*PARAM_SHEETS, *TABLE_SHEETS, "COMMENTS")

# Единица книги → перевод значения в СИ (FEAT-035). «На единицу» — деление на
# точный множитель: v / 1e5 округляется один раз, v * 1e-5 — дважды (1e-5 в
# double неточно).
UNIT_TO_SI = {
    "-": lambda v: v,
    "m": lambda v: v,
    "mD": lambda v: v * MD_TO_M2,
    "bar(a)": lambda v: v * BAR_TO_PA,
    "1/bar": lambda v: v / BAR_TO_PA,
    "kg/m3": lambda v: v,
    "Sm3/Sm3": lambda v: v,
    "rm3/Sm3": lambda v: v,
    "K": lambda v: v,
    "J/(kg*K)": lambda v: v,
    "W/(m*K)": lambda v: v,
    "K/MPa": lambda v: v / 1e6,            # К/МПа → К/Па
    "kJ/kg": lambda v: v * 1e3,
    "h": lambda v: v * HOUR_TO_S,
    "day": lambda v: v * DAY_TO_S,
    "Sm3/day": lambda v: v / DAY_TO_S,     # м³ст/сут → м³ст/с
    "cP": lambda v: v / PA_S_TO_CP,        # сП → Па·с
}

# Поля конфига, которые перевод вычисляет из нескольких ячеек (FEAT-035)
DERIVED = {
    # φ0 = φ_ref·exp(c_r·(p0 − p_ref)) — сообщение _REMOVED_KEYS["rock"]["p_ref"], io/config.py
    "rock.porosity": ("rock.porosity_ref", "rock.p_ref", "rock.compressibility",
                      "initial_conditions.p0"),
    # (ρc_p)_s = ρ_ma·c_ma — определение под eq:main_rhocpeff
    "rock.rho_cp_solid": ("rock.rho_solid", "rock.c_solid"),
    "time.history": ("SCHEDULE",),
}

# Поля конфига, которых в книге нет, с причиной. Книга только табличная:
# корреляции Стендинга и Кори из неё недоступны (решение 28)
NOT_FROM_WORKBOOK = {
    "grid.type": "сетка одна — log_radial",
    "pvt.model": "всегда table",
    "pvt.co_undersaturated": "только Стендинг",
    "pvt.mu_o_undersaturated": "только Стендинг",
    "pvt.oil_pvt_file": "имя CSV пишет перевод",
    "pvt.gas_pvt_file": "имя CSV пишет перевод",
    "relperm.model": "всегда table",
    "relperm.S_or": "только Кори",
    "relperm.S_gc": "только Кори",
    "relperm.n_o": "только Кори",
    "relperm.n_g": "только Кори",
    "relperm.kro_max": "только Кори",
    "relperm.krg_max": "только Кори",
    "relperm.file": "имя CSV пишет перевод",
    "output.log_level": "умолчание конфига: листа OUTPUT нет (решение 44)",
    "output.title": "имя книги (FEAT-036)",
    "output.n_profiles": "умолчание конфига (решение 44)",
    "output.steady_state": "умолчание конфига (решение 44)",
    "output.closed_form_overlays": "умолчание конфига (решение 44)",
}
