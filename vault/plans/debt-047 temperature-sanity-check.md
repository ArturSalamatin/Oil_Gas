---
tags:
  - план
  - рефакторинг
date: 2026-10-07
issue: DEBT-047
github: 76
branch: refactor/debt-047/temperature-sanity-check
status: реализован
worktree: .worktrees/debt-047; удалён после влития
merged: 2ea602f (2026-10-08)
audit:
  date: 2026-10-08
  round: 2
  focus: реализуемость после влития DEBT-015, DEBT-044, DEBT-040, DEBT-031, FEAT-029 — правки «до/после», сигнатуры, тесты, baseline
  found: 5
  auto-fixed: 5
  manual-required: 0
---

# План DEBT-047: отказ при нефизичной температуре и проверка тепловых параметров конфига

**Задача:** DEBT-047 в `vault/roadmap/известные баги и технический долг.md` · GitHub [#76](https://github.com/ArturSalamatin/Oil_Gas/issues/76) · ветка `refactor/debt-047/temperature-sanity-check` в worktree `.worktrees/debt-047` · база `numerical_scheme/implementation` (план — `6b98ffd`, аудит 1 — `cf86aa2`, аудит 2 — `9a4669e`: после влития DEBT-015 `e684ee2`, DEBT-044 `5011af2`, DEBT-040 `1790241`, DEBT-031 `002a96e`, FEAT-029 `f511e39`; шаг 2 переписан под новый `Simulator._advance` DEBT-015)

**Подтип:** рефакторинг с ужесточением проверок: проверка ввода и проверка результата шага. На допустимых данных числа решателя, истории и README примеров не меняются (проверки только читают значения). Прототип не меняется.

## Кратко

Сейчас решатель не проверяет ни температуру после шага энергии, ни тепловые параметры конфига. Нефизичная $T$ доходит до истории без отказа и предупреждения: гидродинамика от $T$ не зависит, поэтому ни один модуль на ней не падает.

Проба `vault/issues/debt-047/probes/red_state.py` (2026-10-07, `9d4321d`, вывод `red_state.out.txt`; повторена аудитом 2 на `9a4669e` — совпадает построчно): `configs/baseline.json`, один подменённый параметр, 24 ч при $p_{wf}$ = 10 МПа (газа нет: $p_b \approx 9.4$ МПа) и 6 МПа (газовая зона у забоя, $S_{g,\max}$ = 0.0999). Эталон: $T$ 349.73…352.24 К при 6 МПа.

| что в конфиге | 10 МПа | 6 МПа | после плана |
|---|---|---|---|
| $c_{p,o} = 0$ | $T_{\min}$ 348.17 К (отклонение 3.9 К) | **$T_{\min}$ 11.8 К** (340 К) | `ValueError` при загрузке |
| $c_{p,o} < 0$ | $T_{\min}$ −690 К | −7947 К | `ValueError` |
| $c_{p,g} = 0$ / $< 0$ | без отличий (газа нет) | отклонение 0.06 / 0.13 К | `ValueError` |
| $(\rho c_p)_s = 0$ | отклонение 0.7 К | 0.9 К | `ValueError` |
| $(\rho c_p)_s < 0$ | $T$ от −3.4e42 до 6.1e37 К, **конечна** | ±7e42 К | `ValueError` |
| $\lambda_s, \lambda_o, \lambda_g < 0$ | отклонение ≤ 0.003 К | ≤ 0.005 К | `ValueError` |
| $c_{p,o} = \infty$, $\lambda_s = \infty$ | отказ scipy `array must not contain infs or NaNs` без имени параметра | то же | `ValueError` с именем |
| $L < 0$ | 5e-10 К (газа нет) | **нагрев +3.2 К** ($T_{\max}$ 355.1 К) | расчёт идёт, предупреждение в журнале |
| в обход проверки ввода: $c_{p,o} < 0$, $(\rho c_p)_s < 0$ | — | $T$ −7947 К, ±7e42 К | `RuntimeError` «Нефизичная температура…» |
| в обход проверки ввода: $c_{p,o} = 0$ | — | $T_{\min}$ = 11.8 К | проходит: $T > 0$ (ограничение критерия) |

Ещё один источник — $B_o < 0$ в таблице PVT: до DEBT-044 $T_{\min} = -245.8$ К (проба DEBT-044, `vault/issues/debt-044/probes/red_state.out.txt`). На входе его закрыл DEBT-044 (влит `5011af2`), проверка $T$ этого плана — второй рубеж.

После правки:
- **`Simulator._advance`** после каждого подшага энергии вызывает новый метод `_check_temperature`. Если $T \le 0$ или $T$ не конечна, он бросает `RuntimeError`. Сообщение называет $\Delta t$ подшага, время его конца (сут), первую от забоя плохую ячейку, её $r$ и $T$, число плохих ячеек. Пример: `Нефизичная температура после шага энергии dt = 3600 с к t = 0.0833 сут: в ячейке 3 (r = 0.9373 м) T = -245.8 К; ячеек с T ≤ 0 или не конечной T — 1 из 10.`
- **`_validate`** (`io/config.py`) проверяет тепловые параметры: $c_{p,o}$, $c_{p,g}$, $(\rho c_p)_s$ — конечные и $> 0$; $\lambda_s$, $\lambda_o$, $\lambda_g$ — конечные и $\ge 0$. При $L < 0$ — предупреждение в журнале, расчёт идёт.
- **P8 §5** и заметка оркестратора описывают обе проверки. В P8 «λ > 0» заменяется на «λ ≥ 0».

Объём: `simulator.py` — вызов в цикле `_advance` и метод (~27 строк с комментариями, новых импортов нет); `io/config.py` — импорт и блок проверок (~35 строк с комментариями); 24 теста (7 в `test_simulator.py`, 17 в `test_config.py`); 2 заметки vault. Тестов: 1405 → 1429, быстрый уровень 1155 → 1179.

**Код плана проверен подменой** — см. раздел «Проверка плана» в конце.

## Как начать работу по этому плану

1. Прочитай этот файл целиком.
2. Прочитай запись DEBT-047 в реестре, тело issue `vault/issues/debt-047/01-issue-body.md` и замер `vault/issues/debt-047/probes/red_state.out.txt`. Варианты решения в issue пронумерованы 1–4; выбраны 1 и 4 (раздел «Решения пользователя» ниже). Тело issue писалось до DEBT-015: его номера строк `simulator.py` и описание рекурсии в `_advance` устарели — верные здесь.
3. Реализация — по `/implement` в worktree `<W>` = `D:\Lessons\Grants\2026\GPN\Oil_Gas\.worktrees\debt-047` (создаёт `/implement`, шаг 1.5). Основной каталог `<КОРЕНЬ>` = `D:\Lessons\Grants\2026\GPN\Oil_Gas` могут занимать параллельные сессии: чужие незакоммиченные правки в `vault/` не трогать и не коммитить. На `9a4669e` worktree других задач нет.
4. Интерпретатор общий, по абсолютному пути (в worktree нет `.venv`):
   ```powershell
   $py = "D:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\.venv\Scripts\python.exe"
   $pr = "<W>\vault\issues\debt-047\probes"
   cd <W>\numerical_solver
   & $py -c "import gpn_multiphase_solver as g; print(g.__file__)"   # путь <W>\... — иначе стоп
   ```
   Все команды pytest и проб — из `<W>\numerical_solver`. Проба берёт код из текущего каталога (`SOLVER = Path.cwd()`) и первой строкой печатает `Код: <путь к simulator.py>`. Путь должен вести в `<W>`.
5. Baseline (замер аудита 2, 2026-10-08, код `9a4669e`):
   ```powershell
   & $py -m pytest tests/ --collect-only -q                # 1405 тестов
   & $py -m pytest tests/ --collect-only -q -m "not slow"  # 1155/1405 (250 deselected)
   & $py -m pytest tests/ -m "not slow" -q                 # быстрый уровень, ~70–90 с
   & $py -m pytest tests/test_simulator.py tests/test_config.py -q   # 146 passed (29 + 117)
   ```
   Если чисел больше, база сдвинулась после аудита. Запиши новые числа и дальше считай от них. План добавляет ровно 24 теста, все в быстром уровне.
6. Если база сдвинулась по `simulator.py`, `io/config.py`, `test_simulator.py`, `test_config.py` или P8 (`git diff --stat 9a4669e HEAD -- <файлы>`), перед шагом 2 запусти пробу плана из `<W>\numerical_solver`: `& $py "$pr\plan_check.py"`. Её этап 1 покажет, какая правка перестала находиться.
7. Начни с шага 1. После каждого шага — его проверка. Полный прогон — шаг 5.

## Контекст для читателя без контекста

**Где считается температура.** `Simulator` (`numerical_solver/gpn_multiphase_solver/simulator.py`) на каждом шаге интегрирования вызывает `_advance` (`:205-300`; единственный вызов — из `run`, `:175`). После DEBT-015 `_advance` идёт циклом `while done < n_units` по подшагам `h` (локальное дробление): подшаг, на котором гидродинамика не сошлась (`HydroConvergenceError`), делится пополам и повторяется; принятый подшаг проходит баланс массы, затем температуру на замороженных $p$, $S_g$, $R_s$ (`self._energy.solve(hydro_result, state, h, bc, collect=balance)`, `:270-271`) и сборку нового `SimulationState` (`:274-281`), с которого начинается следующий подшаг. Решатель энергии в пакете один — `TridiagEnergySolver` (`energy/tridiag.py`); `_energy.solve` вызывается только в `simulator.py:270` (grep `energy.solve`). Поэтому проверка, поставленная сразу после этой строки, видит каждый подшаг. Текст отказа гидродинамики теперь строит `Simulator._failure_message` (`:302-321`).

**Почему нефизичная $T$ проходит молча.** Гидродинамика от $T$ не зависит: Стендинг берёт $T_0$ из конфига (`factory.py:103-115`, `T0=ic.T0`), табличное PVT от $T$ не зависит. $T$ входит только в уравнение энергии, а его решение (`solve_banded`, `tridiag.py:601`) проверяет конечность **входных** коэффициентов (`check_finite=True` по умолчанию), но не знак решения. Проверок `isfinite` / `isnan` в пакете нет, кроме разбора CSV (`factory.py:522`, `:561`).

**Где проверяется конфиг.** `load_config` (`io/config.py:269`) собирает dataclass-секции и вызывает `_validate` (`:328`, определена `:332-376`). Тот проверяет геометрию, сетку, пористость, проницаемость, $p_0$, $T_0 > 0$, $R_{s0}$, шаг, историю и `max_retries`. Тепловые параметры не проверяются: `RockConfig.rho_cp_solid`, `lambda_solid`, `lambda_oil`, `lambda_gas` (`:42-45`), `ThermalConfig.c_p_oil`, `c_p_gas`, `L_degas` (`:89-93`). Они входят в эффективную теплоёмкость и теплопроводность (`tridiag.py:219-225`, ур. (eq. 5), (eq. 7) постановки):

$$(\rho c_p)_{\text{eff}} = (1-\phi)(\rho c_p)_s + \phi\,(S_o \rho_o c_{p,o} + S_g \rho_g c_{p,g}),\qquad \lambda_{\text{eff}} = (1-\phi)\lambda_s + \phi\,(S_o \lambda_o + S_g \lambda_g),$$

а $L$ — в источник дегазации $Q_{deg} = -L\,\dot m$ (`tridiag.py:452`, `:505`). При $\dot m > 0$ (газ выделяется) и $L > 0$ это охлаждение.

**P8 §5 уже требует проверок** (`vault/knowledge/decisions/P8-формат-ввода-json.md:211-215`): «$c_p > 0$; $L$ — любой знак (физически); $\lambda > 0$; $T_0 > 0$». Реализовано только $T_0 > 0$. Правило «$\lambda > 0$» противоречит практике: в 10 примерах (01–09, 04a) $\lambda_s = \lambda_o = \lambda_g = 0$, так в них отключена теплопроводность. План вводит $\lambda \ge 0$ и правит P8.

**Знак $L$.** По корреляции Стендинга $p_b$ растёт с $T$ при заданном $R_s$, значит при заданном $p$ равновесное $R_s$ с ростом $T$ убывает. По принципу Ле Шателье растворение газа экзотермично, а дегазация поглощает теплоту: $L > 0$. Для систем, где растворимость газа растёт с $T$, возможен и $L < 0$ — поэтому P8 записал «любой знак», и пользователь выбрал предупреждение, а не отказ. Во всех конфигах проекта $L \ge 0$ ($L = 0$ в 01, 02, 07, 08, `val001.json`), предупреждение в них не сработает.

**Журнал.** `user_log` (`gpn_multiphase_solver/log.py:33`) — логгер `"gpn_multiphase_solver"`. Обработчик ставит `setup_logging` при `SimulatorFactory.from_config`. Если `load_config` вызван раньше, WARNING всё равно печатается в stderr через «последний» обработчик модуля `logging`. Тесты ловят записи через `caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver")`, как в `test_factory_prototype.py`.

**Решения пользователя (2026-10-07, при планировании):**
1. **Проверка $T$** — в `Simulator._advance` после `energy.solve`, критерий: $T > 0$ и конечна, отказ — `RuntimeError` (вариант 1 issue). Окна правдоподобия $|T - T_0| > \Delta T_{\max}$ нет: порог эвристический, строгой оценки нет (источники Джоуля–Томсона, адиабатический и дегазации нарушают принцип максимума).
2. **Тепловые параметры проверяются в этой задаче** (вариант 4 issue): $c_{p,o}, c_{p,g}, (\rho c_p)_s > 0$; $\lambda_s, \lambda_o, \lambda_g \ge 0$.
3. **$L < 0$ — предупреждение в журнале**, не отказ.
4. **Частичной истории при отказе нет**: `run` прерывается исключением, как при отказе гидродинамики.

**Решения плана (не требовали выбора пользователя):**
5. **Конечность входит в правила параметров:** условие `0 < v < inf` (для λ — `0 <= v < inf`). Python `json` принимает литералы `NaN` и `Infinity`. Запись `v <= 0` пропустила бы NaN (сравнение с NaN всегда `False`). inf проходит `v > 0` и даёт отказ scipy `array must not contain infs or NaNs` без имени параметра (замер, таблица «Кратко»). Существующие проверки (`T0 <= 0` и др.) не трогаются — вне задачи.
6. **Сообщение отказа по $T$ — факты, без догадки о причине**, как у отказа гидродинамики (`Simulator._failure_message`, `simulator.py:302-321`). Называется первая плохая ячейка от забоя, а не самая холодная: при NaN «самой холодной» нет.
7. **Метод `_check_temperature`, а не код внутри `_advance`.** `_advance` уже длинный (96 строк). Метод тестируется через `run`, как остальное поведение `Simulator`.
8. **Проверка $T$ — после `energy.solve`, до сборки состояния подшага.** К этому моменту накопители баланса энергии и массы уже получили вклад подшага. Это неважно: `run` прерывается исключением, и накопители, локальные для `run`, не возвращаются. Следующий подшаг с плохой $T$ не начинается.
9. **Предупреждение о $L$ — в `_validate`, а не в фабрике.** Это свойство конфига, PVT-объект не нужен (в отличие от BUG-019, `_warn_negative_compressibility` в `factory.py:302`). Для этого в `io/config.py` добавляется импорт `user_log`; цикла импортов нет, `log.py` импортирует только `logging`.

## Текущее состояние (baseline)

- Тесты: 1405 всего, 1155 в быстром уровне (HEAD `9a4669e`, замер аудита 2, 2026-10-08). `tests/test_simulator.py` (29) + `tests/test_config.py` (117) — 146 passed.
- Вызовы: `Simulator._advance` — только из `run` (`simulator.py:175`), рекурсии нет (DEBT-015). `Simulator(` создают `factory.py`, `tests/test_simulator.py`, `test_mass_balance.py`, `test_output.py`, `test_val001.py` (grep). `load_config` / `_validate` — 33 файла (тесты, примеры, `io/config.py`); `_validate` вызывается только из `load_config` (`io/config.py:328`).
- Ни один тест и ни один конфиг не задаёт через `load_config` $c_p \le 0$, $(\rho c_p)_s \le 0$, $\lambda < 0$ или $L < 0$ (grep по `numerical_solver/` без `.venv` и прототипа). $\lambda = 0$ — в 10 конфигах примеров, $L = 0$ — в 5 конфигах и в `_minimal_raw` тестов (там `"thermal": {}`, $L$ по умолчанию 0). `test_energy.py`, `test_val002.py` строят `RockConfig` напрямую с $\lambda = 0$ — `_validate` их не касается.
- Ни один тест не гонит `Simulator` с $T \le 0$ (grep `T=np.zeros`, `T0 = 0`). Во всех примерах $T$ в пределах нескольких кельвинов от $T_0$ (README).
- Красное состояние — `vault/issues/debt-047/probes/red_state.out.txt` (таблица в «Кратко»).

## Целевое состояние

- `simulator.py`: в цикле `_advance` сразу после `energy.solve` — вызов `self._check_temperature(T_new, h, hydro_result.state.t)` с комментарием; новый метод `_check_temperature` между `_failure_message` и `_mass_snapshot`. Импорт `DAY_TO_S` уже есть (`:31`, DEBT-015).
- `io/config.py`: импорт `user_log` из `..log`; в `_validate` после проверки проницаемости — блок «Тепловые параметры» (два цикла проверок и предупреждение о $L$).
- Сигнатуры публичных функций и классов не меняются. Новых параметров конфига нет.
- `tests/test_simulator.py`: строки F, G в docstring модуля; раздел G — обёртка `_CorruptingEnergySolver`, класс `TestNonphysicalTemperature` (7 тестов). `tests/test_config.py`: `import logging`, класс `TestValidationThermal` (17 тестов).
- P8 §5 и `модули-simulator-оркестратор.md` описывают проверки.
- Прототип (`HydroSolverPrototype/`), `factory.py`, `energy/`, `tests/_doubles.py` не меняются.

## Варианты и выбор

Подробно — тело issue #76, раздел «Анализ вариантов решения».

| Вариант | Суть | Итог |
|---|---|---|
| 1 | $T > 0$ и конечность в `Simulator._advance` | **выбран** (решение 1) |
| 2 | 1 + окно $\lvert T - T_0\rvert > \Delta T_{\max}$ | отклонён: порог эвристический, новый параметр конфига |
| 3 | проверка в `TridiagEnergySolver` (решение СЛАУ, ёмкости $> 0$) | отклонён: привязан к одной реализации, нет времени шага в удобной форме |
| 4 | тепловые параметры в `_validate` | **выбран** (решение 2), вместе с 1 |

Промежуточные состояния: шаг 2 (проверка $T$) и шаг 3 (параметры) независимы и каждый заканчивается зелёными тестами. Внутри шага тесты пишутся первыми и **не коммитятся** до реализации: тесты и код уходят одним коммитом в конце шага (`/implement` запрещает коммитить сломанное состояние).

## Подводные камни (чеклист)

- ✅ **Все места вызова найдены.** `_energy.solve` вызывается только в `simulator.py:270`, внутри цикла подшагов; `_validate` — только из `load_config`.
- ✅ **Зависимости пакетов:** не меняются. Новый импорт внутри пакета один: `io/config.py` ← `log.py` (`user_log`). `simulator.py` уже импортирует `DAY_TO_S` (`:31`) и `user_log` (`:32`).
- ✅ **Циклические импорты:** `log.py` пакет не импортирует (только `logging`).
- ✅ **Обратная совместимость API:** сигнатуры `Simulator` (с `max_retries=9` после DEBT-015), `run`, `load_config` прежние. Новое поведение — только отказ на данных, которые раньше давали нефизичный результат.
- ✅ **Состояние при ошибке:** `RuntimeError` прерывает `run`. Накопители баланса локальны в `run` и пропадают вместе с ним (решение 8). Объект `Simulator` после отказа повторно не используется — так же, как после отказа гидродинамики (решение 4). `ValueError` в `_validate` бросается до создания `SimulationConfig`.
- ✅ **Отказ не попадает под дробление.** Цикл `_advance` ловит только `HydroConvergenceError` вокруг `self._hydro.solve` (`:250-260`); `RuntimeError` проверки $T$ бросается после этого блока и уходит из `run` наружу с первого раза, подшаг не делится. Так же устроен тест DEBT-015 `test_other_errors_not_subdivided`.
- ⚠️ **NaN в сравнениях.** `T > 0` при NaN даёт `False` без `RuntimeWarning` (numpy 2.5.2, проверено с `-W error`). Плохую ячейку находит `~(np.isfinite(T) & (T > 0))`, первую — `np.argmax` по булеву массиву (первая `True`).
- ✅ **Тесты:** существующие тесты не задают недопустимых тепловых параметров через `load_config` и не гонят `Simulator` с $T \le 0$ (baseline). Проверка подменой: быстрый уровень на коде с правками — 1155 passed.
- ✅ **Docstrings:** однострочные, со ссылкой на DEBT-047; `\eqref{}` нет (проверки, а не формулы).
- ✅ **Конфиги:** имена параметров не меняются, новых нет. Все конфиги проекта проходят новые проверки: $c_p$ 1000…3010, $(\rho c_p)_s$ 1.25e6…2.1e6, $\lambda$ 0…2.5, $L$ 0…230000 (grep по `*.json`).
- ✅ **Побитовая неизменность историй.** Проверки только читают $T$ и параметры, арифметика шага не меняется. Примеры (метка `slow`) пересчитываются полным прогоном шага 5 и сверяются со своими README.
- ✅ **Производительность:** `isfinite` и сравнение на $N \le$ сотен ячеек за подшаг — микросекунды против решения СЛАУ и гидродинамики.
- ✅ **Связь с другими задачами** (на `9a4669e`): DEBT-015, DEBT-044, DEBT-040, DEBT-031, FEAT-029 влиты, план написан против их кода. DEBT-015 переписал `_advance` (локальное дробление) и заменил двойник `SubdividingHydroStub` на `FailingHydroStub` (`tests/_doubles.py:73-97`) — правки шага 2 и тест дробления сделаны под это. DEBT-044 закрыл источник $B_o < 0$ на входе и сдвинул строки P8 — правка P8 ищется по тексту. Открытых worktree других задач нет.
- ✅ **Прототип:** не меняется. Регрессия против `regression/golden/` не нужна.

## Шаги

### Шаг 1: Подготовка — worktree, baseline, красное состояние

**Цель:** ветка от актуальной базы; числа тестов и красное состояние зафиксированы до правки.

**Файлы:** `vault/issues/debt-047/probes/red_state.out.txt` (переснимается и возвращается).

**Что сделать** (из `<W>\numerical_solver`, переменные `$py`, `$pr` — «Как начать», пункт 4):
1. Команды «Как начать работу», пункты 3–6.
2. Воспроизвести красное состояние:
   ```powershell
   & $py "$pr\red_state.py" 2>$null | Tee-Object -FilePath "$pr\red_state.out.txt"
   ```
   Первая строка — `Код: <W>\numerical_solver\gpn_multiphase_solver\simulator.py`, дальше — как в таблице «Кратко». Эталон — закоммиченный `red_state.out.txt`, снятый из основного каталога. После перезаписи `git -C <W> diff -U0 -- vault/issues/debt-047/probes/red_state.out.txt` должен показать ровно одну изменённую строку — первую, с путём к коду (аудит 2 на `9a4669e` так и получил). Любое другое расхождение — стоп, разобраться (база изменила поведение решателя). После сверки вернуть закоммиченный замер, чтобы путь worktree не попал в коммит ветки:
   ```powershell
   git -C <W> checkout -- vault/issues/debt-047/probes/red_state.out.txt
   ```
   Проба создаёт и удаляет `red_state_tmp/` рядом с собой, ~10 с.

**Проверка:** Регресс: быстрый — 1155 passed (или новое число базы).

**Зависимости:** блокирует шаги 2–6.

**Оценка:** 0 строк, ~5 мин.

### Шаг 2: Отказ при нефизичной температуре — тесты, затем `simulator.py`

**Цель:** `Simulator` останавливает расчёт, если после подшага энергии $T \le 0$ или $T$ не конечна; 7 тестов.

**Файлы:** `numerical_solver/tests/test_simulator.py`, `numerical_solver/gpn_multiphase_solver/simulator.py`

**Контекст:** тесты портят $T$ обёрткой решателя энергии, а не нефизичным вводом. Так проверяется сам `Simulator`, независимо от источника плохой $T$. Образец обёртки — `_CountingEnergySolver` (`test_simulator.py:437-451`, раздел F о дроблении). `_make_simulator` (`:52-66`) даёт сетку на 10 ячеек, `LogProfileHydroStub` и настоящий `TridiagEnergySolver`, $\mu_{JT} = 0$, $L = 0$. `_single_interval_schedule()` (`:76-81`) — один интервал 86400 с с шагом 3600 с, то есть 24 вызова энергии, $p_{wf}$ = 10 МПа (выше $p_b$, газа нет). `FailingHydroStub(inner, fails)` (`tests/_doubles.py:73-97`, импортирован в `test_simulator.py:23`) бросает `HydroConvergenceError`, когда `fails(state, dt)` истинно, — `Simulator` тогда делит подшаг пополам (DEBT-015). `lambda s, dt: dt > 1800.0` — короткая безымянная функция: отказ на подшаге длиннее 1800 с. Так же двойник используют тесты раздела F (`_retry_run`, `:454-463`).

`pytest.param` не нужен: `ids=[...]` в `parametrize` даёт имена случаям (`test_nonphysical_T_raises[nan]`). `pytest.raises(...) as exc` сохраняет исключение, его текст — `str(exc.value)`.

**Что сделать:**

2.1. Тесты (красные). В docstring модуля (строки 7-11 перечисляют разделы A–E) добавить строки разделов F и G. Раздел F (дробление, `:435`) в коде уже есть, в docstring его нет; новый раздел этого плана — G:

<!-- правка numerical_solver/tests/test_simulator.py #1 до -->
```python
E. Состав истории: записи на концах интервалов time.history (DEBT-013)
"""
```
<!-- правка numerical_solver/tests/test_simulator.py #1 после -->
```python
E. Состав истории: записи на концах интервалов time.history (DEBT-013)
F. Синхронное дробление шага энергии: подшаги гидро и энергии (BUG-010, DEBT-015)
G. Отказ при нефизичной температуре: T ≤ 0 или не конечна (DEBT-047)
"""
```

В конец файла (после `test_other_errors_not_subdivided`, последняя строка 584) добавить раздел G:

<!-- правка numerical_solver/tests/test_simulator.py #2 в конец -->
```python


# ═══════════════════════════════════════════════════════════
# G. Отказ при нефизичной температуре (DEBT-047)
# ═══════════════════════════════════════════════════════════
#
# Гидродинамика от T не зависит (PVT при T0), поэтому до DEBT-047 нефизичная T
# доходила до истории без отказа и предупреждения: B_o < 0 в таблице до
# DEBT-044 дало T_min = −245.8 К (vault/issues/debt-044/probes/red_state.out.txt),
# c_p,o < 0 в конфиге — −7947 К (vault/issues/debt-047/probes/red_state.out.txt).
# Тесты портят T обёрткой решателя энергии: ввод допустим, отказ обязан дать
# сам Simulator, откуда бы ни взялась нефизичная T.


class _CorruptingEnergySolver:
    """Обёртка решателя энергии: на вызове on_call ставит T[cell] = value.

    Физику не подменяет — делегирует настоящему TridiagEnergySolver и портит
    только его результат.
    """

    def __init__(self, inner, value, cell=3, on_call=2):
        self._inner = inner
        self._value = value
        self._cell = cell
        self._on_call = on_call
        self.n_calls = 0

    def solve(self, hydro_result, state_prev, dt, bc, collect=None):
        T = self._inner.solve(hydro_result, state_prev, dt, bc, collect)
        self.n_calls += 1
        if self.n_calls == self._on_call:
            T = T.copy()
            T[self._cell] = self._value
        return T


class TestNonphysicalTemperature:
    """Simulator останавливает расчёт, если после шага энергии T ≤ 0 или не конечна."""

    @pytest.mark.parametrize("value", [
        -245.8,     # порядок замера DEBT-044 (B_o < 0 в таблице)
        0.0,        # граница: абсолютный нуль недопустим
        np.nan,     # NaN — не число: ловит isfinite
        np.inf,
        -np.inf,
    ], ids=["negative", "zero", "nan", "inf", "minus_inf"])
    def test_nonphysical_T_raises(self, value):
        """Отказ называет шаг, время его конца, ячейку, её r и значение T.

        24 шага по 1 ч, T испорчена на втором вызове энергии: конец шага
        t = 7200 с = 0.0833 сут, ячейка 3 из 10.
        """
        grid, pvt, hydro, inner_energy, _ = _make_simulator()
        energy = _CorruptingEnergySolver(inner_energy, value, cell=3, on_call=2)
        sim = Simulator(grid, hydro, energy, pvt, _single_interval_schedule())

        with pytest.raises(RuntimeError, match="Нефизичная температура") as exc:
            sim.run(_initial_state())

        msg = str(exc.value)
        assert "dt = 3600 с" in msg
        assert "t = 0.0833 сут" in msg
        assert f"в ячейке 3 (r = {grid.r_centers[3]:.4g} м)" in msg
        assert f"T = {value:.6g} К" in msg
        assert "1 из 10" in msg
        # Расчёт остановлен на испорченном шаге, а не дошёл до конца
        assert energy.n_calls == 2

    def test_small_positive_T_passes(self):
        """T = 1 К нефизична для пласта, но положительна — расчёт идёт.

        Критерий — только T > 0 и конечность (решение DEBT-047), окна
        правдоподобия нет: тест ловит порог, добавленный без решения.
        Без JT и дегазации, при стационарном p схема энергии монотонна,
        и T дальше остаётся положительной.
        """
        grid, pvt, hydro, inner_energy, _ = _make_simulator()
        energy = _CorruptingEnergySolver(inner_energy, 1.0, cell=3, on_call=2)
        sim = Simulator(grid, hydro, energy, pvt, _single_interval_schedule())

        history = sim.run(_initial_state())

        assert energy.n_calls == 24
        assert history.times[-1] == pytest.approx(86400.0)
        assert np.all(history.states[-1].T > 0)

    def test_raises_under_subdivision(self):
        """Проверка работает и на подшагах локального дробления (DEBT-015).

        Гидро отказывает на шаге 3600 с: Simulator делит его пополам и
        проходит двумя подшагами по 1800 с. Отказавший шаг энергию не
        вызывает — первый вызов энергии и есть первый подшаг. T испорчена
        на нём: отказ называет его dt и не делит подшаг дальше (дробление
        ловит только HydroConvergenceError).
        """
        grid, pvt, inner_hydro, inner_energy, _ = _make_simulator()
        hydro = FailingHydroStub(inner_hydro, lambda s, dt: dt > 1800.0)
        energy = _CorruptingEnergySolver(inner_energy, -1.0, cell=0, on_call=1)
        schedule = _single_interval_schedule(dt_hist=3600.0, dt_int=3600.0)
        sim = Simulator(grid, hydro, energy, pvt, schedule)

        with pytest.raises(RuntimeError, match="Нефизичная температура") as exc:
            sim.run(_initial_state())

        msg = str(exc.value)
        assert "dt = 1800 с" in msg
        assert "в ячейке 0" in msg
        assert hydro.dt_calls == [3600.0, 1800.0]
        assert energy.n_calls == 1
```

Запуск: `& $py -m pytest tests/test_simulator.py -q` — ожидание до реализации: **6 failed, 30 passed** (29 прежних + `test_small_positive_T_passes`: он проходит и сейчас и защищает от лишней строгости).

2.2. Реализация. Вызов проверки — в цикле `_advance` сразу после `energy.solve` (строки 270-273, отступ 12 пробелов, шаг — подшаг `h`):

<!-- правка numerical_solver/gpn_multiphase_solver/simulator.py #1 до -->
```python
            T_new = self._energy.solve(
                hydro_result, state, h, bc, collect=balance)

            # 3. Обновить состояние (splitting: T из energy, остальное из hydro)
```
<!-- правка numerical_solver/gpn_multiphase_solver/simulator.py #1 после -->
```python
            T_new = self._energy.solve(
                hydro_result, state, h, bc, collect=balance)

            # 2a. Нефизичная T — отказ (DEBT-047). Гидродинамика от T не зависит
            # (PVT при T0), поэтому без этой проверки T ≤ 0 доходит до истории
            # как обычный результат: B_o < 0 в таблице до DEBT-044 дало
            # T_min = −245.8 К (vault/issues/debt-044/probes/red_state.out.txt).
            # Проверка здесь, а не в решателе энергии: одна на любой
            # EnergySolver и на каждом подшаге — следующий подшаг с плохой T не
            # начинается. RuntimeError не HydroConvergenceError: подшаг не
            # делится, отказ уходит из run. Накопители баланса к этому моменту
            # уже получили вклад подшага — неважно: run их не возвращает.
            self._check_temperature(T_new, h, hydro_result.state.t)

            # 3. Обновить состояние (splitting: T из energy, остальное из hydro)
```

Метод — между `_failure_message` и `_mass_snapshot` (строки 321-323):

<!-- правка numerical_solver/gpn_multiphase_solver/simulator.py #2 до -->
```python
            f"не сходится и при мелких подшагах, причина не в его величине.")

    def _mass_snapshot(self, mass: MassBalanceAccumulator | None,
```
<!-- правка numerical_solver/gpn_multiphase_solver/simulator.py #2 после -->
```python
            f"не сходится и при мелких подшагах, причина не в его величине.")

    def _check_temperature(self, T: np.ndarray, dt: float, t: float) -> None:
        """Отказ, если после шага энергии T ≤ 0 или не конечна (DEBT-047)."""
        # NaN и ±inf отсекает isfinite, T ≤ 0 — сравнение
        bad = ~(np.isfinite(T) & (T > 0))
        if not bad.any():
            return
        # Сообщение — факты, а не догадка о причине, как у отказа
        # гидродинамики (_failure_message): первая от забоя плохая ячейка,
        # её r и T, число таких ячеек. t — время конца подшага; dt — его
        # длина (при локальном дроблении — подшаг, а не шаг расписания).
        j = int(np.argmax(bad))
        r = float(self._grid.r_centers[j])
        raise RuntimeError(
            f"Нефизичная температура после шага энергии dt = {dt:g} с к "
            f"t = {t / DAY_TO_S:.4f} сут: в ячейке {j} (r = {r:.4g} м) "
            f"T = {T[j]:.6g} К; ячеек с T ≤ 0 или не конечной T — "
            f"{int(np.count_nonzero(bad))} из {T.size}.")

    def _mass_snapshot(self, mass: MassBalanceAccumulator | None,
```

`np.argmax` по булеву массиву возвращает индекс первого `True`. `f"{dt:g}"`: 3600.0 → `3600`, 7.03125 → `7.03125`. `DAY_TO_S` уже импортирован (`simulator.py:31`), новых импортов нет.

**Проверка после этого шага:**
- `& $py -m pytest tests/test_simulator.py -q` — 36 passed.
- Регресс: быстрый — 1162 passed (1155 + 7).
- Коммит: тесты и `simulator.py` одним коммитом.

**Подводные камни:** NaN в сравнениях; отказ не попадает под дробление (чеклист) — тест `test_raises_under_subdivision` проверяет и dt подшага, и то, что после отказа гидро не вызывалась (`hydro.dt_calls == [3600.0, 1800.0]`).

**Зависимости:** требует шаг 1. Независим от шага 3.

**Оценка:** ~27 строк кода, ~105 строк тестов, ~20 мин.

### Шаг 3: Проверка тепловых параметров — тесты, затем `io/config.py`

**Цель:** `load_config` отвергает $c_p \le 0$, $(\rho c_p)_s \le 0$, $\lambda < 0$ и не конечные значения этих параметров, а при $L < 0$ предупреждает; 17 тестов.

**Файлы:** `numerical_solver/tests/test_config.py`, `numerical_solver/gpn_multiphase_solver/io/config.py`

**Контекст:** образец тестов — `TestValidationRock` / `TestValidationInitial` (`test_config.py:354-391`): `_minimal_raw()` (`:252-266`) → правка словаря → `_write_json` (`:245-249`, `json.dumps`) → `load_config`. `json.dumps(float("nan"))` пишет литерал `NaN`, `json.loads` читает его обратно как float NaN — так тест проверяет ввод NaN из файла. В `_minimal_raw` секция `"thermal": {}` и `"rock"` без тепловых ключей, то есть значения по умолчанию из dataclass (`io/config.py:42-45`, `:89-93`, $L = 0$). Образец теста журнала — `test_factory_prototype.py`, тесты с `caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver")`.

**Что сделать:**

3.1. Тесты (красные). В docstring модуля (строки 3-9) добавить пункт:

<!-- правка numerical_solver/tests/test_config.py #1 до -->
```python
- Валидацию: отсутствующие секции, невалидные значения.
```
<!-- правка numerical_solver/tests/test_config.py #1 после -->
```python
- Валидацию: отсутствующие секции, невалидные значения.
- Тепловые параметры: c_p, (ρc_p)_s > 0, λ ≥ 0, предупреждение при L < 0 (DEBT-047).
```

Импорт `logging` (строки 11-13):

<!-- правка numerical_solver/tests/test_config.py #2 до -->
```python
import json
import pytest
from pathlib import Path
```
<!-- правка numerical_solver/tests/test_config.py #2 после -->
```python
import json
import logging
import pytest
from pathlib import Path
```

Новый класс — после `TestMaxRetriesValidation`, перед разделом E (строки 508-513):

<!-- правка numerical_solver/tests/test_config.py #3 до -->
```python
    def test_bool_rejected(self, tmp_path):
        """bool — подкласс int, но True как лимит бессмыслен."""
        raw = _minimal_raw()
        raw["numerics"] = {"max_retries": True}
        with pytest.raises(ValueError, match="max_retries"):
            load_config(_write_json(tmp_path, raw))
```
<!-- правка numerical_solver/tests/test_config.py #3 после -->
```python
    def test_bool_rejected(self, tmp_path):
        """bool — подкласс int, но True как лимит бессмыслен."""
        raw = _minimal_raw()
        raw["numerics"] = {"max_retries": True}
        with pytest.raises(ValueError, match="max_retries"):
            load_config(_write_json(tmp_path, raw))


class TestValidationThermal:
    """Тепловые параметры (DEBT-047, P8 §5).

    Ошибка в них не роняет расчёт, а даёт правдоподобную, но неверную T.
    Комментарии к случаям — замер до DEBT-047 (vault/issues/debt-047/probes/
    red_state.out.txt: baseline, 24 ч; отклонение — от эталона по всем
    записям и ячейкам): все случаи проходили load_config и run без сообщения.
    """

    @pytest.mark.parametrize("section, key, value", [
        # p_wf = 6 МПа: T_min = 11.8 К при эталоне 349.7 К
        ("thermal", "c_p_oil", 0.0),
        # T_min = −7947 К
        ("thermal", "c_p_oil", -2000.0),
        # NaN проходит `v <= 0` молча; JSON допускает литерал NaN
        ("thermal", "c_p_oil", float("nan")),
        # отказ scipy в СЛАУ энергии без имени параметра
        ("thermal", "c_p_oil", float("inf")),
        # газовая зона: отклонение T 0.06 и 0.13 К
        ("thermal", "c_p_gas", 0.0),
        ("thermal", "c_p_gas", -1000.0),
        # отклонение 0.9 К; при (ρc_p)_s < 0 — T до ±7e42 К, конечна
        ("rock", "rho_cp_solid", 0.0),
        ("rock", "rho_cp_solid", -1.25e6),
        # обратная теплопроводность: отклонение — тысячные доли кельвина
        ("rock", "lambda_solid", -1.5),
        ("rock", "lambda_oil", -0.14),
        ("rock", "lambda_gas", -0.04),
        ("rock", "lambda_solid", float("nan")),
        ("rock", "lambda_solid", float("inf")),
    ], ids=["c_p_oil_zero", "c_p_oil_negative", "c_p_oil_nan", "c_p_oil_inf",
            "c_p_gas_zero", "c_p_gas_negative",
            "rho_cp_solid_zero", "rho_cp_solid_negative",
            "lambda_solid_negative", "lambda_oil_negative", "lambda_gas_negative",
            "lambda_solid_nan", "lambda_solid_inf"])
    def test_invalid_rejected(self, tmp_path, section, key, value):
        """Недопустимое значение → ValueError с полным именем параметра."""
        raw = _minimal_raw()
        raw[section][key] = value
        with pytest.raises(ValueError, match=f"{section}.{key}"):
            load_config(_write_json(tmp_path, raw))

    def test_zero_conductivity_accepted(self, tmp_path):
        """λ = 0 — штатный режим «без теплопроводности» (примеры 01–09, 04a)."""
        raw = _minimal_raw()
        raw["rock"].update(lambda_solid=0.0, lambda_oil=0.0, lambda_gas=0.0)
        cfg = load_config(_write_json(tmp_path, raw))
        assert cfg.rock.lambda_solid == 0.0

    def test_negative_L_warns(self, tmp_path, caplog):
        """L < 0 — предупреждение, не отказ: физически возможно (P8 §5).

        Q_deg = −L·ṁ: при L < 0 выделение газа нагревает пласт (замер:
        T_max 355.1 К против 352.2 К у эталона при p_wf = 6 МПа).
        """
        raw = _minimal_raw()
        raw["thermal"]["L_degas"] = -1.68e5
        with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
            cfg = load_config(_write_json(tmp_path, raw))
        assert cfg.thermal.L_degas == -1.68e5
        text = "\n".join(r.getMessage() for r in caplog.records
                         if r.levelno >= logging.WARNING)
        assert "thermal.L_degas" in text

    @pytest.mark.parametrize("L", [0.0, 1.68e5], ids=["zero", "positive"])
    def test_nonnegative_L_no_warning(self, tmp_path, caplog, L):
        """L ≥ 0 — без предупреждения; L = 0 (теплота дегазации выключена) — граница."""
        raw = _minimal_raw()
        raw["thermal"]["L_degas"] = L
        with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
            load_config(_write_json(tmp_path, raw))
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]
```

Запуск: `& $py -m pytest tests/test_config.py -q` — ожидание до реализации: **14 failed, 120 passed** (117 прежних + 3 новых: `test_zero_conductivity_accepted` и оба `test_nonnegative_L_no_warning` проходят и сейчас — они защищают от лишней строгости).

3.2. Реализация. Импорт журнала (строка 12):

<!-- правка numerical_solver/gpn_multiphase_solver/io/config.py #1 до -->
```python
from typing import Optional
```
<!-- правка numerical_solver/gpn_multiphase_solver/io/config.py #1 после -->
```python
from typing import Optional

from ..log import user_log
```

Блок проверок — в `_validate` после проницаемости (строки 348-351):

<!-- правка numerical_solver/gpn_multiphase_solver/io/config.py #2 до -->
```python
    if r.permeability <= 0:
        raise ValueError(f"permeability должна быть > 0, получено {r.permeability}")

    ic = cfg.initial_conditions
```
<!-- правка numerical_solver/gpn_multiphase_solver/io/config.py #2 после -->
```python
    if r.permeability <= 0:
        raise ValueError(f"permeability должна быть > 0, получено {r.permeability}")

    # Тепловые параметры (DEBT-047, P8 §5). Ошибка в них не роняет расчёт,
    # а даёт правдоподобную, но неверную T. Замер до DEBT-047
    # (vault/issues/debt-047/probes/red_state.out.txt, baseline, 24 ч):
    # c_p,o = 0 при p_wf = 6 МПа — T_min = 11.8 К; (ρc_p)_s = 0 — 0.9 К
    # отклонения; λ < 0 — тысячные доли кельвина. Условие `0 < v < inf`
    # отсекает и NaN (JSON допускает литералы NaN и Infinity, сравнение с NaN
    # всегда False), и inf (иначе отказ дала бы scipy в СЛАУ энергии —
    # «array must not contain infs or NaNs», без имени параметра).
    inf = float("inf")
    th = cfg.thermal
    for name, value in (("rock.rho_cp_solid", r.rho_cp_solid),
                        ("thermal.c_p_oil", th.c_p_oil),
                        ("thermal.c_p_gas", th.c_p_gas)):
        if not (0 < value < inf):
            raise ValueError(f"{name} должна быть конечной и > 0, получено {value}")
    # λ = 0 допустимо: так отключают теплопроводность (примеры 01–09, 04a)
    for name, value in (("rock.lambda_solid", r.lambda_solid),
                        ("rock.lambda_oil", r.lambda_oil),
                        ("rock.lambda_gas", r.lambda_gas)):
        if not (0 <= value < inf):
            raise ValueError(f"{name} должна быть конечной и ≥ 0, получено {value}")
    # L < 0 — предупреждение, не отказ (решение пользователя, DEBT-047).
    # Q_deg = −L·ṁ (energy/tridiag.py, compute_degassing): при L < 0
    # выделение газа нагревает пласт (замер: +3.2 К при p_wf = 6 МПа).
    # По Стендингу p_b растёт с T, то есть при заданном p R_s с ростом T
    # убывает: растворение газа экзотермично, дегазация поглощает теплоту,
    # L > 0. Для систем, где растворимость газа растёт с T, L < 0 физически
    # возможен (P8 §5), поэтому расчёт не запрещается.
    if th.L_degas < 0:
        user_log.warning(
            f"thermal.L_degas = {th.L_degas} Дж/кг < 0: выделение газа в расчёте "
            f"нагревает пласт (Q_deg = −L·ṁ > 0); при L > 0 дегазация охлаждает. "
            f"Проверьте знак.")

    ic = cfg.initial_conditions
```

`not (0 < value < inf)` — цепочка сравнений Python: `0 < value and value < inf`. Для NaN обе части `False`, отрицание — `True`, то есть отказ. `float("inf")` вместо `math.inf`: в проекте `math` не используется (CLAUDE.md).

**Проверка после этого шага:**
- `& $py -m pytest tests/test_config.py -q` — 134 passed.
- Регресс: быстрый — 1179 passed (1162 + 17; если шаг 2 ещё не сделан — 1172).
- Коммит: тесты и `io/config.py` одним коммитом.

**Подводные камни:** граница включается для λ ($\lambda = 0$ — 10 примеров) и не включается для $c_p$, $(\rho c_p)_s$ — тесты `test_zero_conductivity_accepted` и случаи `*_zero`; конфиги проекта проходят (чеклист «Конфиги»).

**Зависимости:** требует шаг 1. Независим от шага 2.

**Оценка:** ~35 строк кода, ~80 строк тестов, ~20 мин.

### Шаг 4: Зелёное состояние пробы и документация

**Цель:** проба показывает отказы на месте молчаливых расчётов; P8 и заметка оркестратора описывают обе проверки.

**Файлы:** `vault/issues/debt-047/probes/green_state.out.txt` (новый), `vault/knowledge/decisions/P8-формат-ввода-json.md`, `vault/knowledge/decisions/модули-simulator-оркестратор.md`

**Что сделать:**
1. Зелёное состояние:
   ```powershell
   & $py "$pr\red_state.py" 2>$null | Tee-Object -FilePath "$pr\green_state.out.txt"
   ```
   Ожидание (проверено подменой на `9a4669e`, «Проверка плана», этап 4):
   - разделы 1–2 (10 и 6 МПа): эталон — как в красном замере; все случаи $c_p$, $(\rho c_p)_s$, $\lambda$ (включая inf) — `load_config: ValueError: <секция>.<параметр> должна быть конечной и …`; `L_degas_negative` — `ПРОШЛИ` с теми же числами, что в красном замере, и строкой `журнал: thermal.L_degas = -168000.0 Дж/кг < 0: …`; `L_degas_nan`, `mu_JT_oil_nan` — как в красном замере (отказ scipy, вне задачи);
   - раздел 3 (в обход `_validate`): `c_p_oil_negative` — `run: RuntimeError: Нефизичная температура после шага энергии dt = 3600 с к t = 0.0417 сут: в ячейке 0 (r = 0.1032 м) T = -2.71906 К; ячеек с T ≤ 0 или не конечной T — 14 из 100.`; `rho_cp_solid_negative` — то же к t = 0.1667 сут, T = -926753 К, 62 из 100; `c_p_oil_zero` — `ПРОШЛИ`, $T_{\min}$ 11.8 К (ограничение критерия, решение 1).
   Первую строку (`Код: <W>\...`) в зелёном замере оставить: он снимается из worktree и коммитится вместе с кодом.
2. P8 §5 — правила тепловых параметров и проверка $T$ (строки 211-215; после DEBT-044 номера сдвинулись — ищи по тексту):

<!-- правка vault/knowledge/decisions/P8-формат-ввода-json.md #1 до -->
```markdown
Валидация данных для температуры — ответственность нашего Factory/config:
- c_p > 0
- L_degas — любой знак (физически)
- λ > 0
- T0 > 0
```
<!-- правка vault/knowledge/decisions/P8-формат-ввода-json.md #1 после -->
```markdown
Валидация данных для температуры — ответственность нашего config (`_validate`, `io/config.py`; DEBT-047):
- `thermal.c_p_oil`, `thermal.c_p_gas`, `rock.rho_cp_solid` — конечные и > 0
- `rock.lambda_solid`, `rock.lambda_oil`, `rock.lambda_gas` — конечные и ≥ 0: λ = 0 отключает теплопроводность (примеры 01–09, 04a). До DEBT-047 здесь стояло «λ > 0», но проверки не было, а примеры с λ = 0 ему противоречили
- `thermal.L_degas` — любой знак (физически); L < 0 — предупреждение в журнале, расчёт идёт. Для Стендинга L > 0: $p_b$ растёт с T, растворение газа экзотермично, дегазация поглощает теплоту; L < 0 возможен для систем, где растворимость газа растёт с T
- `initial_conditions.T0` > 0
- для шести параметров $c_p$, $(\rho c_p)_s$, λ литералы JSON `NaN` и `Infinity` отвергаются теми же проверками

Температура в расчёте — `Simulator._advance` после каждого подшага энергии (DEBT-047): $T \le 0$ или не конечная $T$ → `RuntimeError` с $\Delta t$ подшага, временем его конца, ячейкой, $r$ и значением. Правдоподобную, но неверную $T$ эта проверка не ловит: $c_{p,o} = 0$ в обход проверки ввода даёт $T_{\min} = 11.8$ К (`vault/issues/debt-047/probes/red_state.out.txt`).
```

3. Заметка оркестратора — пункт о проверке $T$ в списке «Ключевые отличия от плана» (строки 107-108):

<!-- правка vault/knowledge/decisions/модули-simulator-оркестратор.md #1 до -->
```markdown
  на каждой записи `_mass_snapshot` берёт у решателя запас текущего состояния.
  У двойников без запаса снимки — `None`
```
<!-- правка vault/knowledge/decisions/модули-simulator-оркестратор.md #1 после -->
```markdown
  на каждой записи `_mass_snapshot` берёт у решателя запас текущего состояния.
  У двойников без запаса снимки — `None`
- после каждого подшага энергии `_advance` проверяет температуру
  (`_check_temperature`, DEBT-047): $T \le 0$ или не конечная $T$ →
  `RuntimeError` с $\Delta t$ подшага, временем его конца, ячейкой, $r$ и
  значением. Гидродинамика от $T$ не зависит, поэтому без проверки
  нефизичная $T$ доходила до истории молча. Проверка одна на любой
  `EnergySolver`; отказ не дробится — дробление ловит только
  `HydroConvergenceError` (DEBT-015)
```

**Проверка:** Регресс: только документы и замер — `& $py -m pytest tests/ --collect-only -q` (1429).

**Зависимости:** требует шаги 2–3.

**Оценка:** ~15 строк документов, ~10 мин.

### Шаг 5: Верификация — полный прогон

**Цель:** весь набор тестов зелёный.

```powershell
& $py -m pytest tests/ -q        # 1429 passed, ~10 мин
```

Регресс: полный — конец реализации (`/implement` §3.1). Примеры (`test_examples.py`, метка `slow`) идут через `load_config` и `Simulator`: это проверка того, что все конфиги примеров проходят новые правила и ни на одном подшаге ни одного примера не появляется $T \le 0$.

**Зависимости:** требует шаги 2–4.

**Оценка:** ~10 мин.

### Шаг 6: Vault и issue

**Цель:** задача отмечена реализованной, issue прокомментирован.

**Что сделать:**
1. Реестр, запись DEBT-047: статус «✅ ГОТОВО (<дата>), не влит — ветка …: 1405 → 1429 тестов, полный прогон зелёный; отказ по $T$ и проверки тепловых параметров (`green_state.out.txt`)».
2. План: `status: реализован`.
3. Комментарий в issue #76: `vault/issues/debt-047/05-comment-done.md` (итог, числа тестов, ссылки на `red_state.out.txt`, `green_state.out.txt`).

**Зависимости:** требует шаг 5.

**Оценка:** ~10 мин.

## Тестовая стратегия

| Тест | Файл | Сценарий | Ожидание | Предотвращает |
|---|---|---|---|---|
| `test_nonphysical_T_raises` ×5 | `tests/test_simulator.py` (раздел G, новый) | обёртка ставит $T$ = −245.8, 0, NaN, inf, −inf в ячейку 3 на втором шаге | `RuntimeError` «Нефизичная температура», в тексте `dt = 3600 с`, `t = 0.0833 сут`, ячейка 3 и её $r$, значение, `1 из 10`; энергия вызвана 2 раза | молчаливый расчёт с нефизичной $T$ (до правки $T_{\min}$ = −245.8 К и −7947 К) |
| `test_small_positive_T_passes` | там же | $T$ = 1 К | расчёт доходит до 24 ч, $T > 0$ | порог правдоподобия, введённый без решения |
| `test_raises_under_subdivision` | там же | гидро отказывает на 3600 с, Simulator делит шаг пополам; $T$ = −1 К в ячейке 0 на первом подшаге | `RuntimeError`, `dt = 1800 с`, ячейка 0; гидро вызвана `[3600, 1800]`, энергия — 1 раз | проверка мимо подшагов дробления; отказ по $T$, принятый за отказ сходимости и раздробленный |
| `test_invalid_rejected` ×13 | `tests/test_config.py` (`TestValidationThermal`, новый) | $c_{p,o}$ = 0, −2000, NaN, inf; $c_{p,g}$ = 0, −1000; $(\rho c_p)_s$ = 0, −1.25e6; $\lambda_s$, $\lambda_o$, $\lambda_g$ < 0; $\lambda_s$ = NaN, inf | `ValueError`, в тексте `<секция>.<параметр>` | правдоподобная, но неверная $T$ (замер — комментарий к каждому случаю) |
| `test_zero_conductivity_accepted` | там же | $\lambda_s = \lambda_o = \lambda_g = 0$ | загружается | строгое неравенство для λ: отвергло бы 10 примеров |
| `test_negative_L_warns` | там же | $L = -1.68\cdot10^5$ | загружается, WARNING с `thermal.L_degas` | отказ вместо предупреждения (решение 3) или молчание |
| `test_nonnegative_L_no_warning` ×2 | там же | $L$ = 0 и $1.68\cdot10^5$ | загружается без WARNING | ложное предупреждение на конфигах проекта |

**Неизменность поведения:**
- `tests/test_simulator.py` (29 тестов до правки, включая раздел F о дроблении: `TestEnergySubstepsUnderRetry`, DEBT-015) и `tests/test_config.py` (117) — без правок, зелёные;
- `tests/test_examples.py` (slow) — все примеры считаются, их README-числа прежние;
- `tests/test_energy.py`, `test_val002.py` строят `RockConfig` с $\lambda = 0$ напрямую — `_validate` их не касается.

## Критерии завершения

- [ ] Шаги 1–6 выполнены
- [ ] Быстрый уровень 1179 passed; полный 1429 passed (или база + 24)
- [ ] Красный замер воспроизведён из worktree (шаг 1); зелёный — `green_state.out.txt` по ожиданию шага 4
- [ ] Прототип, `factory.py`, `energy/`, `tests/_doubles.py` не изменены (`git diff --stat <база> -- numerical_solver/HydroSolverPrototype numerical_solver/gpn_multiphase_solver/factory.py numerical_solver/gpn_multiphase_solver/energy numerical_solver/tests/_doubles.py` пуст)
- [ ] P8 §5 и `модули-simulator-оркестратор.md` описывают проверки
- [ ] Реестр, план, комментарий issue обновлены

## Обнаруженные проблемы

Новых записей в реестр план не добавляет:
- **$L$ и $\mu_{JT}$ = NaN** (замер, разделы 1–2 пробы): расчёт падает в scipy (`array must not contain infs or NaNs`), но сообщение не называет параметр. Это громкий отказ, а не молчаливый, и знаки $L$, $\mu_{JT}$ проверка не ограничивает (решение 3; $\mu_{JT}$ — любого знака по физике). Если нужна проверка конечности всех тепловых скаляров — отдельная запись, по решению пользователя;
- **правдоподобная, но неверная $T$** (например, $c_{p,o} = 0$ в обход проверки ввода — $T_{\min}$ = 11.8 К) проверкой $T$ не ловится — сознательное ограничение (решение 1), не долг;
- **P8 §5 расходился с практикой** («λ > 0» при 10 примерах с λ = 0) — исправляется шагом 4;
- **(аудит 2)** `модули-simulator-оркестратор.md:105-106` после DEBT-015 устарела: «пробный шаг при дроблении отброшен раньше» — пробного шага больше нет (локальное дробление). Это хвост документации DEBT-015, не этой задачи; план добавляет пункт рядом и устаревшую фразу не трогает.

## Оценка

`simulator.py` ~+27 строк, `io/config.py` ~+35 строк, тесты ~+185 строк, документы ~+15 строк. Время реализации ~1 ч, из них ~10 мин — полный прогон.

## Проверка плана

Проба `vault/issues/debt-047/probes/plan_check.py` (вывод — `plan_check.out.txt`). Она берёт правки прямо из этого файла: перед каждым блоком кода стоит метка `<!-- правка <файл> #N до|после|в конец -->`. Правки применяются к текстам файлов в памяти, файлы проекта не меняются. Код `simulator.py` и `io/config.py` с правками исполняется в пространствах имён загруженных модулей (подмена в памяти). Классы при этом остаются прежними объектами, им передаются новые методы: так `factory.py`, импортировавший `Simulator` раньше, видит новый код. Файлы тестов с правками пишутся во временный каталог рядом с пробой (вместе с копией `tests/_doubles.py`) и прогоняются настоящим pytest. Каждый этап — отдельный процесс.

История: план (2026-10-07, `6b98ffd`) и аудит 1 (2026-10-08, `cf86aa2`) проверяли прежний `_advance` с рекурсией; после влития DEBT-015 те правки `simulator.py` и тест дробления на `SubdividingHydroStub` перестали применяться, аудит 2 переписал шаг 2 под новый код.

Прогон аудита 2 (2026-10-08, код `9a4669e`, `plan_check.py --fast`):

1. Все 11 правок применимы: каждый блок «до» встречается в своём файле ровно один раз (2 в `simulator.py`, 2 в `io/config.py`, 2 в `test_simulator.py`, из них 1 «в конец», 3 в `test_config.py`, по 1 в P8 и заметке оркестратора). Добавленные строки кода — не длиннее 88 символов.
2. Тесты плана на текущем коде: 20 failed, 150 passed (146 прежних + `test_small_positive_T_passes`, `test_zero_conductivity_accepted`, 2 × `test_nonnegative_L_no_warning`).
3. На коде с правками: 170 passed; с настройками pytest проекта, хуком `conftest.py` и `-m "not slow"` — тоже 170 passed (все новые тесты в быстром уровне). В том числе `test_raises_under_subdivision` на `FailingHydroStub`: гидро вызвана `[3600, 1800]`, энергия — 1 раз, отказ не раздроблен.
4. Проба `red_state.py` на коде с правками: эталоны и `L_degas_negative` совпадают с красным замером по печатаемым числам, у `L_degas_negative` — строка журнала с предупреждением; все 11 случаев $c_p$, $(\rho c_p)_s$, λ отвергнуты в `load_config` с именем параметра; в обход `_validate` — `RuntimeError` для $c_{p,o} < 0$ (к 0.0417 сут) и $(\rho c_p)_s < 0$ (к 0.1667 сут), $c_{p,o} = 0$ проходит с $T_{\min}$ 11.8 К (ожидаемое ограничение). Красный замер без подмены на `9a4669e` совпал с сохранённым построчно (кроме строки пути).
5. Быстрый уровень существующих тестов на коде с правками: 1155 passed, 250 deselected, 1 warning. Без подмены — то же: 1155 passed, 1 warning (`PytestRemovedIn10Warning` о фикстуре класса, к задаче не относится).

Полный вывод — `vault/issues/debt-047/probes/plan_check.out.txt`.

При реализации правки вносятся Edit-ом по тем же блокам «до → после».

## Связанные заметки

- [[известные баги и технический долг]] — записи DEBT-047, DEBT-044, DEBT-015, BUG-010
- [[P8-формат-ввода-json]] — §5 «Валидация»
- [[модули-simulator-оркестратор]] — `Simulator._advance`
- [[debt-044 csv-table-value-checks]] — проверка таблиц, источник замера $B_o < 0$
- [[debt-015 local-step-subdivision]] — локальное дробление в `_advance`, под которое написан шаг 2
- `vault/issues/debt-047/` — тело issue, пробы
