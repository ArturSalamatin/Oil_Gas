---
tags:
  - план
  - рефакторинг
date: 2026-10-15
issue: DEBT-073
github: 123
branch: refactor/debt-073/relperm-mobile-oil-edge
status: реализован
worktree: .worktrees/debt-073
audit:
  date: 2026-10-15
  round: 1
  found: 7
  auto-fixed: 7
  manual-required: 0
---

# DEBT-073: отказ фабрики при $k_{ro} > 0$ в последней строке таблицы ОФП

## Как начать работу по этому плану

1. Прочитай этот файл целиком.
2. Прочитай запись DEBT-073 в `vault/roadmap/известные баги и технический долг.md` (замеры 1–3, решение пользователя) и комментарии issue #123: `vault/issues/debt-073/02a-comment-probes.md`, `02b-comment-decision.md`.
3. Worktree и ветка — по `/implement`: базовая ветка `numerical_scheme/implementation`, ветка `refactor/debt-073/relperm-mobile-oil-edge`, каталог `.worktrees/debt-073`.
4. Python: `.venv\Scripts\python` основного каталога `numerical_solver/`. Тесты — из `numerical_solver/` worktree, pytest берёт код worktree. Прототип не меняется: его тесты и регрессия не нужны.
5. Исходная точка (на `0d5c491`, 2026-10-15; к аудиту база ушла на `3899d9b` — только коммиты vault, код и числа те же): `.venv\Scripts\python -m pytest tests/ --collect-only -q` — **1993** теста; `.venv\Scripts\python -m pytest tests/ -m "not slow" --collect-only -q` — **1717**. Перед шагом 1 прогнать быстрый уровень (`-m "not slow" -q`, ~70 с): все зелёные, время запомнить.
6. Шаг 1, затем 2, затем 3. После шага 1 — быстрый уровень, после шага 2 — `--collect-only`. Полный прогон — в конце (`/implement` §3.1).

## 1. Задача

### 1.1. Что не так

Выше последней строки таблицы ОФП прототип держит $k_{ro}$ и $k_{rg}$ постоянными. `TabulatedRelPerm.kro/krg` — это `np.interp` (`numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/relperm.py`), а `np.interp` за краем возвращает крайнее значение.

Если в последней строке $k_{ro} > 0$, нефть подвижна при любой $S_o$, в том числе при $S_o \to 0$. У забоя нефть уходит, газ остаётся, $S_g$ растёт, и ничто не удерживает $S_o \ge 0$.

Фабрика такую таблицу принимает: `_check_relperm_table` проверяет только число строк и рост $S_g$, а пределы $[0, 1]$ проверяет разбор CSV (DEBT-044). Если $S_g$ у забоя доходит до края, а доля газа в потоке на краю мала, расчёт отказывает с текстом «HydroSolver не сошёлся при дроблении шага… поможет больший numerics.max_retries или меньший time.dt_integration». В замеренных сценариях (§1.2) совет ложный: у разностной задачи нет физического решения, и дробление не поможет.

### 1.2. Замеры (2026-10-15, `vault/issues/debt-073/probes/`)

- **Пример 05 (Стендинг, таблица ОФП до $S_g$ = 0.01, $k_{ro}$ = 0.98 на краю), `sg_bound_scan.py`.** Принят подшаг 56.25 с, у забоя $S_g$ = 0.917. Следующий подшаг не сходится до dt/512 = 7.03 с. Ступень 4 `advance` сходится (невязка $5.5\cdot10^{-14}$), но корень отвергнут порогом $S_g \le 0.98$. Корни: $S_g[0]$ = 1.727 / 1.322 / 1.120 / 1.019 при dt = 56.2 / 28.1 / 14.1 / 7.03 с (`sg_bound_roots.out.txt`), то есть $S_o < 0$. Без порога расчёт идёт с $S_g[0]$ = 311 через 6 ч (`sg_bound_scan.out.txt`). Порог 0.99, 0.999, 1.0 ничего не меняет.
- **Пример 05 при $R_{s,0}$ = 100, таблица до 0.1.** Корни $S_g[0]$ = 2.04 / 1.46 / 1.10 (`sg_bound_first_substep.out.txt`).
- **Допустимые таблицы, `edge_zero_scan.py`.** У четырёх таблиц последняя строка $k_{ro} = 0$ при $S_g$ = 0.01 / 0.02 / 0.05 / 0.1. Пример 05 сходится за 1 и 6 ч, max $S_g$ = 0.0057 / 0.0116 / 0.0103 / 0.0125 — **ниже края** (`edge_zero_scan.out.txt`). У узла $k_{ro} = 0$ нефть теряет подвижность, газ уходит, и $S_g$ держится внутри таблицы. Выйти за такой узел $S_g$ может только за счёт усадки неподвижной нефти при разгазировании — в замерах этого не было.

### 1.3. Решение пользователя (2026-10-15)

- **Отказ фабрики** (`ValueError`), если $k_{ro}$ в последней строке таблицы больше нуля.
- **Сравнение строгое.** Шум округления (например $10^{-30}$ у табличного Кори без обрезки) — тоже отказ. Допуск был бы ещё одним эвристическим числом, а значение пользователь увидит в тексте отказа.
- **Цена решения (принята осознанно).** Отвергается и таблица, с которой расчёт прошёл бы. Так бывает, если $S_g$ края не достигает: например, `configs/table_pvt/relperm.csv` с последней строкой `0.8,0.05,0.8` (сценарий теста шага 1) в примере 05, где max $S_g$ = 0.014 и ОФП берутся только на отрезке $[0, 0.1]$. Так бывает и при большой доле газа на краю: тогда $S_g$ возвращается в таблицу (не замерялось). Условие $k_{ro} > 0$ необходимо для ухода $S_o$ ниже нуля, но не достаточно. Пользователь выбрал отказ, а не предупреждение: обрезанную таблицу он сам не распознает, а таблицы проекта правило не задевает.
- **Отклонены:**
  - предупреждение вместо отказа — где $S_g$ край проходит, расчёт всё равно откажет с ложным советом;
  - край таблицы в тексте отказа расчёта — при отказе фабрики не нужен;
  - продолжение ОФП за краем по правилу — это досочинение данных.

### 1.4. Мотивация и приоритет

В проекте таких таблиц нет (§2.1), риск касается только будущего ввода. Отсюда низкий приоритет. Но ввод из книги Excel (FEAT-033…036) передаёт лист RELPERM в `relperm.csv` без перевода, и проверка фабрики встретит любую таблицу пользователя.

## 2. Текущее состояние

### 2.1. Таблицы ОФП проекта

Все кончаются строкой $k_{ro} = 0$:

| Файлы | Последняя строка `Sg,kro,krg` |
|---|---|
| `numerical_solver/configs/table_pvt/relperm.csv`, `examples/{04,05,07,08,09,10,11,12,13a,13b,14,15,16}_*/relperm.csv`, `tests/data/bug016_example14/relperm.csv` | `0.8,0.0,0.8` |
| `numerical_solver/examples/18_prototype_input/relperm.csv` (генерируется из книги прототипа `prototype_input.py`) | `0.85,0.0,0.8` |
| `numerical_solver/deliverables/rs150_for_sergey/relperm.csv`, `imex/relperm_slt.csv` (не в git) | `1,0,0.8`, `1,0,1` |
| `numerical_solver/configs/INPUT_TEMPLATE_THERMAL_v1_14.10.2026.xlsx`, лист RELPERM (не в git, черновик книги FEAT-033) | `0.85, 0, 0.8` |

Отслеживаемых git файлов `relperm.csv` — **16**: `configs/table_pvt`, 14 примеров, `tests/data/bug016_example14`.

ОФП Кори фабрика табулирует для прототипа на $S_g \in [0, 1]$ (`factory.py:506-510`, `_get_or_create_proto_rp`). Через `_check_relperm_table` этот путь не проходит. Последний узел ($S_g = 1$) всё равно даёт ровно 0: `CoreyRP._S_star` = `clip((S_g - S_gc)/denom, 0, 1)` = 1, и $k_{ro} = k_{ro}^{max}(1 - 1)^{n_o} = 0$ (`numerical_solver/gpn_multiphase_solver/pvt/relperm.py:34-38`).

### 2.2. Код

`numerical_solver/gpn_multiphase_solver/factory.py:265-280`:

```python
def _check_relperm_table(Sg: list, relperm_file: str) -> None:
    """Таблица ОФП: ≥ 2 строк, S_g строго растёт, иначе ValueError (DEBT-044)."""
    # Правила SGOF (OPM Flow Manual, табл. 8.165). Их же проверяет
    # TabulatedRelPerm (relperm.py:5) — без имени файла; k_ro(S_g), k_rg(S_g)
    # интерполируются np.interp по S_g. Пределы S_g, k_r в [0, 1] проверены
    # при разборе (_RELPERM_LIMITS). Монотонность k_r, которую требует SGOF,
    # не проверяется (решение пользователя 2026-10-07, план DEBT-044).
    if len(Sg) < 2:
        raise ValueError(
            f"{relperm_file}: строк данных {len(Sg)}, нужно не меньше двух: "
            f"k_ro и k_rg интерполируются по S_g.")
    for k in range(1, len(Sg)):
        if Sg[k] <= Sg[k - 1]:
            raise ValueError(
                f"{relperm_file}: S_g не растёт строго: {Sg[k]:g} после {Sg[k - 1]:g}. "
                f"Строки — по возрастанию S_g.")
```

Единственный вызов — `create_relperm`, `factory.py:375-383`:

```python
    elif rc.model == "table":
        # CSV → TabulatedRelPerm (прототип) → PrototypeRPAdapter
        Sg, kro, krg = _read_relperm_csv(config.config_dir / rc.file)
        # DEBT-044: те же правила проверяет TabulatedRelPerm, но без имени файла
        _check_relperm_table(Sg, rc.file)

        from radial_blackoil.relperm import TabulatedRelPerm
        proto_rp = TabulatedRelPerm(Sg, kro, krg)
        return PrototypeRPAdapter(proto_rp)
```

- `_read_relperm_csv` (`factory.py:621-635`) возвращает три списка `float` одной длины. На таблице из одного заголовка — три пустых списка.
- `create_relperm` вызывают `SimulatorFactory.from_config` (`factory.py:64`), `report/relperm.py:82,105`, `examples/two_phase_analytics.py:49`, тесты. Новая проверка видна им всем.
- `rc.file` — значение `relperm.file` из конфига как есть: относительное имя (`"relperm.csv"`) или абсолютный путь (тесты `test_table_range_warnings.py` подставляют `str(tmp_path / "relperm.csv")`).

### 2.3. Тесты, которые касаются кода

`numerical_solver/tests/test_factory_prototype.py`, класс `TestCSVValueChecks` (`:950`). Таблицу целиком проверяют `test_relperm_header_only_raises` (`:1018`), `test_relperm_one_row_raises` (`:1024`) и `test_relperm_sg_not_increasing_raises` (`:1030`). Помощники:
- `RP_HEADER` (`:665`);
- `TABLE_RP_ROWS` (`:854-855`, строки `configs/table_pvt/relperm.csv`, последняя — `"0.8,0.0,0.8\n"`);
- `_with_row` (`:858`);
- `_table_config_with_csv` (`:865`).

Порядок проверок важен:
- `test_relperm_one_row_raises` подаёт одну строку `0.0,1.0,0.0` ($k_{ro}$ = 1 в последней и единственной строке) и ждёт «строк данных 1»;
- `test_relperm_header_only_raises` подаёт пустую таблицу, на которой `kro[-1]` — `IndexError`.

Значит, новая проверка — **после** обеих прежних.

`numerical_solver/tests/test_table_range_warnings.py`, класс `TestStandingRelperm` (DEBT-071, влита `a180d88`), `test_relperm_above_table_before_failure` (`:203-220`). Тест строит пример 05 с таблицей `["0.0,1.0,0.0", "0.01,0.98,0.001"]` на 1 ч и ждёт запись «вне таблиц» при 0.000651 сут и `RuntimeError` «не сошёлся». **После правки фабрика отвергает эту таблицу в `from_config`, и тест падает.** Константа `RELPERM_ABOVE` (`:39`) используется только им (`:220`).

### 2.4. Документы с правилами `relperm.csv`

- `numerical_solver/examples/04_table_table/README.md:60-61`: «В `relperm.csv` не меньше двух строк, $S_g$ строго растёт.» Это справочник формата для пользователя.
- `numerical_solver/examples/05_standing_table_rp/README.md:163`: строка таблицы «Что менять безопасно» — «содержимое `relperm.csv` | — | свои керновые данные (главный сценарий)».
- `vault/knowledge/decisions/P8-формат-ввода-json.md:122` (формат `relperm.csv`) и `:221` (перечень проверок `from_config`).

## 3. Целевое состояние

- `_check_relperm_table(Sg, kro, relperm_file)` после двух прежних проверок отвергает таблицу с `kro[-1] > 0`. Текст отказа называет файл, $S_g$ и $k_{ro}$ последней строки, следствие и требование.
- `create_relperm` передаёт `kro`.
- Тест DEBT-071 на таблице до 0.01 превращён в тест отказа фабрики; `RELPERM_ABOVE` удалена.
- Три новых теста в `TestCSVValueChecks`.
- README 04 и 05, заметка P8 — с новым правилом.
- Таблицы проекта не затронуты, истории примеров побитово прежние: меняется только проверка ввода, а все 16 таблиц её проходят.

Не меняется (зона неприкосновенности):
- прототип `HydroSolverPrototype/` — `TabulatedRelPerm`, `input_reader.py` (собственный ввод прототипа), `_sg_activation_cap`;
- путь Кори;
- `report/relperm.py`;
- конфиги и CSV примеров.

## 4. Варианты

| | Суть | Плюсы | Минусы |
|---|---|---|---|
| **A** (выбран) | условие в `_check_relperm_table` — новый аргумент `kro` | одно место для правил таблицы ОФП, как у DEBT-044; одна правка вызова | сигнатура приватной функции меняется (вызов один) |
| B | отдельная функция `_check_relperm_edge(Sg, kro, file)` рядом, второй вызов в `create_relperm` | прежняя функция не трогается | два вызова, правила таблицы в двух местах, порядок проверок держится на порядке вызовов |
| C | проверка в `_read_relperm_csv` (при разборе) | ближе к данным | разбор проверяет значения по строкам, без числа строк; на пустой таблице `kro[-1]` упадёт раньше «строк данных 0» — порядок нарушится |

## 5. Подводные камни

| Пункт | | Как адресовано |
|---|---|---|
| Все вызовы найдены | ✅ | `_check_relperm_table` — только `factory.py:379`; тесты её не импортируют (новый тест — первый). План FEAT-035 называет её по имени, но вызывает через `create_relperm`. |
| Зависимости пакетов | ✅ | нет |
| Обратная совместимость API | ✅ | функция приватная; `create_relperm`, `from_config` — те же сигнатуры. Новое поведение — `ValueError` на таблице, которую раньше принимали: это и есть цель. |
| Состояние при ошибке | ✅ | `ValueError` до создания `TabulatedRelPerm` и решателя, как у DEBT-044 |
| Тесты | ⚠️ | `test_relperm_above_table_before_failure` падает — переделывается в шаге 1 (§2.3). Порядок проверок держат `test_relperm_one_row_raises`, `test_relperm_header_only_raises`. |
| Циклические импорты | ✅ | новый импорт в тесте — из `gpn_multiphase_solver.factory`, как соседние |
| Ссылки на уравнения | ✅ | новых ссылок на `.tex` нет; сторож `tests/test_eq_references.py` проверяет комментарии |
| Конфиги | ✅ | все 16 отслеживаемых таблиц проходят (§2.1, тест `test_project_relperm_tables_accepted`) |
| Связь с другими задачами | ⚠️ | **DEBT-071** (влита): её запись «RELPERM Sg above table» в настоящем расчёте теперь возможна только выше узла $k_{ro} = 0$. В замерах примера 05 $S_g$ этого края не достигала (`edge_zero_scan.out.txt`); выйти за него может разве что усадка неподвижной нефти. Проверка остаётся страховкой; её текст и вызов после каждого шага держат `test_relperm_above_table_reported_alone` и `test_checked_after_every_accepted_step`. **BUG-018**: `_sg_activation_cap` берёт $S_g$ строки перед первой $k_{ro} = 0$ — у принятых таблиц такая строка теперь есть всегда, поведение на таблицах проекта прежнее. **FEAT-033…036** (книга Excel, планы не в git на 2026-10-15): лист RELPERM → `relperm.csv` без перевода → эта проверка; лист шаблона кончается `0.85, 0, 0.8` — проходит. Проверка книги FEAT-033 (§2.6 её плана) — только пределы ячеек 0…1, правило последней строки она не дублирует, отказ даст программа. Текст отказа называет `relperm.csv`, а не лист RELPERM; соответствие для книги — забота FEAT-035 (её открытый вопрос 5 о сообщениях). **DEBT-075** (#124, проверка $0 \le S_g \le 1$ принятого состояния) — независима. |
| Производительность | ✅ | одно сравнение. Быстрый уровень короче на ~2.8 с: тест DEBT-071 считал час до отказа, новый отказывает в `from_config`. |
| Прототип | ✅ | не меняется — тесты прототипа и регрессия не нужны |

## 6. Шаги

### Шаг 1: проверка $k_{ro} = 0$ в последней строке, тесты

**Цель:** фабрика отвергает таблицу ОФП с $k_{ro} > 0$ в последней строке; тесты — новые и переделанный тест DEBT-071.

**Файлы:**
- `numerical_solver/gpn_multiphase_solver/factory.py`
- `numerical_solver/tests/test_factory_prototype.py`
- `numerical_solver/tests/test_table_range_warnings.py`

**Контекст:** §1–§2. Тест DEBT-071 переделывается в этом же шаге: без этого быстрый уровень после шага красный.

**Что сделать:**

1. `factory.py`, `_check_relperm_table` (`:265-280`): новый аргумент `kro`, новая проверка последней. Докстринг — одна строка.

   До:
   ```python
   def _check_relperm_table(Sg: list, relperm_file: str) -> None:
       """Таблица ОФП: ≥ 2 строк, S_g строго растёт, иначе ValueError (DEBT-044)."""
   ```
   После:
   ```python
   def _check_relperm_table(Sg: list, kro: list, relperm_file: str) -> None:
       """Таблица ОФП: ≥ 2 строк, S_g строго растёт, k_ro последней строки = 0, иначе ValueError (DEBT-044, DEBT-073)."""
   ```
   Комментарий `:267-271` оставить без изменений. В конец функции, после цикла по $S_g$, добавить:
   ```python
       # DEBT-073: выше последней строки TabulatedRelPerm берёт k_ro, k_rg из неё
       # (np.interp). При k_ro > 0 нефть подвижна при любой S_o: у забоя она
       # уходит, газ остаётся, и ничто не держит S_o >= 0. Пример 05 с таблицей
       # до S_g = 0.01 (k_ro = 0.98 на краю): корень разностной задачи — S_g у
       # забоя 1.02-1.73, расчёт отказывал с советом про шаг по времени, хотя
       # дробление не помогает (vault/issues/debt-073/probes/sg_bound_roots.out.txt).
       # С последней строкой k_ro = 0 в замерах примера 05 S_g у забоя оставалась
       # ниже неё (edge_zero_scan.out.txt). Все таблицы проекта ею кончаются.
       # Отвергается и таблица, с которой расчёт прошёл бы (S_g края не достигает)
       # — решение пользователя 2026-10-15: обрезанную таблицу пользователь сам не
       # распознает. Сравнение строгое: шум округления — тоже отказ, значение видно
       # в тексте. Проверка последняя: на пустой таблице kro[-1] нет, а одну строку
       # отвергает проверка числа строк.
       if kro[-1] > 0:
           raise ValueError(
               f"{relperm_file}: k_ro в последней строке (S_g = {Sg[-1]:g}) = {kro[-1]:g}, "
               f"нужно 0. Выше последней строки k_ro и k_rg берутся из неё: при k_ro > 0 "
               f"нефть подвижна при любой S_o, и у забоя S_o ничто не удерживает от "
               f"ухода ниже нуля. Таблица кончается строкой с k_ro = 0 — при "
               f"S_g = 1 - S_or (S_or — остаточная нефтенасыщенность) или выше.")
   ```

2. `factory.py`, `create_relperm` (`:378-379`).

   До:
   ```python
           # DEBT-044: те же правила проверяет TabulatedRelPerm, но без имени файла
           _check_relperm_table(Sg, rc.file)
   ```
   После:
   ```python
           # DEBT-044: число строк и рост S_g проверяет и TabulatedRelPerm, но без
           # имени файла; k_ro = 0 в последней строке (DEBT-073) — только здесь
           _check_relperm_table(Sg, kro, rc.file)
   ```

3. `test_factory_prototype.py`:
   - в импорт из `gpn_multiphase_solver.factory` (`:23-27`) добавить `_check_relperm_table` в строку с ридерами: `_read_oil_pvt_csv, _read_gas_pvt_csv, _read_relperm_csv, _check_relperm_table,`;
   - докстринг модуля, строка 12: «- Допустимость значений CSV: пределы столбцов, число строк, рост p и S_g, ветви R_s (DEBT-044)» → «- Допустимость значений CSV: пределы столбцов, число строк, рост p и S_g, ветви R_s (DEBT-044); k_ro = 0 в последней строке ОФП (DEBT-073)»;
   - в `TestCSVValueChecks` после `test_relperm_sg_not_increasing_raises` (`:1030-1035`) вставить:

   ```python
       # ── Последняя строка ОФП: k_ro = 0 (DEBT-073) ──

       def test_relperm_mobile_oil_at_edge_raises(self, tmp_path):
           """k_ro = 0.05 в последней строке (S_g = 0.8) → ValueError: файл, S_g, k_ro.

           Выше последней строки ОФП берутся из неё (np.interp прототипа): при k_ro > 0
           нефть подвижна при любой S_o. До правки пример 05 с таблицей до S_g = 0.01
           (k_ro = 0.98 на краю) отказывал на первом часе с советом про шаг по времени,
           а корень разностной задачи — S_g у забоя 1.02–1.73 (vault/issues/debt-073/
           probes/sg_bound_roots.out.txt). Ловит пропуск проверки и сравнение не с
           последней строкой: k_ro = 0.05 стоит только в ней.
           """
           config = _table_config_with_csv(
               tmp_path, "relperm.csv", _with_row(RP_HEADER, TABLE_RP_ROWS, 5, "0.8,0.05,0.8\n"))
           with pytest.raises(ValueError, match=r"relperm\.csv: k_ro в последней строке "
                                                r"\(S_g = 0\.8\) = 0\.05, нужно 0"):
               SimulatorFactory.from_config(config)

       def test_relperm_rounding_noise_at_edge_raises(self, tmp_path):
           """k_ro = 1e-30 в последней строке — тоже отказ: сравнение строгое.

           Решение пользователя 2026-10-15: табличный Кори без обрезки может дать в
           последнем узле шум округления, но допуск был бы ещё одним эвристическим
           числом; значение видно в тексте отказа. Ловит замену `> 0` допуском.
           """
           config = _table_config_with_csv(
               tmp_path, "relperm.csv", _with_row(RP_HEADER, TABLE_RP_ROWS, 5, "0.8,1e-30,0.8\n"))
           with pytest.raises(ValueError, match=r"= 1e-30, нужно 0"):
               SimulatorFactory.from_config(config)

       def test_project_relperm_tables_accepted(self):
           """Все таблицы ОФП проекта кончаются строкой k_ro = 0 — проверка DEBT-073 их принимает.

           На 2026-10-15 — 16 файлов: configs/table_pvt, 14 примеров (04, 05, 07–16,
           18), tests/data/bug016_example14. Без этого теста таблицу проекта, которую
           правило отвергло бы, поймали бы только медленные тесты примеров.
           """
           root = TABLE_CONFIG.parent.parent.parent
           files = [path for folder in ("configs", "examples", "tests/data")
                    for path in sorted((root / folder).glob("*/relperm.csv"))]
           assert len(files) >= 16
           for path in files:
               Sg, kro, _ = _read_relperm_csv(path)
               _check_relperm_table(Sg, kro, path.name)
   ```

   `TABLE_CONFIG.parent.parent.parent` — это `numerical_solver/` (`TABLE_CONFIG` = `numerical_solver/configs/table_pvt/config.json`, `:34`). Новый тест запускать из worktree: в worktree `examples/` — та же копия, что в git.

4. `test_table_range_warnings.py`:
   - удалить константу `RELPERM_ABOVE = "RELPERM Sg above table"` (`:39`): она используется только переделываемым тестом;
   - заменить `test_relperm_above_table_before_failure` (`:203-220`) на:

   ```python
       def test_mobile_oil_edge_rejected_before_run(self, tmp_path):
           """Таблица до S_g = 0.01 (k_ro = 0.98 на краю) отвергается фабрикой до расчёта (DEBT-073).

           До DEBT-073 расчёт с ней принимал подшаг 56.25 с с S_g = 0.917 у забоя,
           писал запись «вне таблиц» и не сходился при dt/512: выше края нефть
           подвижна при любой S_o, и у разностной задачи только корни с S_o < 0
           (vault/issues/debt-073/probes/sg_bound_scan.out.txt). С допустимой
           таблицей — последняя строка k_ro = 0 — S_g у забоя остаётся ниже края, и
           записи «вне таблиц» в настоящем расчёте нет (edge_zero_scan.out.txt).
           Выход за таблицу ОФП держат test_relperm_above_table_reported_alone
           (текст записи) и test_checked_after_every_accepted_step (вызов после
           каждого шага).
           """
           config = _standing_config(tmp_path, ["0.0,1.0,0.0", "0.01,0.98,0.001"], hours=1)
           with pytest.raises(ValueError, match=r"relperm\.csv: k_ro в последней строке "
                                                r"\(S_g = 0\.01\) = 0\.98, нужно 0"):
               SimulatorFactory.from_config(config)
   ```

   `_standing_config` кладёт в `relperm.file` абсолютный путь, и текст отказа начинается с него. `match` ищет подстроку (`re.search`), а `relperm\.csv:` совпадает с концом пути.

**Проверка после шага:**
- Новые и переделанный тесты: `.venv\Scripts\python -m pytest tests/test_factory_prototype.py::TestCSVValueChecks tests/test_table_range_warnings.py -q` — зелёные. Их сценарии при планировании прогнаны эмуляцией: `vault/issues/debt-073/probes/plan_tests_emulate.out.txt`, 8 PASS.
- Регресс: быстрый. Ожидание: всего 1993 → **1996** (+3 в `test_factory_prototype.py`; тест DEBT-071 заменён, а не удалён), быстрый уровень 1717 → **1720**, все зелёные. Время быстрого уровня — на ~2.8 с меньше исходного.

**Подводные камни:** порог строгий — `> 0`, не `>= eps`. Порядок проверок (§2.3). Сообщение: `{:g}` даёт `0.8`, `0.05`, `1e-30`, `0.01`, `0.98` — тесты на этом построены.

**Зависимости:** требует исходную точку (раздел «Как начать работу», п. 5); блокирует шаг 2.

**Оценка:** ~25 строк кода, ~60 строк тестов, ~30 минут.

### Шаг 2: документация правила

**Цель:** пользователь и разработчик видят новое правило там, где перечислены правила `relperm.csv`.

**Файлы:**
- `numerical_solver/examples/04_table_table/README.md`
- `numerical_solver/examples/05_standing_table_rp/README.md`
- `vault/knowledge/decisions/P8-формат-ввода-json.md`

**Что сделать:**

1. `04_table_table/README.md:60-61`.

   До:
   ```
   В `gas_pvt.csv` не меньше двух строк, давление строго растёт. В
   `relperm.csv` не меньше двух строк, $S_g$ строго растёт.
   ```
   После:
   ```
   В `gas_pvt.csv` не меньше двух строк, давление строго растёт. В
   `relperm.csv` не меньше двух строк, $S_g$ строго растёт, в последней
   строке $k_{ro} = 0$ — нефть неподвижна (остаточная нефтенасыщенность).
   Выше последней строки ОФП берутся из неё: при $k_{ro} > 0$ нефть
   была бы подвижна при любой $S_o$, и расчёт не начнётся.
   ```

2. `05_standing_table_rp/README.md:163`.

   До:
   ```
   | содержимое `relperm.csv` | — | свои керновые данные (главный сценарий) |
   ```
   После:
   ```
   | содержимое `relperm.csv` | — | свои керновые данные (главный сценарий); последняя строка — $k_{ro} = 0$, иначе расчёт не начнётся |
   ```

3. `P8-формат-ввода-json.md`:
   - `:122`, после «Не меньше двух строк, $S_g$ строго растёт (`_check_relperm_table`, DEBT-044).» вставить: «Последняя строка — $k_{ro} = 0$, строго (`_check_relperm_table`, [[DEBT-073]]): выше неё ОФП берутся из неё, и при $k_{ro} > 0$ нефть подвижна при любой $S_o$ — у забоя $S_o$ уходит ниже нуля.»
   - `:221`, в столбце «что проверяют»: «CSV-таблицы: числа, пределы, монотонность, ветви PVTO, $k_{ro} = 0$ в последней строке ОФП (DEBT-042, DEBT-044, DEBT-038, DEBT-073)».

4. README пакета `numerical_solver/README.md` (FEAT-031, на 2026-10-15 не в git) правил таблиц не перечисляет. Его §3.3 «Табличные PVT и ОФП» отсылает за образцами к `examples/04_table_table/` и говорит общо: «Несогласованные таблицы … при построении решателя отклоняются либо сопровождаются предупреждением». Правка не нужна. Если к реализации файл в базе и в нём появился перечень правил `relperm.csv` (`grep -n "relperm\|ОФП" numerical_solver/README.md`) — добавить то же правило. Файл не в git — не трогать: это работа другой задачи.

**Проверка после шага:**
- Регресс: `--collect-only -q` — 1996 (шаг меняет только документы).
- Правленые строки README 04 и 05 тесты не цитируют (проверено при планировании: «строго растёт» в `tests/` — только докстринги про `gas_pvt.csv` и GOR, «свои керновые» — нигде).

**Зависимости:** требует шаг 1.

**Оценка:** ~10 строк, ~10 минут.

### Шаг 3: vault

**Цель:** запись задачи и связи.

**Файлы:** `vault/roadmap/известные баги и технический долг.md`; `vault/issues/debt-073/05-comment-done.md` (по `/implement`).

**Что сделать:**
- статус DEBT-073 — по правилам `/implement` (реализован, коммит, число тестов);
- в записи DEBT-071 одна строка: тест `test_relperm_above_table_before_failure` заменён тестом отказа фабрики (DEBT-073).

**Проверка:** `--collect-only -q` — 1996.

**Оценка:** ~10 минут.

## 7. Тестовая стратегия

| Тест | Файл | Сценарий | Ожидание | Предотвращает |
|---|---|---|---|---|
| `TestCSVValueChecks::test_relperm_mobile_oil_at_edge_raises` (новый) | `tests/test_factory_prototype.py` | `configs/table_pvt`, последняя строка ОФП `0.8,0.05,0.8` | `ValueError` «relperm.csv: k_ro в последней строке (S_g = 0.8) = 0.05, нужно 0» в `from_config` | таблица с подвижной нефтью на краю принимается |
| `TestCSVValueChecks::test_relperm_rounding_noise_at_edge_raises` (новый) | то же | последняя строка `0.8,1e-30,0.8` | `ValueError` «= 1e-30, нужно 0» | строгость заменена допуском без решения пользователя |
| `TestCSVValueChecks::test_project_relperm_tables_accepted` (новый) | то же | 16 отслеживаемых `relperm.csv` проекта | ≥ 16 файлов, `_check_relperm_table` не бросает | правило отвергает таблицу проекта, а это видно только в медленных тестах |
| `TestStandingRelperm::test_mobile_oil_edge_rejected_before_run` (замена `test_relperm_above_table_before_failure`) | `tests/test_table_range_warnings.py` | пример 05 (Стендинг), таблица `0.0,1.0,0.0 / 0.01,0.98,0.001`, 1 ч | `ValueError` «(S_g = 0.01) = 0.98, нужно 0» в `from_config` | расчёт с таблицей замера DEBT-071 снова запускается и отказывает с советом про шаг |
| `test_relperm_one_row_raises`, `test_relperm_header_only_raises` (существующие) | `tests/test_factory_prototype.py` | одна строка `0.0,1.0,0.0`; только заголовок | прежние тексты «строк данных 1 / 0» | новая проверка раньше старых (`IndexError` или другой текст) |
| регресс: быстрый уровень, полный в конце | `tests/` | все примеры (в медленных) | зелёные; истории не меняются — меняется только проверка ввода | поломку примеров |

## 8. Критерии завершения

- [ ] `_check_relperm_table(Sg, kro, relperm_file)` отвергает `kro[-1] > 0` после проверок числа строк и роста $S_g$; `create_relperm` передаёт `kro`.
- [ ] Три новых теста и заменённый тест DEBT-071 зелёные; `RELPERM_ABOVE` удалена.
- [ ] Всего 1996 тестов, быстрый уровень 1720, все зелёные; полный прогон зелёный.
- [ ] README 04, 05 и P8 — с правилом.
- [ ] Прототип не тронут: `git diff --stat <база> -- numerical_solver/HydroSolverPrototype` пуст.
- [ ] Vault: статус DEBT-073, строка в DEBT-071; комментарий в #123 (`05-comment-done.md`).

## 9. Обнаруженные проблемы

1. **DEBT-075** (#124, зарегистрирована и открыта 2026-10-15): принятое состояние гидродинамики не проверяется на $0 \le S_g \le 1$, и от $S_o < 0$ защищает только порог 0.98 внутри Ньютона прототипа. Найдена замером 2 этой задачи. Не блокирует.
2. **Пример 21 с Кори, обрезанной на 0.3** (`sg_bound_21_first.out.txt`): Ньютон не сходится и без порога, корня не найдено никакого. С полной таблицей на том же подшаге $S_g[0]$ = 0.406 > 0.3. После DEBT-073 такую таблицу фабрика отвергает, и вопрос снимается. Не регистрируется.
3. **Порог $S_g \le 0.98$ прототипа** (`blackoil.py:460`, `:753-754`) без обоснования. Для таблиц, где $k_{ro} = 0$ только при $S_g = 1$ (`deliverables/`), он может резать физически допустимый интервал $(0.98, 1)$ — не замерялось. Записано в записи DEBT-073 (замер 2). Отдельно не регистрируется, пока нет случая.

## 10. Связи

- Запись: DEBT-073 в `vault/roadmap/известные баги и технический долг.md`; issue [#123](https://github.com/ArturSalamatin/Oil_Gas/issues/123).
- [[debt-071 standing-relperm-range-check]] (#122, влита `a180d88`) — обнаружение, тест на таблице до 0.01.
- [[debt-044 csv-table-value-checks]] (#74) — `_check_relperm_table`, `TestCSVValueChecks`.
- [[bug-018 closed-flash-sg-activation]] (#48) — `_sg_activation_cap` по строке $k_{ro} = 0$; физика — [[начальное Sg закрытого сосуда выше 1 − S_or не даёт Ньютону дойти до решения — ограничение по таблице ОФП снимает отказ]] (при $S_g \ge 1 - S_{or}$ ОФП на полках, $k_{ro} = 0$).
- DEBT-075 (#124) — проверка $0 \le S_g \le 1$ принятого состояния.
- FEAT-033…036 — ввод книгой Excel, лист RELPERM идёт через эту проверку.

## 11. Файлы проб (`vault/issues/debt-073/probes/`)

| Файл | Что |
|---|---|
| `sg_bound_scan.py` | порог $S_g$ прототипа, подмена в памяти; режимы: без аргумента (пороги 0.98…inf), `roots`, `first-substep`, `21-first` |
| `sg_bound_scan.out.txt`, `sg_bound_roots.out.txt`, `sg_bound_first_substep.out.txt`, `sg_bound_21_first.out.txt` | выводы |
| `edge_zero_scan.py`, `edge_zero_scan.out.txt`, `relperm_edge_zero_*.csv` | допустимые таблицы с узким краем: $S_g$ остаётся ниже края |
| `plan_tests_emulate.py`, `plan_tests_emulate.out.txt` | код шага 1 в памяти на `0d5c491`: 8 PASS — два новых отказа, три прежних текста (порядок проверок), переделанный тест DEBT-071 на пути Стендинга, 16 таблиц проекта приняты, `configs/table_pvt` строит решатель |
