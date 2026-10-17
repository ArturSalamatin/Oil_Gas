"""Правка заметки модули-hydro-newton.md и обратных ссылок (DEBT-077) — источник точного текста плана.

Режимы (запуск из корня репозитория или worktree):
    numerical_solver/.venv/Scripts/python -I vault/issues/debt-077/probes/note_apply.py
        проверка в памяти, файлы не меняются:
        - якоря старой заметки найдены ровно по одному разу;
        - проектная схема (от «## Вектор неизвестных» до «## Связанные заметки»)
          переносится дословно, меняется только уровень заголовков;
        - новый текст заметки проходит сторож DEBT-010/DEBT-074 (FORBIDDEN и
          существование меток из numerical_solver/tests/test_eq_references.py);
        - каждая вики-ссылка новой заметки ведёт на файл vault/**/<имя>.md или
          это идентификатор задачи (BUG/DEBT/FEAT/VAL-NNN);
        - каждый «До» обратных ссылок встречается в своём файле ровно один раз,
          после замены — ни одного; заметки вне literature/ после замен проходят сторож;
        - утверждения о существующем блочном Ньютоне после замен не остаются.
    ... note_apply.py --show    новый текст заметки целиком (stdout)
    ... note_apply.py --write   записать заметку и замены (шаг 1 плана)

Файлы — по корню, из которого запущен скрипт (Path.cwd()): в worktree правятся
файлы worktree.
"""

import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path.cwd()
K = "vault/knowledge/"
D, L = K + "decisions/", K + "literature/"

NOTE = D + "модули-hydro-newton.md"
ARCH = D + "архитектура библиотеки numerical_solver.md"
DICT = D + "словарь-код-физика.md"
PVT = D + "модули-pvt-контракт.md"
QUEST = D + "открытые вопросы проектирования.md"
ORDER = D + "порядок-реализации-модулей.md"
BENG = L + "Ben Gharbia Jaffré 2014 — полугладкий Ньютон для появления и исчезновения газовой фазы.md"
BOURG = L + "Bourgeat Jurak Smaï 2009 — двухфазная фильтрация с растворением газа в хранилище отходов.md"

# ── Новый текст заметки: куски ──────────────────────────────────────────────

HEAD = """\
---
name: модули-hydro-newton
description: Гидродинамический модуль — контракт HydroSolver и HydroResult (сверен с кодом), действующий решатель — прототип radial_blackoil через PrototypeHydroAdapter; отменённая проектная схема блочного Ньютона 3×3
metadata:
  type: project
---

# HydroSolver — контракт, решатель прототипа, отменённая схема блочного Ньютона

Код: `numerical_solver/gpn_multiphase_solver/hydro/base.py` (ABC `HydroSolver`, `HydroConvergenceError`), `state.py` (`HydroResult`), `hydro/prototype_adapter.py` (`PrototypeHydroAdapter` — единственная реализация). Решатель — прототип Сергея: `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/blackoil.py` (`RadialBlackOilModel`). Постановка: `numerical_solver/doc/problem_statement.tex`.

> **Собственного гидродинамического решателя нет и не будет** (решение пользователя 2026-10-15, [[DEBT-077]]): давление, $S_g$ и $R_s$ решает прототип через адаптер; код прототипа править разрешено. Заметка начата 2026-08-25, до передачи прототипа, как проект блочного Ньютона на $3N$ неизвестных; сверена с кодом в [[DEBT-077]] (2026-10-15):
> - «ABC» и «Тестовые двойники» — действующие, сверены с `hydro/base.py`, `state.py`, `tests/_doubles.py`;
> - «Действующий решатель» — что и где делают прототип и адаптер: ссылки на код и метки постановки, без пересказа;
> - «Проектная схема собственного решателя (отменена)» — исторический текст. Та же схема описана в постановке (`ssec:pressure_disc`, `sssec:switching_disc`) и остаётся там по решению пользователя 2026-10-15; описанием действующего алгоритма ни то, ни другое не является.
"""

ABC = """\
## ABC

Сокращено; полные докстринги — `hydro/base.py`.

```python
class HydroConvergenceError(RuntimeError):
    \"\"\"Шаг гидродинамики не сошёлся при данном dt; шаг дробит Simulator (DEBT-015).\"\"\"


class HydroSolver(ABC):

    @abstractmethod
    def solve(self, state: SimulationState, dt: float,
              bc: BoundaryConditions) -> HydroResult:
        \"\"\"Один шаг гидродинамики: state^n → state^{n+1}.\"\"\"
        ...

    def component_inventories(self, state: SimulationState) -> tuple[float, float] | None:
        \"\"\"Запас нефтяного и газового компонентов, м³ст. Ур. (eq:residual_oil), (eq:residual_gas).\"\"\"
        return None
```

Обязательства реализации:

1. `solve` обновляет `p`, `Sg`, `Rs`, `regime`; `T` не трогает — температуру после гидродинамики считает `EnergySolver` (расщепление).
2. `dt` задаёт `Simulator`; один шаг без дробления ([[DEBT-015]]). Не сошёлся — `HydroConvergenceError`, состояние не меняется; подшаг дробит `Simulator._advance`, чтобы энергия и балансы шли ровно по принятым подшагам ([[BUG-010]], [[P4-адаптивный-шаг]]).
3. Принятое состояние проверяет `Simulator._check_hydro_state` ([[DEBT-075]]): $0 \\le S_g \\le 1$, $p > 0$, $R_s \\ge 0$, все конечны — точно, без допуска; иначе расчёт обрывается `RuntimeError`. Малые отрицательные $S_g$ решатель обнуляет сам.
4. `component_inventories` не абстрактный: `None` — решатель массу не сохраняет (тестовые двойники `tests/_doubles.py`). Решатель, сохраняющий массу, обязан переопределить его **и** заполнять `HydroResult.int_G_*`, иначе `Simulator` бросит `RuntimeError` на первом шаге (`mass_balance.py`, [[DEBT-039]]).
5. `bc` — `well` (`PressureControl` или `RateControl`), `p_ext`, `T_ext`, `Rs_ext`, `Sg_ext`. `PrototypeHydroAdapter` берёт из `bc` только `well` и передаёт `bc` в `phase_fluxes_from_components`; условия контура прототип получает при создании (`factory._create_prototype_hydro`: `p_outer_bar` из $p_0$, `outer_rs_sm3_sm3` = $R_{s,0}$). `bc.p_ext` и `bc.Rs_ext` фабрика строит из тех же $p_0$, $R_{s,0}$ (`_create_schedule`), поэтому они совпадают; менять условия контура по ходу расчёта адаптер не умеет.

HydroResult определён в `state.py` (не в `hydro/base.py`) — это контейнер данных, а не часть ABC гидро-модуля. Избегает циклических зависимостей: SimulationHistory импортирует HydroResult, а hydro/base.py импортирует SimulationState.

```python
@dataclass
class HydroResult:
    state: SimulationState
    # Потоки компонентов (при ст. условиях) через грани
    G_o: np.ndarray        # [N+1] — нефтяной компонент, м³ст/с, >0 = от скважины
    G_g: np.ndarray        # [N+1] — ПОЛНЫЙ газовый компонент (растворённый+свободный), м³ст/с
    G_free_gas: np.ndarray # [N+1] — СВОБОДНЫЙ газовый компонент, м³ст/с
    # Объёмные расходы фаз (при пл. условиях) через грани
    Q_o: np.ndarray        # [N+1] — нефтяная фаза, м³пл/с, >0 = от скважины
    Q_g: np.ndarray        # [N+1] — газовая фаза, м³пл/с
    # Скорости фильтрации на гранях
    u_o: np.ndarray        # [N+1] — м/с, >0 = от скважины
    u_g: np.ndarray        # [N+1] — м/с
    # Фазовые массовые расходы через грани
    m_o: np.ndarray        # [N+1] — кг/с, = ρ_o_up · Q_o
    m_g: np.ndarray        # [N+1] — кг/с, = ρ_g_up · Q_g
    # Покомпонентные массовые расходы через грани
    Gm_o: np.ndarray       # [N+1] — кг/с, = ρ_o_ст · G_o
    Gm_g: np.ndarray       # [N+1] — кг/с, = ρ_g_ст · G_g
    # Давление на забойной грани после шага, Па (FEAT-020)
    p_wf: float
    # Интегралы потоков компонентов через забой и контур за шаг, м³ст (DEBT-039)
    int_G_o_well: float | None = None
    int_G_o_ext: float | None = None
    int_G_g_well: float | None = None
    int_G_g_ext: float | None = None
```

`p_wf` — результат шага при любом управлении: при заданном дебите выражается из уравнения притока (`eq:bc_rate_pwf`), при закрытой скважине равно `p[0]`; энергия и вывод берут $p_{wf}$ только отсюда (FEAT-020). `int_G_*` — $\\int G[0]\\,dt$ и $\\int G[N]\\,dt$ за шаг решателя, знак как у $G$; адаптер подшагов не делает, у него интеграл равен $\\Delta t \\cdot G$ нового состояния. `None` — решатель массу не сохраняет.

"""

STUB = """\
## Тестовые двойники (`numerical_solver/tests/_doubles.py`)

Не решатели: подставляют готовое поле вместо решения уравнения фильтрации и поэтому держатся вне пакета — иначе их можно было бы подставить в рабочий расчёт ([[DEBT-005]], 2026-09-10; до него — `hydro/analytical.py`, класс `AnalyticalHydroSolver`).

- `LogProfileHydroStub(grid, pvt, relperm)` — стационарный логарифмический профиль $p(r)$ в центрах ячеек между `bc.well.p_wf` (только `PressureControl`) и `bc.p_ext`; $S_g = 0$, $R_s$ = `bc.Rs_ext`, режим 2; от `dt` и входного `state.p` не зависит. Потоки — `fluxes.compute_fluxes`: потоки компонентов $G$ двойник считает сам по Дарси, $Q$, $u$, $m$, `Gm_o`, `Gm_g` — общим с адаптером шагом `phase_fluxes_from_components` ([[DEBT-028]]). `component_inventories` не переопределён — массу двойник не сохраняет (тесты баланса массы берут его подклассы с запасом). Нужен тестам `Simulator`, вывода, баланса массы и VAL-001, которым требуется точно известное $p(r)$ (`test_simulator.py`, `test_output.py`, `test_mass_balance.py`, `test_val001.py`; сам двойник — `test_hydro.py`).
- `FailingHydroStub(inner, fails)` — бросает `HydroConvergenceError` на подшагах, где `fails(state, dt)` истинно, и запоминает `dt` каждого вызова: проверка локального дробления ([[DEBT-015]]); физика и запас компонентов — у внутреннего двойника `inner`.

"""

CURRENT = """\
## Действующий решатель: прототип через адаптер

Шаг `PrototypeHydroAdapter.solve`: управление скважиной → прототип (бар, м³ст/сут); `SimulationState` (Па) → `BlackOilState` (бар); один вызов `advance` (или `advance_fourth_stage` по памяти ступени 4, [[DEBT-048]]); отказ — `HydroConvergenceError` с отчётом Ньютона и попытками ступеней ([[DEBT-054]], [[DEBT-069]]); принятое состояние проверяется на выход за таблицы ([[DEBT-027]]) и переводится обратно в `SimulationState`; в `HydroResult` потоки компонентов — от прототипа, остальное — `fluxes.phase_fluxes_from_components` ([[DEBT-028]]); `int_G_*` = $\\Delta t \\cdot G$.

Настройки модели — `factory._create_prototype_hydro`: `phase_switching_stage=True` (ступень 4 включена), `cell_tol` = `numerics.newton_cell_tol` (условие по ячейке включено), `skin`, `rs_switch_tol`, `sg_switch_tol`, `jacobian_mode`, `linear_solver`; лимиты `max_newton`, `max_active_iter` адаптер передаёт в каждый вызов `advance`.

| Что | Код (`blackoil.py`, если не указано иное) | Постановка, заметки |
|---|---|---|
| Неизвестные — $2N$: $z = (p, X)$, $X = S_g$ в ячейке с газом, $R_s$ без газа; замыкание подставлено: при газе $R_s = R_{s,\\text{нас}}(p)$, без газа $S_g = 0$ | `RadialBlackOilModel.pack`, `unpack` | `eq:residual_eq_r1`, `eq:residual_eq_r2` — исключены подстановкой |
| Невязки — балансы компонентов, м³ст/с; газовые строки делятся на `gas_residual_scale` | `physical_residual`, `residual`; запасы — `component_inventories` | `eq:residual_oil`, `eq:residual_gas` |
| Потоки через грани: ячейка выше по потоку — по перепаду давления; на контуре при притоке — состояние контура ($p_{ext}$, $R_{s,0}$, $S_g = 0$); забой — проводимость со скином, ветвь скважины «открыта» / «закрыта» при управлении давлением | `face_component_fluxes_sm3s`, `_well_fluxes` | `eq:flux_oil`, `eq:flux_gas`; знаки — [[P2-знаки-потоков-прототип]] |
| Якобиан — конечные разности с раскраской столбцов, сразу в CSC ([[DEBT-033]]); СЛАУ — `splu`. Это умолчания конфига (`numerics.jacobian_mode = "grouped"`, `numerics.linear_solver = "sparse"`); `"reference"` — поколонные разности, `"dense"` — плотное решение | `finite_difference_jacobian`, `_linear_solve` | аналитического якобиана из `ssec:pressure_disc` в коде нет |
| Ньютон при фиксированном наборе фаз: линейный поиск по невязке, сходимость проверяется на каждом приближении ([[BUG-021]]) | `_newton_fixed_active_set` | — |
| Сходимость: абсолютное условие — допуск не ниже предела округления запасов ([[BUG-025]]) плюс $10^{-8}\\,\\lVert F_0\\rVert_\\infty$; условие по ячейке, отнесённое к её поровому объёму ([[BUG-022]]); строка выше порога принимается на своём пределе округления ([[DEBT-067]]); в отчёте отказа — мера этого предела ([[DEBT-055]]) | `_absolute_tol`, `_cells_converged`, `_cell_floor` | `ssec:convergence`: `eq:newton_abs_tol`, `eq:newton_cell_tol`, `eq:newton_cell_tol_floor`; мера предела — `eq:newton_cell_floor` |
| Физичность пробной точки линейного поиска (ступени 1–3): $p > 1$ бар; $R_s$ ячеек без газа — от $-10^{-8}$ до 1.5 `pvt.max_rs`; $S_g \\le 0.98$; $S_g \\ge -0.05$ — только на ступени 1 | `_trial_is_reasonable` | — |
| Набор фаз — внешние проходы: газ включается при $R_s > R_{s,\\text{нас}}(p) +$ `rs_switch_tol`, выключается при $S_g < -$`sg_switch_tol`; $S_g$ включённой ячейки — по закрытому сосуду, не выше `sg_activation_cap` ([[BUG-018]]); лимит проходов ([[BUG-028]]) | `_advance_phases` | — |
| Ступени `advance`: 1 — исходный алгоритм; 2 — без нижней границы $S_g$, при управлении давлением ветвь скважины «открыта» / «закрыта» зафиксирована на всё решение ([[BUG-014]]; «открыта» не пробуется, где не может быть согласована, — [[DEBT-040]]); 3 — то же с линейным поиском по норме 2 и $\\lvert\\Delta S_g\\rvert \\le 0.2$ ([[BUG-016]]); 4 — переключение набора фаз после каждой итерации, ограничения шага по ячейкам, без линейного поиска, ячейка выше по потоку на гранях с дважды сменившимся направлением удерживается ([[BUG-020]], [[BUG-024]]) | `advance`, `_fallback`, `advance_fourth_stage`, `_newton_switching` | — |
| Единицы и управление скважиной | `PrototypeHydroAdapter.solve` | `eq:bc_rate_pwf`; [[P1-адаптер-единицы]] |
| Состояние прототипа ↔ `SimulationState`: `gas_active` ↔ `regime` (1 — газ есть) | `PrototypeHydroAdapter.solve`, `component_inventories` | [[P3-маппинг-состояния]] |
| $Q_\\alpha$, $u_\\alpha$, $m_\\alpha$, `Gm_o`, `Gm_g` из потоков компонентов | `fluxes.phase_fluxes_from_components` | `eq:phase_flux` |
| Дробление подшага и рост; старт с малого шага после смены управления ([[FEAT-032]]) | `Simulator._advance`; глубина первого подшага — `TimeSchedule.first_substep_depth` | [[P4-адаптивный-шаг]], [[модули-simulator-оркестратор]] |

Разборы, на которых держится устройство решателя:
- [[прототип переживает скачок p_wf вверх, падает равномерное дробление адаптера]], [[запасной путь с отрицательной насыщенностью и веткой скважины снимает порог шага на скачке p_wf вверх]] — ступень 2 (BUG-014);
- [[линейный поиск по норме ∞ стоит при массовой активации газа — поиск по норме 2 с ограничителем ΔSg снимает отказ]] — ступень 3 (BUG-016);
- [[начальное Sg закрытого сосуда выше 1 − S_or не даёт Ньютону дойти до решения — ограничение по таблице ОФП снимает отказ]] — `sg_activation_cap` (BUG-018);
- [[останов из развитой газовой зоны — забойная ячейка без потока и дребезг ячейки выше по потоку]], [[ступень 4 без ограничения шага по R_s застревала на R_s = 0 — суточный останов проходил или нет по округлениям]] — ступень 4 (BUG-020, BUG-024);
- [[абсолютный допуск Ньютона один на все ячейки недорешал забойную — условие по ячейке отнесено к её поровому объёму]] — условие по ячейке (BUG-022);
- [[на коротком шаге невязка Ньютона стоит на пределе округления запасов — допуск не ниже 4ε·M_max на Δt]] — абсолютный допуск (BUG-025);
- [[решение на пределе округления принимается построчно — дробление ради порога точности не добавляет]] — предел округления по строке (DEBT-067);
- [[при c_o = 0 первый проход набора фаз включает газ почти во всей области]] — лимит проходов (BUG-028);
- [[отказ Ньютона только по условию ячейки выглядел обычным — отчёт называет допуск, меру и причину выхода]], [[отказ всех ступеней advance скрывал ветку «открыта» ступеней 2–4 — отчёт перечисляет попытки]] — текст отказа (DEBT-054, DEBT-069);
- [[локальное дробление шага проходит останов при суточном dt_integration — равномерное падает на одном подшаге из 512]] — дробление в `Simulator` (DEBT-015).

## Проектная схема собственного решателя (отменена)

> **Не реализована и реализована не будет** (решение пользователя 2026-10-15, [[DEBT-077]]). Ниже — проект 2026-08-25, составленный до передачи прототипа; текст сохранён без изменений по существу (понижен только уровень заголовков), номера уравнений заменены метками в [[DEBT-074]]. Сохранён потому, что на него как на «проектную схему» ссылаются обзоры [[Ben Gharbia Jaffré 2014 — полугладкий Ньютон для появления и исчезновения газовой фазы]], [[Jaffré Sboui 2010 — закон Генри и исчезновение газовой фазы]], [[Bourgeat Jurak Smaï 2009 — двухфазная фильтрация с растворением газа в хранилище отходов]] (раздел «Переключение режимов») и [[ключевые работы по исчезновению газовой фазы]]. Та же схема — в постановке: `ssec:pressure_disc`, `sssec:switching_disc`, шаги 2 и 5 в `ssec:algorithm`; постановку не исправляем (решение пользователя 2026-10-15), поэтому метки `eq:daccum_oil_dp` … `eq:daccum_gas_dRs`, `eq:deq_r1`, `eq:deq_r2` ниже остаются верными.

Отличия от действующего решателя:

| Схема | Действующий решатель (раздел выше) |
|---|---|
| $3N$ неизвестных $(p, S_g, R_s)$, замыкающее уравнение — строка системы | $2N$: $(p, X)$, замыкание подставлено (`pack`, `unpack`) |
| Аналитический якобиан, блоки $3\\times3$, блочная прогонка за $O(N)$ | Конечные разности с раскраской, CSC, `splu` |
| Переключение режимов после каждой итерации; при 2 → 1 $S_g := 10^{-6}$ | Внешние проходы набора фаз (`_advance_phases`), $S_g$ включённой ячейки — по закрытому сосуду; после каждой итерации — только на ступени 4 (`_newton_switching`) |
| Контур: подвижность ячейки $N-1$ при любом направлении потока | При притоке — подвижность при условиях контура ($p_{ext}$, $R_{s,0}$, $S_g = 0$) |
| Без глобализации; нефизично или не сошлось — `dt *= cut_factor` внутри решателя, отказ при `dt < dt_min` | Линейный поиск (ступени 1–3), ограничения по ячейкам (ступень 4); отказ — `HydroConvergenceError`, подшаг дробит `Simulator._advance`; `dt_min` удалён ([[DEBT-008]]) |
| Сходимость — `tol_abs` или `tol_rel` к начальной невязке, по ячейке | `eq:newton_abs_tol` и `eq:newton_cell_tol` с построчным пределом округления `eq:newton_cell_tol_floor` |
| Скорости $u_\\alpha$ «нужны для уравнения энергии» | Энергия берёт $Q_\\alpha$, $G^o$, $p_{wf}$, а не $u_\\alpha$ ([[модули-energy-tridiag]]) |

"""

RELATED = """\
## Связанные заметки

- [[архитектура библиотеки numerical_solver]]
- [[hydro-prototype-анализ]] — устройство прототипа v1.0.3 (единицы, $2N$, конечно-разностный якобиан, набор фаз); ступени 2–4 и условия сходимости появились позже — см. «Действующий решатель»
- [[P1-адаптер-единицы]] — единицы и управление скважиной в адаптере
- [[P2-знаки-потоков-прототип]] — знаки потоков прототипа
- [[P3-маппинг-состояния]] — `BlackOilState` ↔ `SimulationState`
- [[P4-адаптивный-шаг]] — дробление подшага в `Simulator`
- [[модули-simulator-оркестратор]] — цикл шага, `_advance`, проверка состояния
- [[конвенции-знаков]] — положительное направление — от скважины
- [[модули-pvt-контракт]] — PVT-интерфейс (заменена [[P5-pvt-архитектура]])
- [[модули-grid-сетка]] — проводимости, объёмы
- [[модули-energy-tridiag]] — использование HydroResult: Q_o, Q_g, G_o, p_wf
"""

# Якоря старой заметки (строка целиком)
A_ABC = "## ABC"
A_LINKS = "Связи: `Q_o = G_o · Bo_up`, `Q_g = G_free_gas · Bg_up`, `G_g = Rs_up · G_o + G_free_gas`."
A_STUB = "## Аналитическая заглушка (AnalyticalHydroSolver → LogProfileHydroStub)"
A_DESIGN = "## Вектор неизвестных"
A_RELATED = "## Связанные заметки"

# ── Обратные ссылки и смежные заметки: (файл, «До», «После») ─────────────────
REPLACEMENTS = [
    (ARCH, "`NewtonHydroSolver` (гидродинамику решает прототип через `PrototypeHydroAdapter`)",
           "`NewtonHydroSolver` (и не будет: гидродинамику решает прототип через "
           "`PrototypeHydroAdapter`, собственный решатель отменён 2026-10-15 — [[DEBT-077]])"),
    (ARCH, "2. Реализовать собственный `NewtonHydroSolver` по problem_statement.tex.",
           "2. ~~Реализовать собственный `NewtonHydroSolver` по problem_statement.tex.~~ "
           "Отменено 2026-10-15 ([[DEBT-077]]): гидродинамику решает прототип."),
    (ARCH, "| СЛАУ | Eigen SparseLU | numpy/scipy (блочная прогонка вручную) |",
           "| СЛАУ | Eigen SparseLU | scipy: `solve_banded` (энергия), `splu` прототипа (гидродинамика) |"),
    (ARCH, "- [[модули-hydro-newton]] — детали блочного Ньютона",
           "- [[модули-hydro-newton]] — контракт HydroSolver, действующий решатель (прототип), "
           "отменённая схема блочного Ньютона"),
    (DICT, "- [[модули-hydro-newton]] — невязки, якобиан",
           "- [[модули-hydro-newton]] — контракт HydroSolver и HydroResult, действующий решатель (прототип)"),
    (PVT, "- [[модули-hydro-newton]] — использование PVT в якобиане",
          "- [[модули-hydro-newton]] — контракт HydroSolver; PVT в якобиане — только в отменённой "
          "проектной схеме"),
    (QUEST, "**Статус:** решено — начинаем с чистого numpy.",
            "**Статус:** снят 2026-10-15 ([[DEBT-077]]) — блочной прогонки нет и не будет: "
            "гидродинамику решает прототип (разреженный якобиан, `splu`, [[DEBT-033]]). "
            "Прежнее решение — начинать с чистого numpy."),
    # Добавлено аудитом 1: ещё одно обещание собственного Ньютона «на будущее»
    (ORDER, "**С Newton-реализацией (если понадобится):** +3-4 сессии.",
            "**С Newton-реализацией:** не понадобится — собственный решатель отменён 2026-10-15 "
            "([[DEBT-077]]); прежняя оценка — +3-4 сессии."),
    (BENG, "Если её когда-нибудь реализуют, замечания 2–3 и этот пункт относятся к ней напрямую.",
           "Реализована не будет: собственный решатель отменён (решение пользователя 2026-10-15, "
           "[[DEBT-077]]); замечания 2–3 и этот пункт относятся к ней как к проекту."),
    # Попутно (обнаружено при планировании): номера строк прототипа устарели —
    # закрытый сосуд при включении газа сейчас в _advance_phases, не на 278–280.
    (BOURG, "(`blackoil.py:278-279`)", "(`blackoil.py`, `_advance_phases`, ветвь `activate`)"),
    (BOURG, "(`:280`)", "(там же, ветвь `deactivate`)"),
]

# Утверждения о существующем блочном Ньютоне — после замен их быть не должно
STALE = ["детали блочного Ньютона", "— невязки, якобиан", "использование PVT в якобиане",
         "собственный блочный Ньютон, будущее", "блочная прогонка вручную",
         "Если её когда-нибудь реализуют", "Newton-реализацией (если понадобится)"]
# Только в новой заметке: метод удалён в FEAT-020; исторические заметки
# (модули-bc-граничные-условия, вопросы-реализации-2, решения-финальные) — вне задачи
NOTE_STALE = ["boundary_pressure"]

WIKI = re.compile(r"\[\[([^\]|#]+)(?:[#|][^\]]*)?\]\]")
TASK_ID = re.compile(r"^(BUG|DEBT|FEAT|VAL)-\d{3}$")


def load_guard():
    """FORBIDDEN, LABEL_REF, LABEL_DEF сторожа — из самого теста, без копий."""
    path = ROOT / "numerical_solver/tests/test_eq_references.py"
    spec = importlib.util.spec_from_file_location("test_eq_references", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def read(rel):
    """(текст, перевод строки) — перевод строки файла сохраняется при записи."""
    text = (ROOT / rel).read_bytes().decode("utf-8")
    return text, ("\r\n" if "\r\n" in text else "\n")


def index_once(lines, anchor):
    hits = [i for i, s in enumerate(lines) if s == anchor]
    assert len(hits) == 1, f"якорь {anchor!r}: {len(hits)} вхождений"
    return hits[0]


def demote(block):
    """## → ###, ### → #### вне блоков кода; остальное дословно."""
    out, fence = [], False
    for s in block:
        if s.startswith("```"):
            fence = not fence
        elif not fence and re.match(r"#{2,3} ", s):
            s = "#" + s
        out.append(s)
    return out


def promote(block):
    """Обратное к demote: ### → ##, #### → ### вне блоков кода."""
    out, fence = [], False
    for s in block:
        if s.startswith("```"):
            fence = not fence
        elif not fence and re.match(r"#{3,4} ", s):
            s = s[1:]
        out.append(s)
    return out


def build_note():
    text, nl = read(NOTE)
    lines = text.split(nl)
    i_abc, i_links = index_once(lines, A_ABC), index_once(lines, A_LINKS)
    i_stub = index_once(lines, A_STUB)
    i_design, i_rel = index_once(lines, A_DESIGN), index_once(lines, A_RELATED)
    assert i_abc < i_links < i_stub < i_design < i_rel
    original = lines[i_design:i_rel]
    # В исходном куске заголовков #### нет — понижение обратимо однозначно
    assert not any(re.match(r"#### ", s) for s in original)
    design = demote(original)
    assert promote(design) == original, "проектная схема перенесена не дословно"
    # Связи и конвенция знаков (от A_LINKS до раздела заглушки) — дословно;
    # раздел заглушки — заново по tests/_doubles.py (листинг устарел: boundary_pressure)
    new = (HEAD.split("\n") + ABC.split("\n")[:-1] + lines[i_links:i_stub]
           + STUB.split("\n")[:-1] + CURRENT.split("\n")[:-1] + design + RELATED.split("\n"))
    return text, nl.join(new), nl


def table_bad(text):
    """Строки таблиц markdown, у которых число ячеек не как у заголовка (неэкранированный «|» в ячейке)."""
    bad, cols = [], None
    for n, s in enumerate(text.splitlines(), 1):
        if s.startswith("|"):
            k = len(re.findall(r"(?<!\\)\|", s))
            if cols is None:
                cols = k
            elif k != cols:
                bad.append(f"строка {n}: {k - 1} ячеек вместо {cols - 1}")
        else:
            cols = None
    return bad


def guard_bad(guard, labels, rel, text):
    bad = [f"{rel}:{n}: {what}: {s.strip()}"
           for n, s in enumerate(text.splitlines(), 1)
           for what, rx in guard.FORBIDDEN.items() if rx.search(s)]
    bad += [f"{rel}:{n}: нет метки {m.group()}"
            for n, s in enumerate(text.splitlines(), 1)
            for m in guard.LABEL_REF.finditer(s) if m.group() not in labels]
    return bad


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    mode = sys.argv[1] if len(sys.argv) > 1 else "--check"
    guard = load_guard()
    labels = set(guard.LABEL_DEF.findall((ROOT / "numerical_solver/doc/problem_statement.tex")
                                         .read_text(encoding="utf-8")))
    old, new, nl = build_note()

    if mode == "--show":
        print(new.replace("\r\n", "\n"))
        return

    # ── Заметка ──
    print(f"Заметка: {len(old.splitlines())} → {len(new.splitlines())} строк, перевод строки "
          f"{'CRLF' if nl == chr(13) + chr(10) else 'LF'}")
    print(f"  сторож по старому тексту: {len(guard_bad(guard, labels, NOTE, old))} нарушений")
    bad = guard_bad(guard, labels, NOTE, new)
    print(f"  сторож по новому тексту: {len(bad)} нарушений")
    for b in bad:
        print("   ", b)
    tb = table_bad(new)
    print(f"  строк таблиц с неверным числом ячеек: {len(tb)}")
    for b in tb:
        print("   ", b)
    stems = {p.stem for p in (ROOT / "vault").rglob("*.md")}
    links = sorted(set(WIKI.findall(new)))
    dangling = [x for x in links if x not in stems and not TASK_ID.match(x)]
    print(f"  вики-ссылок: {len(links)}, ведут в никуда: {len(dangling)}")
    for x in dangling:
        print("   ", x)

    # ── Обратные ссылки ──
    texts = {}
    for f, before, after in REPLACEMENTS:
        if f not in texts:
            texts[f] = read(f)[0]
        n = texts[f].count(before)
        assert n == 1, f"{f}: «До» {before!r} — {n} вхождений"
        texts[f] = texts[f].replace(before, after)
        assert texts[f].count(before) == 0
    print(f"Замен обратных ссылок: {len(REPLACEMENTS)} в {len(texts)} файлах, каждая «До» — ровно один раз")
    bad = [b for f, t in texts.items() if not f.startswith(L) for b in guard_bad(guard, labels, f, t)]
    print(f"  сторож по заметкам вне literature/ после замен: {len(bad)} нарушений")
    for b in bad:
        print("   ", b)

    # ── Остаток утверждений о существующем блочном Ньютоне ──
    after = dict(texts)
    after[NOTE] = new
    left = []
    for p in sorted((ROOT / "vault/knowledge").rglob("*.md")):
        rel = p.relative_to(ROOT).as_posix()
        t = after.get(rel) or p.read_text(encoding="utf-8")
        left += [f"{rel}: {s}" for s in STALE if s in t]
    left += [f"{NOTE}: {s}" for s in NOTE_STALE if s in new]
    base = (ROOT / "numerical_solver/gpn_multiphase_solver/hydro/base.py").read_text(encoding="utf-8")
    print(f"Утверждений о существующем блочном Ньютоне в vault/knowledge после замен: {len(left)}")
    for x in left:
        print("   ", x)
    print(f"hydro/base.py: «NewtonHydroSolver» {'есть — шаг 2 плана' if 'NewtonHydroSolver' in base else 'нет'}")

    if mode == "--write":
        (ROOT / NOTE).write_bytes(new.encode("utf-8"))
        for f, t in texts.items():
            (ROOT / f).write_bytes(t.encode("utf-8"))
        print(f"Записано: {NOTE} и {len(texts)} файлов")


if __name__ == "__main__":
    main()
