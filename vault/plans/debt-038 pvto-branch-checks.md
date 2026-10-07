---
tags:
  - план
  - инфраструктура
date: 2026-10-07
issue: DEBT-038
github: 67
branch: refactor/debt-038/pvto-branch-checks
status: готов к реализации
---

# План DEBT-038: проверка ветвей PVTO в CSV-пути фабрики

**Задача:** DEBT-038 в `vault/roadmap/известные баги и технический долг.md` · GitHub [#67](https://github.com/ArturSalamatin/Oil_Gas/issues/67) · ветка `refactor/debt-038/pvto-branch-checks` · база `numerical_scheme/implementation` (`59e9eab`)

**Подтип:** инфраструктура (проверка ввода). Добавляется проверка CSV-таблицы `oil_pvt.csv` до построения `BlackOilPVT`. Корректные таблицы проходят как раньше: числа решателя, результаты примеров и код прототипа не меняются. В прототипе меняется только комментарий в одном тесте.

## Кратко

Сейчас ошибка в ветвях `oil_pvt.csv` проходит молча:
- ветвь $R_s$ из одной строки;
- повтор давления внутри ветви;
- строки ветви не по возрастанию давления.

`BlackOilPVT` строит из такой таблицы другие $B_o$, $\mu_o$ недонасыщенной нефти. XLSX-ридер прототипа такие таблицы отклоняет.

После правки функция фабрики `_check_pvto_branches` отклоняет их с `ValueError`. Сообщение называет файл, ветвь $R_s$ и давления. Пустую таблицу функция тоже отклоняет: сейчас она падает `IndexError` внутри `BlackOilPVT`.

Объём: 1 функция (~35 строк), 1 вызов, 7 тестов, 1 комментарий теста прототипа, 3 абзаца документации. Тестов: 1270 → 1277.

## Как начать работу по этому плану

1. Прочитай этот файл целиком.
2. Прочитай запись DEBT-038 в `vault/roadmap/известные баги и технический долг.md` и тело issue `vault/issues/debt-038/01-issue-body.md`. В issue есть таблица поведения `BlackOilPVT` на ошибочных таблицах.
3. ⚠️ **Работай в основном каталоге проекта, не в worktree.** Этот план, проба `vault/issues/debt-038/probes/` и поля GitHub, Ветка и План записи DEBT-038 могут быть не закоммичены: `vault/issues/` в `.gitignore`. В worktree их не будет. Параллельные worktree `.worktrees/bug-021` и `.worktrees/debt-039` файлы этого плана не меняют (проверено `git diff --stat` 2026-10-07). Чужие незакоммиченные правки в `vault/` не трогать и не коммитить.
   ```powershell
   git branch --show-current          # numerical_scheme/implementation
   git log -1 --oneline               # 59e9eab или новее
   git checkout -b refactor/debt-038/pvto-branch-checks
   ```
4. Venv: `numerical_solver\.venv\Scripts\python` напрямую. Команды pytest — из `numerical_solver/`.
5. Baseline (замер при планировании 2026-10-07, HEAD `59e9eab`):
   ```powershell
   cd numerical_solver
   .venv\Scripts\python -m pytest tests/ --collect-only -q                # 1270 тестов
   .venv\Scripts\python -m pytest tests/ --collect-only -q -m "not slow"  # 1035/1270 (235 deselected)
   .venv\Scripts\python -m pytest tests/ -m "not slow" -q                 # ожидается 1035 passed, ~70 с
   ```
   Если чисел больше, база сдвинулась: план DEBT-037 (+10 тестов) готов к реализации параллельно. Записать новые числа и дальше считать от них. План добавляет ровно 7 тестов, все в быстром уровне.
6. Начни с шага 1. После каждого шага — его проверка. Полный прогон — в шаге 6.

## Контекст для читателя без контекста

**Таблица PVTO** (формат ECLIPSE) задаёт свойства нефти с растворённым газом. Строки сгруппированы по газосодержанию $R_s$: каждая группа — «ветвь». Первая строка ветви — насыщенная точка: давление насыщения $p_b(R_s)$ и $B_o$, $\mu_o$ при нём. Следующие строки той же ветви — недонасыщенная нефть: тот же $R_s$, давление выше $p_b$. По ним определяются сжимаемость $c_o$ и рост $\mu_o$ с давлением.

CSV-формат проекта: `Rs_sm3_sm3,pressure_Pa,Bo,mu_o_Pa_s`, единицы СИ. Образец — `numerical_solver/configs/table_pvt/oil_pvt.csv`: ветви $R_s$ = 0 и 30, по две строки.

**Путь табличной PVT в фабрике** (`numerical_solver/gpn_multiphase_solver/factory.py`, функция `_create_pvt`, ветвь `pc.model == "table"`, строки 115–146):

```
_read_oil_pvt_csv (:371-395)   — разбор CSV → [(Rs, p_бар, Bo, mu_сП), ...], без проверок
_read_gas_pvt_csv (:398-421)
BlackOilPVT(oil_rows, gas_rows) (:126-127) — прототип, radial_blackoil/pvt.py
_check_rs0_in_table (:136, определена :152-162) — Rs0 в диапазоне ветвей (BUG-017)
PrototypePVTAdapter → TableFullPVT — те же B_o, μ_o идут и в гидродинамику, и в уравнение энергии
```

Дальше `from_config` проверяет пересыщенный старт (`_check_undersaturated_start`) и согласованность PVT (BUG-019, только предупреждение).

**Что делает `BlackOilPVT` с ошибочной ветвью.** `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/pvt.py:13-33`: строки ветви сортируются по кортежу $(p, B_o, \mu_o)$. Замер 2026-10-07 (тело issue #67) и проба `vault/issues/debt-038/probes/red_state.py` (вывод `red_state.out.txt`):

| Таблица (TABLE_CONFIG, $R_{s,0}$ = 30, $p_0$ = 20 МПа) | `from_config` сейчас |
|---|---|
| ветвь $R_s$ = 15 из одной строки между ветвями 0 и 30 | проходит; $B_o$, $\mu_o$ ветви выше $p_b$ постоянны ($c_o$ = 0) |
| последняя ветвь $R_s$ = 30 из одной строки | проходит |
| давление 20 МПа дважды в ветви 30 | проходит; `RuntimeWarning: divide by zero` (`pvt.py:56`), скачок $B_o$ при 20 МПа |
| строки ветви 30 в порядке 15, 30, 20 МПа | проходит, сортировка исправляет порядок молча |
| опечатка $R_s$ = 30.01 у средней строки ветви 30 | проходит: лишняя ветвь из одной строки |
| только заголовок | `IndexError: index -1 is out of bounds` из `BlackOilPVT` |
| строки ветвей 0 и 30 чередуются в файле | проходит, это корректная таблица |

**Эталон правил — XLSX-ридер прототипа** (`numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/input_reader.py:54-64`):
- нет числовых строк → ошибка;
- в каждой ветви $R_s$ не меньше двух строк;
- давление строго растёт внутри ветви по порядку строк в файле.

Ветвь — все строки с одним $R_s$, совпадение точное; смежность строк не требуется.

**Стандарт ECLIPSE / OPM.** OPM Flow Reference Manual 2025-10 (`Refs/incoming/OPM_Flow_Reference_Manual_2025-10_Rev-0_compressed.pdf`, §8.3.245 PVTO, табл. 8.133, с. 1131–1133): недонасыщенные строки не обязательны, но «there must be at least two entries for the last Rs value». ECLIPSE достраивает ветвь из одной строки по соседней ветви. Прототип этого не делает: у него $B_o$, $\mu_o$ такой ветви выше $p_b$ постоянны. Поэтому ветвь из одной строки отклоняется в любой позиции (решение пользователя 2026-10-07).

**Решения пользователя (2026-10-07, при планировании):**
1. Место проверки — отдельная функция фабрики `_check_pvto_branches` до `BlackOilPVT` (вариант 1 issue). Прототип и ридер не меняются.
2. Ветвь из одной строки отклоняется любая, не только последняя.
3. Различные давления не по возрастанию отклоняются, как в XLSX. Отклоняется не только повтор.
4. Смежная проблема (CSV-ридеры молча пропускают нечисловые строки) — отдельная запись DEBT-042, в этот план не входит.

## Текущее состояние (baseline)

- Тесты: 1270 всего, 1035 в быстром уровне (HEAD `59e9eab`). Тесты прототипа: 93 (`--collect-only` из `Prototype_1.0.3`).
- Все 16 файлов `oil_pvt.csv` проекта корректны: в ветвях от 2 до 31 строки, давление строго растёт по порядку файла. Файлы: `configs/table_pvt`, примеры 04, 04a, 06–16, `tests/data/bug016_example14`; замер 2026-10-07. Все 47 CSV-таблиц проекта (нефть, газ, ОФП) разбираются без пропусков.
- Вызовов `_read_oil_pvt_csv` в коде пакета один: `factory.py:123`. `BlackOilPVT` в пакете строится только в `factory.py:127`. Тесты строят его и напрямую: `tests/test_prototype_adapter.py:81`, тесты прототипа. Эти вызовы проверка не затрагивает.

## Целевое состояние

- `factory.py`: новая функция `_check_pvto_branches(oil_rows, oil_pvt_file)` после `_check_rs0_in_table`. Вызов в ветви `"table"` между чтением CSV и `BlackOilPVT(...)`.
- Ошибочная таблица → `ValueError` с именем файла, $R_s$ ветви и давлениями в МПа, до построения `BlackOilPVT`. `RuntimeWarning` из `pvt.py:56` в CSV-пути больше не возникает.
- Корректные таблицы: поведение побитно прежнее, так как функция только читает `oil_rows`.
- Импорты не меняются: `BAR_TO_PA` уже импортирован в `factory.py:30`.

## Варианты и выбор

Подробно — в теле issue #67, раздел «Анализ вариантов решения». Кратко:

| Вариант | Суть | Итог |
|---|---|---|
| 1 | отдельная функция фабрики до `BlackOilPVT` | **выбран** (решение 1): прототип и тесты ридера не меняются, приём как у `_check_rs0_in_table`, сообщение на русском с именем файла |
| 2 | проверка в `_read_oil_pvt_csv` | отклонён: ридер смешивает разбор и проверку, а два теста формата CSV (`test_oil_pvt_csv_format`, `test_oil_csv_skips_blank_lines` — по одной строке на ветвь) пришлось бы переписать |
| 3 | проверка в `BlackOilPVT.__init__` | отклонён: ломает фикстуру «one-row branch» поразрядной сверки DEBT-036 (`test_pvto_vectorized.py:44-46`), дублирует XLSX-проверку другим типом исключения, сообщение без имени файла, нужна регрессия прототипа |
| 4 | достраивать ветвь из одной строки по правилу ECLIPSE | вне задачи (это FEAT, меняет интерполяцию) |

Минус варианта 1: прямой вызов `BlackOilPVT` не защищён (тесты, скрипты). Это принято.

## Подводные камни (чеклист)

- ✅ **Все места вызова найдены:** `_read_oil_pvt_csv` → только `factory.py:123`. Функция новая, старых вызовов нет.
- ✅ **Зависимости пакетов:** не меняются.
- ✅ **Обратная совместимость:** закрытая функция, API не меняется. Конфиги с корректными таблицами работают как раньше (все 16 таблиц проекта проходят).
- ✅ **Состояние при ошибке:** `raise` до создания объектов PVT, частично построенного состояния нет.
- ✅ **Существующие тесты:**
  - `TestCSVReaders` (`tests/test_factory_prototype.py:37-108`) вызывает ридеры напрямую, проверку не проходит. В двух его тестах ветви по одной строке, и это нормально.
  - Таблицы `OIL_BAD`, `OIL_UNDER_BAD` (`tests/test_pvt_consistency.py:40-51`) корректны по ветвям: по 2 строки, давление растёт.
  - `test_rs0_below_first_branch_raises` (`test_factory_prototype.py:327-341`): таблица корректна, по-прежнему ждёт «вне диапазона таблицы».
  - Фикстура «one-row branch» прототипа строит `BlackOilPVT` напрямую.
- ✅ **Циклические импорты:** новых импортов нет.
- ✅ **Docstrings:** `\eqref{}` нет (проверка ввода, не формула).
- ✅ **Конфиги:** имена параметров не меняются.
- ⚠️ **Порядок проверок в `_create_pvt`.** Новая проверка должна стоять **до** `BlackOilPVT(...)`, а значит и до `_check_rs0_in_table`. Иначе пустая таблица упадёт `IndexError` в конструкторе. А при опечатке в $R_s$ ($R_s$ = 30.01 в последней позиции) диапазон ветвей станет ложным: `_check_rs0_in_table` сообщит не о той ошибке. Адресовано в шаге 3 и тестом `test_rs_typo_extra_branch_raises`.
- ✅ **Связь с другими задачами:**
  - BUG-017 (`_check_rs0_in_table`) и BUG-019 (согласованность PVT) идут после новой проверки и не меняются.
  - DEBT-039, BUG-021 (worktree) и DEBT-037 (тесты примеров) файлы плана не трогают.
  - DEBT-042 (строгий разбор CSV) — следующий уровень той же защиты, не конфликтует.
- ✅ **Производительность:** один проход по строкам таблицы при создании симулятора, пренебрежимо.
- ✅ **Прототип:** меняется только комментарий в `tests/test_pvto_vectorized.py:44`, код `radial_blackoil/` — нет. Регрессия против `regression/golden/` не нужна, так как ни одна строка, которую она исполняет, не меняется. Тесты прототипа прогоняются (шаг 4), ожидание — 93 passed.

## Шаги

### Шаг 1: Подготовка — ветка и baseline

**Цель:** ветка от актуальной базы, числа тестов зафиксированы.

**Файлы:** нет.

**Что сделать:**
1. Команды из «Как начать работу», пункты 3 и 5.
2. Воспроизвести красное состояние: `.venv\Scripts\python ..\vault\issues\debt-038\probes\red_state.py` (из `numerical_solver/`). Ожидание — как в таблице раздела «Контекст»: 6 строк «from_config прошёл», 1 `IndexError`. Проба создаёт и удаляет `vault/issues/debt-038/probes/red_state_tmp/`.

**Проверка:** `-m "not slow" -q` — 1035 passed (или новое число базы).

**Зависимости:** блокирует шаги 2–7.

**Оценка:** 0 строк, ~3 мин.

### Шаг 2: Тесты ветвей PVTO (красные)

**Цель:** 7 тестов фабрики на правила ветвей. До реализации 6 красных и 1 зелёный.

**Файлы:** `numerical_solver/tests/test_factory_prototype.py`

**Контекст:** тесты идут через `SimulatorFactory.from_config`, а не через прямой вызов функции. Так они проверяют и правила, и то, что вызов стоит в `_create_pvt` до `BlackOilPVT`. Подмена таблицы — существующим помощником `_table_config_with_oil_csv(tmp_path, oil_csv_text)` (`test_factory_prototype.py:284-291`): он копирует `gas_pvt.csv`, `relperm.csv` из `configs/table_pvt`, пишет переданный текст в `oil_pvt.csv` и переводит `config_dir` на `tmp_path`. Конфиг `configs/table_pvt/config.json`: `oil_pvt_file = "oil_pvt.csv"`, $p_0$ = 20 МПа, $R_{s,0}$ = 30.

**Что сделать:**
1. В докстринг модуля (строки 3–9, список «Проверяют:») добавить строку после строки 9:
   ```
   - Ветви PVTO-таблицы: не меньше двух строк, давление растёт (DEBT-038)
   ```
2. В конец файла (после `TestInitialRangeWarnings`, строка 413) добавить раздел G:

```python


# ═══════════════════════════════════════════════════════════
# G. Ветви PVTO-таблицы (DEBT-038)
# ═══════════════════════════════════════════════════════════

# Ветви таблицы configs/table_pvt: R_s = 0 (p_b = 5 МПа) и 30 (p_b = 15 МПа)
OIL_HEADER = "Rs_sm3_sm3,pressure_Pa,Bo,mu_o_Pa_s\n"
OIL_BRANCH_0 = "0.0,5000000,1.05,0.003\n0.0,30000000,1.04,0.0032\n"
OIL_BRANCH_30 = "30.0,15000000,1.20,0.0015\n30.0,30000000,1.18,0.0016\n"


class TestPVTOBranches:
    """Фабрика отвергает CSV-таблицу PVTO с ошибкой в ветвях (DEBT-038).

    Правила XLSX-ридера прототипа (input_reader.py:59-64): в ветви R_s не
    меньше двух строк, давление строго растёт по порядку файла. BlackOilPVT
    их не проверяет: до правки все таблицы ниже, кроме пустой, проходили
    from_config молча (проба vault/issues/debt-038/probes/red_state.py).
    Конфиг — TABLE_CONFIG (Rs0 = 30, p0 = 20 МПа); проверка ветвей идёт
    раньше проверок Rs0 и пересыщения.
    """

    def test_one_row_branch_raises(self, tmp_path):
        """Ветвь R_s = 15 из одной строки между полными ветвями 0 и 30.

        До правки B_o = 1.12 и μ_o этой ветви постоянны выше p_b = 10 МПа
        (c_o = 0): нефть у этой ветви несжимаема, сообщения нет.
        """
        config = _table_config_with_oil_csv(
            tmp_path,
            OIL_HEADER + OIL_BRANCH_0 + "15.0,10000000,1.12,0.0022\n" + OIL_BRANCH_30)
        with pytest.raises(ValueError,
                           match=r"R_s = 15 м³ст/м³ст из одной строки \(p = 10 МПа\)") as exc:
            SimulatorFactory.from_config(config)
        assert str(exc.value).startswith("oil_pvt.csv:")

    def test_one_row_last_branch_raises(self, tmp_path):
        """Последняя ветвь R_s = 30 из одной строки — её не допускает и ECLIPSE.

        OPM Flow Manual §8.3.245: для последнего R_s нужны не меньше двух
        строк, иначе недонасыщенная область не интерполируется.
        """
        config = _table_config_with_oil_csv(
            tmp_path, OIL_HEADER + OIL_BRANCH_0 + "30.0,15000000,1.20,0.0015\n")
        with pytest.raises(ValueError, match=r"R_s = 30 м³ст/м³ст из одной строки"):
            SimulatorFactory.from_config(config)

    def test_repeated_pressure_raises(self, tmp_path):
        """Давление 20 МПа дважды в ветви 30 (B_o 1.19 и 1.185).

        До правки BlackOilPVT сортировал строки по (p, B_o, μ_o): первой шла
        строка с меньшим B_o, и B_o скачком менялся при 20 МПа. Единственный
        сигнал — RuntimeWarning «divide by zero» из pvt.py без имени файла.
        """
        config = _table_config_with_oil_csv(tmp_path, OIL_HEADER + OIL_BRANCH_0 + (
            "30.0,15000000,1.20,0.0015\n"
            "30.0,20000000,1.19,0.00152\n"
            "30.0,20000000,1.185,0.00153\n"
            "30.0,30000000,1.18,0.0016\n"))
        with pytest.raises(ValueError, match="не растёт строго") as exc:
            SimulatorFactory.from_config(config)
        assert "20 МПа после 20 МПа (строки 2 и 3 ветви)" in str(exc.value)

    def test_pressure_out_of_order_raises(self, tmp_path):
        """Строки ветви 30 переставлены: 15, 30, 20 МПа (решение пользователя 2026-10-07).

        BlackOilPVT исправил бы порядок сортировкой, но XLSX-путь такую
        таблицу отвергает — правила двух путей одинаковы.
        """
        config = _table_config_with_oil_csv(tmp_path, OIL_HEADER + OIL_BRANCH_0 + (
            "30.0,15000000,1.20,0.0015\n"
            "30.0,30000000,1.18,0.0016\n"
            "30.0,20000000,1.19,0.00152\n"))
        with pytest.raises(ValueError, match=r"20 МПа после 30 МПа \(строки 2 и 3 ветви\)"):
            SimulatorFactory.from_config(config)

    def test_rs_typo_extra_branch_raises(self, tmp_path):
        """Опечатка R_s = 30.01 вместо 30 у средней строки ветви 30 — лишняя ветвь из одной строки.

        До правки Rs0 = 30 лежал внутри [0, 30.01], R_s^eq(20 МПа) = 30.007 —
        from_config проходил, B_o около R_s = 30 шёл по искажённым ветвям.
        Ловит и порядок проверок: ветви проверяются раньше диапазона Rs0.
        """
        config = _table_config_with_oil_csv(tmp_path, OIL_HEADER + OIL_BRANCH_0 + (
            "30.0,15000000,1.20,0.0015\n"
            "30.01,22000000,1.19,0.00155\n"
            "30.0,30000000,1.18,0.0016\n"))
        with pytest.raises(ValueError, match=r"R_s = 30\.01 м³ст/м³ст из одной строки"):
            SimulatorFactory.from_config(config)

    def test_empty_table_raises(self, tmp_path):
        """Только заголовок: до правки — IndexError из BlackOilPVT без имени файла."""
        config = _table_config_with_oil_csv(tmp_path, OIL_HEADER)
        with pytest.raises(ValueError, match="oil_pvt.csv: нет ни одной числовой строки"):
            SimulatorFactory.from_config(config)

    def test_interleaved_branches_pass(self, tmp_path):
        """Строки ветвей 0 и 30 чередуются в файле — таблица корректна.

        Ветвь — все строки с одним R_s, порядок давлений проверяется внутри
        ветви, как в XLSX-ридере и BlackOilPVT. Ловит слишком строгую проверку
        (требование смежности строк ветви).
        """
        config = _table_config_with_oil_csv(tmp_path, OIL_HEADER + (
            "0.0,5000000,1.05,0.003\n30.0,15000000,1.20,0.0015\n"
            "0.0,30000000,1.04,0.0032\n30.0,30000000,1.18,0.0016\n"))
        SimulatorFactory.from_config(config)   # не бросает
```

**Проверка после этого шага:**
```powershell
.venv\Scripts\python -m pytest tests/test_factory_prototype.py -k TestPVTOBranches -q
```
Ожидание: **6 failed, 1 passed**.
- `test_interleaved_branches_pass` проходит.
- Пять тестов падают с `DID NOT RAISE`.
- `test_empty_table_raises` падает с `IndexError` (не `ValueError`).

Если какой-то из шести проходит, проверка уже где-то есть: остановиться и разобраться. Регресс не нужен, так как изменён только файл тестов.

**Подводные камни:** регулярные выражения `match` экранируют `(`, `)`, `.`. Символ `³` и `/` в регулярном выражении буквальные.

**Зависимости:** требует шаг 1, блокирует шаг 3.

**Оценка:** ~110 строк, ~15 мин.

### Шаг 3: Функция `_check_pvto_branches` и её вызов

**Цель:** фабрика отклоняет ошибочные ветви до построения `BlackOilPVT`.

**Файлы:** `numerical_solver/gpn_multiphase_solver/factory.py`

**Контекст:** правила — как у XLSX-ридера (`input_reader.py:59-64`): ветви группируются по точному значению $R_s$, давления сравниваются в порядке файла. Значения сравниваются в барах — так их получает `BlackOilPVT`. В МПа они переводятся только для сообщения, потому что CSV задан в Па, а бары пользователь не видит. Ветви перебираются по возрастанию $R_s$, как в XLSX-ридере: сообщение детерминировано. Ошибка — `ValueError`, как у `_check_rs0_in_table`; тесты `from_config` ловят именно этот тип.

**Что сделать:**

1. Вставить функцию после `_check_rs0_in_table` (после строки 162, перед пустыми строками и комментарием `# Допуск пересыщения на старте` на строке 165):

```python


def _check_pvto_branches(oil_rows: list[tuple], oil_pvt_file: str) -> None:
    """Ветви PVTO-таблицы: не меньше двух строк, давление строго растёт, иначе ValueError (DEBT-038)."""
    # Правила XLSX-ридера прототипа (input_reader.py:59-64). BlackOilPVT
    # ветви не проверяет, и ошибка таблицы молча меняет B_o, μ_o
    # недонасыщенной нефти — а через PrototypePVTAdapter и уравнение энергии:
    #   - ветвь из одной строки: B_o, μ_o выше p_b постоянны (c_o = 0).
    #     ECLIPSE такую ветвь допускает (кроме последней) и достраивает по
    #     соседней (OPM Flow Manual, §8.3.245 PVTO); прототип — нет;
    #   - повтор давления: BlackOilPVT сортирует строки по (p, B_o, μ_o), а не
    #     по порядку файла, — скачок B_o в этой точке;
    #   - давление не по возрастанию: сортировка исправила бы его молча, но
    #     XLSX-путь такую таблицу отвергает — правила двух путей одинаковы.
    if not oil_rows:
        # Без строк BlackOilPVT падает IndexError без имени файла
        raise ValueError(f"{oil_pvt_file}: нет ни одной числовой строки.")
    # Ветвь — все строки с одним R_s (точное совпадение, как в BlackOilPVT);
    # давления в барах — как их получает BlackOilPVT, в порядке файла
    branches: dict[float, list[float]] = {}
    for Rs, p_bar, _, _ in oil_rows:
        branches.setdefault(Rs, []).append(p_bar)
    for Rs, p_bar in sorted(branches.items()):
        p_mpa = [p * BAR_TO_PA / 1e6 for p in p_bar]   # только для сообщений
        if len(p_bar) < 2:
            raise ValueError(
                f"{oil_pvt_file}: ветвь R_s = {Rs:g} м³ст/м³ст из одной строки "
                f"(p = {p_mpa[0]:g} МПа). Нужно не меньше двух: насыщенная точка "
                f"p_b(R_s) и хотя бы одна строка выше p_b — иначе B_o, μ_o "
                f"недонасыщенной нефти не заданы.")
        for k in range(1, len(p_bar)):
            if p_bar[k] <= p_bar[k - 1]:
                raise ValueError(
                    f"{oil_pvt_file}: в ветви R_s = {Rs:g} м³ст/м³ст давление "
                    f"не растёт строго: {p_mpa[k]:g} МПа после {p_mpa[k - 1]:g} МПа "
                    f"(строки {k} и {k + 1} ветви). Первая строка ветви — "
                    f"насыщенная точка p_b(R_s), дальше давление растёт.")
```

   Нумерация «строки {k} и {k + 1} ветви» — с единицы: `k` — индекс с нуля у второй из двух строк, поэтому номера $k$ и $k+1$.

2. Вызов в `_create_pvt`, ветвь `"table"` (строки 123–127):

   До:
   ```python
           oil_rows = _read_oil_pvt_csv(config.config_dir / pc.oil_pvt_file)
           gas_rows = _read_gas_pvt_csv(config.config_dir / pc.gas_pvt_file)

           from radial_blackoil.pvt import BlackOilPVT
           proto_pvt = BlackOilPVT(oil_rows, gas_rows)
   ```
   После:
   ```python
           oil_rows = _read_oil_pvt_csv(config.config_dir / pc.oil_pvt_file)
           gas_rows = _read_gas_pvt_csv(config.config_dir / pc.gas_pvt_file)
           # DEBT-038: ветви PVTO — до BlackOilPVT: он их не проверяет, а пустую
           # таблицу встречает IndexError. До _check_rs0_in_table: лишняя ветвь
           # из опечатки в R_s исказила бы диапазон ветвей.
           _check_pvto_branches(oil_rows, pc.oil_pvt_file)

           from radial_blackoil.pvt import BlackOilPVT
           proto_pvt = BlackOilPVT(oil_rows, gas_rows)
   ```

**Проверка после этого шага:**
- `pytest tests/test_factory_prototype.py -k TestPVTOBranches -q` → **7 passed**.
- `pytest tests/test_factory_prototype.py tests/test_pvt_consistency.py -q` → все зелёные: соседние проверки BUG-017 и BUG-019 не задеты.
- Регресс: быстрый → 1042 passed (1035 + 7).
- Проба `red_state.py` теперь печатает `ValueError` с ожидаемыми текстами у шести таблиц и «from_config прошёл» у `interleaved`. Это для глаз, вывод не сохранять.

**Код шага проверен подменой при планировании** (2026-10-07): `vault/issues/debt-038/probes/plan_check.py` подключает функцию дословно, обёрткой `_read_oil_pvt_csv` — то же место, что вызов по плану. Вывод `plan_check.out.txt`:
- все 7 таблиц шага 2 дают сообщения, совпадающие с регулярными выражениями тестов (`re.search`, как у `pytest.raises(match=...)`);
- `interleaved` проходит;
- все 16 таблиц `oil_pvt*.csv` проекта проверку проходят.

**Подводные камни:** порядок проверок (чеклист, ⚠️). Имя файла в сообщении — `pc.oil_pvt_file`, как у `_check_rs0_in_table`; это значение из конфига, а не полный путь.

**Зависимости:** требует шаг 2, блокирует шаги 4–6.

**Оценка:** ~40 строк, ~15 мин.

### Шаг 4: Комментарий фикстуры «one-row branch» в тестах прототипа

**Цель:** комментарий теста прототипа не утверждает устаревшее.

**Файлы:** `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/tests/test_pvto_vectorized.py`

**Контекст:** фикстура `_tables()` строит `BlackOilPVT` с ветвью из одной строки напрямую. Это случай поразрядной сверки DEBT-036, он остаётся. Комментарий на строке 44 говорит, что CSV-ридер GPN такую таблицу не запрещает, — после шага 3 это неверно. Стиль файла: английские комментарии, компактные строки — так и оставить.

**Что сделать:** заменить строку 44.

До:
```python
    # A one-row branch (Rs = 30): the GPN CSV reader does not forbid it; np.interp returns its only value
```
После:
```python
    # A one-row branch (Rs = 30): BlackOilPVT accepts it, np.interp returns its only value.  The XLSX
    # reader and the GPN factory (CSV, DEBT-038) reject such tables before BlackOilPVT is built
```

**Проверка после этого шага** (из `numerical_solver/HydroSolverPrototype/Prototype_1.0.3`):
```powershell
..\..\.venv\Scripts\python -m pytest tests -q    # 93 passed
```
Регрессия прототипа не нужна: код `radial_blackoil/` не меняется. Регресс GPN не нужен: файл GPN-тестами не собирается.

**Зависимости:** требует шаг 3.

**Оценка:** 2 строки, ~3 мин.

### Шаг 5: Документация формата `oil_pvt.csv`

**Цель:** требования к ветвям записаны там, где пользователь и разработчик ищут формат таблицы.

**Файлы:**
- `vault/knowledge/decisions/P8-формат-ввода-json.md` (раздел «Формат oil_pvt.csv», строки 77–89)
- `vault/knowledge/decisions/json-config-schema.md` (строка 64 и абзац строки 108)
- `numerical_solver/examples/04_table_table/README.md` (строки 47–48)

**Что сделать:**
1. `P8-формат-ввода-json.md`: после строки 89 («Единицы в CSV: **SI** …») добавить абзац:
   ```markdown
   Ветвь — все строки с одним $R_s$. В ветви не меньше двух строк: первая — насыщенная точка $p_b(R_s)$, дальше давление строго растёт по порядку строк. Ветвей не меньше двух. Нарушение — `ValueError` фабрики с именем файла и ветвью (`_check_pvto_branches`, DEBT-038; число ветвей — `BlackOilPVT`, DEBT-036). ECLIPSE допускает ветвь из одной строки (кроме последней) и достраивает её по соседней; решатель так не делает, поэтому такая ветвь — ошибка.
   ```
2. `json-config-schema.md`:
   - Строка 64 описывает табличный путь неверно: «колонки p, Bo, Bg, mu_o, mu_g, Rs_eq». Заменить на:
     ```markdown
     Для `"table"`: `oil_pvt_file` (PVTO нефти) и `gas_pvt_file` (газ), CSV в СИ — формат и требования к ветвям в [[P8-формат-ввода-json]].
     ```
   - В абзац строки 108 после предложения «Обе проверки — `SimulatorFactory.from_config`, нарушение — `ValueError` (BUG-017).» добавить:
     ```markdown
     До них проверяются ветви `oil_pvt.csv`: не меньше двух строк, давление строго растёт (DEBT-038).
     ```
3. `examples/04_table_table/README.md`: после строки 47 («`oil_pvt.csv` — таблица PVTO: строки сгруппированы по веткам $R_s$.») добавить:
   ```markdown
   В каждой ветке не меньше двух строк: первая — давление насыщения, дальше давление строго растёт. Иначе решатель остановится с сообщением об ошибке в таблице.
   ```
   README 04 тестами не проверяется: grep `README` в `tests/` даёт только `test_examples.py`, `test_pvt_consistency.py`, `test_prototype_activation_cap.py`, и ни один не читает README 04.

**Проверка:** `--collect-only -q` → 1277 (меняются только документы).

**Зависимости:** требует шаг 3, так как текст ссылается на функцию.

**Оценка:** ~8 строк текста, ~10 мин.

### Шаг 6: Верификация — полный прогон

**Цель:** все тесты зелёные, примеры не задеты.

**Что сделать** (из `numerical_solver/`):
```powershell
.venv\Scripts\python -m pytest tests/ -q
```
Ожидание: **1277 passed** (или база + 7). Тесты примеров (`results`, метка `slow`) строят все табличные примеры через `from_config`. Это и есть проверка, что 16 таблиц проекта проходят новую проверку в штатном пути. Отдельный тест-перебор таблиц примеров не добавляется: примеры самостоятельны, а их тесты уже проходят фабрику.

**Зависимости:** требует шаги 3–5.

**Оценка:** 0 строк, ~10 мин.

### Шаг 7: Vault и issue

**Цель:** закрыть запись и оставить результат в issue.

**Файлы:**
- `vault/roadmap/известные баги и технический долг.md` (запись DEBT-038)
- `vault/issues/debt-038/05-comment-done.md` (новый)
- `vault/00-home/index.md` (строка плана)
- `vault/plans/debt-038 pvto-branch-checks.md` (`status`)

**Что сделать:**
1. DEBT-038: поле «Результат» — функция, вызов, 7 тестов, число тестов было/стало, тесты прототипа 93 passed, полный прогон. Статус — `✅ ГОТОВО (дата)`.
2. Комментарий в #67: `gh issue comment 67 --repo ArturSalamatin/Oil_Gas --body-file vault/issues/debt-038/05-comment-done.md`.
3. Строка в `index.md` — отметить «реализовано», `status` плана — `реализован`.

**Проверка:** `--collect-only -q`.

**Зависимости:** требует шаг 6.

**Оценка:** ~15 строк текста, ~10 мин.

## Тестовая стратегия

Новые тесты — класс `TestPVTOBranches` в `numerical_solver/tests/test_factory_prototype.py`, раздел G. Все идут через `SimulatorFactory.from_config` с подменённой `oil_pvt.csv` (помощник `_table_config_with_oil_csv`).

| Тест | Сценарий | Ожидание | До правки (проба) | Предотвращает |
|---|---|---|---|---|
| `test_one_row_branch_raises` | ветвь $R_s$ = 15 из одной строки между 0 и 30 | `ValueError`, «R_s = 15 м³ст/м³ст из одной строки (p = 10 МПа)», начало «oil_pvt.csv:» | проходит | несжимаемая ветвь без сообщения |
| `test_one_row_last_branch_raises` | последняя ветвь 30 из одной строки | «R_s = 30 м³ст/м³ст из одной строки» | проходит | случай, который отвергает и ECLIPSE |
| `test_repeated_pressure_raises` | 20 МПа дважды в ветви 30 | «не растёт строго», «20 МПа после 20 МПа (строки 2 и 3 ветви)» | проходит + `RuntimeWarning` | скачок $B_o$, выбор строки сортировкой по $B_o$ |
| `test_pressure_out_of_order_raises` | ветвь 30: 15, 30, 20 МПа | «20 МПа после 30 МПа (строки 2 и 3 ветви)» | проходит | расхождение правил CSV и XLSX |
| `test_rs_typo_extra_branch_raises` | $R_s$ = 30.01 у средней строки ветви 30 | «R_s = 30.01 м³ст/м³ст из одной строки» | проходит | опечатка в $R_s$; порядок проверок (до `_check_rs0_in_table`) |
| `test_empty_table_raises` | только заголовок | «oil_pvt.csv: нет ни одной числовой строки» | `IndexError` | непонятное падение в конструкторе |
| `test_interleaved_branches_pass` | строки ветвей 0 и 30 чередуются | `from_config` не бросает | проходит | слишком строгая проверка (смежность) |

**Неизменность поведения:**
- `TestCSVReaders`, `TestFactoryTablePVT`, `TestInitialStateVsTable`, `TestInitialRangeWarnings` (тот же файл).
- `tests/test_pvt_consistency.py` (BUG-019, табличные случаи).
- `tests/test_prototype_adapter.py` (прямой `BlackOilPVT`).
- Тесты примеров (полный прогон) — все табличные примеры через фабрику.
- Тесты прототипа (93) — фикстура «one-row branch» без изменений.

## Критерии завершения

- [ ] `_check_pvto_branches` в `factory.py` и вызов до `BlackOilPVT` в `_create_pvt`
- [ ] 7 тестов `TestPVTOBranches` зелёные; до реализации было 6 красных и 1 зелёный (шаг 2)
- [ ] Быстрый уровень: база + 7, все зелёные; полный прогон: база + 7 (1277 при базе 1270), все зелёные
- [ ] Тесты прототипа: 93 passed; код `radial_blackoil/` не изменён (`git diff --stat` по `HydroSolverPrototype/Prototype_1.0.3/radial_blackoil` пуст)
- [ ] Документация: P8, json-config-schema (включая исправление строки 64), README 04
- [ ] Vault: запись DEBT-038 «Результат» и статус, план `status: реализован`, index.md
- [ ] Комментарий в #67 (`05-comment-done.md`); issue закрывается при влитии

## Обнаруженные проблемы

1. **DEBT-042** (зарегистрирован 2026-10-07 по решению пользователя). CSV-ридеры фабрики при нечисловом значении делают `continue`: опечатка в числе молча удаляет строку таблицы. Лишние столбцы отбрасываются без сообщения: десятичная запятая сдвигает значения. У `_read_relperm_csv` столбцы дописываются по одному, поэтому при ошибке во 2-м или 3-м столбце они получаются разной длины. `TabulatedRelPerm` такие столбцы принимает, отказ наступает позже: `np.interp: fp and xp are not of the same length`. Проверки DEBT-038 ловят пропуск строки, только если ветвь сократилась до одной строки. Не блокирует.
2. **`json-config-schema.md:64`** неверно описывает табличный путь («колонки p, Bo, Bg, mu_o, mu_g, Rs_eq»). Исправляется в шаге 5, отдельной записи не требует.
3. **Прямой вызов `BlackOilPVT`** с повтором давления по-прежнему даёт `RuntimeWarning: divide by zero` (`pvt.py:56`) без имени файла. Это осознанный минус варианта 1 (решение пользователя). XLSX- и CSV-пути до этого места не доходят.

## Оценка

Файлов: 2 кода и теста GPN, 1 теста прототипа (комментарий), 3 документации, 4 vault. Строк: ~40 кода, ~110 тестов, ~10 текста. Время: ~70 мин, из них ~10 — полный прогон. Сложность — простая.

## Связанные заметки

- [[известные баги и технический долг]] — DEBT-038, DEBT-042, BUG-017, BUG-019, DEBT-036
- [[bug-017 rs0-table-range-check]] — образец проверки таблицы в фабрике (`_check_rs0_in_table`)
- [[debt-036 table-pvt-residual-speedup]] — векторизованная интерполяция PVTO, фикстура «one-row branch»
- [[P8-формат-ввода-json]], [[json-config-schema]] — формат ввода
- [[P5-pvt-архитектура]] — табличный путь PVT через прототип
