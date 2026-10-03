---
tags:
  - план
  - рефакторинг
date: 2026-10-03
issue: DEBT-026
github: 56
branch: refactor/debt-026/rs-check-any-pressure-history
status: в процессе
audit:
  date: 2026-10-03
  round: 2
  found: 3
  auto-fixed: 3
  manual-required: 0
---

# DEBT-026: проверка $R_s$, верная при любой истории давления

**Подтип:** рефакторинг проверочного модуля примеров (`numerical_solver/examples/rs_analytics.py`) + документация. Ядро решателя (`gpn_multiphase_solver/`) и прототип (`HydroSolverPrototype/`) **не меняются**.

**Решения пользователя (2026-10-03):**

| Вопрос | Решение |
|---|---|
| Условие для однофазных ячеек | $R_s \le R_s^{eq}(p)$ (вариант 2). Число ячеек с $R_s > R_{s,0}$ печатается отдельной строкой как наблюдение, не как нарушение |
| Наложение на `rs_profiles.png` | Кружки $R_s^{eq}(p)$ **только в двухфазных ячейках** + прежняя линия $R_{s,0}$ |
| Вертикальная линия «фронт $r_b$» | Подпись по ситуации: если множества «$p < p_b$» и «двухфазные» совпадают — прежняя «фронт $r_b$ = … м»; иначе «изобара $p_b$: $r$ = … м» |
| Какие README править | Только где проверка ломается или где описан меняющийся рисунок: сводный `examples/README.md`, 03 (описание рисунка), 04, 04a, 05, 12, 13b. Фразы «$R_s = \min(\ldots)$ с точностью …» в 03 (§3), 19, 20, 21 **не трогать** — при падающем давлении они верны. Плюс одна фраза докстринга `pvt_plot._physical_rs` |
| **Что такое «двухфазная ячейка»** (решение при аудите) | **Ячейка со свободным газом, $S_g > 10^{-8}$** — а не флаг решателя `regime == 1`. Причина — §1, «Два определения двухфазной ячейки» |

---

## Как начать работу по этому плану

1. Прочитай этот файл целиком.
2. Прочитай запись DEBT-026 в `vault/roadmap/известные баги и технический долг.md` (секция `### DEBT-026`) и issue: `gh issue view 56 --repo ArturSalamatin/Oil_Gas --comments`.
3. Создай ветку от базовой ветки направления (в `master` каталога `numerical_solver/` нет):
   ```powershell
   git checkout numerical_scheme/implementation
   git checkout -b refactor/debt-026/rs-check-any-pressure-history
   ```
4. Все команды pytest — из `numerical_solver/`; Python — `.venv\Scripts\python`.
5. Baseline:
   ```powershell
   cd numerical_solver
   .venv\Scripts\python -m pytest tests/ --collect-only -q                # ожидается 1210
   .venv\Scripts\python -m pytest tests/ -m "not slow" --collect-only -q  # ожидается 987/1210
   .venv\Scripts\python -m pytest tests/ -m "not slow" -q                  # быстрый уровень, ~70 с, зелёный
   ```
   Замер при аудите (2026-10-03, HEAD `6a5e850`): 1210 тестов всего, 987 в быстром уровне. После влития DEBT-035 (`afcad9d`, README 19/21 и докстринг в `test_examples.py`) число тестов и все номера строк, на которые ссылается план, перепроверены — не изменились. Запомни время быстрого уровня.
6. Прототип не меняется — его тесты и регрессию не запускать.
7. **Пути для шагов 1 и 5** (замер скриптом из `vault/issues/`). Каталог `vault/issues` в `.gitignore`: скрипт замера и эталон аудита лежат **только в основном каталоге** проекта, в git worktree их нет. Поэтому команды шагов 1 и 5 используют абсолютные пути и ключ `--solver` — какой `numerical_solver` мерить. Задать один раз в сессии PowerShell:
   ```powershell
   $ROOT = "D:\Lessons\Grants\2026\GPN\Oil_Gas"                 # основной каталог проекта
   $PY = "$ROOT\numerical_solver\.venv\Scripts\python.exe"     # venv общий, в worktree его нет
   $P = "$ROOT\vault\issues\debt-026\probes"                   # скрипт замера и эталон
   $S = (Resolve-Path numerical_solver).Path                   # из корня рабочего каталога: основного или worktree
   ```
   В worktree скрипты примеров (`examples\*\main.py`, шаг 5) берут пакет `gpn_multiphase_solver` из основного каталога (заметка памяти о worktree и `PYTHONPATH`); этот план пакет не меняет, а `rs_analytics.py` скрипт примера берёт из своей папки `examples/` — `PYTHONPATH` не нужен. `pytest` из `numerical_solver` worktree импортирует код worktree.
8. Начни с шага 1. После каждого шага — тест шага и регресс по полю «Регресс»; полный прогон — в конце (`/implement` §3.1).

---

## 1. Суть проблемы (для читателя без контекста)

### Физика

В модели Black Oil газосодержание $R_s$ (м³ст газа на м³ст нефти) не имеет собственной кинетики. Равновесие задаёт его по-разному в ячейке со свободным газом и без него:

- **Есть свободный газ** (двухфазная ячейка): нефть насыщена, $R_s = R_s^{eq}(p)$ — равенство.
- **Газа нет** (однофазная ячейка): растворённый газ переносится с нефтью, $R_s$ — самостоятельная переменная. Равновесие даёт только неравенство $R_s \le R_s^{eq}(p)$: недонасыщенность допустима, пересыщение — нет.

### Что делает код сейчас

`numerical_solver/examples/rs_analytics.py` (151 строка) сравнивает численное $R_s$ последней записи с $\min(R_s^{eq}(p), R_{s,0})$ **во всех ячейках** и требует, чтобы множества «$p < p_b$» и «$S_g > 10^{-12}$» совпадали. Формула верна, только пока давление в каждой ячейке падает: нефть без газа тогда исходная, с $R_{s,0}$.

При восстановлении давления (переменный режим скважины) свободный газ растворяется обратно лишь в пределах своего запаса. Когда запас кончается, нефть остаётся **недонасыщенной и ниже $p_b$**: $S_g = 0$, $R_s < R_s^{eq}(p)$. Решатель это воспроизводит; проверка печатает «совпадают: False» и ошибку.

| Пример | Последняя запись | $\max\lvert\Delta R_s\rvert$ сейчас | ячеек $p<p_b$ / $S_g>0$ | Причина |
|---|---|---|---|---|
| 12 | 15 сут | $2.5\cdot10^{-2}$ | 47 / 46 | одна ячейка (117.9 м) за стационарным фронтом теряет газ при возврате давления |
| 13b | 30 сут, 10.75 МПа после суток при 6 МПа | 2.437 (8.1 % $R_{s,0}$) | 44 / 14 | 30 ячеек недонасыщенной нефти на 0.9–75 м (центры ячеек; изобара $p_b$ по интерполяции — 81.8 м) |
| 04a | 3 сут | $8.9\cdot10^{-14}$ | 65 / 70 | газ остался в 5 ячейках с $p > p_b$ (остаток переходного процесса; там таблица даёт $R_s^{eq} = R_{s,0}$) |

### Почему не $R_s \le \min(R_s^{eq}(p), R_{s,0})$

$R_{s,0}$ — не верхняя граница. Газ подвижнее нефти и копится у забоя (GOR выше $R_{s,0}$). Если затем давление поднимется выше $p_b(R_{s,0})$, а PVT допускает $R_s^{eq}(p) > R_{s,0}$ (Стендинг: `numerical_solver/gpn_multiphase_solver/pvt/standing.py:85` — без ограничения сверху), газ растворится до $R_s > R_{s,0}$. В текущих примерах этого нет (у табличных PVT $R_s^{eq} \le R_{s,0}$, у Стендинга нет восстановления давления), но условие с $R_{s,0}$ дало бы ложное «нарушение» на первом же таком сценарии.

### Два определения двухфазной ячейки (решение при аудите)

**Флаг решателя `regime`** (`numerical_solver/gpn_multiphase_solver/state.py:23`; пишет его единственный гидро-путь — `PrototypeHydroAdapter`, `gpn_multiphase_solver/hydro/prototype_adapter.py:113`: `regime=np.where(new_proto.gas_active, 1, 2)`). Он определяет, какие неизвестные решаются в ячейке:

| `regime` | Неизвестные | Остальное |
|---|---|---|
| 1 | $p$, $S_g$ | $R_s$ присваивается как $R_s^{eq}(p)$ (`blackoil.py`, `unpack`: `rs=np.where(mask,self.pvt.rs_sat(p),x)`) |
| 2 | $p$, $R_s$ | $S_g = 0$ (`unpack`: `sg=np.where(mask,x,0.0)`) |

Флаг переключается с гистерезисом (`numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/blackoil.py`, метод `_advance_phases`):
- 2 → 1: при $R_s > R_s^{eq}(p) + $ `rs_switch_tol` ($10^{-5}$);
- 1 → 2: только при $S_g < -$`sg_switch_tol` ($-10^{-9}$);
- при $-10^{-9} \le S_g < 0$ прототип ставит $S_g = 0$ и **оставляет ячейку `regime = 1`** (`trial.sg[tiny]=0.0`).

**Физическое определение:** двухфазная — есть свободный газ, $S_g > 0$.

Замер аудита (`vault/issues/debt-026/probes/sg_noise.py`, последние записи): в табличных примерах 04, 06–09 и 04a определения расходятся. На первых шагах изобара уходит дальше, ячейки за будущим фронтом становятся двухфазными; потом давление в них поднимается выше $p_b$, газ растворяется. Таблица не имеет ветвей выше $R_{s,0}$, поэтому там $R_s^{eq}(p) = R_{s,0} = 30$; $S_g$ доходит до нуля, но не ниже $-10^{-9}$, и флаг остаётся `regime = 1`:

| Пример | `regime == 1` | $S_g > 0$ | $S_g > 10^{-8}$ | $p < p_b$ | «флаг без газа» |
|---|---|---|---|---|---|
| 04 (и 06–09) | 27 | 26 | 26 | 26 | ячейка 26, $r = 2.70$ м, $p - p_b = +40$ кПа, $S_g = 0$ |
| 04a | 79 | 78 | 70 | 65 | 9 ячеек на 1.86–2.59 м, $p - p_b$ = +296…+766 кПа, $S_g$ = 0…$2.8\cdot10^{-14}$ |
| 12 | 46 | 46 | 46 | 47 | нет |
| 13b | 14 | 14 | 14 | 44 | нет |

Во всех «флагах без газа» $R_s = R_s^{eq}(p) = R_{s,0}$ точно: физически это нефть без газа с исходным $R_s$. По флагу у 04, 06–09 (давление только падает) подпись линии стала бы «изобара», у 04a 9 кружков встали бы в ячейки без газа. Поэтому **двухфазной считается ячейка с $S_g > 10^{-8}$** — порог шума округления из `tests/test_examples.py::test_gas_active_cells_match_pressure` (стр. 1854–1895, там же описан этот артефакт таблиц без ветвей выше $R_{s,0}$). Настоящий газ — $S_g \ge 1.8\cdot10^{-3}$ (у 04a за изобарой).

Что гарантирует корректность обеих проверок при этом определении:
- газ бывает только в `regime == 1` (в `regime == 2` прототип держит $S_g = 0`; замер: «газ только в regime 1: True» у всех 18 примеров) ⇒ в ячейке с газом $R_s$ присвоен решателем как $R_s^{eq}(p)$ по PVT гидродинамики, и равенство проверяет согласованность PVT энергетического блока с гидродинамикой;
- в «флаге без газа» $R_s = R_s^{eq}(p)$ ⇒ неравенство $R_s \le R_s^{eq}(p)$ выполняется как равенство.

### Допуск пересыщения — допуск решателя

Решатель оставляет ячейку однофазной, пока $R_s \le R_s^{eq}(p) + 10^{-5}$ (`rs_switch_tol`, умолчание в сигнатуре `RadialBlackOilModel.__init__`, `blackoil.py`; фабрика его не задаёт, `gpn_multiphase_solver/factory.py:318-326`). Значит, однофазная ячейка с пересыщением до $10^{-5}$ — принятое решателем состояние. Проверка с меньшим порогом давала бы ложные нарушения. Тот же порог — у проверки начального состояния (`factory.py:170`, `_RS0_SUPERSAT_TOL = 1e-5`, BUG-017) и в решении `vault/knowledge/debugging/пересыщенный старт решатель молча уравновешивает скачком давления.md` («проверять … по тому же критерию, по которому решатель включает газ»). Поле `NumericsConfig.rs_switch_tol` (`io/config.py:145`) прототипу **не передаётся** — брать допуск из конфига нельзя (см. §9).

---

## 2. Текущее состояние (baseline)

### Код

| Функция в `numerical_solver/examples/rs_analytics.py` | Строки | Что делает | Кто вызывает |
|---|---|---|---|
| докстринг модуля | 1–29 | «$R_s$ алгебраически следует за давлением», $\min(\ldots)$ | — |
| `rs_expected(config, pvt, p)` | 36–38 | $\min(R_s^{eq}(p), R_{s,0})$ | `rs_error`, `_draw_rs`, **`tests/test_examples.py:911,919`** (`test_physical_branch_matches_rs_analytics` — сверка с `pvt_plot._physical_rs`) |
| `rs_error(config, history, pvt)` | 41–52 | (max_abs, max_rel) по всем ячейкам | `report_rs` |
| `_degassed_cells(config, history, pvt)` | 55–59 | маска $p < p_b$ и $p_b$ | `front_radius`, `report_rs` |
| `front_radius(config, history, grid, pvt)` | 62–82 | интерполяция изобары $p = p_b$ по $\ln r$ | `_draw_rs`, **`examples/04_table_table/grid_convergence.py:59`** |
| `make_overlay_rs(config)` | 85–94 | замыкание config для хука | `examples/example_runner.py:70,176` |
| `_draw_rs(ax, history, grid, simulator, config)` | 97–121 | кружки $\min(\ldots)$ во всех ячейках, линия $R_{s,0}$, линия «фронт $r_b$» | `make_overlay_rs` |
| `report_rs(config, history, pvt) -> dict` | 124–150 | печать + сравнение множеств; возвращает dict | `examples/example_runner.py:233` (возврат не используется); шпион в `tests/test_examples.py:584` |

Ни одна пример-папка не подменяет наложение `"Rs"` (grep `"Rs"` в `examples/*/main.py` — пусто). Выходы примеров (`examples/*/output/`) в git не хранятся. Комментарии, описывающие модуль как проверку $\min(\ldots)$: `examples/03_standing_corey/main.py:10-12, 86-88`, `examples/05_standing_table_rp/main.py:9-11` (правятся в шаге 6).

### Тесты, покрывающие затронутый код

| Тест | Файл:строки | Уровень | Что проверяет |
|---|---|---|---|
| `test_steady_state_false_skips_steady_analytics` (шпионы `report_rs` и др.) | `tests/test_examples.py:551–597` | быстрый | `report_rs` вызывается при `steady_state=False` |
| `test_gas_active_cells_match_pressure` | `tests/test_examples.py:1854` (14), `:2147` (19–21) | slow | у 14 и 19–21 $S_g > 0 \Leftrightarrow$ `regime == 1`, ниже $p_b$ однофазных нет, порог шума $S_g$ $10^{-8}$ |
| `test_physical_branch_matches_rs_analytics` | `tests/test_examples.py:901–921` | slow | `pvt_plot._physical_rs` побитово = `rs_expected` |
| `test_rho_matches_formula` | `tests/test_examples.py:923–` | slow | использует `pvt_plot._physical_rs` |
| `test_repressurization_leaves_undersaturated_oil` | `tests/test_examples.py:1988–2019` | slow | 13b: недонасыщенная нефть ниже $p_b$, в `regime == 1` $R_s = R_s^{eq}(p)$ с `atol=1e-10` |

**Пробел:** ни один тест не проверяет, что `rs_error` мала у всех примеров. Проверка работала только как печать в консоль.

### Зона неприкосновенности

- `rs_expected` — семантика $\min(R_s^{eq}(p), R_{s,0})$ сохраняется (её использует `pvt_plot._physical_rs` через тест побитовой сверки). Меняется только докстринг.
- `front_radius`, `_degassed_cells` — алгоритм не меняется (на них опирается `04_table_table/grid_convergence.py`).
- `make_overlay_rs`, сигнатура `report_rs(config, history, pvt)` — не меняются (вызов в `example_runner.py:233` остаётся как есть).
- `gpn_multiphase_solver/`, `HydroSolverPrototype/` — не трогать.

---

## 3. Целевое состояние

- Две константы модуля: `SG_GAS = 1e-8` (порог свободного газа) и `RS_TOL = 1e-5` (допуск пересыщения = `rs_switch_tol` решателя).
- `report_rs` печатает (формат зафиксирован в шаге 2, проверен при аудите на 04, 04a, 12, 13b):
  1. ячейки с газом: их число и $\max\lvert R_s - R_s^{eq}(p)\rvert$ (абс. и в % от $R_{s,0}$);
  2. ячейки без газа: их число, число пересыщенных ($R_s > R_s^{eq}(p) + 10^{-5}$), число ячеек ниже $p_b$ (недонасыщенная нефть); при пересыщении — наибольшее превышение;
  3. диапазон $R_s$, $R_{s,0}$, $p_b$ и число ячеек с $R_s > R_{s,0}$ (наблюдение).
- Сравнение множеств «$p<p_b$» и «$S_g>0$» из печати убрано.
- `rs_error` — только по ячейкам с газом; новая `rs_supersaturation` — по ячейкам без газа.
- `_draw_rs` — кружки $R_s^{eq}(p)$ только в ячейках с газом; подпись вертикальной линии по ситуации.
- Новые тесты: `tests/test_rs_analytics.py` (12, быстрый уровень, синтетические состояния) и `TestSharedChecks::test_rs_check_all_two_phase_examples` (slow, все примеры с газом).
- README: на 12, 13b объяснение «совпадают: False» больше не нужно; сводная таблица — по новой проверке.

**Ожидаемые числа после реализации** (замер аудита `vault/issues/debt-026/probes/rs_check_audit.txt`; проверяются в шаге 5): у всех 18 примеров с газом пересыщенных 0; ошибка в ячейках с газом 0 (побитово) у 03–10, 19–21 и $\le 2.8\cdot10^{-14}$ у остальных; без газа ниже $p_b$: 12 → 1, 13b → 30, остальные → 0; подпись «изобара» ровно у 04a, 12, 13b.

---

## 4. Варианты решения (итог анализа issue #56)

| Вариант | Суть | Решение |
|---|---|---|
| 1 | Разделение по наличию газа; однофазные $R_s \le \min(R_s^{eq}(p), R_{s,0})$ | отклонён: $R_{s,0}$ не инвариант Black Oil (§1) |
| **2** | Разделение по наличию газа; однофазные $R_s \le R_s^{eq}(p)$; $R_s > R_{s,0}$ — наблюдение | **выбран пользователем** |
| 3 | Оставить формулу, отключать проверку при немонотонном давлении | отклонён: на 12, 13b пропала бы и верная двухфазная часть |

Критерий «двухфазности» внутри варианта 2: флаг `regime == 1` / наличие газа $S_g > 10^{-8}$ / гибрид — выбрано наличие газа (решение при аудите, §1).

Критерии DEBT: минимальный diff (один модуль + тесты + документы), обратная совместимость (`report_rs`, `rs_expected`, `front_radius`, `make_overlay_rs` — те же имена и сигнатуры), тестируемость (появляются автоматические тесты, которых не было).

---

## 5. Подводные камни (чеклист 2.5)

| Пункт | Статус | Комментарий |
|---|---|---|
| Все call sites найдены | ✅ | grep `rs_analytics\|report_rs\|rs_error\|rs_expected\|_draw_rs\|front_radius` по `numerical_solver/` (§2). Возврат `report_rs` никто не читает. Комментарии в `main.py` 03 и 05 — шаг 6 |
| Зависимости пакетов | ✅ | новых нет |
| Обратная совместимость API | ✅ | имена и сигнатуры прежние; меняются ключи возвращаемого словаря `report_rs` — потребителей нет |
| Состояние при ошибке | ✅ | функции чистые; пустые маски обработаны явно (нет ячеек с газом / без газа) — `pvt.Rs_eq` на пустом массиве не вызывается (хотя и не падает: проверено, возвращает пустой массив) |
| Тесты | ⚠️ | шпион `report_rs` (стр. 584) не зависит от вывода; `test_physical_branch_matches_rs_analytics` зависит от `rs_expected` — не меняем семантику |
| Circular imports | ✅ | импорт-граф не меняется |
| Docstrings / `\eqref` | ✅ | ссылок на уравнения нет; докстринг модуля переписывается. Ссылки на прототип — по имени метода (`blackoil.py`, `_advance_phases`), без номеров строк: ветка DEBT-033 (worktree `.worktrees/debt-033`) добавляет в `blackoil.py` 56 строк |
| Configs | ✅ | не меняются |
| Связь с другими задачами | ✅ | FEAT-019 (переменный режим) — выигрывает; FEAT-028 (`pvt_plot.py`) влит, меняется только докстринг `_physical_rs`. DEBT-035 (#57, план готов) правит README 19, 21 (стр. 191–200) и докстринг `TestStandingCoreyCooling.test_config_follows_decisions` в `tests/test_examples.py` — с этим планом не пересекается (README 19, 21 здесь не трогаются; вставка — в `TestSharedChecks`). DEBT-033 (ветка в работе) меняет только прототип |
| Производительность | ✅ | одна проверка на последней записи |
| Прототип | ✅ | не меняется |
| **Флаг `regime` и газ расходятся** | ✅ | решено: двухфазная — $S_g > 10^{-8}$ (§1). Замер аудита: «флаги без газа» у 04, 06–09 (1 ячейка), 04a (9); у остальных маски совпадают |
| **`front_radius` при немонотонном $p$** | ✅ | `np.searchsorted` корректен, если ячейки с $p<p_b$ образуют префикс. Замер аудита: префикс у всех 18, включая 13b. Шаг 1 перепроверяет |
| Допуск `RS_TOL` | ✅ | $10^{-5}$ = `rs_switch_tol` решателя (§1); тест сверяет с умолчанием `RadialBlackOilModel` — при смене умолчания в прототипе тест упадёт |
| Ячейка в полосе переключения | ⚠️ принято | однофазная ячейка с $p$ ниже $p_b$ на единицы Па (пересыщение исходной нефти меньше $10^{-5}$: $dR_s^{eq}/dp \approx 3\cdot10^{-6}$ 1/Па у таблицы 04, $\approx 6\cdot10^{-6}$ у Стендинга 03) осталась бы без газа законно — подпись дала бы «изобара», счётчик «ниже pb» = 1. Вероятность попадания центра ячейки в полосу ~единиц Па на последней записи пренебрежима; в замере аудита таких нет |
| Реализация в git worktree | ✅ | `vault/issues` в `.gitignore` (`.gitignore:48`): скрипт замера и эталон есть только в основном каталоге; без ключа `--solver` скрипт мерил бы код основного каталога. Шаги 1 и 5 — абсолютные пути и `--solver $S` («Как начать», п. 7); проверено при аудите (раунд 2) на копии дерева: `--solver` берёт её `rs_analytics.py` |
| Тест на `results` использует PVT фабрики | ✅ | `_pvt_of_config` пересобирает PVT по конфигу (как `test_physical_branch_matches_rs_analytics`), а пример передаёт `simulator._energy._pvt`; фикстура `results` симулятора не хранит. Обе — один и тот же класс по одному конфигу |

---

## 6. Шаги

### Шаг 1: Замер до правки (гейт)

**Цель:** подтвердить на ветке числа и предпосылки, на которых стоит план, до правки кода.

**Файлы:**
- `vault/issues/debt-026/probes/rs_check_numbers.py` — **уже создан при аудите** (текст ниже — для справки; если файла нет, создать дословно)
- новый `vault/issues/debt-026/probes/rs_check_before.txt` (вывод)
- эталон для сверки: `vault/issues/debt-026/probes/rs_check_audit.txt` (замер аудита 2026-10-03 на HEAD `6a5e850`, ~4 мин)

**Контекст:** скрипт считает новую проверку **независимо от `rs_analytics`** (прямыми формулами, с теми же порогами $10^{-8}$ и $10^{-5}$), поэтому им же мерят и до, и после правки модуля; в конце он печатает вывод `rs_analytics.report_rs` — ровно то, что печатает пример. Скрипты вне pytest сами подключают прототип через `sys.path` (`tests/conftest.py` делает это только для pytest). Перенаправление `| Out-File` в PowerShell 5.1 портит кириллицу — файл пишет сам скрипт (`--out`).

Текст скрипта (`vault/issues/debt-026/probes/rs_check_numbers.py`):

```python
"""DEBT-026: числа проверки R_s на всех примерах с газом (до и после правки).

Для каждого примера с Rs0 > 0 — расчёт штатного конфига; на последней записи:
  прежняя проверка: max|Rs - min(Rs_eq(p), Rs0)| по всем ячейкам;
    ячеек p < pb, Sg > 1e-12 (порог прежнего report_rs) и regime == 1;
  новая — считается здесь прямыми формулами, независимо от rs_analytics:
    ячеек с газом (Sg > 1e-8) и max|Rs - Rs_eq(p)| в них; ячеек без газа,
    пересыщенных из них (Rs > Rs_eq(p) + 1e-5) и наибольшее Rs - Rs_eq(p);
    ячеек без газа с p < pb; ячеек Rs > Rs0 + 1e-5;
  предпосылки плана:
    mask(p < pb) == mask(газ)      — подпись линии «фронт» или «изобара»;
    газ только в regime == 1       — в ячейках с газом Rs задан решателем
                                     как Rs_eq(p);
    ячейки p < pb образуют префикс — front_radius (searchsorted) корректен;
  затем вывод rs_analytics.report_rs — как его печатает пример.

Пороги 1e-8 и 1e-5 — те же, что SG_GAS и RS_TOL в rs_analytics после
DEBT-026; здесь они продублированы, чтобы замер до правки модуля считал
новую проверку теми же числами.

Запуск, все примеры ~4 мин:
    python rs_check_numbers.py [--solver каталог] [--out файл] [папка ...]
--solver — каталог numerical_solver, чей код мерить (пакет, examples/,
прототип); по умолчанию — numerical_solver рядом с этим vault. Нужен при
реализации в git worktree: vault/issues в .gitignore, скрипт лежит только
в основном каталоге и без ключа мерил бы его код, а не код worktree.
--out — копия вывода в файл UTF-8. Перенаправление «| Out-File» в
PowerShell 5.1 не годится: оно перекодирует вывод через кодировку консоли
и портит кириллицу.
"""

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ARGS = sys.argv[1:]
SOLVER = HERE.parents[3] / "numerical_solver"
if ARGS[:1] == ["--solver"]:
    SOLVER = Path(ARGS[1]).resolve()
    ARGS = ARGS[2:]
for p in (SOLVER, SOLVER / "examples",
          SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"):
    sys.path.insert(0, str(p))

# Консоль Windows (cp1251) не печатает «≤», «…», «³» — BUG-009.
for _stream in (sys.stdout, sys.stderr):
    _stream.reconfigure(encoding="utf-8")

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
import rs_analytics  # noqa: E402

EXAMPLES = SOLVER / "examples"
SG = 1e-8            # порог свободного газа (SG_GAS в rs_analytics)
TOL = 1e-5           # допуск пересыщения = rs_switch_tol решателя (RS_TOL)


def _is_prefix(mask: np.ndarray) -> bool:
    """True, если True-ячейки маски идут подряд от забоя (или их нет)."""
    k = int(np.count_nonzero(mask))
    return bool(np.all(mask[:k]) and not np.any(mask[k:]))


def probe(name: str) -> None:
    cfg = load_config(EXAMPLES / name / "config.json")
    Rs0 = cfg.initial_conditions.Rs0
    if Rs0 <= 0.0:
        return
    sim, init = SimulatorFactory.from_config(cfg)
    hist = sim.run(init)
    pvt = sim._energy._pvt          # тот PVT, что передаёт report_rs пример
    st = hist.states[-1]
    pb = float(pvt.pb(np.array([Rs0]))[0])

    below = st.p < pb
    gas = st.Sg > SG
    one = ~gas
    rs_eq = pvt.Rs_eq(st.p)

    old = float(np.abs(np.minimum(rs_eq, Rs0) - st.Rs).max())
    n_old_gas = int(np.count_nonzero(st.Sg > 1e-12))
    n_regime = int(np.count_nonzero(st.regime == 1))
    err2 = float(np.abs(rs_eq[gas] - st.Rs[gas]).max()) if gas.any() else 0.0
    exc = (st.Rs - rs_eq)[one]
    n_bad = int(np.count_nonzero(exc > TOL))
    exc_max = float(exc.max()) if exc.size else float("nan")
    n_under = int(np.count_nonzero(one & below))
    n_above = int(np.count_nonzero(st.Rs > Rs0 + TOL))

    print(f"\n=== {name}  (t = {st.t / 86400:.3f} сут, N = {st.p.size}) ===")
    # Какой rs_analytics мерится — при --solver на worktree должен быть его.
    # В файл не пишется: путь различается между основным каталогом и
    # worktree, а сверка «до/после» побитовая.
    print(f"  [rs_analytics: {Path(rs_analytics.__file__).parent.parent.name}"
          f"/{Path(rs_analytics.__file__).parent.name}]", file=sys.stderr)
    print(f"  прежняя: max|Rs - min(Rs_eq, Rs0)| = {old:.3e}; "
          f"p<pb: {int(below.sum())}, Sg>1e-12: {n_old_gas}, regime 1: {n_regime}")
    print(f"  новая: с газом {int(gas.sum())}, max|Rs - Rs_eq(p)| = {err2:.3e}; "
          f"без газа {int(one.sum())}, пересыщенных {n_bad} "
          f"(max Rs - Rs_eq = {exc_max:.3e}), ниже pb {n_under}; Rs > Rs0: {n_above}")
    print(f"  предпосылки: (p<pb)==(газ): {np.array_equal(below, gas)}; "
          f"газ только в regime 1: {bool(np.all(st.regime[gas] == 1))}; "
          f"префикс p<pb: {_is_prefix(below)}")
    print("  --- report_rs ---")
    rs_analytics.report_rs(cfg, hist, pvt)


class _Tee:
    """Печать одновременно в консоль и в файл UTF-8."""

    def __init__(self, path):
        self._console = sys.stdout
        self._file = open(path, "w", encoding="utf-8")

    def write(self, s):
        self._console.write(s)
        self._file.write(s)

    def flush(self):
        self._console.flush()
        self._file.flush()


if __name__ == "__main__":
    args = ARGS                     # --solver уже снят при подключении путей
    if args[:1] == ["--out"]:
        sys.stdout = _Tee(args[1])
        args = args[2:]
    names = args or sorted(
        d.name for d in EXAMPLES.iterdir() if (d / "config.json").is_file())
    for n in names:
        probe(n)
    sys.stdout.flush()
```

**Что сделать:**
1. Запустить (`timeout` ≥ 600 с; 18 примеров с газом, 01 и 02 пропускаются; переменные `$PY`, `$P`, `$S` — «Как начать», п. 7):
   ```powershell
   & $PY "$P\rs_check_numbers.py" --solver $S --out "$P\rs_check_before.txt"
   ```
   В stderr у каждого примера строка `[rs_analytics: numerical_solver/examples]` — в worktree родительская папка та же по имени; если сомнение, какой модуль мерится, — `& $PY -c "import sys; sys.path.insert(0, r'$S\examples'); import rs_analytics; print(rs_analytics.__file__)"`.
2. Сравнить с эталоном аудита — должно совпасть побитово (решатель детерминирован, код не менялся; в эталоне нет строк журнала и времени — проверено):
   ```powershell
   Compare-Object (Get-Content -Encoding UTF8 "$P\rs_check_audit.txt") (Get-Content -Encoding UTF8 "$P\rs_check_before.txt")
   ```
   Пустой вывод — совпадение.

**Гейт:** если `Compare-Object` что-то вывел — база изменилась после аудита; сверить строки «новая» и «предпосылки» с таблицей ниже. Расхождение в них — остановиться и сообщить пользователю.

Замер аудита (последние записи):

| пример | с газом | $p<p_b$ | без газа ниже $p_b$ | max\|Rs − Rs_eq\| в ячейках с газом | (p<pb)==(газ) | газ только в regime 1 | префикс |
|---|---|---|---|---|---|---|---|
| 03 | 16 | 16 | 0 | 0 | True | True | True |
| 04, 06, 07, 08, 09 | 26 | 26 | 0 | 0 | True | True | True |
| 04a | 70 | 65 | 0 | $5.3\cdot10^{-15}$ | **False** | True | True |
| 05 | 6 | 6 | 0 | 0 | True | True | True |
| 10 | 29 | 29 | 0 | 0 | True | True | True |
| 11 | 50 | 50 | 0 | $7.1\cdot10^{-15}$ | True | True | True |
| 12 | 46 | 47 | **1** | $7.1\cdot10^{-15}$ | **False** | True | True |
| 13a | 47 | 47 | 0 | $5.3\cdot10^{-15}$ | True | True | True |
| 13b | 14 | 44 | **30** | $7.1\cdot10^{-15}$ | **False** | True | True |
| 14 | 320 | 320 | 0 | $2.8\cdot10^{-14}$ | True | True | True |
| 15 | 46 | 46 | 0 | $3.6\cdot10^{-15}$ | True | True | True |
| 19 / 20 / 21 | 334 / 289 / 328 | те же | 0 | 0 | True | True | True |

Пересыщенных 0 у всех (наибольшее $R_s - R_s^{eq}$ в ячейках без газа $\le 3.5\cdot10^{-13}$), $R_s > R_{s,0}$ — 0 у всех.

**Проверка после этого шага:**
- Регресс: `--collect-only -q` (код решателя и тесты не менялись) — 1210.

**Подводные камни:** скрипт печатает и старый `report_rs` (до правки) — это ожидаемо; после шага 2 тот же скрипт напечатает новый формат.

**Зависимости:** блокирует шаги 2–7.

**Оценка:** ~5 мин (из них ~4 мин расчёт).

---

### Шаг 2: Новая проверка в `rs_analytics.py` + модульные тесты (быстрый уровень)

**Цель:** проверка разделена по наличию свободного газа; добавлены быстрые тесты на синтетических состояниях.

**Файлы:**
- `numerical_solver/examples/rs_analytics.py` (переписать докстринг модуля, константы `SG_GAS`, `RS_TOL`, `rs_expected` — только докстринг, `rs_error`, новая `rs_supersaturation`, `front_radius` — только первая строка докстринга, `_draw_rs`, `report_rs`)
- новый `numerical_solver/tests/test_rs_analytics.py`

**Контекст:** см. §1. Тесты пишутся первыми: создать `tests/test_rs_analytics.py`, запустить — убедиться, что падают на старом коде (нет `rs_supersaturation`, `RS_TOL`, ключей `n_supersaturated` и т. д.), затем переписать модуль. Синтетические состояния строятся на настоящем PVT примеров (`_create_pvt(load_config(...))` — без расчёта, доли секунды), поэтому тесты попадают в быстрый уровень (фикстура `results` не используется). PVT примера 04 — таблица, $R_{s,0} = 30$, $p_b = 15.0$ МПа, $R_s^{eq}$ при 8 / 10 / 10.75 / 12 / 14 / 16 / 18 МПа = 9 / 15 / 17.25 / 21 / 27 / 30 / 30. PVT примера 03 — Стендинг, $R_{s,0} = 50$, $p_b = 9.43$ МПа, $R_s^{eq}(1.5\,p_b) = 80.9$, без ограничения сверху. Прототип (`radial_blackoil`) в тестах импортируется: путь ставит `tests/conftest.py`.

**Код ниже проверен при аудите:** раунд 1 — дословные копии модуля и тестов, 12 passed; модуль с новым наложением построил `rs_profiles.png` у 04, 04a, 12, 13b ровно как ожидается в шаге 5. Раунд 2 — те же блоки, извлечённые из плана, в копии дерева с **настоящим** `tests/conftest.py` (прототип — через его `sys.path`): 12 passed на новом модуле, 11 failed / 1 passed на старом; тело теста шага 3 (PVT через `_create_pvt`) на 04, 04a, 12, 13b — все утверждения выполнены. Копии удалены после аудита.

**Что сделать:**

1. Создать `numerical_solver/tests/test_rs_analytics.py`:

```python
"""Проверка R_s общего модуля examples/rs_analytics.py (DEBT-026).

Проверка обязана быть верной при любой истории давления:
  ячейка со свободным газом (Sg > SG_GAS): Rs = Rs_eq(p);
  ячейка без газа:                         Rs <= Rs_eq(p) + RS_TOL —
                                           недонасыщенность допустима.
Прежняя формула Rs = min(Rs_eq(p), Rs0) во всех ячейках верна только при
монотонно падающем давлении и на примерах 12, 13b печатала «не совпадают».

Состояния синтетические, PVT — настоящий, примеров 04 (таблица, Rs0 = 30,
pb = 15 МПа, Rs_eq = 30 при p >= 15 МПа) и 03 (Стендинг, Rs0 = 50).
Расчёта нет — быстрый уровень.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pytest  # noqa: E402

from gpn_multiphase_solver.factory import _create_pvt  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.state import SimulationState  # noqa: E402

# Модуль примеров, не пакета: путь только до examples/ (как в
# test_energy_balance_examples.py).
_EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
if str(_EXAMPLES) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES))

import rs_analytics  # noqa: E402

MPA = 1e6
R = np.geomspace(0.1, 100.0, 6)        # центры ячеек, м (только для рисунка)


def _case(name):
    """(config, pvt) примера без расчёта."""
    cfg = load_config(_EXAMPLES / name / "config.json")
    return cfg, _create_pvt(cfg)


def _history(p_mpa, Rs, regime, Sg=None):
    """История из одного состояния: rs_analytics читает только states[-1].

    Sg по умолчанию — 0.1 в ячейках regime == 1 и 0 в остальных, как у
    решателя без артефактов; явный Sg — для ячеек «флаг без газа».
    """
    p = np.asarray(p_mpa, float) * MPA
    regime = np.asarray(regime, int)
    if Sg is None:
        Sg = np.where(regime == 1, 0.1, 0.0)
    st = SimulationState(p=p, Sg=np.asarray(Sg, float), Rs=np.asarray(Rs, float),
                         T=np.full(p.size, 350.0), regime=regime, t=0.0)
    return SimpleNamespace(states=[st])


def _report(cfg, hist, pvt, capsys):
    """report_rs без засорения вывода теста."""
    rep = rs_analytics.report_rs(cfg, hist, pvt)
    capsys.readouterr()
    return rep


def _draw(cfg, pvt, hist):
    """Наложение на пустые оси; возвращает (кружки, подписи линий)."""
    fig, ax = plt.subplots()
    grid = SimpleNamespace(r_centers=R[:hist.states[-1].p.size])
    sim = SimpleNamespace(_energy=SimpleNamespace(_pvt=pvt))
    rs_analytics._draw_rs(ax, hist, grid, sim, cfg)
    marks = [ln for ln in ax.get_lines() if ln.get_marker() == "o"]
    labels = [ln.get_label() for ln in ax.get_lines()]
    plt.close(fig)
    return marks, labels


# ── Падающее давление: прежняя и новая проверки согласны ──

def test_monotone_pressure_passes(capsys):
    """Фронт на 15 МПа: левее газ (Rs = Rs_eq), правее исходная нефть (Rs0).

    Ожидание: ошибка в ячейках с газом ровно 0 (одна функция от одного p),
    нарушений нет, нефти без газа ниже pb нет.
    """
    cfg, pvt = _case("04_table_table")
    p = [8, 10, 12, 14, 16, 18]
    regime = [1, 1, 1, 1, 2, 2]
    Rs = pvt.Rs_eq(np.array(p, float) * MPA)
    Rs[4:] = 30.0
    rep = _report(cfg, _history(p, Rs, regime), pvt, capsys)
    assert rep["max_abs"] == 0.0
    assert rep["n_two_phase"] == 4
    assert rep["n_supersaturated"] == 0
    assert rep["n_single_below_pb"] == 0


# ── Восстановление давления: случай DEBT-026 ──

def test_repressurization_undersaturated_is_not_violation(capsys):
    """Нефть без газа ниже pb с Rs < Rs_eq(p) — допустимое состояние.

    Картина 13b на конце 30 сут: газ только у забоя, дальше до изобары
    недонасыщенная нефть. Прежняя формула min(Rs_eq, Rs0) дала бы здесь
    ошибку 2 — это и проверяется первой строкой, чтобы тест не стал
    тавтологией. Новая: нарушений нет, три ячейки ниже pb учтены.
    """
    cfg, pvt = _case("04_table_table")
    p = [10.75, 11, 12, 13, 16, 18]
    regime = [1, 2, 2, 2, 2, 2]
    p_pa = np.array(p, float) * MPA
    Rs = pvt.Rs_eq(p_pa)
    Rs[1:4] -= 2.0                         # недонасыщенность 2 м³ст/м³ст
    Rs[4:] = 30.0
    hist = _history(p, Rs, regime)
    old = np.abs(rs_analytics.rs_expected(cfg, pvt, p_pa) - Rs).max()
    assert old == pytest.approx(2.0)       # прежняя проверка «не совпадают»
    rep = _report(cfg, hist, pvt, capsys)
    assert rep["max_abs"] == 0.0
    assert rep["n_supersaturated"] == 0
    assert rep["n_single_below_pb"] == 3


# ── Что проверка обязана ловить ──

def test_supersaturated_single_phase_is_violation(capsys):
    """Ячейка без газа с Rs > Rs_eq(p) — газ растворился сверх равновесия."""
    cfg, pvt = _case("04_table_table")
    p = [10, 12, 16]
    regime = [1, 2, 2]
    Rs = pvt.Rs_eq(np.array(p, float) * MPA)
    Rs[1] += 0.5
    Rs[2] = 30.0
    rep = _report(cfg, _history(p, Rs, regime), pvt, capsys)
    assert rep["n_supersaturated"] == 1
    assert rep["max_excess"] == pytest.approx(0.5)


def test_two_phase_mismatch_is_reported(capsys):
    """Ячейка с газом и Rs != Rs_eq(p): задержка выделения или чужой PVT."""
    cfg, pvt = _case("04_table_table")
    p = [10, 12, 16]
    regime = [1, 1, 2]
    Rs = pvt.Rs_eq(np.array(p, float) * MPA)
    Rs[1] -= 1e-3
    Rs[2] = 30.0
    rep = _report(cfg, _history(p, Rs, regime), pvt, capsys)
    assert rep["max_abs"] == pytest.approx(1e-3)
    assert rep["max_rel"] == pytest.approx(1e-3 / 30.0)


def test_tolerance_on_flat_branch(capsys):
    """На табличном PVT при p >= pb Rs_eq = Rs0: шум 1e-12 — не нарушение.

    Нефть без газа с Rs = Rs0 лежит ровно на границе Rs <= Rs_eq(p); без
    допуска шум Ньютона ~1e-13 давал бы ложные «пересыщения».
    """
    cfg, pvt = _case("04_table_table")
    p = [10, 16, 18]
    regime = [1, 2, 2]
    Rs = pvt.Rs_eq(np.array(p, float) * MPA)
    Rs[1:] += 1e-12
    rep = _report(cfg, _history(p, Rs, regime), pvt, capsys)
    assert rep["n_supersaturated"] == 0


def test_supersaturation_within_solver_tolerance_is_accepted(capsys):
    """Пересыщение до RS_TOL — состояние, принятое решателем; сверх — нарушение.

    Прототип включает газ в ячейке только при Rs > Rs_eq(p) + rs_switch_tol
    (blackoil.py, _advance_phases): ячейка с меньшим пересыщением остаётся
    однофазной законно. RS_TOL обязан совпадать с этим допуском — сверка с
    умолчанием RadialBlackOilModel (фабрика его не задаёт).
    """
    import inspect
    from radial_blackoil.blackoil import RadialBlackOilModel
    params = inspect.signature(RadialBlackOilModel.__init__).parameters
    assert rs_analytics.RS_TOL == params["rs_switch_tol"].default

    cfg, pvt = _case("04_table_table")
    p = [10, 12, 13]
    regime = [1, 2, 2]
    Rs = pvt.Rs_eq(np.array(p, float) * MPA)
    Rs[1] += 0.5 * rs_analytics.RS_TOL     # в пределах допуска решателя
    Rs[2] += 2.0 * rs_analytics.RS_TOL     # сверх допуска: решатель включил бы газ
    rep = _report(cfg, _history(p, Rs, regime), pvt, capsys)
    assert rep["n_supersaturated"] == 1


def test_rs_above_rs0_is_observation_not_violation(capsys):
    """Стендинг, p выше pb(Rs0): Rs0 < Rs < Rs_eq(p) — допустимо.

    Газ, скопившийся у забоя, при росте давления растворяется сверх Rs0.
    Условие Rs <= min(Rs_eq, Rs0) сочло бы это нарушением (вариант 1,
    отклонён); здесь — только счётчик наблюдения.
    """
    cfg, pvt = _case("03_standing_corey")
    Rs0 = cfg.initial_conditions.Rs0
    pb = float(pvt.pb(np.array([Rs0]))[0])
    p = np.array([0.5, 1.5, 1.5]) * pb / MPA
    regime = [1, 2, 2]
    Rs = pvt.Rs_eq(p * MPA)
    assert Rs[1] > Rs0 + 1.0               # предпосылка: у Стендинга есть запас
    Rs[1] = Rs0 + 1.0
    Rs[2] = Rs0
    rep = _report(cfg, _history(p, Rs, regime), pvt, capsys)
    assert rep["n_supersaturated"] == 0
    assert rep["n_above_rs0"] == 1


def test_no_two_phase_cells(capsys):
    """Газа нет нигде: мера для ячеек с газом — ноль, Rs_eq на пустом массиве не зовётся."""
    cfg, pvt = _case("04_table_table")
    rep = _report(cfg, _history([16, 18], [30.0, 30.0], [2, 2]), pvt, capsys)
    assert rep["max_abs"] == 0.0
    assert rep["n_two_phase"] == 0


def test_noise_cell_with_solver_flag_is_single_phase(capsys):
    """Ячейка regime == 1 с Sg ~ 1e-14 за изобарой — без газа (замер 04, 04a).

    На таблице без ветвей выше Rs0 растворившийся газ оставляет флаг решателя
    двухфазным при Sg ~ 1e-14 и Rs = Rs_eq(p) = Rs0 (у 04 — ячейка на 2.70 м,
    +40 кПа над pb). Газа нет: в счёт ячеек с газом она не идёт, кружка нет,
    подпись остаётся «фронт». По флагу regime пример с падающим давлением
    получил бы подпись «изобара».
    """
    cfg, pvt = _case("04_table_table")
    p = [8, 10, 12, 14, 16, 18]
    regime = np.array([1, 1, 1, 1, 1, 2])           # ячейка 4 — флаг без газа
    Sg = np.array([0.1, 0.1, 0.1, 0.1, 1e-14, 0.0])
    Rs = pvt.Rs_eq(np.array(p, float) * MPA)        # в ячейке 4 = Rs0 = 30
    Rs[5] = 30.0
    hist = _history(p, Rs, regime, Sg)
    rep = _report(cfg, hist, pvt, capsys)
    assert rep["n_two_phase"] == 4
    assert rep["n_supersaturated"] == 0
    marks, labels = _draw(cfg, pvt, hist)
    np.testing.assert_array_equal(marks[0].get_xdata(), R[:4])
    assert any(lb.startswith("фронт") for lb in labels)


# ── Рисунок rs_profiles.png ──

def test_overlay_marks_only_two_phase_and_front_label():
    """Падающее давление: кружки только в ячейках с газом, линия — «фронт»."""
    cfg, pvt = _case("04_table_table")
    p = [8, 10, 12, 14, 16, 18]
    regime = np.array([1, 1, 1, 1, 2, 2])
    Rs = pvt.Rs_eq(np.array(p, float) * MPA)
    Rs[4:] = 30.0
    marks, labels = _draw(cfg, pvt, _history(p, Rs, regime))
    assert len(marks) == 1
    np.testing.assert_array_equal(marks[0].get_xdata(), R[regime == 1])
    assert any(lb.startswith("фронт") for lb in labels)


def test_overlay_isobar_label_after_repressurization():
    """Восстановление давления: газ у забоя, ниже pb нефть без газа — «изобара».

    Изобара p = pb стоит между 13 и 16 МПа, а граница газа — у первой ячейки:
    называть линию фронтом разгазирования нельзя.
    """
    cfg, pvt = _case("04_table_table")
    p = [10.75, 11, 12, 13, 16, 18]
    regime = np.array([1, 2, 2, 2, 2, 2])
    Rs = pvt.Rs_eq(np.array(p, float) * MPA)
    Rs[1:4] -= 2.0
    Rs[4:] = 30.0
    marks, labels = _draw(cfg, pvt, _history(p, Rs, regime))
    np.testing.assert_array_equal(marks[0].get_xdata(), R[regime == 1])
    assert any(lb.startswith("изобара") for lb in labels)
    assert not any(lb.startswith("фронт") for lb in labels)


def test_overlay_without_gas_has_no_marks():
    """Газа нет: кружков нет (пустая линия дала бы пункт легенды без точек)."""
    cfg, pvt = _case("04_table_table")
    marks, _labels = _draw(cfg, pvt, _history([16, 18], [30.0, 30.0], [2, 2]))
    assert marks == []
```

Примечание к `test_overlay_without_gas_has_no_marks`: при всех $p \ge p_b$ `front_radius` возвращает `nan` (`searchsorted` даёт `j = 0`), вертикальная линия не рисуется — тест это неявно покрывает (падения нет).

2. Запустить новый файл на старом коде — ожидается **11 failed, 1 passed** (`KeyError` по новым ключам, `AttributeError` на `RS_TOL`, несовпадение кружков; замер аудита, раунд 2). Проходит `test_two_phase_mismatch_is_reported`: расхождение в ячейке с газом ловила и старая проверка — это не дефект теста:
   ```powershell
   .venv\Scripts\python -m pytest tests/test_rs_analytics.py -q
   ```

3. Заменить `numerical_solver/examples/rs_analytics.py` целиком на:

```python
"""Аналитическая проверка Rs(r) — общая для всех примеров с растворённым газом.

В модели Black Oil газосодержание не имеет собственной динамики: нет ни
уравнения релаксации, ни кинетики выделения. Равновесие задаёт Rs
по-разному в ячейке со свободным газом и без него:

    газ есть (Sg > SG_GAS):  Rs = Rs_eq(p)   — нефть насыщена;
    газа нет:                Rs <= Rs_eq(p)  — недонасыщенность допустима,
                                               пересыщение — нет (с точностью
                                               до допуска решателя RS_TOL).

Rs_eq — равновесное газосодержание насыщенной нефти (корреляция Стендинга
или интерполяция ветвей PVTO-таблицы — по модели PVT). В ячейке без газа
Rs — самостоятельная переменная: растворённый газ переносится с нефтью.

Почему не Rs = min(Rs_eq(p), Rs0) во всех ячейках (так было до DEBT-026).
Формула верна, пока давление в каждой ячейке только падает: нефть без газа
тогда исходная, с Rs0. При восстановлении давления свободный газ
растворяется обратно лишь в пределах своего запаса; когда он кончается,
нефть остаётся недонасыщенной и при p < pb: Sg = 0, Rs < Rs_eq(p)
(примеры 12, 13b). Rs0 — тоже не верхняя граница: газ подвижнее нефти и
копится у забоя, и при росте давления выше pb(Rs0) он растворится до
Rs > Rs0, если PVT это допускает (у Стендинга Rs_eq(p) > Rs0 при p > pb).
Такие ячейки печатаются как наблюдение, не как нарушение.

Двухфазной считается ячейка со свободным газом, а не с флагом решателя
regime == 1. Флаг переключается с гистерезисом: газ включается при
Rs > Rs_eq(p) + RS_TOL, а выключается, только когда Sg уходит ниже -1e-9;
меньшую отрицательную Sg прототип обнуляет, оставляя ячейку двухфазной
(blackoil.py, _advance_phases). На таблицах без ветвей выше Rs0 ячейки,
ставшие двухфазными на первых шагах, после растворения газа так и остаются
regime == 1 с Sg ~ 1e-14 (у 04 — одна, у 04a — девять ячеек за изобарой).
Газа в них нет, Rs = Rs_eq(p) = Rs0, неравенство выполняется как равенство.
Ячейка со свободным газом всегда regime == 1 (в однофазной прототип держит
Sg = 0), поэтому в ней Rs присвоен решателем как Rs_eq(p) по PVT
гидродинамики, и равенство проверяет согласованность PVT.

Проверка НЕ ЗАВИСИТ ОТ ВИДА ОФП и от тепловых параметров: в неё входят
только PVT, поле давления и Sg. Поэтому один и тот же код применим ко всем
сценариям с Rs0 > 0 — и с аналитическим PVT, и с табличным.

Что она ловит:
  * схема выделяет газ не мгновенно (появилась паразитная релаксация либо
    рассогласование Rs с p внутри шага Ньютона) — нарушено равенство в
    ячейках с газом;
  * PVT в энергетическом блоке отличается от PVT гидродинамики — тогда
    Rs_eq(p), посчитанное здесь, не совпадёт с тем, что применил решатель;
  * газ растворился сверх равновесия — пересыщенная ячейка без газа.

Чего не ловит: неверную величину недонасыщения (газ «потерялся» при
переходе ячейки в однофазный режим). Это задача баланса массы газового
компонента, а не алгебраической проверки.

Ожидаемая точность равенства — уровень машинного нуля (1e-13 и ниже):
обе величины считаются одной и той же функцией от одного и того же p.
"""

from __future__ import annotations

import numpy as np

# Порог свободного газа: ячейка с Sg <= SG_GAS считается однофазной. Тот же
# порог шума округления, что в test_gas_active_cells_match_pressure: газ,
# растворившийся в ячейке с флагом regime == 1, оставляет Sg ~ 1e-16…1e-14,
# настоящий газ у фронта — Sg ~ 1e-3 и выше (замер DEBT-026: у 04a за
# изобарой 1.8e-3…1.4e-2).
SG_GAS = 1e-8

# Допуск пересыщения ячейки без газа, м³ст/м³ст, — допуск переключения фаз
# решателя rs_switch_tol. Прототип включает газ в ячейке только при
# Rs > Rs_eq(p) + rs_switch_tol (blackoil.py, _advance_phases; по умолчанию
# 1e-5, фабрика его не задаёт — поле NumericsConfig.rs_switch_tol прототипу
# не передаётся, брать допуск из конфига нельзя). Однофазная ячейка с
# пересыщением до 1e-5 — принятое решателем состояние, а не дефект; проверка
# строже решателя давала бы ложные нарушения. Тот же порог у проверки
# начального состояния (factory._RS0_SUPERSAT_TOL, BUG-017). Шум ~1e-13 на
# горизонтальной ветви таблицы (Rs_eq = Rs0 при p >= pb) он покрывает тоже.
RS_TOL = 1e-5


def rs_expected(config, pvt, p):
    """Rs при монотонно падающем давлении: min(Rs_eq(p), Rs0), [N].

    Физическая кривая PVT-графика (pvt_plot._physical_rs сверяется с ней
    побитово). Для проверки решения при произвольной истории давления не
    годится — см. докстринг модуля.
    """
    return np.minimum(pvt.Rs_eq(p), config.initial_conditions.Rs0)


def rs_error(config, history, pvt):
    """Отклонение Rs от Rs_eq(p) в ячейках со свободным газом (Sg > SG_GAS).

    Возвращает (max_abs, max_rel). Относительная нормируется на Rs0, а не
    поячеечно: у фронта Rs -> Rs0, а не к нулю, поэтому деление на Rs0 даёт
    устойчивую меру. Ячеек с газом нет — проверять нечего, (0.0, 0.0).
    """
    st = history.states[-1]
    gas = st.Sg > SG_GAS
    if not np.any(gas):
        return 0.0, 0.0
    d = np.abs(pvt.Rs_eq(st.p[gas]) - st.Rs[gas])
    Rs0 = config.initial_conditions.Rs0
    return float(d.max()), float(d.max() / Rs0) if Rs0 > 0 else 0.0


def rs_supersaturation(history, pvt):
    """Пересыщение ячеек без свободного газа: Rs > Rs_eq(p) + RS_TOL.

    Возвращает (max_excess, n_bad): наибольшее Rs - Rs_eq(p) по ячейкам без
    газа (отрицательное — запас до насыщения; nan, если таких ячеек нет) и
    число ячеек сверх допуска.
    """
    st = history.states[-1]
    one = st.Sg <= SG_GAS
    if not np.any(one):
        return float("nan"), 0
    excess = st.Rs[one] - pvt.Rs_eq(st.p[one])
    return float(excess.max()), int(np.count_nonzero(excess > RS_TOL))


def _degassed_cells(config, history, pvt):
    """Маска ячеек, где газ выделился (p < pb), и само pb."""
    Rs0 = config.initial_conditions.Rs0
    pb = float(pvt.pb(np.array([Rs0]))[0])
    return history.states[-1].p < pb, pb


def front_radius(config, history, grid, pvt):
    """Радиус изобары p = pb (фронта разгазирования при падающем давлении).

    Брать центр последней ячейки с p < pb нельзя: фронт лежит ВНУТРИ ячейки,
    и такая оценка систематически занижает r_b. На логарифмической сетке
    ячейки к периферии широкие, и при фронте в несколько метров занижение
    доходит до ~10 %. Поэтому интерполируем ln r по p между соседними
    ячейками — профиль логарифмичен, интерполяция именно по ln r.

    np.interp здесь не годится: он требует возрастающий массив узлов, а p
    и ln r монотонны в противоположные стороны, и он молча вернёт мусор.
    """
    p = history.states[-1].p
    r = grid.r_centers
    _below, pb = _degassed_cells(config, history, pvt)

    j = int(np.searchsorted(p, pb))          # p возрастает с ростом r
    if not (0 < j < len(p)):
        return np.nan
    w = (pb - p[j - 1]) / (p[j] - p[j - 1])
    return float(np.exp(np.log(r[j - 1]) + w * (np.log(r[j]) - np.log(r[j - 1]))))


def make_overlay_rs(config):
    """Собрать overlay-функцию для example_runner, замкнув на неё config.

    Хук вызывается как overlay(ax, history, grid, simulator) и своего config
    не получает, а Simulator его не хранит — поэтому конфиг замыкается здесь.
    Так один и тот же код годится для любого примера без обёрток в нём.
    """
    def overlay(ax, history, grid, simulator):
        _draw_rs(ax, history, grid, simulator, config)
    return overlay


def _draw_rs(ax, history, grid, simulator, config):
    """Наложить Rs_eq(p) ячеек со свободным газом на профиль газосодержания.

    Вызывается после отрисовки численных кривых, поэтому отдельного PNG
    не создаётся — точки ложатся в rs_profiles.png.
    """
    pvt = simulator._energy._pvt

    st = history.states[-1]
    Rs0 = config.initial_conditions.Rs0
    gas = st.Sg > SG_GAS

    # Кружки — только в ячейках со свободным газом: там Rs обязано равняться
    # Rs_eq(p). В ячейках без газа равенства нет — нефть может быть
    # недонасыщена (DEBT-026), численная кривая там ограничена сверху, а не
    # задана. Без газа линию не строим: пустая дала бы пункт легенды без точек.
    if np.any(gas):
        ax.semilogx(grid.r_centers[gas], pvt.Rs_eq(st.p[gas]), 'ko',
                    markersize=4, markerfacecolor='none', zorder=5,
                    label=r"$R_s = R_s^{eq}(p)$, ячейки с газом")

    # Линия Rs0: при падающем давлении правее фронта нефть исходная и Rs
    # строго равно Rs0, левее — идёт разгазирование.
    ax.axhline(Rs0, color='gray', linestyle='-.', linewidth=1.0,
               label=rf"$R_{{s,0}}$ = {Rs0:.0f} м³ст/м³ст")

    # Изобара p = pb. Фронтом разгазирования она является, только если
    # свободный газ есть ровно в ячейках с p < pb. После восстановления
    # давления (12, 13b) газ остаётся лишь у забоя, а ниже pb лежит и
    # недонасыщенная нефть; у 04a газ остался и за изобарой. Тогда линия
    # подписывается тем, что она есть, — изобарой.
    r_b = front_radius(config, history, grid, pvt)
    if np.isfinite(r_b):
        below, _pb = _degassed_cells(config, history, pvt)
        if np.array_equal(below, gas):
            label = rf"фронт $r_b$ = {r_b:.3f} м"
        else:
            label = rf"изобара $p_b$: $r$ = {r_b:.3f} м"
        ax.axvline(r_b, color='gray', linestyle=':', linewidth=1.5,
                   label=label)


def report_rs(config, history, pvt) -> dict:
    """Печать проверки Rs в консоль. Возвращает сводку."""
    Rs0 = config.initial_conditions.Rs0
    if Rs0 <= 0.0:
        print("── Rs: сценарий однофазный (Rs0 = 0), проверять нечего ──")
        return dict(max_abs=0.0, max_rel=0.0)

    st = history.states[-1]
    d_abs, d_rel = rs_error(config, history, pvt)
    excess, n_bad = rs_supersaturation(history, pvt)
    below, pb = _degassed_cells(config, history, pvt)
    gas = st.Sg > SG_GAS
    one = ~gas
    # Нефть без газа ниже pb бывает только недонасыщенной: газ ушёл из
    # ячейки потоком или растворился весь при росте давления (12, 13b).
    # При монотонно падающем давлении таких ячеек нет.
    n_under = int(np.count_nonzero(one & below))
    # Rs > Rs0 — не нарушение: скопившийся у забоя газ при росте давления
    # выше pb(Rs0) растворяется сверх Rs0, если PVT это допускает.
    n_above = int(np.count_nonzero(st.Rs > Rs0 + RS_TOL))

    print("── Rs: равновесие Black Oil без кинетики ──")
    print(f"  ячейки с газом (Sg > {SG_GAS:g}) — {int(gas.sum())}: "
          f"max|Rs_числ - Rs_eq(p)| = {d_abs:.3e} м³ст/м³ст "
          f"({d_rel * 100:.2e} % от Rs0)")
    print(f"  ячейки без газа — {int(one.sum())}: пересыщенных "
          f"(Rs > Rs_eq(p) + {RS_TOL:g}) — {n_bad}, "
          f"ниже pb (нефть недонасыщена) — {n_under}")
    if n_bad:
        print(f"    наибольшее Rs - Rs_eq(p) = {excess:.3e} м³ст/м³ст")
    print(f"  Rs: {st.Rs.min():.4f} … {st.Rs.max():.4f} при Rs0 = {Rs0:.1f}, "
          f"pb = {pb / 1e6:.4f} МПа; ячеек с Rs > Rs0: {n_above}")

    return dict(max_abs=d_abs, max_rel=d_rel, n_two_phase=int(gas.sum()),
                n_supersaturated=n_bad, max_excess=excess,
                n_single_below_pb=n_under, n_above_rs0=n_above, pb=pb)
```

Отличия от старой версии, которые важно не потерять при переносе: `_degassed_cells`, тело `front_radius` и `make_overlay_rs` — без изменений; у `front_radius` поменялась только первая строка докстринга; `rs_expected` — только докстринг.

4. Запустить новый файл — зелёный; затем быстрый уровень.

**Изменения (старый → новый, ключевое):**
- До: `rs_error` — `Rs_ana = rs_expected(config, pvt, st.p); d = np.abs(Rs_ana - st.Rs)` по всем ячейкам.
  После: только ячейки `st.Sg > SG_GAS`, сравнение с `pvt.Rs_eq(st.p[gas])`.
- До: `report_rs` печатает `ячеек с p < pb: …, с Sg > 0: … — совпадают: {same}`.
  После: строки «ячейки с газом», «ячейки без газа», «Rs: … ячеек с Rs > Rs0».
- До: `_draw_rs` — кружки `rs_expected` во всех ячейках, подпись `$R_s = \min(R_s^{eq}(p),\ R_{s,0})$`, линия «фронт $r_b$».
  После: кружки `Rs_eq(p)` в ячейках с газом, подпись линии по ситуации.

Пример вывода нового `report_rs` (замер аудита, 13b):
```
── Rs: равновесие Black Oil без кинетики ──
  ячейки с газом (Sg > 1e-08) — 14: max|Rs_числ - Rs_eq(p)| = 7.105e-15 м³ст/м³ст (2.37e-14 % от Rs0)
  ячейки без газа — 36: пересыщенных (Rs > Rs_eq(p) + 1e-05) — 0, ниже pb (нефть недонасыщена) — 30
  Rs: 17.4143 … 30.0000 при Rs0 = 30.0, pb = 15.0000 МПа; ячеек с Rs > Rs0: 0
```

**Проверка после этого шага:**
- `.venv\Scripts\python -m pytest tests/test_rs_analytics.py -q` — 12 passed.
- Регресс: быстрый (`-m "not slow" -q`) — ожидается 987 + 12 = 999 passed. В нём и шпион `report_rs` (`test_examples.py:551–597`, пример 05 со `steady_state=False`).

**Подводные камни:** `rs_expected` не трогать по семантике (тест побитовой сверки с `pvt_plot._physical_rs`, slow — проверится в шаге 3). Ключи словаря `report_rs` меняются — потребителей нет (§2).

**Зависимости:** требует шаг 1 (гейт); блокирует 3, 5.

**Оценка:** ~450 строк (модуль ~230, тесты ~260 — текст готов, перенос), ~30 мин.

---

### Шаг 3: Общий slow-тест проверки $R_s$ на всех примерах с газом

**Цель:** закрыть пробел — проверка $R_s$ впервые проверяется автоматически на штатных конфигах всех 18 примеров с газом, включая 12 и 13b.

**Файлы:** `numerical_solver/tests/test_examples.py` — класс `TestSharedChecks` (стр. 625–782), новый метод после `test_energy_balance_reported_for_all_examples` (стр. 739–781, перед разделителем `# J. Графики PVT` на стр. 784).

**Контекст:** фикстура `results` уже считает все примеры для других slow-тестов, поэтому новый тест расчётов не добавляет. PVT берётся `_pvt_of_config` (`test_examples.py:816`, фабрика по конфигу — тот же приём, что в `test_physical_branch_matches_rs_analytics`); функция определена ниже по файлу, но вызывается во время теста — порядок определения не важен. Метка `slow` ставится автоматически хуком `tests/conftest.py` (тест использует `results`).

**Что сделать:** добавить метод:

```python
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
        import sys
        sys.path.insert(0, str(EXAMPLES_DIR))
        from rs_analytics import report_rs

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
```

Порог `1e-10` для равенства — тот же, что `atol` в `test_repressurization_leaves_undersaturated_oil`; запас к замеру — 4 порядка.

**Проверка после этого шага:**
- Целевой прогон slow-тестов модуля (~4 мин, считаются все примеры):
  ```powershell
  .venv\Scripts\python -m pytest tests/test_examples.py -q -k "rs_check_all_two_phase or physical_branch_matches_rs_analytics or rho_matches_formula or repressurization_leaves_undersaturated"
  ```
  Ожидается 4 passed.
- Регресс: быстрый — 999 passed (новый тест в быстрый уровень не входит).

**Подводные камни:** если порог `1e-10` нарушен у какого-то примера — это не повод поднимать порог: замер шага 1 показал, что нарушать нечему; разобрать.

**Зависимости:** требует шаг 2.

**Оценка:** ~40 строк, ~10 мин (+4 мин прогона).

---

### Шаг 4: Докстринг `pvt_plot._physical_rs`

**Цель:** убрать ложное утверждение «газосодержание, реально бывшее в расчёте».

**Файл:** `numerical_solver/examples/pvt_plot.py:93–101`.

**Контекст:** `_physical_rs` рисует физическую кривую PVT и считает опорные точки сводки (стр. 251) по $\min(R_s^{eq}(p), R_{s,0})$. У 12 и 13b в расчёте была и недонасыщенная нефть ниже $p_b$, которой на этой кривой нет. Код не меняется — решение пользователя: только фраза докстринга.

**Изменения:**
До:
```python
    """Газосодержание, реально бывшее в расчёте: min(Rs_eq(p), Rs0).

    p >= p_b — нефть недонасыщена, весь газ растворён, Rs держится на Rs0;
    p <  p_b — нефть насыщена, избыток выделился, Rs = Rs_eq(p).
    Та же формула, что в rs_analytics.rs_expected; ядро считает её само,
    здесь она нужна для сводки и для ординат узлов таблицы.
    """
```
После:
```python
    """Газосодержание при падающем давлении: min(Rs_eq(p), Rs0).

    p >= p_b — нефть недонасыщена, весь газ растворён, Rs держится на Rs0;
    p <  p_b — нефть насыщена, избыток выделился, Rs = Rs_eq(p).
    После восстановления давления в расчёте бывает и недонасыщенная нефть
    ниже p_b (примеры 12, 13b; DEBT-026) — этой кривой она не описывается.
    Та же формула, что в rs_analytics.rs_expected; ядро считает её само,
    здесь она нужна для сводки и для ординат узлов таблицы.
    """
```

**Проверка после этого шага:** Регресс: `--collect-only -q` — число тестов не меняется (только докстринг).

**Зависимости:** нет (можно делать в любом порядке после шага 1).

**Оценка:** 2 строки, ~3 мин.

---

### Шаг 5: Замер после правки и визуальная проверка `rs_profiles.png`

**Цель:** подтвердить числа для README и убедиться, что рисунок соответствует решению пользователя.

**Файлы:** новый `vault/issues/debt-026/probes/rs_check_after.txt`; `examples/*/output/` (в git не хранятся).

**Что сделать:**
1. Повторить замер шага 1 тем же скриптом (переменные — «Как начать», п. 7; `--solver $S` обязателен в worktree, иначе скрипт возьмёт старый `rs_analytics.py` основного каталога, и блок `report_rs` выйдет в прежнем формате):
   ```powershell
   & $PY "$P\rs_check_numbers.py" --solver $S --out "$P\rs_check_after.txt"
   ```
2. Сверить: блоки «прежняя», «новая», «предпосылки» **побитово совпадают** с `rs_check_before.txt` (решатель не менялся); блок `report_rs` — новый формат, его числа совпадают с блоком «новая» (с газом, max|Rs − Rs_eq(p)|, пересыщенных, ниже pb, Rs > Rs0).
3. Запустить примеры, у которых меняется рисунок, и посмотреть `output/rs_profiles.png` (Read по PNG). Из `numerical_solver` рабочего каталога (`$S`); `$PY` — потому что в worktree своего `.venv` нет:
   ```powershell
   & $PY examples\03_standing_corey\main.py
   & $PY examples\04_table_table\main.py
   & $PY examples\04a_high_gas_saturation\main.py
   & $PY examples\12_large_drainage_radius\main.py
   & $PY examples\13b_pwf_alternating\main.py
   ```
   Ожидание (04, 04a, 12, 13b проверены при аудите тем же кодом наложения):
   - 03 — кружки только левее фронта, «фронт $r_b$ = … м»;
   - 04 — 26 кружков, «фронт $r_b$ = 2.637 м» (ячейка «флаг без газа» на 2.70 м — без кружка);
   - 04a — 70 кружков, из них 5 за линией, «изобара $p_b$: $r$ = 1.508 м»;
   - 12 — 46 кружков до ~100 м, у ячейки 117.9 м кружка нет, «изобара $p_b$: $r$ = 121.112 м»;
   - 13b — 14 кружков ближе 0.8 м, «изобара $p_b$: $r$ = 81.811 м».
4. Из консоли 13b взять блок `── Rs: равновесие Black Oil без кинетики ──` (4 строки) — пойдёт в README 13b дословно (ожидаемый текст — в шаге 2, «Пример вывода»). Из консоли 12 — числа для README 12.

**Проверка после этого шага:** Регресс: `--collect-only -q` — 1223 (код не менялся).

**Зависимости:** требует шаги 2–3; блокирует шаг 6.

**Оценка:** ~15 мин (расчёт ~4 мин + 5 примеров).

---

### Шаг 6: README и комментарии примеров

**Цель:** документация и комментарии описывают новую проверку; объяснения «совпадают: False» убраны.

**Файлы:**
- `numerical_solver/examples/README.md` (стр. 228, 393–440, 620)
- `numerical_solver/examples/03_standing_corey/README.md` (стр. 297–300)
- `numerical_solver/examples/04_table_table/README.md` (стр. 124–125, 320–321)
- `numerical_solver/examples/04a_high_gas_saturation/README.md` (стр. 229, 431)
- `numerical_solver/examples/05_standing_table_rp/README.md` (стр. 104, 107)
- `numerical_solver/examples/12_large_drainage_radius/README.md` (стр. 168–173)
- `numerical_solver/examples/13b_pwf_alternating/README.md` (стр. 162–181)
- `numerical_solver/examples/03_standing_corey/main.py` (стр. 10–12, 86–88) — комментарии
- `numerical_solver/examples/05_standing_table_rp/main.py` (стр. 9–11) — комментарий

**Не трогать** (решение пользователя): `03_standing_corey/README.md` §3 (стр. 167–170), `19_rs150_cooling/README.md:148`, `20_rs300_cooling/README.md:163–167`, `21_rs100_cooling/README.md:148` — утверждения о решении при падающем давлении остаются верными.

Числа ниже — замер аудита (`rs_check_audit.txt`); сверить с `rs_check_after.txt` (шаг 5), при расхождении — взять из `rs_check_after.txt`. Стиль README — без англицизмов (CLAUDE.md, «Без англицизмов»).

**Изменения:**

**6.1. `examples/README.md:228`**
До:
```
| `rs_profiles.png` | $R_s(r)$ + аналитика $\min(R_s^{eq}(p), R_{s,0})$ — только у сценариев с $R_{s,0} > 0$ (все, кроме 01–02); в 01–02 газа нет |
```
После:
```
| `rs_profiles.png` | $R_s(r)$ + $R_s^{eq}(p)$ в ячейках с газом — только у сценариев с $R_{s,0} > 0$ (все, кроме 01–02); в 01–02 газа нет |
```

**6.2. `examples/README.md:393–440`** — раздел «Проверка $R_s$ — во всех сценариях с газом» целиком (от заголовка до строки «другое не видно на профилях $p$ и $S_g$.» включительно; следующий раздел «### Баланс энергии — во всех сценариях без исключения» не трогать). После:

```
### Проверка $R_s$ — во всех сценариях с газом

В модели Black Oil газосодержание не имеет собственной динамики — ни
релаксации, ни кинетики выделения. В ячейке со свободным газом нефть
насыщена, и $R_s$ задан давлением; в ячейке без газа равновесие даёт
только верхнюю границу:

$$\text{есть газ: } R_s = R_s^{eq}(p), \qquad
\text{газа нет: } R_s \le R_s^{eq}(p).$$

Нефть без газа может быть недонасыщена: исходная правее фронта
($R_s = R_{s,0}$) или оставшаяся после восстановления давления, когда
свободный газ растворился весь, а давление ещё ниже $p_b$. Пересыщенной
она быть не может — с точностью до допуска, при котором решатель
включает газ ($10^{-5}$ м³ст/м³ст). Формула
$R_s = \min(R_s^{eq}(p), R_{s,0})$ верна только при монотонно падающем
давлении.

Модуль [rs_analytics.py](rs_analytics.py) проверяет оба условия на
последней записи у всех сценариев с $R_{s,0} > 0$ и печатает в консоль
расхождение в ячейках с газом, число пересыщенных ячеек без газа и число
ячеек без газа ниже $p_b$. Ячейкой с газом считается $S_g > 10^{-8}$. Ячейки,
которые решатель после растворения газа ещё числит двухфазными
($S_g \sim 10^{-14}$; таблицы без ветвей выше $R_{s,0}$ — одна ячейка у
04, 06–09, девять у 04a), идут в ячейки без газа: в них
$R_s = R_s^{eq}(p) = R_{s,0}$. На `rs_profiles.png` кружки — $R_s^{eq}(p)$ в
ячейках с газом; вертикальная линия — изобара $p = p_b$. Она подписана
«фронт $r_b$», если свободный газ есть ровно в ячейках с $p < p_b$, и
«изобара $p_b$» иначе.

Проверка зависит только от PVT, поля давления и $S_g$, поэтому применима
и к аналитическому PVT (03, 05, 19–21), и к табличному (остальные с
газом). Ноль в столбце расхождения — побитовое совпадение: в ячейке с
газом решатель присваивает $R_s = R_s^{eq}(p)$ той же функцией.

| пример | PVT | $R_s$ диапазон | ячеек с газом | $\max\|R_s^{числ}-R_s^{eq}(p)\|$ | без газа с $p<p_b$ | пересыщенных |
|---|---|---|---|---|---|---|
| 03 | Standing | 41.48 … 50 | 16 | 0 | 0 | 0 |
| 04, 07–09 | таблица | 9.50 … 30 | 26 | 0 | 0 | 0 |
| 04a | таблица | 0 … 30 | 70 | $5.3\cdot10^{-15}$ | 0 | 0 |
| 05 | Standing | 42.00 … 50 | 6 | 0 | 0 | 0 |
| 06 | таблица | 9.52 … 30 | 26 | 0 | 0 | 0 |
| 10 | таблица | 3.61 … 30 | 29 | 0 | 0 | 0 |
| 11 | таблица | 3.35 … 29.95 | 50 | $7.1\cdot10^{-15}$ | 0 | 0 |
| 12 | таблица | 3.37 … 30 | 46 | $7.1\cdot10^{-15}$ | 1 | 0 |
| 13a | таблица | 3.37 … 30 | 47 | $5.3\cdot10^{-15}$ | 0 | 0 |
| 13b | таблица | 17.41 … 30 | 14 | $7.1\cdot10^{-15}$ | 30 | 0 |
| 14 | таблица | 29.66 … 150 | 320 | $2.8\cdot10^{-14}$ | 0 | 0 |
| 15 | таблица | 3.76 … 30 | 46 | $3.6\cdot10^{-15}$ | 0 | 0 |
| 19 | Standing | 13.25 … 150 | 334 | 0 | 0 | 0 |
| 20 | Standing | 36.17 … 300 | 289 | 0 | 0 | 0 |
| 21 | Standing | 13.10 … 100 | 328 | 0 | 0 | 0 |

Нефть без газа ниже $p_b$ есть только у сценариев с восстановлением
давления. У 12 это ячейка за стационарным фронтом: свободный газ ушёл из
неё, пока давление возвращалось, но было ещё ниже $p_b$, и растворять
обратно нечего. У 13b последняя запись сделана при 10.75 МПа после суток
при 6 МПа: свободного газа на обратное растворение не хватило, и на
0.9–75 м нефть недонасыщена. У 04a свободный газ остался и в пяти ячейках
с $p > p_b$ — остаток переходного процесса; таблица даёт там
$R_s^{eq}(p) = R_{s,0}$, и равенство выполняется. У этих трёх сценариев
линия на `rs_profiles.png` подписана «изобара $p_b$».

Точность в ячейках с газом машинная, потому что обе величины — одна и та
же функция от одного и того же $p$. Проверка не избыточна: расхождение
означало бы либо паразитную релаксацию в схеме (газ выделяется не
мгновенно), либо рассогласование PVT энергетического блока с PVT
гидродинамики, а пересыщение — растворение газа сверх равновесия. Ничего
из этого не видно на профилях $p$ и $S_g$.
```

Строка 14 прежней таблицы устарела (было «10.40 … 150», «47» — до перевода примера на $N = 350$ и год расчёта); новые числа — из замера. Если у 04 и 07–09 числа в шаге 5 различаются — разбить строку.

**6.3. `examples/README.md:620`**
До:
```
| [rs_analytics.py](rs_analytics.py) | $R_s = \min(R_s^{eq}(p), R_{s,0})$ | — |
```
После:
```
| [rs_analytics.py](rs_analytics.py) | $R_s = R_s^{eq}(p)$ в ячейках с газом, $R_s \le R_s^{eq}(p)$ в остальных | — |
```

**6.4. `03_standing_corey/README.md:297–300`**
До:
```
- `rs_profiles.png` — $R_s(r)$ с изломом ровно на фронте: слева
  газосодержание падает по корреляции Стендинга, справа держится на
  $R_{s,0} = 50$. Кружки — $R_s = \min(R_s^{eq}(p), R_{s,0})$, совпадение
  $1.4\cdot10^{-14}$.
```
После:
```
- `rs_profiles.png` — $R_s(r)$ с изломом ровно на фронте: слева
  газосодержание падает по корреляции Стендинга, справа держится на
  $R_{s,0} = 50$. Кружки — $R_s^{eq}(p)$ в ячейках с газом, совпадение
  побитовое.
```

**6.5. `04_table_table/README.md:124–125`**
До:
```
| $R_s = \min(R_s^{eq}(p), R_{s,0})$ | $2.1\cdot10^{-14}$ |
| ячейки с $p < p_b$ и с $S_g > 0$ | совпадают (26) |
```
После:
```
| $R_s = R_s^{eq}(p)$ в ячейках с газом | 0, побитово (26 ячеек) |
| ячейки без газа: пересыщенных / ниже $p_b$ | 0 / 0 |
```

**6.6. `04_table_table/README.md:320–321`**
До:
```
- `rs_profiles.png` — $R_s(r)$ с изломом на фронте; кружки —
  $R_s = \min(R_s^{eq}(p), R_{s,0})$.
```
После:
```
- `rs_profiles.png` — $R_s(r)$ с изломом на фронте; кружки —
  $R_s^{eq}(p)$ в ячейках с газом.
```

**6.7. `04a_high_gas_saturation/README.md:229`**
До:
```
$R_s = \min(R_s^{eq}(p), R_{s,0})$ выполняется с точностью $10^{-13}$.
```
После:
```
$R_s = R_s^{eq}(p)$ в 70 ячейках с газом выполняется с точностью
$5.3\cdot10^{-15}$, в том числе в пяти за изобарой $p_b$: там
$R_s^{eq}(p) = R_{s,0}$.
```

**6.8. `04a_high_gas_saturation/README.md:431`**
До:
```
- `rs_profiles.png` — $R_s(r)$: ноль у забоя, $R_{s,0}$ за фронтом.
```
После:
```
- `rs_profiles.png` — $R_s(r)$: ноль у забоя, $R_{s,0}$ за фронтом.
  Вертикальная линия подписана «изобара $p_b$»: свободный газ остался и в
  пяти ячейках за ней (см. «Газ за фронтом» выше).
```

**6.9. `05_standing_table_rp/README.md:104` и `:107`**
До (стр. 104):
```
| ячейки $p<p_b$ и ячейки $S_g>0$ | совпадают |
```
После:
```
| ячейки без газа: пересыщенных / ниже $p_b$ | 0 / 0 |
```
До (стр. 107):
```
| $R_s = \min(R_s^{eq}(p), R_{s,0})$ | $\max\|\Delta R_s\| = 7.1\times10^{-15}$ |
```
После:
```
| $R_s = R_s^{eq}(p)$ в ячейках с газом | $\max\|\Delta R_s\| = 0$, побитово (6 ячеек) |
```

**6.10. `12_large_drainage_radius/README.md:168–173`**
До:
```
Поэтому проверка $R_s$ в консоли на 15 сут печатает «ячеек с p < pb: 47,
с Sg > 0: 46 — совпадают: False» и $\max\lvert R_s - R_s^{равн}\rvert =
0.025$ м³ст/м³ст. Проверка предполагает $R_s = \min(R_s^{eq}(p), R_{s,0})$
и не учитывает восстановление давления без свободного газа. Это поведение
модели Black Oil, а не ошибка. По той же причине число двухфазных ячеек в
таблице выше убывает с 47 до 46 на 13 сут.
```
После:
```
Проверка $R_s$ в консоли на 15 сут это состояние допускает: равенство
$R_s = R_s^{eq}(p)$ проверяется в 46 ячейках с газом ($7.1\cdot10^{-15}$
м³ст/м³ст), а для ячеек без газа — только отсутствие пересыщения; ячейка
за фронтом попадает в строку «ниже pb (нефть недонасыщена) — 1». По той
же причине число двухфазных ячеек в таблице выше убывает с 47 до 46 на
13 сут, а вертикальная линия на `rs_profiles.png` подписана «изобара
$p_b$», а не «фронт».
```

**6.11. `13b_pwf_alternating/README.md:162–181`** — раздел «## Проверка газосодержания $R_s$» до строки «ячеек (46 и 46).» включительно (следующий раздел «## Стационарная аналитика отключена» не трогать). После:

````
## Проверка газосодержания $R_s$

Общий модуль `rs_analytics.py` проверяет на последней записи равновесие
Black Oil: в ячейках со свободным газом $R_s = R_s^{eq}(p)$, в ячейках без
газа $R_s \le R_s^{eq}(p)$. Консоль печатает:

```
── Rs: равновесие Black Oil без кинетики ──
  ячейки с газом (Sg > 1e-08) — 14: max|Rs_числ - Rs_eq(p)| = 7.105e-15 м³ст/м³ст (2.37e-14 % от Rs0)
  ячейки без газа — 36: пересыщенных (Rs > Rs_eq(p) + 1e-05) — 0, ниже pb (нефть недонасыщена) — 30
  Rs: 17.4143 … 30.0000 при Rs0 = 30.0, pb = 15.0000 МПа; ячеек с Rs > Rs0: 0
```

Равенство выполняется в 14 ячейках с газом у забоя. 30 ячеек без газа
ниже $p_b$ — недонасыщенная нефть на 0.9–75 м (см. выше), а не
расхождение: давление поднялось после суток при 6 МПа, и свободного газа
на обратное растворение не хватило. На `rs_profiles.png` кружки стоят
только в ячейках с газом; вертикальная линия подписана «изобара $p_b$» —
она на 82 м (интерполяция между ячейками), а свободный газ только ближе
0.9 м.
````

(Внешняя ограда в плане — четыре обратных апострофа только для отображения; в README — обычный блок кода в три апострофа, как сейчас на стр. 168–173.) «0.9–75 м» — центры ячеек недонасыщенной нефти, как в тексте README 13b выше (стр. 145–150); изобара по интерполяции `front_radius` лежит между ячейками, на 81.8 м.

**6.12. `03_standing_corey/main.py:10–12`** (докстринг модуля примера)
До:
```
  p, Sg, Rs — ставит сам example_runner из общих модулей closed_form.py и
       rs_analytics.py: замкнутое решение (дебит квадратурой, профили p и
       Sg без единого числа из расчёта) и равновесие Rs = min(Rs_eq(p), Rs0).
```
После:
```
  p, Sg, Rs — ставит сам example_runner из общих модулей closed_form.py и
       rs_analytics.py: замкнутое решение (дебит квадратурой, профили p и
       Sg без единого числа из расчёта) и равновесие Rs: Rs = Rs_eq(p) в
       ячейках с газом, Rs <= Rs_eq(p) в остальных.
```

**6.13. `03_standing_corey/main.py:86–88`**
До:
```
        # Rs здесь не передаём: проверка min(Rs_eq(p), Rs0) не зависит
        # ни от ОФП, ни от источника PVT, поэтому её ставит сам
        # example_runner из общего модуля rs_analytics.py.
```
После:
```
        # Rs здесь не передаём: проверка равновесия Rs не зависит
        # ни от ОФП, ни от источника PVT, поэтому её ставит сам
        # example_runner из общего модуля rs_analytics.py.
```

**6.14. `05_standing_table_rp/main.py:9–11`**
До:
```
  p, Sg, Rs — ставит сам example_runner из общих модулей closed_form.py и
       rs_analytics.py: замкнутое решение (дебит квадратурой, профили без
       единого числа из расчёта) и равновесие Rs = min(Rs_eq(p), Rs0).
```
После:
```
  p, Sg, Rs — ставит сам example_runner из общих модулей closed_form.py и
       rs_analytics.py: замкнутое решение (дебит квадратурой, профили без
       единого числа из расчёта) и равновесие Rs: Rs = Rs_eq(p) в ячейках
       с газом, Rs <= Rs_eq(p) в остальных.
```

**Проверка после этого шага:**
- Регресс: быстрый — 999 passed (`TestReadme` — быстрый уровень, проверяет разделы «Как модифицировать», «увеличить газонасыщенность», имена классов; ни один из них правками не затрагивается).
- grep контроля по `numerical_solver/examples` (`**/README.md`, `**/main.py`): `совпадают: False`, `задача DEBT-026`, `‹` — пусто; `min(R_s^{eq}` / `min(Rs_eq` остаётся только в 03 README §3, README 19, 20, 21, `rs_analytics.py` (`rs_expected`, докстринг), `pvt_plot.py` и в новом тексте сводного README («верна только при монотонно падающем давлении»).

**Зависимости:** требует шаг 5.

**Оценка:** ~110 строк текста, ~30 мин.

---

### Шаг 7: Vault

**Цель:** знания и реестр отражают новое состояние.

**Файлы:**
- `vault/knowledge/science/давление и газонасыщенность выходят на стационар вместе — различается амплитуда.md` (стр. 69–71)
- `vault/roadmap/известные баги и технический долг.md` — секция `### DEBT-026`

**Что сделать:**
1. В заметке о стационаре — фраза начинается в середине стр. 70 и переносится на стр. 71.
   До:
   ```
   $R_s < R_s^{eq}(p)$. Проверка `rs_analytics` ($R_s = \min(R_s^{eq}(p), R_s^0)$)
   такие ячейки не учитывает и печатает расхождение.
   ```
   После:
   ```
   $R_s < R_s^{eq}(p)$. До [[DEBT-026]] проверка `rs_analytics`
   ($R_s = \min(R_s^{eq}(p), R_s^0)$ во всех ячейках) такие ячейки не учитывала
   и печатала расхождение; теперь в ячейках без газа проверяется только
   $R_s \le R_s^{eq}(p)$.
   ```
2. Реестр DEBT-026: статус и строка о результате — по контракту `/implement` (влитие, коммит, число тестов).

**Проверка после этого шага:** `--collect-only -q` — 1223.

**Зависимости:** требует шаги 2–6.

**Оценка:** ~5 строк, ~5 мин.

---

## 7. Тестовая стратегия

| Тест | Файл | Сценарий | Ожидание | Предотвращает |
|---|---|---|---|---|
| `test_monotone_pressure_passes` | `tests/test_rs_analytics.py` (новый, быстрый) | падающее давление, фронт на 15 МПа | `max_abs == 0`, нарушений 0, ниже pb 0 | ложные срабатывания на штатных примерах |
| `test_repressurization_undersaturated_is_not_violation` | то же | картина 13b | прежняя формула даёт 2.0; новая — нарушений 0, ниже pb 3 | возврат к $\min(\ldots)$ во всех ячейках |
| `test_supersaturated_single_phase_is_violation` | то же | без газа $R_s = R_s^{eq} + 0.5$ | `n_supersaturated == 1`, `max_excess ≈ 0.5` | проверка перестала ловить пересыщение |
| `test_two_phase_mismatch_is_reported` | то же | с газом $R_s = R_s^{eq} - 10^{-3}$ | `max_abs ≈ 1e-3`, `max_rel ≈ 1e-3/30` | двухфазная часть ослабла |
| `test_tolerance_on_flat_branch` | то же | шум $10^{-12}$ на горизонтальной ветви таблицы | нарушений 0 | ложные пересыщения от шума Ньютона |
| `test_supersaturation_within_solver_tolerance_is_accepted` | то же | пересыщение $0.5\,$`RS_TOL` и $2\,$`RS_TOL`; `RS_TOL` = умолчание `rs_switch_tol` прототипа | нарушение ровно одно | проверка строже решателя; рассинхрон с прототипом |
| `test_rs_above_rs0_is_observation_not_violation` | то же | Стендинг, $R_{s,0} < R_s < R_s^{eq}(p)$ | нарушений 0, `n_above_rs0 == 1` | возврат к варианту 1 |
| `test_no_two_phase_cells` | то же | газа нет | `max_abs == 0`, `n_two_phase == 0` | падение на пустой маске |
| `test_noise_cell_with_solver_flag_is_single_phase` | то же | `regime == 1`, $S_g = 10^{-14}$ за изобарой (артефакт 04, 04a) | не считается ячейкой с газом, кружка нет, подпись «фронт» | возврат к отбору по флагу `regime` |
| `test_overlay_marks_only_two_phase_and_front_label` | то же | рисунок, падающее давление | кружки = ячейки с газом, подпись «фронт» | рисунок разошёлся с проверкой; смена подписи у штатных примеров |
| `test_overlay_isobar_label_after_repressurization` | то же | рисунок, картина 13b | подпись «изобара», «фронт» нет | ложная подпись «фронт» |
| `test_overlay_without_gas_has_no_marks` | то же | газа нет | кружков нет | пустой пункт легенды |
| `test_rs_check_all_two_phase_examples` | `tests/test_examples.py::TestSharedChecks` (slow) | штатные конфиги 18 примеров | `max_abs ≤ 1e-10`, пересыщенных 0; 12 и 13b — ниже pb ≥ 1 | регресс проверки на реальных решениях; пробел «проверка только печатается» |

Существующие тесты, которые должны остаться зелёными без изменений: шпион `report_rs` (`test_examples.py:551–597`, быстрый), `test_physical_branch_matches_rs_analytics`, `test_rho_matches_formula`, `test_repressurization_leaves_undersaturated_oil` (slow, прогоняются в шаге 3 целевым запуском и в итоговом полном).

Число тестов: 1210 → 1223. В `tests/test_rs_analytics.py` 12 тестов (быстрый уровень), в `test_examples.py` +1 (slow). Быстрый уровень: 987 → 999.

Предпосылки синтетических тестов проверены (2026-10-03) на настоящем PVT: пример 04 — $R_{s,0} = 30$, $p_b = 15.0$ МПа, $R_s^{eq}$ при 8 / 10 / 10.75 / 12 / 14 / 16 / 18 МПа = 9 / 15 / 17.25 / 21 / 27 / 30 / 30; пример 03 — $R_{s,0} = 50$, $p_b = 9.43$ МПа, $R_s^{eq}(1.5\,p_b) = 80.9$; `pvt.Rs_eq(np.array([]))` возвращает пустой массив без ошибки.

---

## 8. Критерии завершения

- [ ] Шаги 1–7 выполнены; замер шага 1 совпал с `rs_check_audit.txt` (или расхождения согласованы с пользователем).
- [ ] `tests/test_rs_analytics.py` — 12 passed; `test_rs_check_all_two_phase_examples` — passed.
- [ ] Полный прогон зелёный: 1223 passed (итоговый прогон `/implement`).
- [ ] `rs_check_after.txt`: блоки «прежняя/новая/предпосылки» побитово равны `rs_check_before.txt`; у всех 18 примеров пересыщенных 0, ошибка в ячейках с газом $\le 10^{-10}$; без газа ниже pb: 12 → 1, 13b → 30, остальные 0.
- [ ] Визуальная проверка `rs_profiles.png` у 03, 04, 04a, 12, 13b пройдена (шаг 5).
- [ ] README и `main.py`: grep `совпадают: False`, `задача DEBT-026`, `‹` по `numerical_solver/examples` — пусто.
- [ ] `gpn_multiphase_solver/` и `HydroSolverPrototype/` не изменены (`git diff --stat numerical_scheme/implementation -- numerical_solver/gpn_multiphase_solver numerical_solver/HydroSolverPrototype` — пусто).
- [ ] Vault обновлён (заметка о стационаре, реестр).
- [ ] Issue #56 прокомментирован с результатом (`vault/issues/debt-026/05-comment-done.md`).

---

## 9. Обнаруженные проблемы

1. **Список `SHARED_CHECK_MODULES` в `tests/test_examples.py:610–616` неполон.** Защита «общий модуль не скопирован в папку примера» (копия в папке молча перекрывает общий модуль — механизм BUG-004) охватывает только модули FEAT-016 и `pvt_plot.py`. `rs_analytics.py`, `closed_form.py`, `relperm_plot.py` и `figure_io.py` не защищены. Текущую задачу не блокирует. Зарегистрировано как [[DEBT-037]].
2. **Шесть полей `NumericsConfig` не передаются прототипу** (аудит 2026-10-03): `newton_max_iter`, `newton_rtol`, `newton_atol`, `max_active_set_iter`, `rs_switch_tol`, `sg_switch_tol` (`io/config.py:141-146`) — фабрика создаёт `RadialBlackOilModel` только с `skin`, `jacobian_mode`, `linear_solver` (`factory.py:318-326`); grep по пакету — только объявления (и проверка умолчания в `tests/test_config.py:276`). Докстринг класса («передаются в Newton-солвер прототипа») неверен. Для DEBT-026 следствие одно: допуск `RS_TOL` нельзя брать из конфига. Не блокирует. Дописано в [[DEBT-008]] (мёртвые поля конфига).
3. Строка примера 14 в сводной таблице `examples/README.md` устарела («10.40 … 150», «да (47)»; замер: 29.66 … 150, 320 ячеек) — исправляется шагом 6.2 этого плана.
4. Фразы «Проверка $R_s = \min(R_s^{eq}(p), R_{s,0})$ и баланс энергии остаются» в README 19 и 21 (стр. 148) называют проверку по прежней формуле. Решение пользователя — не трогать (при падающем давлении утверждение верно). Не регистрируется.

---

## Связанные заметки

- Запись: `vault/roadmap/известные баги и технический долг.md` → `### DEBT-026`
- Issue: [#56](https://github.com/ArturSalamatin/Oil_Gas/issues/56); тело и комментарии — `vault/issues/debt-026/`
- Замеры: `vault/issues/debt-026/probes/rs_check_numbers.py` (скрипт шагов 1 и 5), `rs_check_audit.txt` (эталон аудита), `sg_noise.py` («флаги без газа» у 04, 04a, 12, 13b); замер, на котором обнаружено, — `vault/issues/feat-023/probes/plan_numbers.py`
- [[давление и газонасыщенность выходят на стационар вместе — различается амплитуда]] — пример 12, недонасыщенная нефть за фронтом
- [[проверка выносится в общий модуль если не зависит от комбинации PVT и ОФП]] — почему `rs_analytics.py` общий
- [[пересыщенный старт решатель молча уравновешивает скачком давления]] — допуск пересыщения = критерий включения газа решателем ($10^{-5}$)
- Связанные задачи: [[FEAT-019]], [[FEAT-021]] (#39), [[FEAT-023]] (#40), [[BUG-014]] (#42), [[BUG-017]] (`_RS0_SUPERSAT_TOL`), [[DEBT-008]], [[DEBT-037]]
