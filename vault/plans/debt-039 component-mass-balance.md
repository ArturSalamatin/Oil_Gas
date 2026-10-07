---
tags:
  - план
  - инфраструктура
date: 2026-10-06
issue: DEBT-039
github: 65
branch: refactor/debt-039/component-mass-balance
status: готов к реализации
audit:
  date: 2026-10-06
  round: 1
  found: 7
  auto-fixed: 7
  manual-required: 0
---

# DEBT-039: накопленный баланс массы компонентов — план

## Кратко

Баланс энергии копится на подшагах решателя и проверяется у всех примеров ([[DEBT-013]]). Баланса массы нефтяного и газового компонентов нет нигде. План добавляет его по образцу баланса энергии:

- интегралы потоков компонентов через забой и контур копятся по **всем принятым шагам** в `Simulator`;
- запас компонентов $M_o$, $M_g$ на каждой записи истории отдаёт **решатель** (у прототипа — те же $\phi(p)$, $B_o$, $B_g$, что в невязке Ньютона);
- адаптер интегрирует потоки по **своим внутренним подшагам** A-retry, а не умножает поток последнего подшага на весь шаг;
- конвейер примеров печатает невязку и рисует `mass_balance.png`; тест — по всем примерам, порог $10^{-6}$.

Решение (поля, температура, дебиты, баланс энергии) **не меняется ни в одном бите**.

- Подтип: инфраструктура (новая проверка; численный метод не меняется, прототип не трогается).
- Шагов: 8 (подготовка; контракты; адаптер; накопитель и `Simulator`; конвейер примеров; документация; верификация; vault).
- **Код и тесты плана проверены при планировании** подклассами в памяти — проба `vault/issues/debt-039/probes/planned_code_check.py`, база `5ce2168`:
  - истории всех 21 примера побитово равны исходным (состояния, потоки, данные скважины, баланс энергии);
  - максимум относительной невязки массы по всем записям всех примеров — $2.9\cdot10^{-8}$ (пример 15), порог $10^{-6}$;
  - время расчёта всех примеров 138.1 → 140.4 с (+1.7 %, на уровне разброса);
  - тесты плана для адаптера, двойников и укороченных конфигов дают ожидаемые числа (раздел «Тестовая стратегия»).

## Как начать работу по этому плану

1. Прочитай этот файл целиком.
2. Прочитай связанные заметки: [[контейнер-simulation-history]], [[модули-simulator-оркестратор]], [[P4-адаптивный-шаг]], [[словарь-код-физика]] §3, [[проверка выносится в общий модуль если не зависит от комбинации PVT и ОФП]] (конвенция общих модулей примеров), шапку `numerical_solver/gpn_multiphase_solver/energy/balance.py`.
3. Ветка от базовой (CLAUDE.md, «Базовые ветки»):
   ```powershell
   git checkout numerical_scheme/implementation
   git checkout -b refactor/debt-039/component-mass-balance
   ```
4. Venv: команды ниже — из `numerical_solver/`, `.venv\Scripts\python` напрямую.
5. Baseline (шаг 1): число тестов, быстрый уровень, снимок историй всех примеров.
6. Запомни число тестов (всего и в быстром уровне) и время быстрого уровня.
7. Шаги 2–5 — код, после каждого тест шага и быстрый регресс. Полный прогон — шаг 7.

Прототип (`HydroSolverPrototype/`) план **не меняет**: тесты и регрессия прототипа не нужны.

## Контекст для читателя без контекста

### Баланс массы и что он проверяет

Уравнения сохранения нефтяного и газового компонентов дискретизуются в дивергентной форме. Невязки ячейки (`numerical_solver/doc/problem_statement.tex`, `eq:residual_oil`, `eq:residual_gas`) — изменение запаса за шаг плюс разность потоков через две грани:

$$F^o_j = V_j\phi\,\frac{(S_o/B_o)^{n+1}_j - (S_o/B_o)^{n}_j}{\Delta t} + G^o_{j+1/2} - G^o_{j-1/2}.$$

Сумма по ячейкам и шагам сворачивается к двум крайним граням (внутренние сокращаются):

$$\text{невязка}_\alpha(t) = \Delta M_\alpha(t) + \int_0^t G^\alpha_N\,dt - \int_0^t G^\alpha_0\,dt,$$

$$M_o = \sum_j \phi V_j \frac{S_{o,j}}{B_{o,j}},\qquad M_g = \sum_j \phi V_j \Big(\frac{S_{o,j} R_{s,j}}{B_{o,j}} + \frac{S_{g,j}}{B_{g,j}}\Big),\quad \text{м³ст}.$$

Знак $G$ — от скважины (CLAUDE.md, «Конвенция знаков»): при добыче $\int G_0\,dt < 0$, при притоке с контура $\int G_N\,dt < 0$.

**Что проверяет накопленная невязка.** Не физику: прототип решает именно эти невязки, сохранение массы заложено в метод. Проверяется всё, что стоит между невязкой Ньютона и историей:

- допуск Ньютона, накопленный по шагам (`blackoil.py:292`, `_newton_fixed_active_set`: `rtol = 1e-8` к начальной невязке шага, `atol_sm3s = 1e-11` м³ст/с на ячейку; строки газа невязки делятся на `gas_residual_scale` = $\max(R_{s,ext}, 1)$ — для газа абсолютный допуск во столько же раз больше). Это умолчания аргументов прототипа: поля конфига `numerics.newton_rtol`, `newton_atol`, `newton_max_iter` мёртвые — фабрика их не передаёт ([[DEBT-008]]); в документах плана не писать, что допуск задаётся конфигом;
- правки состояния после сходимости (`blackoil.py:383`: $S_g \in [-10^{-9}, 0) \to 0$);
- знаки и сопоставление потоков в адаптере (`oil_well` → `G_o[0]` с инверсией, `oil_outer` → `G_o[N]` без);
- учёт дробления шага в `Simulator` (пробный шаг, вложенное дробление).

Поэтому уровень невязки — допуск Ньютона, а не округления, как у баланса энергии ($10^{-10}$).

### Образец: баланс энергии (DEBT-013)

`EnergyBalanceAccumulator` (`gpn_multiphase_solver/energy/balance.py:134`) создаётся в `Simulator.run` (`simulator.py:129`), получает вклады каждого принятого подшага из `TridiagEnergySolver.solve(..., collect=balance)`, снимок кладётся в `SimulationHistory.balance` на каждой записи (`simulator.py:175-177`). Сборка массивов, график и печать — `examples/energy_balance.py`, вызов — `examples/example_runner.py:217-218`. Тест по всем примерам — `tests/test_examples.py:636-666`.

По записям истории баланс не восстановить: запись делается раз в интервал истории, а внутри интервала — до сотен подшагов, потоки за это время меняются (DEBT-013: 04a — невязка $2\cdot10^{-1}$ против $10^{-3}$). Для массы — тот же довод.

### Ловушка: поток последнего подшага

`PrototypeHydroAdapter.solve` (`hydro/prototype_adapter.py:57-156`) при отказе Ньютона дробит шаг: 2, 4, …, $2^{9}$ подшагов (A-retry, `:83-138`). `HydroResult` собирается по **последнему** внутреннему подшагу (`_build_result`, `:137`). `Simulator._advance` (`simulator.py:185-252`) отбрасывает такой пробный результат и проходит интервал заново теми же подшагами (BUG-010), но в повторном проходе дробление запрещено (`allow_subdivision=False`): если подшаг снова раздробится, результат принимается как есть (`:228-234`), и `G_o`, `G_g` в нём — потоки последнего из внутренних подшагов.

Интеграл $\Delta t\cdot G$ по такому результату неверен. Замер при планировании (принудительный A-retry на первом шаге, проба `planned_code_check.py retry` и `fixture`): невязка баланса шага с $\Delta t\cdot G$ последнего подшага — $8.7\cdot10^{-2}$, с интегралом по подшагам — $6.5\cdot10^{-12}$. Поэтому интегрирует **адаптер**: только он видит все внутренние подшаги.

На примерах вложенного дробления сейчас нет ни одного (проба `mass_balance_baseline.py`: 0 случаев на 21 примере), но BUG-020 (останов из развитой газовой зоной) упирается именно в дробление.

### Почему запас берёт решатель

Прототип считает пористость $\phi(p) = \phi_{ref}\exp(c_r(p - p_{ref}))$ (`radial_blackoil/rock.py:5-8`), объёмы ячеек — своей сеткой, $B_o$, $B_g$ — своей PVT. Запас, пересчитанный формулами GPN (постоянная $\phi$, объёмы `LogRadialGrid`), совпадает с прототипом только пока $c_r = 0$ и PVT общая. Это механизм BUG-004 («коэффициенты приходят от решателя, а не пересчитываются»). Поэтому запас отдаёт решатель: метод `HydroSolver.component_inventories(state)`, у адаптера — `RadialBlackOilModel.component_inventories` (`blackoil.py:152-157`).

### Замер при планировании

Проба `vault/issues/debt-039/probes/mass_balance_baseline.py` (обёртка `EnergySolver.solve`, как проба FEAT-019; запас — функцией прототипа), вывод — `mass_balance_baseline.out.txt`. Относительная невязка, нормировка на $|\Delta M| + |\int G_0| + |\int G_N|$, максимум по записям:

| пример | нефть | газ | | пример | нефть | газ |
|---|---|---|---|---|---|---|
| 01 | $2.4\cdot10^{-9}$ | 0 | | 11 | $1.2\cdot10^{-11}$ | $1.1\cdot10^{-10}$ |
| 02 | $2.4\cdot10^{-9}$ | 0 | | 12 | $4.2\cdot10^{-11}$ | $3.7\cdot10^{-10}$ |
| 03 | $1.7\cdot10^{-11}$ | $6.9\cdot10^{-12}$ | | 13a | $5.4\cdot10^{-11}$ | $1.2\cdot10^{-9}$ |
| 04 | $1.9\cdot10^{-9}$ | $2.5\cdot10^{-9}$ | | 13b | $5.8\cdot10^{-11}$ | $1.2\cdot10^{-9}$ |
| 04a | $4.0\cdot10^{-13}$ | $9.8\cdot10^{-12}$ | | 14 | $9.2\cdot10^{-13}$ | $8.7\cdot10^{-13}$ |
| 05 | $4.7\cdot10^{-12}$ | $1.2\cdot10^{-12}$ | | 15 | $2.9\cdot10^{-8}$ | $2.9\cdot10^{-8}$ |
| 06 | $2.7\cdot10^{-9}$ | $4.6\cdot10^{-9}$ | | 16 | $5.6\cdot10^{-9}$ | $3.5\cdot10^{-9}$ |
| 07–09 | $1.9\cdot10^{-9}$ | $2.5\cdot10^{-9}$ | | 19 | $1.0\cdot10^{-11}$ | $4.4\cdot10^{-11}$ |
| 10 | $2.6\cdot10^{-9}$ | $4.9\cdot10^{-9}$ | | 20 | $1.9\cdot10^{-11}$ | $1.2\cdot10^{-10}$ |
| | | | | 21 | $1.4\cdot10^{-12}$ | $5.3\cdot10^{-12}$ |

Пример 16, нормировка на накопленную добычу: $1.24\cdot10^{-8}$ (нефть), $7.07\cdot10^{-9}$ (газ) — совпадает с пробой FEAT-019 ($1.2\cdot10^{-8}$, $7.1\cdot10^{-9}$, своя PVT и постоянная $\phi$; при $c_r = 0$ запасы равны).

**Рост невязки на останове 16** (проба `shutin_freeze.py`, вывод `shutin_freeze.out.txt`). С 21-х суток Ньютон принимает шаг без итераций: невязка старого состояния уже ниже `atol_sm3s` = $10^{-11}$ м³ст/с на ячейку. Состояние застывает ($\max|\Delta p| = 0$ ровно), а поток через контур на этом состоянии не нулевой — $5.3\cdot10^{-6}$ м³ст/сут нефти — и копится. Невязка растёт ровно на него: с $2\cdot10^{-12}$ до $5.6\cdot10^{-9}$ за 10 сут. Это свойство абсолютного допуска прототипа, а не дефект учёта. До порога $10^{-6}$ при $\sum|\text{членов}| \approx 9\cdot10^{3}$ м³ст так надо стоять ~1700 сут.

### Код плана проверен при планировании

Проба `vault/issues/debt-039/probes/planned_code_check.py` (база `5ce2168`): код шагов 3–5 — подклассы `PrototypeHydroAdapter` и `Simulator` и накопитель; новые поля ставятся через `setattr`. Режимы и результаты (выводы — `planned_code_check_<режим>.out.txt`):

| режим | что | результат |
|---|---|---|
| `all` | 21 пример: история кода плана против исходной | побитово у всех 21; max невязки $2.9\cdot10^{-8}$; 138.1 → 140.4 с |
| `retry` | пример 04 ($N = 25$), принудительный A-retry | интегралы = сумма по подшагам; невязка шага $1.1\cdot10^{-10}$ / $3.4\cdot10^{-10}$ (нефть/газ), с $\Delta t\cdot G$ последнего — $8.6\cdot10^{-2}$ / $9.6\cdot10^{-2}$ |
| `fixture` | настройка фикстур `test_prototype_adapter.py` | без дробления $\int = \Delta t\cdot G$ побитово, невязка шага $1.5\cdot10^{-12}$; с дроблением интегралы побитово = два `solve(DT/2)` (и свежего, и того же адаптера), невязка $6.5\cdot10^{-12}$ против $8.7\cdot10^{-2}$ |
| `stub` | двойники | пробный шаг не в интегралах (`cum_o_well` = $3600\cdot G$ побитово, не $5400\cdot G$); вложенное дробление (аудит) — тоже $3600\cdot G$ побитово; двойник без запаса — `[None, None]`; запас без интегралов — `RuntimeError` |
| `short` | 03, 04 (6 ч, $N = 25$), 16 (2 + 2 ч) | невязка ≤ $4.5\cdot10^{-10}$; снимок 1 интервал = 6 интервалов побитово; на останове $\int G_0$ постоянен побитово, приток с контура = $\Delta M_o$ |
| `plot` | `mass_balance.png` 16 и 01 | `probes/plot_16/`, `probes/plot_01/` — просмотрены |

## Решения пользователя (2026-10-06)

| # | Вопрос | Решение |
|---|---|---|
| 1 | Откуда запас | **Метод решателя** `HydroSolver.component_inventories(state)` (не абстрактный, по умолчанию `None`); интегралы потоков — 4 поля `HydroResult` |
| 2 | Нормировка и порог | **Сумма модулей членов** $|\Delta M| + |\int G_0| + |\int G_N|$ (как у баланса энергии), порог **$10^{-6}$**, максимум по записям |
| 3 | Вывод | **Печать + `mass_balance.png`** |
| 4 | Формула в `problem_statement.tex` | **Нет**: docstring-и ссылаются на `eq:residual_oil`, `eq:residual_gas` |

## Текущее состояние (baseline)

- База `5ce2168`: 1267 тестов, быстрый уровень 1032 (`-m "not slow"`), ~70 с (сверено аудитом 2026-10-06).
- ⚠️ **Параллельно: DEBT-030** реализован в `.worktrees/debt-030`, слияние `7f83ef8` в `numerical_scheme/implementation` ещё не перенесено на ветку (на 2026-10-06 ветка на `5ce2168`). После влития: +3 теста (1270), правка `blackoil.py` (`advance`, отчёт отказа) сдвигает его строки на +2 до `:316` и до +18 ниже. Номера строк `blackoil.py` в этом плане — на `5ce2168`; план `blackoil.py` не правит, ищи по именам (`_newton_fixed_active_set`, `_advance_phases`, `component_inventories`, `step_global_balance`). Решение DEBT-030 (отчёт отказа) на баланс массы не влияет: принятый путь прежний.
- `HydroResult` (`gpn_multiphase_solver/state.py:30-74`): потоки последнего подшага, `n_substeps`; интегралов нет.
- `SimulationHistory` (`state.py:132-167`): `times, states, hydro_results, well_data, balance`.
- `HydroSolver` (`hydro/base.py:13-42`): один абстрактный метод `solve`.
- `Simulator.run` / `_advance` (`simulator.py:115-252`): накопитель энергии, отбрасывание пробного шага.
- `examples/example_runner.py:210-218`: баланс энергии; баланса массы нет.

## Целевое состояние

| Файл | Изменение |
|---|---|
| `gpn_multiphase_solver/mass_balance.py` | **новый**: `MASS_KEYS`, `MassBalanceAccumulator` (`add_step`, `snapshot`) |
| `gpn_multiphase_solver/state.py` | `HydroResult.int_G_o_well`, `int_G_o_ext`, `int_G_g_well`, `int_G_g_ext` (по умолчанию `None`); `SimulationHistory.mass_balance`, параметр `append(..., mass_balance=None)` |
| `gpn_multiphase_solver/hydro/base.py` | `HydroSolver.component_inventories(state)` — не абстрактный, `None` |
| `gpn_multiphase_solver/hydro/prototype_adapter.py` | `component_inventories` от прототипа; интегралы по подшагам A-retry |
| `gpn_multiphase_solver/simulator.py` | накопитель, `add_step` на принятом шаге, снимок на записи |
| `tests/_doubles.py` | `SubdividingHydroStub.component_inventories` — делегирование |
| `examples/mass_balance.py` | **новый**: `compute_mass_balance`, `plot_mass_balance`, автономный запуск |
| `examples/example_runner.py` | вызов `plot_mass_balance` |
| тесты | `tests/test_mass_balance.py` (**новый**), классы/строки в `test_prototype_adapter.py`, `test_energy_balance_examples.py`, `test_examples.py` |
| документы | `examples/README.md`, README 01, 02, 03, 04, 04a, 16, 19, 20, 21 |

Граф импортов: `simulator` → `mass_balance` → `state` (только аннотация). `state` не импортирует `mass_balance` — циклов нет. Внешний API не ломается: новые поля и параметры — с умолчаниями.

## Варианты и выбор

Подробно — в issue #65. Кратко:

1. **Накопитель в `Simulator` по `HydroResult`, запас — формулами GPN.** Отвергнут: пересчёт запаса вне решателя (BUG-004); при вложенном дроблении — ложная невязка $\sim 10^{-1}$ на шаге.
2. **Решатель отдаёт запас и интегралы, накопитель в `Simulator`.** Выбран (решение 1). Согласован со схемой по построению; вложенное дробление учтено точно.
3. **Обёртка в конвейере примеров** (как проба FEAT-019). Отвергнут: подмена метода в обход архитектуры, пользователю библиотеки недоступна, та же ошибка при дроблении.

Внутри варианта 2 — запас методом решателя, а не приращением $\Delta M$ в `HydroResult` (решение 1): абсолютный запас печатается и рисуется, начальный запас берётся тем же методом, телескопирование приращений через перевод Па↔бар не нужно.

## Подводные камни (чеклист)

- ✅ **Все места вызова найдены.** `Simulator._advance` вызывают только `simulator.py:156` и `:224` (grep `_advance(` по `numerical_solver/`). `HydroResult(` строят `fluxes.py:103`, `simulator.py:259` и тесты (`test_energy.py:60`, `test_fluxes.py:802, 833`, `test_output.py:259, 359`, `test_val002.py:68`) — новые поля с умолчанием `None`, правки не нужны. `SimulationHistory.append` — `simulator.py` и тесты (`test_fluxes.py:791-833`, `test_output.py:254, 354`) — новый параметр с умолчанием. Классы с `solve(self, state, dt, bc)` — адаптер и два двойника `tests/_doubles.py` (grep).
- ✅ **Обратная совместимость.** `HydroSolver` получает не абстрактный метод — двойники и `test_hydro.py` (ABC нельзя инстанцировать) не затронуты.
- ⚠️ **`SubdividingHydroStub` без делегирования.** Метод ABC вернул бы `None`, и `Simulator` не вёл бы баланс на обёрнутом двойнике — тест «пробный шаг не в интегралах» прошёл бы впустую (снимки `None`). Адресовано: делегирование в шаге 4 и `assert ... is not None` в тесте.
- ✅ **`dataclasses.replace` сохраняет поля.** `SubdividingHydroStub.solve` (`_doubles.py:101`) и адаптер (шаг 3) строят результат через `replace` — копируются все поля dataclass, включая `int_G_*`.
- ✅ **Состояние при ошибке.** `MassBalanceAccumulator.add_step` проверяет все 4 поля **до** накопления — после `RuntimeError` накопитель не тронут (тест).
- ✅ **Круговые импорты.** `mass_balance.py` импортирует `HydroResult` только для аннотации (`TYPE_CHECKING`).
- ✅ **Docstring-и.** Ссылки на `eq:residual_oil`, `eq:residual_gas` (существуют: `problem_statement.tex:1053, 1067`). Формулу в постановку не добавляем (решение 4).
- ✅ **Конфиги.** Не меняются.
- ⚠️ **Связь с BUG-020** (план готов, `vault/plans/bug-020 shutin-phase-switching-newton.md`): правит текст ошибки адаптера `prototype_adapter.py:140-156`. Наши правки — `:82-138` и новый метод. При слиянии второй ветки возможен текстовый конфликт рядом — разрешается вручную, смысловой связи нет. После BUG-020 баланс массы проверит и новую ступень прототипа.
- ✅ **DEBT-037** (защита от копий общих модулей): `mass_balance.py` сразу входит в `SHARED_CHECK_MODULES`.
- ✅ **Производительность.** Лишнее: одно вычисление потоков на подшаг адаптера (`face_component_fluxes_sm3s`) и запас на записи. Замер: 138.1 → 140.4 с на всех примерах (+1.7 %, разброс того же порядка).
- ⚠️ **Нормировка у сценария без течения** (аудит). Нормировка на $\sum|\text{членов}|$ ломается, когда все члены сами на уровне допуска Ньютона: расчёт из равновесия при $q = 0$ дал бы отношение $\sim 1$ — ложный провал. Ни один пример так не устроен (у 01, 02 газ нулевой ровно — защита `scale > 0`). Появится такой пример — нормировать на $\max(\sum|\text{членов}|,\ N\cdot\text{atol}\cdot t)$; сейчас не делаем (решение пользователя 2 — нормировка как у энергии).
- ⚠️ **Конвенция общих модулей** (аудит; [[проверка выносится в общий модуль если не зависит от комбинации PVT и ОФП]]): `config` — первый аргумент. Поэтому `plot_mass_balance(config, history, output_dir)`, а не по образцу `plot_energy_balance(history, grid, config, output_dir)` — у того порядок исторический.
- ⚠️ **Консоль cp1251.** `print` с `Δ`, `³`, `−`, `─` падает `UnicodeEncodeError` при выводе в файл (`examples/energy_balance.py:165-166`). Печать плана — только ASCII-знаки и кириллица: `dM`, `м3ст`, `-`. В подписях рисунка — можно.
- ✅ **EMF.** `plot_mass_balance` сохраняет через `save_figure` до `export_emf(output_dir)` (`example_runner.py:223`) — SVG и EMF появятся сами.
- ✅ **Прототип.** Не меняется: регрессия прототипа не нужна.

## Шаги

### Шаг 1: Подготовка — ветка и baseline

**Цель:** ветка от базовой и три числа baseline плюс снимок историй.

**Файлы:** —

**Что сделать** (из `numerical_solver/`):
```powershell
git checkout numerical_scheme/implementation
git checkout -b refactor/debt-039/component-mass-balance
.venv\Scripts\python -m pytest tests/ --collect-only -q          # 1267 на 5ce2168
.venv\Scripts\python -m pytest tests/ -m "not slow" -q           # 1032 passed, ~70 с
.venv\Scripts\python ..\vault\issues\debt-039\probes\history_snapshot.py save base   # ~4 мин
```
Если база сдвинулась (влиты другие ветки) — записать фактические числа. Снимок `history_base/` — эталон для шага 7: план не меняет решение.

**Проверка:** числа записаны; `vault/issues/debt-039/probes/history_base/` — 21 файл `.npz`.

**Оценка:** ~10 мин.

### Шаг 2: Контракты — поля `HydroResult`, `SimulationHistory`, метод `HydroSolver`

**Цель:** места для интегралов, снимка и запаса; поведение не меняется.

**Файлы:** `numerical_solver/gpn_multiphase_solver/state.py`, `numerical_solver/gpn_multiphase_solver/hydro/base.py`, `numerical_solver/tests/test_mass_balance.py` (новый).

**Контекст:** все новые элементы — с умолчанием `None`, поэтому существующий код и тесты, строящие `HydroResult` и `SimulationHistory`, не меняются.

**Что сделать:**

1. `state.py`, `HydroResult` — после `n_substeps: int = 1` (`:74`):
   ```python
       n_substeps: int = 1

       # Интегралы потоков компонентов через забой и контур за шаг, м³ст
       # (DEBT-039): ∫G[0] dt и ∫G[N] dt по ВСЕМ внутренним подшагам решателя.
       # Знак — как у G (> 0 от скважины): при добыче int_G_*_well < 0, при
       # притоке с контура int_G_*_ext < 0. Нужны балансу массы: G_o, G_g выше —
       # потоки ПОСЛЕДНЕГО внутреннего подшага, и при дроблении шага (A-retry)
       # dt·G от интеграла отличается (замер при планировании: невязка баланса
       # шага 9·10⁻² вместо ≤ 10⁻¹⁰). None — решатель массу не сохраняет
       # (тестовые двойники); тогда и его component_inventories возвращает None.
       int_G_o_well: float | None = None
       int_G_o_ext: float | None = None
       int_G_g_well: float | None = None
       int_G_g_ext: float | None = None
   ```

2. `state.py`, `SimulationHistory` — в docstring после абзаца о `balance` (`:141-144`):
   ```
       mass_balance — баланс массы компонентов на момент каждой записи
       (снимок MassBalanceAccumulator, DEBT-039): запас нефтяного и газового
       компонентов M_o, M_g и интегралы потоков через забой и контур от t = 0,
       м³ст. Интегралы, как и члены баланса энергии, копятся по ВСЕМ принятым
       шагам. None — решатель массу не сохраняет (тестовые двойники).
   ```
   Поле после `balance` (`:150`):
   ```python
       balance: list[dict] = field(default_factory=list)
       mass_balance: list[dict | None] = field(default_factory=list)
   ```
   `append` (`:152-162`), до → после:
   ```python
       def append(self, t: float, state: SimulationState,
                  hydro: HydroResult, well: WellData,
                  balance: dict | None = None) -> None:
   ```
   ```python
       def append(self, t: float, state: SimulationState,
                  hydro: HydroResult, well: WellData,
                  balance: dict | None = None,
                  mass_balance: dict | None = None) -> None:
   ```
   и в конец тела:
   ```python
           # None — баланс массы не считается: решатель-двойник массу не
           # сохраняет (DEBT-039). Нулевого снимка, как у баланса энергии, нет:
           # запас компонентов в начальном состоянии не нулевой, его даёт решатель.
           self.mass_balance.append(mass_balance)
   ```

3. `hydro/base.py` — после `solve` (`:42`):
   ```python
       def component_inventories(self, state: SimulationState) -> tuple[float, float] | None:
           """Запас нефтяного и газового компонентов, м³ст. Ур. (eq:residual_oil), (eq:residual_gas)."""
           # None — решатель массу не сохраняет. Не абстрактный (DEBT-039):
           # тестовые двойники (tests/_doubles.py) уравнения фильтрации не
           # решают и массу не сохраняют — баланс
           # массы для них не считается. Решатель, сохраняющий массу, обязан
           # переопределить метод И заполнять HydroResult.int_G_*: иначе
           # Simulator бросит RuntimeError на первом шаге (mass_balance.py).
           return None
   ```
   В docstring класса — строка «Запас компонентов для баланса массы — `component_inventories` (DEBT-039).»

4. `tests/test_mass_balance.py` — создать с шапкой и тестами контрактов (полный текст файла — «Тестовая стратегия», блок `test_mass_balance.py`). На этом шаге — шапка, `TOL`, `_stub_result`, `_max_rel` и класс `TestContracts`; импорты — все, **кроме** `from gpn_multiphase_solver.mass_balance import ...` (модуль появится на шаге 4) и `from mass_balance import compute_mass_balance` (шаг 5): с ними файл не импортируется.

**Проверка после шага:**
- `.venv\Scripts\python -m pytest tests/test_mass_balance.py -q` — 3 passed.
- Регресс: быстрый.

**Подводные камни:** умолчания `None` — чеклист «Все места вызова».

**Зависимости:** требует шаг 1; блокирует 3, 4.

**Оценка:** ~35 строк кода, ~30 строк тестов, ~25 мин.

### Шаг 3: Адаптер — запас от прототипа и интегралы по подшагам A-retry

**Цель:** `PrototypeHydroAdapter` отдаёт запас и интегралы, согласованные со схемой прототипа.

**Файлы:** `numerical_solver/gpn_multiphase_solver/hydro/prototype_adapter.py`, `numerical_solver/tests/test_prototype_adapter.py`.

**Контекст:** раздел «Ловушка: поток последнего подшага». Потоки подшага считаются на **новом** состоянии — как в невязке Ньютона (неявная схема) и в `_build_result`. `face_component_fluxes_sm3s` не меняет состояние модели, влияющее на решение: пишет только `_last_effective_bhp_bar`, `_last_constraint_active` (читает их лишь `well_rates` для вывода, `blackoil.py:395-399`); `_build_result` вызывает его снова на том же `new_proto` — значения те же. Ветка скважины после `advance` снята (`_well_branch = None`, `blackoil.py:371`), выбор ветки по правилу — тот же, что принят в запасном пути (`blackoil.py:362-364`).

**Что сделать:**

1. Импорт: `from dataclasses import replace` (к импортам, `:28`).
2. В docstring модуля — абзац:
   ```
   Баланс массы (DEBT-039): component_inventories — запас компонентов
   функцией прототипа; HydroResult.int_G_* — интегралы потоков через забой
   и контур по всем подшагам A-retry (G в HydroResult — последнего).
   ```
3. Метод после `__init__`:
   ```python
       def component_inventories(self, state: SimulationState) -> tuple[float, float]:
           """Запас компонентов функцией прототипа, м³ст. Ур. (eq:residual_oil), (eq:residual_gas)."""
           from radial_blackoil.state import BlackOilState

           # Запас берётся у прототипа, а не пересчитывается здесь: те же
           # φ(p) (rock.py, экспонента по c_r), B_o, B_g и объёмы его сетки,
           # что в невязке Ньютона. Пересчёт своими формулами — механизм
           # BUG-004: при c_r ≠ 0 разошлась бы пористость.
           proto_state = BlackOilState(
               pressure_bar=state.p / BAR_TO_PA,
               rs_sm3_sm3=state.Rs.copy(),
               sg=state.Sg.copy(),
               gas_active=(state.regime == 1),
           )
           oil, gas = self._model.component_inventories(proto_state)
           return float(np.sum(oil)), float(np.sum(gas))
   ```
4. `solve`, цикл попыток (`:83-138`). После `current_state = state` (`:92`):
   ```python
               # Интегралы потоков компонентов через забой и контур по подшагам
               # этой попытки, м³ст (DEBT-039). Обнуляются на каждой попытке:
               # подшаги отвергнутой попытки в баланс не идут.
               int_o_well = int_o_ext = int_g_well = int_g_ext = 0.0
   ```
   После проверки `if not report.converged: ... break` (`:106-111`), перед «Шаг 4»:
   ```python
                   # Потоки подшага — на новом состоянии, как в невязке Ньютона
                   # (неявная схема). Знаки: у прототипа отток к скважине
                   # положителен — инверсия только на забое, как в _build_result:
                   # при добыче int_*_well < 0, при притоке с контура int_*_ext < 0.
                   f = self._model.face_component_fluxes_sm3s(new_proto)
                   int_o_well += dt_sub * (-f['oil_well'])
                   int_o_ext += dt_sub * f['oil_outer']
                   int_g_well += dt_sub * (-f['gas_component_well'])
                   int_g_ext += dt_sub * f['gas_component_outer']
   ```
   Возврат (`:137-138`), до → после:
   ```python
                   return self._build_result(current_state, new_proto, bc,
                                             n_substeps=n_sub)
   ```
   ```python
                   # G в HydroResult — потоки последнего подшага; балансу массы
                   # нужны интегралы по всем (DEBT-039).
                   result = self._build_result(current_state, new_proto, bc,
                                               n_substeps=n_sub)
                   return replace(result,
                                  int_G_o_well=int_o_well, int_G_o_ext=int_o_ext,
                                  int_G_g_well=int_g_well, int_G_g_ext=int_g_ext)
   ```
   Комментарий «Шаг 5–8: потоки и сборка HydroResult…» над возвратом сохранить.
5. Тесты — класс `TestMassBalanceIntegrals` в `test_prototype_adapter.py` («Тестовая стратегия»).

**Проверка после шага:**
- `.venv\Scripts\python -m pytest tests/test_prototype_adapter.py -q` — все зелёные, +4 теста.
- Регресс: быстрый.

**Подводные камни:** `replace` (чеклист); BUG-020 рядом (`:140-156`).

**Зависимости:** требует шаг 2; блокирует 4.

**Оценка:** ~35 строк кода, ~75 строк тестов, ~40 мин.

### Шаг 4: Накопитель и `Simulator`

**Цель:** интегралы копятся по принятым шагам, снимок — на каждой записи.

**Файлы:** `numerical_solver/gpn_multiphase_solver/mass_balance.py` (новый), `numerical_solver/gpn_multiphase_solver/simulator.py`, `numerical_solver/tests/_doubles.py`, `numerical_solver/tests/test_mass_balance.py`, `numerical_solver/tests/test_energy_balance_examples.py`.

**Контекст:** накопитель — только сумматор; принятие шага решает `Simulator._advance` (пробный шаг отбрасывается до вызова `add_step`, как и до решения энергии — `simulator.py:200-204`). Запас — функция состояния, его не копят: на каждой записи его отдаёт решатель.

**Что сделать:**

1. `gpn_multiphase_solver/mass_balance.py`:
   ```python
   """Накопление интегралов потоков компонентов для баланса массы (DEBT-039).

   Схема гидродинамики консервативна: невязки eq:residual_oil, eq:residual_gas
   (problem_statement.tex) — изменение запаса компонента в ячейке плюс разность
   потоков через её грани. Сумма по ячейкам и шагам сворачивается к забою и
   контуру:

       ΔM_α(t) + ∫G_α[N] dt − ∫G_α[0] dt = 0,   α = нефть, газ (м³ст).

   Потоки через забой и контур надо интегрировать по ВСЕМ принятым шагам: по
   записям истории их не восстановить (довод DEBT-013 для баланса энергии). Здесь
   — только сумматор; интегралы шага по внутренним подшагам решателя приходят в
   HydroResult.int_G_* (у адаптера прототипа — по подшагам A-retry). Запас M_α —
   функция состояния, его не копят: на каждой записи его отдаёт решатель
   (HydroSolver.component_inventories), с теми же φ, B_o, B_g, что в невязке.

   Невязка — уровень допуска Ньютона, а не округлений, как у баланса энергии:
   проверяется не физика, а всё между невязкой Ньютона и историей (допуск,
   накопленный по шагам; знаки потоков адаптера; учёт дробления шага). Сборка
   невязки, график и печать — examples/mass_balance.py.
   """

   from __future__ import annotations

   from typing import TYPE_CHECKING

   if TYPE_CHECKING:
       from .state import HydroResult


   # Ключи снимка: запас компонентов на момент записи и интегралы потоков
   # через забой и контур от t = 0, м³ст.
   MASS_KEYS = ("M_o", "M_g", "cum_o_well", "cum_o_ext", "cum_g_well", "cum_g_ext")


   class MassBalanceAccumulator:
       """Интегралы потоков компонентов по принятым шагам. Ур. (eq:residual_oil), (eq:residual_gas)."""

       def __init__(self) -> None:
           # ∫G[0] dt и ∫G[N] dt от t = 0, м³ст. Знак — как у G (> 0 от
           # скважины): при добыче cum_*_well < 0, при притоке с контура
           # cum_*_ext < 0.
           self.cum_o_well = 0.0
           self.cum_o_ext = 0.0
           self.cum_g_well = 0.0
           self.cum_g_ext = 0.0

       def add_step(self, hydro_result: HydroResult) -> None:
           """Добавить интегралы потоков принятого шага. Ур. (eq:residual_oil), (eq:residual_gas)."""
           hr = hydro_result
           ints = (hr.int_G_o_well, hr.int_G_o_ext, hr.int_G_g_well, hr.int_G_g_ext)
           # Проверка до накопления: прерванный вызов не оставляет сумматор
           # частично обновлённым. Сюда приходят только решатели, отдавшие
           # запас (Simulator.run): запас без интегралов — несогласованный
           # решатель, баланс по dt·G последнего подшага был бы ложным.
           if None in ints:
               raise RuntimeError(
                   "HydroResult без интегралов потоков int_G_*: решатель отдаёт "
                   "запас компонентов, но не интегралы — баланс массы не замкнуть "
                   "(DEBT-039)")
           self.cum_o_well += hr.int_G_o_well
           self.cum_o_ext += hr.int_G_o_ext
           self.cum_g_well += hr.int_G_g_well
           self.cum_g_ext += hr.int_G_g_ext

       def snapshot(self, inventories: tuple[float, float]) -> dict:
           """Снимок для SimulationHistory: запас на записи и накопленные интегралы, м³ст."""
           M_o, M_g = inventories
           return {"M_o": M_o, "M_g": M_g,
                   "cum_o_well": self.cum_o_well, "cum_o_ext": self.cum_o_ext,
                   "cum_g_well": self.cum_g_well, "cum_g_ext": self.cum_g_ext}
   ```

2. `simulator.py`:
   - импорт после `EnergyBalanceAccumulator` (`:25`): `from .mass_balance import MassBalanceAccumulator`;
   - `run`, после создания `balance` (`:129`):
     ```python
             # Баланс массы компонентов (DEBT-039). Интегралы потоков через
             # забой и контур копятся по ВСЕМ принятым шагам — по записям
             # истории их не восстановить, как и члены баланса энергии. Запас —
             # функция состояния, на каждой записи его отдаёт решатель. None —
             # решатель массу не сохраняет (тестовые двойники): баланс не
             # считается, снимки истории — None.
             mass = (MassBalanceAccumulator()
                     if self._hydro.component_inventories(initial_state) is not None
                     else None)
     ```
   - начальная запись (`:134-139`) — аргумент `mass_balance=self._mass_snapshot(mass, state),`;
   - вызов `_advance` (`:156-157`): `state, dt, interval.bc, balance, mass)`;
   - запись на конце интервала (`:175-177`):
     ```python
                         history.append(t=state.t, state=state,
                                        hydro=hydro_result, well=well,
                                        balance=balance.snapshot(),
                                        mass_balance=self._mass_snapshot(mass, state))
     ```
   - `_advance`: сигнатура
     ```python
         def _advance(self, state: SimulationState, dt: float,
                      bc: BoundaryConditions,
                      balance: EnergyBalanceAccumulator,
                      mass: MassBalanceAccumulator | None,
                      allow_subdivision: bool = True
                      ) -> tuple[SimulationState, HydroResult]:
     ```
     В docstring к абзацу «Порядок вызовов критичен…» добавить: «То же для `MassBalanceAccumulator`: интегралы потоков добавляются только у принятого результата (DEBT-039).»
     Рекурсивный вызов (`:224-225`): `state, dt_sub, bc, balance, mass, allow_subdivision=False)`.
     После блока `if n_sub > 1: user_log.warning(...)` (`:228-234`), перед «2. Температура…»:
     ```python
             # Баланс массы (DEBT-039): только ПРИНЯТЫЙ результат — пробный шаг
             # выше отброшен до этой точки, как и для баланса энергии. При
             # вложенном дроблении (n_sub > 1 здесь) G_o, G_g результата — потоки
             # последнего внутреннего подшага, а int_G_* — интегралы по всем.
             if mass is not None:
                 mass.add_step(hydro_result)
     ```
   - новый метод после `_advance`:
     ```python
         def _mass_snapshot(self, mass: MassBalanceAccumulator | None,
                            state: SimulationState) -> dict | None:
             """Снимок баланса массы на записи истории; None — решатель массу не сохраняет."""
             if mass is None:
                 return None
             return mass.snapshot(self._hydro.component_inventories(state))
     ```

3. `tests/_doubles.py`, `SubdividingHydroStub` — метод после `solve`:
   ```python
       def component_inventories(self, state: SimulationState):
           """Запас — у внутреннего двойника (DEBT-039)."""
           # Без делегирования метод ABC вернул бы None, и Simulator не вёл бы
           # баланс массы на обёрнутом двойнике с интегралами
           # (test_mass_balance.py, пробный шаг не в интегралах).
           return self._inner.component_inventories(state)
   ```

4. `tests/test_mass_balance.py` — импорт `from gpn_multiphase_solver.mass_balance import MASS_KEYS, MassBalanceAccumulator`, классы `TestAccumulator`, `TestSimulatorWiring`, двойники `_FluxIntegralStub`, `_NestedSubdividingStub` («Тестовая стратегия»).

5. `tests/test_energy_balance_examples.py` — в двух побитовых тестах расписания после `assert stepped.balance[j] == uniform.balance[k], t` (`:232`, `:297`):
   ```python
           # Баланс массы (DEBT-039): интегралы — те же подшаги, запас — та же
           # функция побитово равных состояний
           assert stepped.mass_balance[j] == uniform.mass_balance[k], t
   ```
   В docstring обоих тестов — «…и накопленные балансы энергии и массы совпадают ПОБИТОВО».

**Проверка после шага:**
- `.venv\Scripts\python -m pytest tests/test_mass_balance.py tests/test_simulator.py tests/test_energy_balance_examples.py -q` — зелёные.
- Регресс: быстрый.

**Подводные камни:** делегирование в `SubdividingHydroStub`; проверка до накопления.

**Зависимости:** требует шаги 2, 3; блокирует 5.

**Оценка:** ~90 строк кода, ~60 строк тестов, ~50 мин.

### Шаг 5: Конвейер примеров — `examples/mass_balance.py`

**Цель:** печать и рисунок у каждого примера; тест по всем примерам.

**Файлы:** `numerical_solver/examples/mass_balance.py` (новый), `numerical_solver/examples/example_runner.py`, `numerical_solver/tests/test_examples.py`, `numerical_solver/tests/test_mass_balance.py`.

**Что сделать:**

1. `examples/mass_balance.py`:
   ```python
   """Баланс массы компонентов во времени — общая проверка для всех примеров (DEBT-039).

   Схема гидродинамики консервативна: невязки eq:residual_oil, eq:residual_gas
   (problem_statement.tex) — изменение запаса компонента в ячейке плюс разность
   потоков через её грани. Сумма по ячейкам и шагам сворачивается к забою и
   контуру:

     невязка_α(t) = ΔM_α(t) + ∫G_α[N] dt − ∫G_α[0] dt,    ΔM_α = M_α(t) − M_α(0)

     M_o = Σ φV S_o/B_o,   M_g = Σ φV (S_o R_s/B_o + S_g/B_g),   м³ст.

   Знак G — от скважины: при добыче ∫G[0] < 0, при притоке с контура ∫G[N] < 0.

   ЧТО ПРОВЕРЯЕТ. Не физику — сохранение массы заложено в невязку Ньютона, — а
   всё, что стоит между ней и историей: допуск Ньютона, накопленный по шагам;
   правки состояния после сходимости; знаки и сопоставление потоков в адаптере;
   учёт дробления шага в Simulator. Уровень невязки поэтому — допуск Ньютона,
   а не округления, как у баланса энергии: замер при планировании — до 2.9e-8
   (пример 15), порог тестов 1e-6. Когда невязка старого состояния ниже
   абсолютного допуска Ньютона (1e-11 м³ст/с на ячейку), шаг принимается без
   итераций, состояние стоит, а поток через контур копится — невязка растёт
   на него линейно (останов 16 после 21 сут: 5.3e-6 м³ст/сут).

   ФИЗИКА ЖИВЁТ В ЯДРЕ: интегралы потоков копит gpn_multiphase_solver/
   mass_balance.py по всем принятым шагам, запас на записях отдаёт решатель.
   Здесь — только сборка массивов, график и печать.

   Запуск для конкретного примера:
       cd numerical_solver
       .venv\\Scripts\\python examples\\mass_balance.py 16
   """

   import sys
   from pathlib import Path

   import numpy as np

   import matplotlib
   matplotlib.use("Agg")
   import matplotlib.pyplot as plt  # noqa: E402

   _EXAMPLES = Path(__file__).resolve().parent
   _ROOT = _EXAMPLES.parent
   for _p in (str(_ROOT), str(_EXAMPLES),
              str(_ROOT / "HydroSolverPrototype" / "Prototype_1.0.3")):
       if _p not in sys.path:
           sys.path.insert(0, _p)

   from gpn_multiphase_solver.mass_balance import MASS_KEYS  # noqa: E402
   from gpn_multiphase_solver.units import S_TO_DAY  # noqa: E402
   from figure_io import save_figure, export_emf  # noqa: E402
   from energy_balance import _resolve_example  # noqa: E402


   def compute_mass_balance(history) -> dict | None:
       """Баланс массы по снимкам истории; None — масса не сохраняется. Ур. (eq:residual_oil)."""
       # Снимки либо все есть, либо все None: Simulator решает один раз, по
       # запасу начального состояния (simulator.py, run).
       if not history.mass_balance or history.mass_balance[0] is None:
           return None
       out = {k: np.array([s[k] for s in history.mass_balance]) for k in MASS_KEYS}
       out["t"] = np.array(history.times)
       for a in ("o", "g"):
           well, ext = out[f"cum_{a}_well"], out[f"cum_{a}_ext"]
           dM = out[f"M_{a}"] - out[f"M_{a}"][0]
           out[f"dM_{a}"] = dM
           # Физические знаки для чтения: добыча и приток с контура > 0.
           # 0.0 − x, а не −x: у примеров без газа печаталось бы −0.0000e+00.
           out[f"prod_{a}"] = 0.0 - well
           out[f"inflow_{a}"] = 0.0 - ext
           # Сумма невязок eq:residual_oil (eq:residual_gas) по ячейкам и шагам:
           # внутренние грани сократились, остались забой и контур
           out[f"residual_{a}"] = dM + ext - well
           # Нормировка — сумма модулей членов, как у баланса энергии
           # (energy_balance.compute_balance). При t = 0 и у газа примеров 01,
           # 02 все члены нулевые: делить не на что, невязка 0.
           scale = np.abs(dM) + np.abs(well) + np.abs(ext)
           scale = np.where(scale > 0.0, scale, 1.0)
           out[f"rel_residual_{a}"] = np.abs(out[f"residual_{a}"]) / scale
       return out


   def plot_mass_balance(config, history, output_dir: Path) -> dict | None:
       """График и печать баланса массы; массивы compute_mass_balance. Ур. (eq:residual_oil)."""
       # config — первый аргумент: конвенция общих модулей (plot_relperm,
       # plot_pvt; заметка «проверка выносится в общий модуль...»). Исключение
       # plot_energy_balance(history, grid, config, ...) — историческое.
       bal = compute_mass_balance(history)
       if bal is None:
           print("Баланс массы не считается: решатель не отдаёт запас компонентов")
           return None
       t_days = bal["t"] * S_TO_DAY    # время на графиках — в сутках (FEAT-022)

       # Две колонки, а не одни оси: запасы нефти и газа различаются на два
       # порядка (у 16: 10³ и 10⁵ м³ст), общая шкала спрятала бы нефть.
       fig, axes = plt.subplots(2, 2, figsize=(13, 8), sharex=True,
                                gridspec_kw={"height_ratios": [3, 1]})
       for col, (a, name) in enumerate((("o", "Нефтяной компонент"),
                                        ("g", "Газовый компонент"))):
           ax1, ax2 = axes[0, col], axes[1, col]
           ax1.plot(t_days, bal[f"dM_{a}"], 'k-', linewidth=2,
                    label=r"$\Delta M$ (изменение запаса)")
           # Добыча — широкой полупрозрачной линией под штриховой притока: в
           # стационаре (01, 02) кривые совпадают, и узкая скрылась бы.
           ax1.plot(t_days, bal[f"prod_{a}"], 'r-', linewidth=3, alpha=0.5,
                    label="добыча через забой (кумул.)")
           ax1.plot(t_days, bal[f"inflow_{a}"], 'b--', linewidth=1.5,
                    label="приток через контур (кумул.)")
           ax1.plot(t_days, bal[f"inflow_{a}"] - bal[f"prod_{a}"], 'g:',
                    linewidth=1.5, label="приток − добыча")
           ax1.set_ylabel("Объём, м³ст")
           ax1.set_title(name)
           ax1.legend(fontsize=9)
           ax1.grid(True, alpha=0.3)
           ax1.ticklabel_format(axis='y', style='scientific', scilimits=(0, 0))

           ax2.plot(t_days, bal[f"rel_residual_{a}"], 'k-', linewidth=1)
           ax2.set_xlabel("Время, сут")
           ax2.set_ylabel(r"|невязка| / $\Sigma$|членов|")
           ax2.grid(True, alpha=0.3)
           ax2.ticklabel_format(axis='y', style='scientific', scilimits=(0, 0))

       # Имя примера — из пути к конфигу: модуль общий для всех примеров.
       fig.suptitle(f"Баланс массы компонентов — {Path(config.config_dir).name}")
       fig.tight_layout()
       output_dir = Path(output_dir)
       output_dir.mkdir(parents=True, exist_ok=True)
       out_path = output_dir / "mass_balance.png"
       save_figure(fig, out_path, dpi=130)
       plt.close(fig)
       print(f"Сохранён: {out_path}")

       # Только ASCII-знаки и кириллица: консоль Windows под cp1251 не
       # кодирует Δ, ³, − и print падает с UnicodeEncodeError
       # (energy_balance.py, plot_energy_balance).
       print("Баланс массы компонентов, м3ст:")
       for a, name in (("o", "Нефть"), ("g", "Газ  ")):
           print(f"  {name}: dM = {bal[f'dM_{a}'][-1]:+.4e}, "
                 f"добыча = {bal[f'prod_{a}'][-1]:+.4e}, "
                 f"приток с контура = {bal[f'inflow_{a}'][-1]:+.4e}")
           print(f"         невязка финал = {bal[f'residual_{a}'][-1]:+.4e} "
                 f"({bal[f'rel_residual_{a}'][-1]:.2e}), max по записям "
                 f"{float(np.max(bal[f'rel_residual_{a}'])):.2e}")
       return bal


   # ── Автономный запуск ──
   if __name__ == "__main__":
       from gpn_multiphase_solver.io.config import load_config
       from gpn_multiphase_solver.factory import SimulatorFactory

       if len(sys.argv) < 2:
           raise SystemExit(
               "укажите пример: python examples\\mass_balance.py 16")

       folder = _resolve_example(sys.argv[1])
       config = load_config(folder / "config.json")
       sim, initial_state = SimulatorFactory.from_config(config)
       history = sim.run(initial_state)

       plot_mass_balance(config, history, folder / "output")
       # Автономный запуск: SVG только что сохранённого рисунка — в EMF (FEAT-026).
       export_emf(folder / "output")
   ```
   `_resolve_example` берётся из `energy_balance.py` (`:196-211`), а не копируется: одна копия правила разбора имени примера.

2. `examples/example_runner.py`:
   - импорт после `energy_balance` (`:73`): `from mass_balance import plot_mass_balance  # noqa: E402`;
   - после `plot_energy_balance(history, grid, config, output_dir)` (`:218`), до блока EMF:
     ```python

         # ── Баланс массы компонентов (DEBT-039) ──
         # Интегралы потоков через забой и контур копит решатель по всем
         # принятым шагам, запас на записях отдаёт решатель — как у баланса
         # энергии, структура истории проверке не мешает. До export_emf:
         # рисунок попадает в тот же пакет EMF.
         print()
         plot_mass_balance(config, history, output_dir)
     ```

3. `tests/test_examples.py`:
   - `SHARED_CHECK_MODULES` (`:620-626`) — добавить `"mass_balance.py",`;
   - `test_pipeline_writes_output`, список `expected` (`:501-509`) — после `"energy_balance.png",`:
     ```python
             # DEBT-039: баланс массы компонентов — общий модуль для всех примеров
             "mass_balance.png",
     ```
   - `test_energy_balance_reported_for_all_examples` (`:749-779`) — после проверки `energy_balance.png`:
     ```python
             # DEBT-039: баланс массы подключён к тому же run_example
             assert "Баланс массы компонентов" in out, (
                 "run_example не печатает баланс массы")
             assert (tmp_path / "mass_balance.png").is_file(), (
                 "run_example не сохранил график баланса массы")
     ```
     В docstring: «…и баланс массы компонентов (DEBT-039).»
   - `TestSharedChecks` — тест `test_mass_balance_all_examples` после `test_energy_balance_all_examples` («Тестовая стратегия»).
   - Заголовок секции I (`:611`): «Общие проверки: балансы энергии и массы у всех примеров (FEAT-016, DEBT-039)».

4. `tests/test_mass_balance.py` — укороченные конфиги (`test_mass_balance_closes_short`, `test_mass_balance_independent_of_history_structure`, `test_mass_balance_through_shut_in`), импорт `compute_mass_balance`.

**Проверка после шага:**
- `.venv\Scripts\python -m pytest tests/test_mass_balance.py tests/test_examples.py -m "not slow" -q` — зелёные.
- `.venv\Scripts\python examples\mass_balance.py 16` — печать как в «Ожидаемый вывод» ниже, `examples/16_well_shut_in/output/mass_balance.png` — открыть и посмотреть: две колонки, линии добычи и притока различимы, невязка ~$10^{-9}$.
- Регресс: быстрый. Новый медленный тест `test_mass_balance_all_examples` проходит в полном прогоне шага 7.

**Ожидаемый вывод** `examples\mass_balance.py 16` (код плана, проба `plot`):
```
Баланс массы компонентов, м3ст:
  Нефть: dM = +4.3826e+02, добыча = +4.1113e+03, приток с контура = +4.5496e+03
         невязка финал = -5.0967e-05 (5.60e-09), max по записям 5.60e-09
  Газ  : dM = -8.4155e+04, добыча = +2.2064e+05, приток с контура = +1.3649e+05
         невязка финал = -1.5604e-03 (3.54e-09), max по записям 3.54e-09
```
Последние знаки могут отличаться: проба суммирует интегралы в другом порядке.

**Подводные камни:** cp1251; EMF до `export_emf`; DEBT-037.

**Зависимости:** требует шаг 4; блокирует 6, 7.

**Оценка:** ~150 строк модуля, ~10 строк в `example_runner.py`, ~70 строк тестов, ~60 мин.

### Шаг 6: Документация примеров

**Цель:** новый выходной файл и проверка описаны там же, где баланс энергии.

**Файлы:** `numerical_solver/examples/README.md`; README примеров `01_single_phase_no_jt`, `02_single_phase_jt`, `03_standing_corey`, `04_table_table`, `04a_high_gas_saturation`, `16_well_shut_in`, `19_rs150_cooling`, `20_rs300_cooling`, `21_rs100_cooling`.

**Что сделать:**

1. `examples/README.md`:
   - таблица «Что получается на выходе» (`:240-252`) — строка после `energy_balance.png`:
     `| `mass_balance.png` | баланс массы компонентов: изменение запаса, добыча через забой, приток через контур (нефть, газ) + относительная невязка |`
   - новый раздел после «Баланс энергии — во всех сценариях без исключения» (перед «### Асимптотика температуры», `:563`):
     ```markdown
     ### Баланс массы компонентов — во всех сценариях

     Схема гидродинамики консервативна: невязки уравнений нефтяного и газового
     компонентов (`eq:residual_oil`, `eq:residual_gas` в
     [problem_statement.tex](../doc/problem_statement.tex)) — изменение запаса
     в ячейке плюс разность потоков через её грани. Сумма по ячейкам и шагам
     сворачивается к забою и контуру:

     $$\Delta M_\alpha = Q^\alpha_{\text{приток}} - Q^\alpha_{\text{добыча}},
     \qquad M_o = \sum \phi V \frac{S_o}{B_o},\quad
     M_g = \sum \phi V \Big(\frac{S_o R_s}{B_o} + \frac{S_g}{B_g}\Big),\ \text{м³ст}.$$

     Модуль [mass_balance.py](mass_balance.py) подключён к каждому примеру,
     рисунок — `mass_balance.png`. Потоки через забой и контур решатель
     интегрирует по всем принятым шагам (при дроблении шага — по подшагам),
     запас на записях отдаёт прототип — с теми же $\phi(p)$, $B_o$, $B_g$, что
     в его невязке.

     Проверяется не физика — сохранение массы заложено в уравнения, — а всё
     между невязкой Ньютона и историей: допуск Ньютона, накопленный по шагам;
     знаки потоков в адаптере; учёт дробления шага. Поэтому уровень невязки —
     допуск Ньютона (относительный $10^{-8}$ к начальной невязке шага), а не
     округления, как у баланса энергии. Порог тестов — $10^{-6}$.

     <таблица: пример | нефть | газ — максимум относительной невязки по записям,
     числа — из печати примеров (или `history_snapshot.py compare`, шаг 7);
     ожидаемые — таблица «Замер при планировании» плана DEBT-039>

     Нормировка — сумма модулей членов $|\Delta M| + |Q_{\text{добыча}}| +
     |Q_{\text{приток}}|$, как у баланса энергии. Выше всех — 15 (управление
     по дебиту). У 16 невязка растёт на останове после 21 сут линейно:
     невязка старого состояния там ниже абсолютного допуска Ньютона
     ($10^{-11}$ м³ст/с на ячейку), шаг принимается без итераций, состояние
     стоит, а приток с контура ($5.3\cdot10^{-6}$ м³ст/сут) копится.
     ```
   - таблица «Общие модули проверок» (`:667-683`) — строка после `energy_balance_convergence.py`:
     `| [mass_balance.py](mass_balance.py) | баланс массы нефтяного и газового компонентов | `python examples\mass_balance.py 16` |`
   - абзац «Для двухфазной зоны аналитики температуры нет…» (`:583-586`) не трогать.

2. README примеров — по строке рядом с упоминанием `energy_balance.png` (строки — по grep `energy_balance.png` в `examples/*/README.md`):
   - 01 (`:165`), 02 (`:240`) — `- `mass_balance.png` — баланс массы компонентов; газа нет, правая колонка на нуле, добыча нефти равна притоку с контура (нефть несжимаема).`
   - 03 (`:306`), 04 (`:325`), 04a (`:436`) — `- `mass_balance.png` — баланс массы компонентов (нефть, газ) и его невязка.`
   - 19, 21 (`:177`), 20 (`:207`) — дописать к перечню: «`mass_balance.png` — баланс массы компонентов.»
   - 16 — после раздела «Откуда нагрев» (перед «## Проверка газосодержания $R_s$», `:151`) — раздел:
     ```markdown
     ## Баланс массы компонентов

     Состав призабойной зоны после останова не возвращается к начальному
     (раздел о $R_s$ выше), поэтому возврат к начальному состоянию —
     не инвариант этого сценария. Инвариант — баланс массы: изменение запаса
     равно притоку с контура минус добыча. Консоль (`mass_balance.png`), м³ст,
     за 30 сут:

     | компонент | $\Delta M$ | добыча | приток с контура | отн. невязка |
     |---|---|---|---|---|
     | нефть | <из печати> | <…> | <…> | <…> |
     | газ | <…> | <…> | <…> | <…> |

     На останове добыча стоит (забой закрыт), а пласт добирает нефть с
     контура, пока давление не выровняется. После 21 сут невязка растёт
     линейно: невязка состояния там ниже абсолютного допуска Ньютона
     прототипа ($10^{-11}$ м³ст/с на ячейку), шаг принимается без итераций,
     состояние стоит, а приток с контура ($5.3\cdot10^{-6}$ м³ст/сут) копится.
     ```
     Числа — из печати `main.py` (ожидаемые — «Ожидаемый вывод» шага 5: нефть $+438.3$, $4111.3$, $4549.6$, $5.6\cdot10^{-9}$; газ $-84155$, $220642$, $136487$, $3.5\cdot10^{-9}$).

**Проверка после шага:** `.venv\Scripts\python -m pytest tests/ --collect-only -q` (только документы) и `.venv\Scripts\python -m pytest tests/test_examples.py::TestReadme -q` — обязательные разделы README на месте.

**Оценка:** ~60 строк, ~30 мин.

### Шаг 7: Верификация

**Цель:** решение не изменилось ни в одном бите; все тесты зелёные; рисунок просмотрен.

**Что сделать** (из `numerical_solver/`):
```powershell
.venv\Scripts\python -m pytest tests/ -q                                             # полный, ~10 мин
.venv\Scripts\python ..\vault\issues\debt-039\probes\history_snapshot.py save new     # ~4 мин
.venv\Scripts\python ..\vault\issues\debt-039\probes\history_snapshot.py compare base new
.venv\Scripts\python examples\16_well_shut_in\main.py
```

**Проверка:**
- Регресс: полный — новый медленный тест `test_mass_balance_all_examples` только здесь.
- `compare`: «побитово» у всех 21 примера (состояния, потоки, данные скважины, баланс энергии), «итого: различий 0»; max невязки массы — как в таблице «Замер при планировании».
- `examples/16_well_shut_in/output/mass_balance.png` — открыть.
- Время полного прогона — не больше baseline + ~15 с (новые тесты укороченных конфигов, ~5 с).
- Удалить `vault/issues/debt-039/probes/history_base/` и `history_new/` после разбора.

**Оценка:** ~20 мин.

### Шаг 8: Vault и issue

**Файлы:**
- `vault/knowledge/decisions/контейнер-simulation-history.md` — поле `mass_balance` в схеме (`:16-25`) и таблице (`:29-35`), раздел «mass_balance — баланс массы компонентов (DEBT-039)» после раздела `balance` (`:54-68`): ключи `MASS_KEYS`, запас — у решателя на записи, интегралы — по принятым шагам, `None` у двойников.
- `vault/knowledge/decisions/модули-simulator-оркестратор.md` — фрагмент цикла (`:83-87`): `mass_balance=self._mass_snapshot(mass, state)`; абзац о накопителе массы.
- `vault/knowledge/decisions/P4-адаптивный-шаг.md` — после абзаца о порядке вызовов (`:155`): адаптер интегрирует потоки по подшагам A-retry, `HydroResult.G` — последнего подшага, `int_G_*` — интеграл (замер ловушки: $8.7\cdot10^{-2}$ против $6.5\cdot10^{-12}$).
- `vault/knowledge/decisions/словарь-код-физика.md` §3.1 (`:73-79`) — таблица: `int_G_o_well`, `int_G_o_ext`, `int_G_g_well`, `int_G_g_ext` ($\int G^\alpha_{0,N}\,dt$, м³ст, скаляры) и `HydroSolver.component_inventories` ($M_o$, $M_g$, м³ст).
- Реестр DEBT-039 — статус, ветка, коммит; комментарий к #65 (`vault/issues/debt-039/05-comment-done.md`) — `/implement`.

## Тестовая стратегия

Регресс: все существующие тесты зелёные после каждого шага; покрывают затронутый код `test_simulator.py` (`TestEnergySubstepsUnderRetry` — пробный шаг), `test_prototype_adapter.py`, `test_energy_balance_examples.py`, `test_examples.py`, `test_hydro.py` (ABC). Инвариант — побитовая история (шаг 7, `history_snapshot.py`).

### `tests/test_mass_balance.py` (новый, быстрый уровень)

```python
"""Баланс массы компонентов (DEBT-039): контракты, накопитель, Simulator, укороченные примеры.

Схема гидродинамики консервативна: невязки eq:residual_oil, eq:residual_gas —
изменение запаса в ячейке плюс разность потоков через грани; их сумма по
ячейкам и шагам сворачивается к забою и контуру:
ΔM + ∫G[N] dt − ∫G[0] dt = 0. Накопленная невязка проверяет не физику, а то,
что стоит между невязкой Ньютона и историей: допуск Ньютона, учёт дробления
шага, знаки потоков адаптера.

Конфиги примеров укорочены (6 ч или 2 + 2 ч, N = 25) — тесты идут доли секунды.
"""

import copy
import json
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.io.config import load_config
from gpn_multiphase_solver.mass_balance import MASS_KEYS, MassBalanceAccumulator
from gpn_multiphase_solver.simulator import Simulator

from ._doubles import LogProfileHydroStub, SubdividingHydroStub
from .test_simulator import _initial_state, _make_simulator, _single_interval_schedule

# Модуль сборки невязки — общий для примеров (examples/mass_balance.py)
_EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
if str(_EXAMPLES) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES))

from mass_balance import compute_mass_balance  # noqa: E402

# Порог относительной невязки (нормировка — сумма модулей членов). Уровень —
# допуск Ньютона прототипа (rtol = 1e-8 к начальной невязке шага, atol =
# 1e-11 м³ст/с на ячейку), а не округления: замер при планировании — до
# 4.5e-10 на укороченных конфигах здесь, до 2.9e-8 на полных примерах.
# Дефекты, которые ловит проверка, дают 1e-3...1: поток последнего подшага
# вместо интеграла при дроблении — 9e-2 на шаге.
TOL = 1e-6


def _stub_result(**integrals):
    """HydroResult двойника за шаг 3600 с, с заданными интегралами потоков."""
    _, _, hydro, _, _ = _make_simulator()
    bc = _single_interval_schedule().intervals[0].bc
    return replace(hydro.solve(_initial_state(), 3600.0, bc), **integrals)


def _max_rel(bal):
    """Максимум относительной невязки по записям: нефть и газ вместе."""
    return max(float(np.max(bal["rel_residual_o"])),
               float(np.max(bal["rel_residual_g"])))


# ── Контракты (шаг 2) ─────────────────────────────────────────

class TestContracts:
    def test_hydro_result_integrals_default_none(self):
        """Без интегралов HydroResult строится как прежде: поля — None.

        Шесть мест в тестах и fluxes.py строят HydroResult без новых полей;
        умолчание None — признак «решатель массу не сохраняет».
        """
        r = _stub_result()
        assert (r.int_G_o_well, r.int_G_o_ext,
                r.int_G_g_well, r.int_G_g_ext) == (None, None, None, None)

    def test_solver_inventories_default_none(self):
        """Метод ABC по умолчанию — None: двойник уравнений не решает."""
        _, _, hydro, _, _ = _make_simulator()
        assert hydro.component_inventories(_initial_state()) is None

    def test_stub_history_without_mass_balance(self):
        """На двойнике без запаса снимки баланса массы — None, расчёт идёт."""
        grid, pvt, hydro, energy, _ = _make_simulator()
        sim = Simulator(grid, hydro, energy, pvt,
                        _single_interval_schedule(dt_hist=7200.0, dt_int=3600.0))
        history = sim.run(_initial_state())
        # Один интервал — две записи: начальная и конец интервала
        assert history.mass_balance == [None, None]


# ── Накопитель (шаг 4) ────────────────────────────────────────

class TestAccumulator:
    def test_sums_integrals_and_snapshot(self):
        """Интегралы шагов складываются; снимок — запас + суммы, ключи MASS_KEYS."""
        acc = MassBalanceAccumulator()
        r = _stub_result(int_G_o_well=-1.0, int_G_o_ext=-2.0,
                         int_G_g_well=-3.0, int_G_g_ext=-4.0)
        acc.add_step(r)
        acc.add_step(r)
        snap = acc.snapshot((10.0, 20.0))
        assert snap == {"M_o": 10.0, "M_g": 20.0,
                        "cum_o_well": -2.0, "cum_o_ext": -4.0,
                        "cum_g_well": -6.0, "cum_g_ext": -8.0}
        assert tuple(snap) == MASS_KEYS

    def test_missing_integrals_raise_before_accumulation(self):
        """Без любого из int_G_* — RuntimeError, накопитель не тронут.

        Запас без интегралов — несогласованный решатель: баланс по dt·G
        последнего подшага был бы ложным при дроблении шага (DEBT-039).
        """
        acc = MassBalanceAccumulator()
        with pytest.raises(RuntimeError, match="int_G"):
            acc.add_step(_stub_result(int_G_o_well=-1.0))   # три поля — None
        assert acc.snapshot((0.0, 0.0))["cum_o_well"] == 0.0


# ── Simulator (шаг 4) ─────────────────────────────────────────

class _FluxIntegralStub(LogProfileHydroStub):
    """Двойник с интегралами dt·G и нулевым запасом — проверка учёта шагов в Simulator."""

    def solve(self, state, dt, bc):
        r = super().solve(state, dt, bc)
        # Профиль стационарный, потоки шага постоянны: интеграл = dt·G
        return replace(r, int_G_o_well=dt * r.G_o[0], int_G_o_ext=dt * r.G_o[-1],
                       int_G_g_well=dt * r.G_g[0], int_G_g_ext=dt * r.G_g[-1])

    def component_inventories(self, state):
        return (0.0, 0.0)


class _NestedSubdividingStub(SubdividingHydroStub):
    """Сообщает о дроблении на КАЖДОМ вызове — путь вложенного дробления Simulator._advance."""

    def solve(self, state, dt, bc):
        self.dt_calls.append(dt)
        # replace сохраняет int_G_* внутреннего двойника, меняет только n_substeps
        return replace(self._inner.solve(state, dt, bc), n_substeps=self._n_substeps)


class TestSimulatorWiring:
    def test_pilot_step_not_counted(self):
        """Пробный шаг, отброшенный при дроблении, в интегралы не попадает.

        SubdividingHydroStub на первом вызове сообщает n_substeps = 2:
        Simulator отбрасывает пробный результат (3600 с) и проходит интервал
        двумя шагами по 1800 с (BUG-010). Потоки двойника постоянны, поэтому
        интеграл через забой — ровно 3600·G_o[0]; с пробным шагом было бы
        5400·G_o[0]. Замер при планировании: равенство побитовое.
        """
        grid, pvt, inner, energy, _ = _make_simulator()
        hydro = SubdividingHydroStub(_FluxIntegralStub(grid, pvt, inner._relperm),
                                     n_substeps=2)
        sim = Simulator(grid, hydro, energy, pvt,
                        _single_interval_schedule(dt_hist=3600.0, dt_int=3600.0))
        history = sim.run(_initial_state())

        assert hydro.dt_calls == [3600.0, 1800.0, 1800.0]
        # Не None: SubdividingHydroStub делегирует запас внутреннему двойнику
        assert history.mass_balance[-1] is not None
        assert history.mass_balance[0]["cum_o_well"] == 0.0
        G0 = history.hydro_results[-1].G_o[0]
        assert history.mass_balance[-1]["cum_o_well"] == pytest.approx(
            3600.0 * G0, rel=1e-12)

    def test_nested_subdivision_counted_once(self):
        """Вложенное дробление: принятый как есть подшаг учтён ровно один раз.

        Двойник сообщает n_substeps = 2 на КАЖДОМ вызове. Simulator отбрасывает
        пробный шаг (3600 с), проходит интервал двумя подшагами по 1800 с с
        запретом повторного дробления, и каждый из них, снова «раздробленный»,
        принимается как есть (simulator.py, ветка с предупреждением). Именно
        на этом пути G_o, G_g результата — потоки последнего внутреннего
        подшага, и интегралы обязаны прийти из int_G_*. Интеграл через забой —
        ровно 3600·G_o[0] (замер при аудите: побитово).
        """
        grid, pvt, inner, energy, _ = _make_simulator()
        hydro = _NestedSubdividingStub(_FluxIntegralStub(grid, pvt, inner._relperm),
                                       n_substeps=2)
        sim = Simulator(grid, hydro, energy, pvt,
                        _single_interval_schedule(dt_hist=3600.0, dt_int=3600.0))
        history = sim.run(_initial_state())

        assert hydro.dt_calls == [3600.0, 1800.0, 1800.0]
        G0 = history.hydro_results[-1].G_o[0]
        assert history.mass_balance[-1]["cum_o_well"] == pytest.approx(
            3600.0 * G0, rel=1e-12)

    def test_inventories_without_integrals_raise(self):
        """Решатель отдаёт запас, но не интегралы — RuntimeError на первом шаге."""

        class _InventoryOnly(LogProfileHydroStub):
            def component_inventories(self, state):
                return (1.0, 1.0)

        grid, pvt, inner, energy, _ = _make_simulator()
        sim = Simulator(grid, _InventoryOnly(grid, pvt, inner._relperm), energy,
                        pvt, _single_interval_schedule(dt_hist=3600.0, dt_int=3600.0))
        with pytest.raises(RuntimeError, match="int_G"):
            sim.run(_initial_state())


# ── Укороченные конфиги примеров, настоящий решатель (шаг 5) ──

def _short_config(example: str, n_intervals: int = 1):
    """Конфиг примера: 6 ч одним или n интервалами, N = 25 (как test_energy_balance_examples)."""
    config = load_config(_EXAMPLES / example / "config.json")
    config.grid.N = 25
    iv = copy.deepcopy(config.time.history[0])
    config.time.history = [copy.deepcopy(iv) for _ in range(n_intervals)]
    for h in config.time.history:
        h.dt = 21600.0 / n_intervals
    config.output.log_level = "WARNING"
    return config


def _run(config):
    simulator, initial_state = SimulatorFactory.from_config(config)
    return simulator.run(initial_state)


@pytest.mark.parametrize("example", ["03_standing_corey", "04_table_table"])
def test_mass_balance_closes_short(example):
    """Невязка баланса массы — на уровне допуска Ньютона: Стендинг и таблица.

    Источник PVT был разделительной линией в BUG-004 — проверяются обе ветви.
    Замер при планировании: 3.4e-11 (03), 1.0e-12 (04).
    """
    bal = compute_mass_balance(_run(_short_config(example)))
    assert _max_rel(bal) < TOL


@pytest.mark.parametrize("example", ["03_standing_corey", "04_table_table"])
def test_mass_balance_independent_of_history_structure(example):
    """Снимок баланса массы не зависит от частоты записи — побитово.

    Одни и те же 6 подшагов по 3600 с, одна запись или шесть: интегралы
    складываются в том же порядке, запас — функция побитово равного
    состояния. Восстановление по записям так не умело бы (DEBT-013).
    """
    sparse = _run(_short_config(example, 1))
    dense = _run(_short_config(example, 6))
    assert dense.n_saved == 7
    assert sparse.mass_balance[-1] == dense.mass_balance[-1]


def test_mass_balance_through_shut_in(tmp_path):
    """Баланс массы через останов: 2 ч добычи при 6 МПа, 2 ч останова (q_oil = 0).

    Конфиг примера 16, N = 25, шаг 300 с — как в
    test_energy_balance_examples.py::test_stepped_schedule_matches_uniform_across_shut_in.
    Запись 24 — конец добычи. На останове забой закрыт: интегралы через
    забой не меняются ни в одном бите, а пласт добирает нефть с контура —
    приток за останов равен росту запаса. Замер при планировании: невязка
    1.1e-11 (нефть), 4.5e-10 (газ); приток и рост запаса нефти — по 1.649 м³ст.
    """
    src = _EXAMPLES / "16_well_shut_in" / "config.json"
    raw = json.loads(src.read_text(encoding="utf-8"))
    raw["time"]["history"] = [
        {"dt": 300.0, "repeat": 24, "control": "pressure", "p_wf": 6.0e6},
        {"dt": 300.0, "repeat": 24, "control": "rate", "q_oil": 0.0,
         "min_bhp": 101325.0}]
    raw["time"]["dt_integration"] = 300.0
    path = tmp_path / "shut_in.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    config = load_config(path)
    # Таблицы PVT и ОФП фабрика ищет относительно конфига — каталог примера
    config.config_dir = src.parent
    config.grid.N = 25
    config.output.log_level = "WARNING"

    bal = compute_mass_balance(_run(config))
    assert _max_rel(bal) < TOL
    assert np.all(bal["cum_o_well"][24:] == bal["cum_o_well"][24])
    assert np.all(bal["cum_g_well"][24:] == bal["cum_g_well"][24])
    inflow = bal["inflow_o"][-1] - bal["inflow_o"][24]
    assert inflow > 0.0
    assert bal["dM_o"][-1] - bal["dM_o"][24] == pytest.approx(inflow, rel=1e-6)
```

| Тест | Сценарий | Ожидание (замер) | Предотвращает |
|---|---|---|---|
| `TestContracts` (3) | умолчания `None` | поля `None`; снимки `[None, None]` | поломку существующих мест сборки `HydroResult`; падение на двойниках |
| `test_sums_integrals_and_snapshot` | две добавки | суммы −2, −4, −6, −8; ключи `MASS_KEYS` | перепутанные поля |
| `test_missing_integrals_raise_before_accumulation` | одно поле из четырёх | `RuntimeError`, сумма 0 | молчаливый баланс по $\Delta t\cdot G$ |
| `test_pilot_step_not_counted` | двойник с дроблением | $3600\cdot G$ (побитово) | учёт отброшенного пробного шага |
| `test_nested_subdivision_counted_once` | дробление на каждом вызове | $3600\cdot G$ (побитово) | пропуск или двойной учёт подшага, принятого как есть |
| `test_inventories_without_integrals_raise` | запас без интегралов | `RuntimeError` | несогласованный решатель |
| `test_mass_balance_closes_short` (2) | 03, 04, 6 ч | $3.4\cdot10^{-11}$, $1.0\cdot10^{-12}$ < $10^{-6}$ | ошибки знаков, единиц, запаса |
| `test_mass_balance_independent_of_history_structure` (2) | 1 и 6 интервалов | снимки равны побитово | накопление по записям, а не по шагам |
| `test_mass_balance_through_shut_in` | 16, 2 + 2 ч | $4.5\cdot10^{-10}$; $\int G_0$ постоянен; приток = $\Delta M_o$ | поток через закрытый забой; потерю притока |

### `tests/test_prototype_adapter.py` — класс `TestMassBalanceIntegrals` (быстрый уровень)

В конец файла; импорт `from types import SimpleNamespace` — к импортам.

```python
# ═══════════════════════════════════════════════════════════
# K. Баланс массы: запас и интегралы потоков (DEBT-039)
# ═══════════════════════════════════════════════════════════

def _step_rel_residuals(adapter, state_old, r, use_integrals=True):
    """Отн. невязка баланса массы шага (нефть, газ): ΔM + ∫G[N] − ∫G[0], нормировка — сумма модулей."""
    (Mo0, Mg0) = adapter.component_inventories(state_old)
    (Mo1, Mg1) = adapter.component_inventories(r.state)
    dt = r.state.t - state_old.t
    out = []
    for dM, iw, ie, Gw, Ge in (
            (Mo1 - Mo0, r.int_G_o_well, r.int_G_o_ext, r.G_o[0], r.G_o[-1]),
            (Mg1 - Mg0, r.int_G_g_well, r.int_G_g_ext, r.G_g[0], r.G_g[-1])):
        # use_integrals=False — как считал бы накопитель без интегралов:
        # поток последнего подшага на весь шаг
        w, e = (iw, ie) if use_integrals else (dt * Gw, dt * Ge)
        out.append(abs(dM + e - w) / (abs(dM) + abs(w) + abs(e)))
    return out


class TestMassBalanceIntegrals:
    """Адаптер отдаёт запас прототипа и интегралы потоков по подшагам A-retry."""

    def test_integrals_equal_dt_flux_without_retry(self, result):
        """Без дробления интеграл = DT·G побитово.

        Один подшаг: 0.0 + DT·(−f) и DT·G[0], где G[0] = −f того же вызова
        face_component_fluxes_sm3s на том же состоянии. Знак забоя
        инвертирован (G < 0 при добыче), контура — нет.
        """
        assert result.n_substeps == 1
        assert result.int_G_o_well == DT * result.G_o[0]
        assert result.int_G_o_ext == DT * result.G_o[-1]
        assert result.int_G_g_well == DT * result.G_g[0]
        assert result.int_G_g_ext == DT * result.G_g[-1]
        assert result.int_G_o_well < 0.0           # добыча

    def test_inventories_from_prototype(self, adapter, model, initial_state):
        """Запас — суммы component_inventories прототипа, без пересчёта (BUG-004)."""
        ps = BlackOilState(pressure_bar=initial_state.p / BAR_TO_PA,
                           rs_sm3_sm3=initial_state.Rs.copy(),
                           sg=initial_state.Sg.copy(),
                           gas_active=(initial_state.regime == 1))
        oil, gas = model.component_inventories(ps)
        assert adapter.component_inventories(initial_state) == (
            float(np.sum(oil)), float(np.sum(gas)))

    def test_step_mass_balance_closes(self, adapter, initial_state, result):
        """Баланс массы шага замыкается на уровне допуска Ньютона (замер 1.5e-12)."""
        assert max(_step_rel_residuals(adapter, initial_state, result)) < 1e-6

    def test_integrals_sum_retry_substeps(self, adapter, model, initial_state,
                                          bc, monkeypatch):
        """При A-retry интегралы — сумма по подшагам, а не DT·G последнего.

        Первый вызов advance отказывает: адаптер дробит шаг на 2 подшага по
        DT/2. Интегралы обязаны совпасть с суммой двух solve(DT/2) того же
        адаптера — побитово (те же операции в том же порядке). Баланс шага с
        интегралами замыкается (замер 6.5e-12), с потоком последнего подшага
        на весь DT — нет (замер 8.7e-2): ловушка, ради которой интегралы
        считает адаптер.
        """
        real = model.advance
        calls = []

        def failing_first(proto_state, dt, *args, **kwargs):
            calls.append(dt)
            if len(calls) == 1:
                # Отчёт отказа: адаптер читает converged, iterations, residual_inf
                return proto_state, SimpleNamespace(
                    converged=False, iterations=0, residual_inf=1.0)
            return real(proto_state, dt, *args, **kwargs)

        monkeypatch.setattr(model, "advance", failing_first)
        r = adapter.solve(initial_state, dt=DT, bc=bc)
        monkeypatch.undo()

        assert calls == [DT, DT / 2, DT / 2]
        assert r.n_substeps == 2

        h1 = adapter.solve(initial_state, dt=DT / 2, bc=bc)
        h2 = adapter.solve(h1.state, dt=DT / 2, bc=bc)
        assert r.int_G_o_well == h1.int_G_o_well + h2.int_G_o_well
        assert r.int_G_o_ext == h1.int_G_o_ext + h2.int_G_o_ext
        assert r.int_G_g_well == h1.int_G_g_well + h2.int_G_g_well
        assert r.int_G_g_ext == h1.int_G_g_ext + h2.int_G_g_ext

        assert max(_step_rel_residuals(adapter, initial_state, r)) < 1e-6
        assert min(_step_rel_residuals(adapter, initial_state, r,
                                       use_integrals=False)) > 1e-2
```

### `tests/test_examples.py::TestSharedChecks::test_mass_balance_all_examples` (медленный)

```python
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
        import sys
        sys.path.insert(0, str(EXAMPLES_DIR))
        from mass_balance import compute_mass_balance

        bad = {}
        for name in ALL_EXAMPLES:
            bal = compute_mass_balance(results[name]["history"])
            assert bal is not None, f"{name}: баланс массы не считается"
            worst = max(float(np.max(bal["rel_residual_o"])),
                        float(np.max(bal["rel_residual_g"])))
            if worst >= 1e-6:
                bad[name] = worst
        assert not bad, f"невязка баланса массы >= 1e-6: {bad}"
```

Прочие правки тестов — шаги 4 (`test_energy_balance_examples.py`, 2 строки) и 5 (`test_examples.py`: модуль, файл, печать). Итого новых тестов: 13 в `test_mass_balance.py` (3 + 2 + 3 + 2 + 2 + 1), 4 в `test_prototype_adapter.py`, 1 в `TestSharedChecks` (медленный), 1 параметр `test_no_duplicate_helper_scripts` — **+19** (1267 → 1286; быстрый уровень +18: 1032 → 1050). Если до реализации влит DEBT-030 (+3 теста, см. «Текущее состояние») — 1270 → 1289.

## Критерии завершения

- [ ] Шаги 1–8 выполнены.
- [ ] Полный прогон зелёный; тестов baseline + 19.
- [ ] `history_snapshot.py compare base new` — «итого: различий 0».
- [ ] max невязки массы по всем примерам < $10^{-6}$ (ожидается $2.9\cdot10^{-8}$).
- [ ] `mass_balance.png` примера 16 просмотрен: две колонки, добыча и приток различимы.
- [ ] Импорт без циклов (`python -c "import gpn_multiphase_solver.simulator"`).
- [ ] Прототип не изменён (`git diff --stat` не содержит `HydroSolverPrototype/`).
- [ ] Vault: заметки шага 8, реестр, комментарий к #65; issue закрывается при влитии.
- [ ] Время полного прогона — в пределах baseline + ~15 с.

## Обнаруженные проблемы

1. **Застывание состояния у равновесия** (проба `shutin_freeze.py`). Ньютон прототипа принимает шаг без итераций, когда невязка старого состояния ниже `atol_sm3s` = $10^{-11}$ м³ст/с на ячейку (`blackoil.py:299`). У 16 с 21-х суток давление не меняется ни в одном бите, хотя приток с контура на этом состоянии — $5.3\cdot10^{-6}$ м³ст/сут. Влияние на решение ничтожно (последнее изменение давления до застывания — 0.05 Па за сутки), на баланс массы — линейный рост невязки, до порога ~1700 сут. Задачу не блокирует; описывается в README (шаг 6). Регистрировать — по решению пользователя.
2. **Сжимаемость породы: комментарий конфига неверен, энергия её не видит.** `io/config.py:46-48`: «Компрессия породы (пока не используется)», но фабрика передаёт `rock.compressibility` прототипу (`factory.py:301-305`, $\phi(p)$ по экспоненте), уравнение энергии и постановка считают $\phi$ постоянной (`problem_statement.tex:154`, 276: «$c_r = 0$ в данной модели»). При $c_r \ne 0$ гидродинамика и энергия разойдутся по $\phi$; `RockConfig.p_ref` не используется вовсе (опорное давление — $p_0$). Ни один пример $c_r$ не задаёт. Задачу не блокирует; баланс массы по плану корректен при любом $c_r$ (запас — у прототипа). Связано с [[DEBT-008]] (мёртвые поля конфига). Регистрировать — по решению пользователя (свободный номер — DEBT-041).
3. Ссылка реестра DEBT-039 на `blackoil.py:378-380` устарела после DEBT-036 — актуально `:400-402` (отмечено в поле GitHub реестра).

## Оценка

- Файлы: 2 новых модуля, 1 новый файл тестов; правки — 5 файлов кода и тестов ядра, 3 файла тестов, `example_runner.py`, 10 README, 4 заметки vault.
- Строки: ~320 кода (ядро ~120, `examples/mass_balance.py` ~150, прочее ~50), ~330 тестов, ~70 документации.
- Время: ~4.5 ч, из них ~20 мин прогонов.

## Связанные заметки

- [[известные баги и технический долг]] — DEBT-039, DEBT-013, BUG-004, BUG-010, BUG-020, BUG-021, DEBT-037
- [[feat-019 well-regime-change-examples]] — решение 4 (баланс массы вне FEAT-019), проба на примере 16
- [[bug-020 shutin-phase-switching-newton]] — правка соседних строк адаптера
- [[контейнер-simulation-history]], [[модули-simulator-оркестратор]], [[P4-адаптивный-шаг]], [[словарь-код-физика]]
- [[проверка выносится в общий модуль если не зависит от комбинации PVT и ОФП]] — конвенция общих модулей примеров
- [[debt-030 rejected-step-report]] — параллельная правка `blackoil.py` (слияние `7f83ef8`)
- Пробы: `vault/issues/debt-039/probes/` — `mass_balance_baseline.py`, `planned_code_check.py`, `shutin_freeze.py`, `history_snapshot.py`
