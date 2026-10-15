---
tags:
  - план
  - рефакторинг
date: 2026-10-15
issue: DEBT-075
github: 124
branch: refactor/debt-075/saturation-bounds-check
status: реализован
worktree: .worktrees/debt-075
audit:
  date: 2026-10-15
  round: 2
  focus: реализуемость — полный прогон с правкой в памяти, путь отказа до пользователя (run_case, CLI), смещение базы (DEBT-073 влит, DEBT-074 в работе), сторож ссылок по новым текстам
  found: 4
  auto-fixed: 4
  manual-required: 0
---

# План DEBT-075: проверка принятого состояния гидродинамики — $0 \le S_g \le 1$, $p > 0$, $R_s \ge 0$, конечность

**Задача:** DEBT-075 в `vault/roadmap/известные баги и технический долг.md` · GitHub [#124](https://github.com/ArturSalamatin/Oil_Gas/issues/124) · ветка `refactor/debt-075/saturation-bounds-check` в worktree `.worktrees/debt-075` · база `numerical_scheme/implementation` (план — `3899d9b`; код на нём = `a180d88`, после DEBT-071: две последние фиксации меняли только vault; аудит 1 — `130b88d`, код тот же; аудит 2 — `3eee0d4`: влит DEBT-073 `1ee0ab6` — `factory.py`, тесты фабрики, README 04/05, P8; файлы этого плана в коде не тронуты)

**Подтип:** рефакторинг с ужесточением проверки результата шага — по образцу DEBT-047 (проверка $T$). На допустимых данных числа решателя, истории и README примеров не меняются: проверка только читает состояние. Прототип не меняется.

## Кратко

`Simulator._advance` принимает подшаг гидродинамики, если `HydroSolver.solve` не бросил `HydroConvergenceError`. Что в возвращённом состоянии, не проверяет никто: от $S_g > 1$ ($S_o < 0$) защищает только порог $S_g \le 0.98$ внутри Ньютона прототипа — число без обоснования, о котором GPN не знает. Без порога пример 05 с таблицей ОФП до $S_g$ = 0.01 доходит до $S_g[0]$ = 311 к 6 ч без единого отказа (замер DEBT-073).

После плана `_advance` сразу после `hydro.solve` вызывает `_check_hydro_state`: $S_g \notin [0, 1]$, $p \le 0$, $R_s < 0$ или не конечное значение → `RuntimeError` с фактами (подшаг, время, первая от забоя плохая ячейка, её $r$, величина и значение, число таких ячеек). Сравнение точное, без допуска.

### Решения пользователя (2026-10-15, при планировании)

1. **Состав:** $S_g$, $p$, $R_s$ и конечность всех трёх — тот же набор, что `state_sanity` прототипа (`radial_blackoil/diagnostics.py:7-14`), а не только $S_g$.
2. **Вид отказа:** `RuntimeError` (расчёт обрывается), не `HydroConvergenceError` (дробление).
3. **Допуск:** точное сравнение, без допуска.

## Замеры при планировании

Пробы — `vault/issues/debt-075/probes/`, на `3899d9b` (код `a180d88`), запуск из `numerical_solver/`.

### 1. Красное состояние: что делает `Simulator` сейчас (`red_state.py`, `red_state.out.txt`)

Двойники `tests/test_simulator.py` (`_make_simulator`: `LogProfileHydroStub` + настоящий `TridiagEnergySolver`, N = 10, 24 шага по 1 ч). Обёртка гидродинамики на 2-м вызове ставит в ячейку 3 значение:

| величина = значение | исход до плана | после плана |
|---|---|---|
| $S_g$ = 1.5, 6.585, −0.01, $1 + 2^{-52}$, $-5\cdot10^{-324}$ | расчёт до конца, 24 вызова, молча | `RuntimeError` на 2-м подшаге |
| $p$ = 0, −1e5 Па | до конца, молча (у $p$ = 0 — `RuntimeWarning: divide by zero` в $B_g$) | `RuntimeError` |
| $R_s$ = −1 | до конца, молча | `RuntimeError` |
| NaN или inf в $S_g$, $p$, $R_s$ | `ValueError: array must not contain infs or NaNs` из `scipy.linalg.solve_banded` в шаге энергии — без ячейки и величины, с пачкой `RuntimeWarning` | `RuntimeError` до шага энергии |
| $S_g$ = 0, 1; $p$ = 1 Па; $R_s$ = 0 | до конца | до конца (границы включены, окна правдоподобия нет) |

### 2. Штатные примеры: значений за пределами нет (`sg_range_scan.py`, `sg_range_scan.out.txt`)

Обёртка `PrototypeHydroAdapter.solve` записывает каждое возвращённое без исключения состояние (это принятые подшаги: `Simulator` отвергает подшаг только по `HydroConvergenceError`). Все 23 примера `examples/`, 6161 принятый подшаг (13 с — 25 с на пример):

- значений $S_g < 0$, $S_g > 1$, $R_s < 0$, не конечных — **0**;
- $\min S_g = 0$ ровно (у однофазных ячеек $S_g = 0$ точно во всех примерах), $\max S_g$ = 0.701 (04a); $\min R_s = 0$ ровно (01, 02, 04a); $\min p$ = 3.04 МПа (21).

Отсюда точное сравнение: прототип сам обнуляет малые отрицательные $S_g$ двухфазных ячеек (`blackoil.py:670` в `_advance_phases`, `:752` в `_newton_switching`), у однофазных ставит $S_g = 0$ (`unpack`, `:261`). Тот же точный критерий на конечном состоянии уже стоит в `tests/test_examples.py:308-313`.

### 3. Сценарий DEBT-073 без порога 0.98 (`real_scenario.py`, `real_scenario_emulate.out.txt`)

Пример 05, таблица ОФП до $S_g$ = 0.01, порог 0.98 → inf в памяти, проверка таблиц фабрики отключена подменой (после DEBT-073 фабрика такую таблицу отвергает). Режим `emulate`: обёртка адаптера бросает `RuntimeError` на первом принятом состоянии с $S_g \notin [0, 1]$ — то же место, где встанет проверка. Итог: **отказ на первом принятом подшаге, $t$ = 450 с, $dt$ = 450 с, ячейка 0, $S_g$ = 6.58519, таких ячеек 2 из 50** (без проверки — $S_g[0]$ = 311 к 6 ч). Режим `real` — после шага 1, проверка самой реализации (шаг 1, п. 10).

### 4. Исполнение шага 1 из текста плана (аудит 1 — `130b88d`, аудит 2 — `3eee0d4`)

`plan_apply.py` берёт из шага 1 этого файла блоки «До/После», метод и тесты раздела J, проверяет, что каждый «До» найден в файле ровно один раз, пишет копии (`probes/patched/`) и подставляет `_advance` и `_check_hydro_state` в существующий класс `Simulator` в памяти; `plan_patch_plugin.py` делает это до сбора тестов (`pytest -p plan_patch_plugin`, `PYTHONPATH` на `probes/`). Рабочие файлы не меняются.

- Все блоки «До» совпали; исправленные `simulator.py` и `hydro/base.py` разбираются `ast`.
- Тесты J на исходном коде: **14 failed, 4 passed** (9 `DID NOT RAISE`, 5 `ValueError` scipy) — как в шаге 1, п. 3.
- С правкой: J + `tests/test_simulator.py` — 78 passed; быстрый уровень + J — **1735 passed** (`fast_with_plan.out.txt`; 140 с при параллельном `/implement` DEBT-073).
- `real_scenario.py real` с правкой — отказ на первом принятом подшаге, текст — в шаге 1, п. 10 (`real_scenario_real_emulated.out.txt`).
- Первый прогон нашёл, что у `_CorruptingHydroSolver` не было `component_inventories` — все 18 тестов падали `AttributeError`; исправлено (подводные камни).

Аудит 2 (`3eee0d4`, после влития DEBT-073; код к `045228e` не менялся):
- **полный прогон с правкой в памяти — 2014 passed** (1996 + 18, 596 с; `full_with_plan.out.txt`): медленные тесты — примеры через фикстуру `results`, сгущённые сетки, VAL-004 — проверку не задевают;
- блок «До» нового п. 8 (`report/pipeline.py`) совпал; `real_scenario.py` в обоих режимах на базе с DEBT-073 — прежний результат;
- `test_eq_references.py` читает файлы с диска, правку в памяти не видит — поэтому `plan_apply.py` прогоняет его шаблоны по исправленным копиям и текстам шага 2 сам (`check_eq_refs`): нарушений 0.

Повтор при необходимости (из `numerical_solver/`): `python ..\vault\issues\debt-075\probes\plan_apply.py`, затем `$env:PYTHONPATH="..\vault\issues\debt-075\probes"; python -m pytest -p plan_patch_plugin ..\vault\issues\debt-075\probes\test_plan_j.py -q`.

## Текущее состояние (на `3899d9b`)

`numerical_solver/gpn_multiphase_solver/simulator.py`:
- `:7-12` — докстринг модуля: «подшаг × (hydro.solve → energy.solve → обновить state)»;
- `:315-327` — `hydro.solve` в `try`, `except HydroConvergenceError` (дробление, `continue`);
- `:329-331` — баланс массы принятого подшага (`mass.add_step`);
- `:337-338` — `energy.solve`;
- `:340-349` — комментарий и вызов `self._check_temperature(T_new, h, hydro_result.state.t)` (DEBT-047);
- `:416-432` — `_check_temperature`: образец метода проверки.

`numerical_solver/gpn_multiphase_solver/hydro/base.py:33-52` — докстринг `HydroSolver.solve`: контракт шага; о допустимости состояния — ничего.

`numerical_solver/gpn_multiphase_solver/hydro/prototype_adapter.py:338-352` — отказ `advance` → `HydroConvergenceError`; принятый шаг обновляет память ступени 4 (`:345-347`, DEBT-048) и пишет предупреждения о выходе за таблицы (`:352`). **Не меняется.**

Прототип: `radial_blackoil/diagnostics.py:7-14` — `state_sanity` (те же величины, допуск 1e-9; GPN её не вызывает, сам прототип вызывает только в `simulation.py:56, 98` и лишь копит тексты). `radial_blackoil/blackoil.py:460`, `:753-754` — порог 0.98. **Не меняются.**

Тесты: `numerical_solver/tests/test_simulator.py` — раздел G (`:779-885`): `_CorruptingEnergySolver` (`:790-810`), `TestNonphysicalTemperature` (`:813-885`). Файл кончается на `:885`. Двойник `FailingHydroStub` — `tests/_doubles.py:73-98`. Помощники: `_make_simulator` (`:56-70`), `_initial_state` (`:73-77`), `_single_interval_schedule` (`:80`).

Baseline (аудит 2, `3eee0d4`, после влития DEBT-073): **1996 тестов** (`--collect-only -q`), быстрый уровень **1720** (`-m "not slow"`, 276 отобрано в медленные), ~70 с. На `3899d9b` (план) было 1993 / 1717.

## Целевое состояние

- `simulator.py`: метод `Simulator._check_hydro_state(state, dt)` после `_check_temperature`; вызов в `_advance` сразу после блока `try/except` гидродинамики, до баланса массы и энергии.
- `hydro/base.py`: в докстринге `HydroSolver.solve` — контракт: принятое состояние $0 \le S_g \le 1$, $p > 0$, $R_s \ge 0$, конечное, точно.
- `tests/test_simulator.py`: раздел J — обёртка `_CorruptingHydroSolver` и класс `TestNonphysicalHydroState` (18 тестов). Итог: 1996 → **2014**, быстрый 1720 → **1738**.
- Документы: `vault/knowledge/decisions/P8-формат-ввода-json.md` (таблица проверок + абзац), `vault/knowledge/decisions/модули-simulator-оркестратор.md` (псевдокод цикла + список).
- `report/pipeline.py`: комментарий к `except RuntimeError` в `run_case` называет новый источник отказа (код тот же).
- Адаптер, прототип, фабрика, конфиги, примеры, README — без изменений.

## Варианты (из issue) и выбор

| вариант | суть | итог |
|---|---|---|
| 1 | проверка в `Simulator._advance` после `hydro.solve` | **выбран**: одна на любой `HydroSolver`, рядом с проверкой $T$; адаптер и прототип не трогаются |
| 2 | `state_sanity` в `PrototypeHydroAdapter.solve` | отклонён: только для прототипа; английские тексты без ячейки и значения; допуск 1e-9 — против решения 3 |
| 3 | вид отказа и допуск | `RuntimeError`, точно (решения 2, 3) |

Почему `RuntimeError`, а не `HydroConvergenceError`:
- у сценария DEBT-073 корень выше 1 при любом подшаге ($S_g[0] = 0.917 + 0.0144\,\text{с}^{-1}\cdot dt$, $S_g = 1$ при $t^* \approx 62$ с, наименьший подшаг 7.03 с длиннее) — дробление дало бы 9 бесполезных повторов и прежний совет «увеличьте `max_retries`»;
- к моменту проверки адаптер уже записал шаг как принятый (память ступени 4, `prototype_adapter.py:345-347`): повтор подшага из прежнего состояния не совпал бы с ключом памяти и сбросил бы серию — поведение иное, чем при отказе внутри `advance`. При `RuntimeError` расчёт кончается, память не важна.

## Подводные камни (чеклист)

| пункт | оценка | комментарий |
|---|---|---|
| Все места вызова | ✅ | `_advance` — единственное место, где принимается подшаг гидродинамики; `run` вызывает только его |
| Зависимости пакетов | ✅ | новых нет; `np`, `DAY_TO_S` уже импортированы в `simulator.py` |
| Обратная совместимость API | ✅ | новый приватный метод; сигнатуры `Simulator`, `HydroSolver` не меняются |
| Состояние при ошибке | ✅ | `RuntimeError` уходит из `run`; накопители балансов к моменту проверки этого подшага не получили (проверка до `mass.add_step` и `energy.solve`) — `run` их всё равно не возвращает |
| Существующие тесты | ✅ | все двойники `HydroSolver` в тестах возвращают допустимые состояния (`LogProfileHydroStub`: $S_g = 0$, $R_s = R_{s,ext} \ge 0$, лог-профиль $p > 0$; обёртки в `test_mass_balance.py:118`, `test_prototype_activation_cap.py:133`, `test_prototype_phase_switching.py:261, 573`, `test_simulator.py:681` делегируют настоящему решателю или бросают исключение); примеры — замер 2 |
| Циклы импорта | ✅ | импортов не добавляется |
| Ссылки на уравнения в докстрингах | ✅ | новых формул нет; `tests/test_eq_references.py` ловит числовые ссылки — в тексте их нет |
| Конфиги | ✅ | не меняются |
| Связь с другими задачами | ⚠️ | DEBT-073 (план готов): правит `factory.py`, тесты фабрики и строку `:221` в P8 — с этим планом пересекается только P8 (строка ниже, `:223-224`); при конфликте влития — оставить обе правки. Проба `real_scenario.py` работает до и после DEBT-073 (проверка таблиц отключена подменой). DEBT-047: проверка $T$ остаётся как есть |
| Производительность | ✅ | три сравнения массивов длины N на подшаг; рядом решение Ньютона с якобианом — не видно |
| Прототип | ✅ | не меняется — регрессия прототипа не нужна |
| NaN в сравнениях | ✅ | `np.nan >= 0` — `False` без предупреждения; `isfinite` отсекает ±inf (`inf > 0` истинно) |
| Формат значения | ⚠️ | не `.6g`: $1 + 2^{-52}$ печаталось бы как «1» — непонятно, за что отказ. `repr(float(x))` даёт кратчайшую точную запись: `6.585`, `1.0000000000000002`, `-5e-324`, `nan`, `-100000.0` |
| Обёртка тестов без `component_inventories` | ⚠️ (аудит 1) | `Simulator.run` спрашивает запас начального состояния у любой гидродинамики (`simulator.py:199`), `FailingHydroStub` — у обёрнутой (`tests/_doubles.py:98`). `_CorruptingHydroSolver` не наследует `HydroSolver`, поэтому метод обязан делегировать сам — без него все 18 тестов падают `AttributeError` до первого шага (замер аудита) |
| Точность для $R_s$ — только замер | ⚠️ (аудит 1) | Для $S_g$ точное сравнение держит код прототипа (обнуление $S_g \in [-10^{-9}, 0)$, `blackoil.py:670`; ступень 4 переключает ячейку при $S_g < -10^{-9}$ на каждом приближении, `_switch_phases`, `:693`, и обнуляет остаток, `:752`). Для $R_s$ такого нет: пробная точка однофазной ячейки принимается при $R_s \ge -10^{-8}$ (`_trial_is_reasonable`, `blackoil.py:451`), и принятое $R_s \in [-10^{-8}, 0)$ код не исправляет. Отрицательное $R_s$ возможно только при $R_s \approx 0$: при $R_{s,0} = 0$ газовые строки якобиана не зависят от $p$, правая часть по газу — нуль, и $R_s$ остаётся нулём точно (01, 02: $\min R_s = 0$ ровно, замер 2). Отказ на $R_s \in [-10^{-8}, 0)$ — сигнал вернуться к допуску (решение 3); текст отказа называет величину и значение, путаницы с $S_g$ нет. Записано в комментарии метода |
| DEBT-073 | ✅ (аудит 2) | влит `1ee0ab6` (база `3eee0d4`): правил `factory.py`, тесты фабрики, README 04/05 и строку `:221` в P8 — с файлами этого плана в коде не пересекается; якоря шага 2 в P8 (`:223`, `:254`) на месте. Baseline стал 1996 / 1720, итог — 2014 / 1738 (сверено `--collect-only`). Проба `real_scenario.py` отключает `_check_relperm_table` через `*args` — на `3eee0d4` (сигнатура `(Sg, kro, relperm_file)`) оба режима дают прежний результат (аудит 2) |
| Путь отказа до пользователя | ✅ (аудит 2) | `run_case` (`report/pipeline.py:125-131`) превращает любой `RuntimeError` из `simulator.run` в `CaseRunError` с тем же текстом; `cli.py:88-90` печатает «Расчёт не завершён: <текст>» и возвращает 1. Новый отказ идёт этим путём без правок кода; общий тест — `tests/test_examples.py::test_run_case_run_failure`. Комментарий `pipeline.py:128-130` перечисляет источники отказа — дополняется (шаг 1, п. 8) |

## Обнаруженные проблемы

Новых задач нет. Уточнение к issue: в вопросе пользователю при планировании я утверждал, что NaN в $p$ без проверки «всплыл бы как „Нефизичная температура“». Замер 1 это опровергает: это `ValueError` scipy в `solve_banded` (`check_finite`) из шага энергии. Вывод — диагноз неверный — тот же.

## Шаги

### Шаг 1: проверка в `Simulator` + тесты

**Цель:** `_advance` обрывает расчёт `RuntimeError` при нефизичном состоянии гидродинамики; тесты на все величины, границы, порядок и дробление.

**Файлы:**
- `numerical_solver/gpn_multiphase_solver/simulator.py`
- `numerical_solver/gpn_multiphase_solver/hydro/base.py`
- `numerical_solver/gpn_multiphase_solver/report/pipeline.py` (только комментарий, п. 8)
- `numerical_solver/tests/test_simulator.py`

**Контекст:** §«Кратко», замеры 1–3. Образец — DEBT-047: `_check_temperature` (`simulator.py:416-432`) и раздел G тестов. Сначала тесты (красные на базе — замер 1), затем код.

**Что сделать:**

1. `tests/test_simulator.py`, докстринг модуля (`:7-16`) — после строки `I. Нарастание шага после смены управления (FEAT-032)` добавить:
   ```
   J. Отказ при нефизичном состоянии гидродинамики: S_g вне [0, 1], p ≤ 0, R_s < 0 или не конечны (DEBT-075)
   ```

2. `tests/test_simulator.py`, импорт: в начало (после `from pathlib import Path`, `:18`) добавить `from dataclasses import replace`.

3. `tests/test_simulator.py`, в конец файла (после `:885`) — раздел J:

   ```python


   # ═══════════════════════════════════════════════════════════
   # J. Отказ при нефизичном состоянии гидродинамики (DEBT-075)
   # ═══════════════════════════════════════════════════════════
   #
   # От S_g > 1 (S_o < 0) прототип защищает только порог S_g <= 0.98 в своём
   # Ньютоне; без него пример 05 с таблицей ОФП до S_g = 0.01 дошёл до
   # S_g[0] = 311 без отказа (замер DEBT-073). До DEBT-075 S_g вне [0, 1],
   # p <= 0 и R_s < 0 проходили молча, а NaN и inf давали ValueError scipy в
   # шаге энергии без ячейки и величины (vault/issues/debt-075/probes/
   # red_state.out.txt). Тесты портят результат гидродинамики обёрткой: отказ
   # обязан дать сам Simulator, какой бы HydroSolver ни вернул такое состояние.


   class _CorruptingHydroSolver:
       """Обёртка гидродинамики: на вызове on_call ставит state.<поле>[ячейка] = значение.

       Физику не подменяет — делегирует внутреннему двойнику и портит только
       состояние его результата; потоки остаются прежними.
       """

       def __init__(self, inner, changes, on_call=2):
           # changes — список (поле SimulationState, ячейка, значение)
           self._inner = inner
           self._changes = changes
           self._on_call = on_call
           self.n_calls = 0

       def solve(self, state, dt, bc):
           result = self._inner.solve(state, dt, bc)
           self.n_calls += 1
           if self.n_calls != self._on_call:
               return result
           fields = {}
           for field, cell, value in self._changes:
               x = fields.get(field, getattr(result.state, field).copy())
               x[cell] = value
               fields[field] = x
           return replace(result, state=replace(result.state, **fields))

       def component_inventories(self, state):
           """Запас — у внутреннего двойника (DEBT-039)."""
           # Simulator.run спрашивает запас начального состояния у любой
           # гидродинамики (simulator.py, run): без метода — AttributeError до
           # первого шага. FailingHydroStub тоже зовёт его у обёрнутого.
           return self._inner.component_inventories(state)


   class TestNonphysicalHydroState:
       """Simulator останавливает расчёт, если после шага гидродинамики S_g, p или R_s нефизичны."""

       @pytest.mark.parametrize("field, value, shown", [
           # S_g > 1 — S_o < 0; 6.585 — S_g[0] первого подшага сценария DEBT-073
           # без порога (vault/issues/debt-075/probes/real_scenario_emulate.out.txt)
           ("Sg", 6.585, "S_g = 6.585"),
           ("Sg", -0.01, "S_g = -0.01"),
           # точное сравнение (решение пользователя): соседние с границами
           # числа с плавающей точкой — уже нарушение
           ("Sg", np.nextafter(1.0, 2.0), "S_g = 1.0000000000000002"),
           ("Sg", np.nextafter(0.0, -1.0), "S_g = -5e-324"),
           ("Sg", np.nan, "S_g = nan"),
           ("Sg", np.inf, "S_g = inf"),
           ("p", 0.0, "p = 0.0 Па"),
           ("p", -1e5, "p = -100000.0 Па"),
           ("p", np.nan, "p = nan Па"),
           ("p", np.inf, "p = inf Па"),
           ("Rs", -1.0, "R_s = -1.0 м³ст/м³ст"),
           ("Rs", np.nan, "R_s = nan м³ст/м³ст"),
       ], ids=["sg_above_1", "sg_negative", "sg_1_plus_ulp", "sg_minus_tiny",
               "sg_nan", "sg_inf", "p_zero", "p_negative", "p_nan", "p_inf",
               "rs_negative", "rs_nan"])
       def test_nonphysical_state_raises(self, field, value, shown):
           """Отказ называет подшаг, время его конца, ячейку, её r, величину и значение.

           24 шага по 1 ч, состояние испорчено на втором вызове гидродинамики:
           конец шага t = 7200 с = 0.0833 сут, ячейка 3 из 10. Шаг энергии
           испорченного подшага не вызывается: проверка стоит до него.
           """
           grid, pvt, inner_hydro, inner_energy, _ = _make_simulator()
           hydro = _CorruptingHydroSolver(inner_hydro, [(field, 3, value)])
           # on_call=0 не совпадает ни с одним вызовом: обёртка только считает вызовы
           energy = _CorruptingEnergySolver(inner_energy, 0.0, on_call=0)
           sim = Simulator(grid, hydro, energy, pvt, _single_interval_schedule())

           with pytest.raises(RuntimeError, match="Нефизичное состояние") as exc:
               sim.run(_initial_state())

           msg = str(exc.value)
           assert "после шага гидродинамики dt = 3600 с" in msg
           assert "t = 0.0833 сут" in msg
           assert f"в ячейке 3 (r = {grid.r_centers[3]:.4g} м)" in msg
           assert shown in msg
           assert "— 1 из 10" in msg
           assert hydro.n_calls == 2
           assert energy.n_calls == 1

       @pytest.mark.parametrize("field, value", [
           ("Sg", 0.0),
           ("Sg", 1.0),
           ("p", 1.0),
           ("Rs", 0.0),
       ], ids=["sg_zero", "sg_one", "p_one_pa", "rs_zero"])
       def test_bounds_pass(self, field, value):
           """Границы включены, окна правдоподобия нет: расчёт идёт до конца.

           S_g = 1 (S_o = 0) и R_s = 0 допустимы; p = 1 Па нефизично для
           пласта, но положительно — критерий только p > 0 (как T > 0 у
           DEBT-047). Тест ловит строгие неравенства и пороги, добавленные без
           решения. Замер: все четыре случая до плана тоже доходят до конца
           (red_state.out.txt).
           """
           grid, pvt, inner_hydro, energy, _ = _make_simulator()
           hydro = _CorruptingHydroSolver(inner_hydro, [(field, 3, value)])
           sim = Simulator(grid, hydro, energy, pvt, _single_interval_schedule())

           history = sim.run(_initial_state())

           assert hydro.n_calls == 24
           assert history.times[-1] == pytest.approx(86400.0)

       def test_first_violation_named(self):
           """Отказ называет первую нарушенную величину и первую от забоя ячейку.

           Порядок проверки — S_g, p, R_s: p испорчено в ячейке 2, S_g — в
           ячейках 7 и 3. Отказ — по S_g (хотя ячейка p ближе к забою), ячейка 3
           (первая от забоя среди плохих по S_g), число ячеек — 2.
           """
           grid, pvt, inner_hydro, energy, _ = _make_simulator()
           hydro = _CorruptingHydroSolver(
               inner_hydro, [("p", 2, -1.0), ("Sg", 7, 1.5), ("Sg", 3, -0.01)])
           sim = Simulator(grid, hydro, energy, pvt, _single_interval_schedule())

           with pytest.raises(RuntimeError, match="Нефизичное состояние") as exc:
               sim.run(_initial_state())

           msg = str(exc.value)
           assert f"в ячейке 3 (r = {grid.r_centers[3]:.4g} м) S_g = -0.01" in msg
           assert "газонасыщенность вне [0, 1] или не конечна, — 2 из 10" in msg
           assert "p = " not in msg

       def test_raises_under_subdivision(self):
           """Проверка работает на подшагах локального дробления и сама подшаг не дробит.

           Гидро отказывает на шаге 3600 с: Simulator делит его пополам.
           Обёртка порчи стоит внутри FailingHydroStub, поэтому считает только
           несостоявшиеся отказом вызовы: первый из них — подшаг 1800 с, он и
           испорчен. Отказ называет dt = 1800 с; подшаг 900 с не пробуется —
           RuntimeError не HydroConvergenceError (решение пользователя).
           """
           grid, pvt, inner_hydro, inner_energy, _ = _make_simulator()
           corrupting = _CorruptingHydroSolver(inner_hydro, [("Sg", 0, 6.585)], on_call=1)
           hydro = FailingHydroStub(corrupting, lambda s, dt: dt > 1800.0)
           energy = _CorruptingEnergySolver(inner_energy, 0.0, on_call=0)
           schedule = _single_interval_schedule(dt_hist=3600.0, dt_int=3600.0)
           sim = Simulator(grid, hydro, energy, pvt, schedule)

           with pytest.raises(RuntimeError, match="Нефизичное состояние") as exc:
               sim.run(_initial_state())

           msg = str(exc.value)
           assert "dt = 1800 с" in msg
           assert "в ячейке 0" in msg
           assert hydro.dt_calls == [3600.0, 1800.0]
           assert energy.n_calls == 0
   ```

   Прогнать `pytest tests/test_simulator.py -k NonphysicalHydroState -q` — **ожидание до кода: 14 failed, 4 passed.** Подсчёт по замеру 1: в `test_nonphysical_state_raises` 7 случаев с конечными значениями доходят до конца (`DID NOT RAISE`), 5 случаев NaN/inf дают `ValueError` scipy — не `RuntimeError`, `pytest.raises` его пропускает; `test_first_violation_named` и `test_raises_under_subdivision` — `DID NOT RAISE`; зелёные — 4 случая `test_bounds_pass`. Записать фактическое в отчёт шага.

4. `simulator.py`, `_advance` — между концом блока `except` (`:327`, `continue`) и комментарием баланса массы (`:329`) вставить:

   До:
   ```python
                   size //= 2
                   continue

               # Баланс массы (DEBT-039): только принятый подшаг.
   ```
   После:
   ```python
                   size //= 2
                   continue

               # 1a. Нефизичное состояние гидродинамики — отказ (DEBT-075). От
               # S_g > 1 (S_o < 0) прототип защищает только порог S_g <= 0.98 в
               # своём Ньютоне (blackoil.py: _trial_is_reasonable, _newton_switching);
               # без порога пример 05 с таблицей ОФП до S_g = 0.01 дошёл до
               # S_g[0] = 311 без отказа (замер DEBT-073), а NaN в состоянии давал
               # ValueError scipy в шаге энергии без ячейки и величины
               # (vault/issues/debt-075/probes/red_state.out.txt). Проверка здесь,
               # а не в адаптере: одна на любой HydroSolver, до баланса массы и
               # энергии. RuntimeError, не HydroConvergenceError: дробление не
               # поможет (у DEBT-073 корень выше 1 при любом подшаге), а адаптер
               # уже записал шаг как принятый (память ступени 4, DEBT-048).
               self._check_hydro_state(hydro_result.state, h)

               # Баланс массы (DEBT-039): только принятый подшаг.
   ```

5. `simulator.py` — новый метод сразу после `_check_temperature` (после `:432`, перед `_mass_snapshot`):

   ```python
       def _check_hydro_state(self, state: SimulationState, dt: float) -> None:
           """Отказ, если после шага гидродинамики S_g вне [0, 1], p ≤ 0, R_s < 0 или не конечны (DEBT-075)."""
           # Те же величины и пределы, что у state_sanity прототипа
           # (radial_blackoil/diagnostics.py; GPN её не вызывает), но без
           # допуска (решение пользователя): прототип сам обнуляет малые
           # отрицательные S_g двухфазных ячеек (blackoil.py: _advance_phases,
           # _newton_switching), у однофазных S_g = 0 точно (unpack). R_s
           # однофазных ячеек прототип не исправляет (пробная точка
           # принимается при R_s >= -1e-8, _trial_is_reasonable): для R_s
           # точность держится на замере; при R_s0 = 0 R_s остаётся нулём
           # точно (примеры 01, 02). Замер:
           # 23 примера, 6161 принятый подшаг — ни одного значения за
           # пределами, min S_g = min R_s = 0 ровно
           # (vault/issues/debt-075/probes/sg_range_scan.out.txt). Граница —
           # S_o >= 0, не S_o >= S_or: нефть усаживается при разгазировании.
           # Порядок S_g, p, R_s: отказ называет первую нарушенную величину.
           # NaN и ±inf отсекает isfinite (сравнение с NaN ложно, inf > 0
           # истинно). Значение — repr: при .6g 1 + 2e-16 печаталось бы как 1.
           checks = (
               ("S_g", state.Sg, (state.Sg >= 0.0) & (state.Sg <= 1.0), "",
                "газонасыщенность вне [0, 1] или не конечна"),
               ("p", state.p, state.p > 0.0, " Па",
                "давление ≤ 0 или не конечно"),
               ("R_s", state.Rs, state.Rs >= 0.0, " м³ст/м³ст",
                "газосодержание < 0 или не конечно"),
           )
           for name, x, in_range, unit, condition in checks:
               bad = ~(np.isfinite(x) & in_range)
               if not bad.any():
                   continue
               # Факты, как у _check_temperature: первая от забоя плохая ячейка,
               # её r и значение, число таких ячеек; t — конец подшага, dt — его
               # длина (при локальном дроблении — подшаг, а не шаг расписания).
               j = int(np.argmax(bad))
               r = float(self._grid.r_centers[j])
               raise RuntimeError(
                   f"Нефизичное состояние после шага гидродинамики dt = {dt:g} с к "
                   f"t = {state.t / DAY_TO_S:.4f} сут: в ячейке {j} (r = {r:.4g} м) "
                   f"{name} = {float(x[j])!r}{unit}; ячеек, где {condition}, — "
                   f"{int(np.count_nonzero(bad))} из {x.size}.")
   ```

   Пример текста (тест `sg_above_1`): `Нефизичное состояние после шага гидродинамики dt = 3600 с к t = 0.0833 сут: в ячейке 3 (r = … м) S_g = 6.585; ячеек, где газонасыщенность вне [0, 1] или не конечна, — 1 из 10.`

6. `simulator.py`, докстринг модуля (`:9-12`):

   До:
   ```
     Внутренний: шаги dt_integration; шаг, на котором гидродинамика не
     сошлась, дробится локально (DEBT-015): подшаг × (hydro.solve →
     energy.solve → обновить state). Первый шаг интервала со сменой
     управления начинается с подшага dt/2**m и растёт ×2 (FEAT-032)
   ```
   После:
   ```
     Внутренний: шаги dt_integration; шаг, на котором гидродинамика не
     сошлась, дробится локально (DEBT-015): подшаг × (hydro.solve →
     проверка состояния → energy.solve → проверка T → обновить state;
     DEBT-075, DEBT-047). Первый шаг интервала со сменой управления
     начинается с подшага dt/2**m и растёт ×2 (FEAT-032)
   ```

7. `hydro/base.py`, докстринг `HydroSolver.solve` — после абзаца «Один шаг без дробления (DEBT-015). …» (`:48-50`) добавить абзац:
   ```

           Принятое состояние проверяет Simulator (DEBT-075): 0 ≤ Sg ≤ 1,
           p > 0, Rs ≥ 0, все конечны — точно, без допуска; иначе расчёт
           обрывается RuntimeError. Малые отрицательные Sg решатель обнуляет
           сам, как прототип.
   ```

8. `report/pipeline.py`, `run_case` — комментарий к `except RuntimeError` (`:128-130`) перечисляет источники отказа расчёта; добавить новый (аудит 2). Код не меняется: `CaseRunError` и печать «Расчёт не завершён: …» (`cli.py:88-90`) уже берут любой `RuntimeError`.

   До:
   ```python
           # Отказ шага (Simulator._failure_message) или нефизичная T —
           # сообщения решателя написаны для пользователя. Каталог вывода не
           # тронут: очистка — после расчёта.
   ```
   После:
   ```python
           # Отказ шага (Simulator._failure_message), нефизичное состояние
           # гидродинамики (DEBT-075) или нефизичная T (DEBT-047) — сообщения
           # решателя написаны для пользователя. Каталог вывода не тронут:
           # очистка — после расчёта.
   ```

9. Тесты шага: `pytest tests/test_simulator.py -q` — все зелёные (18 новых + прежние).

10. Проба реального сценария в worktree (правило 3 `/implement`: `PYTHONPATH` на worktree, проба печатает путь пакета — сверить, что это worktree):
   ```powershell
   cd .worktrees\debt-075\numerical_solver
   $env:PYTHONPATH = (Get-Location).Path
   $env:PYTHONIOENCODING = "utf-8"
   ..\..\..\numerical_solver\.venv\Scripts\python ..\..\..\vault\issues\debt-075\probes\real_scenario.py real
   ```
   `.venv` — основного каталога (в worktree его нет); проба берёт примеры из текущего каталога (`SOLVER = Path.cwd()`), таблицу ОФП — из `vault/issues/debt-071/probes/` рядом с собой. Первая строка вывода — путь пакета: должен быть worktree. Вывод сохранить в `vault/issues/debt-075/probes/real_scenario_real.out.txt`. **Ожидание:** `RuntimeError: Нефизичное состояние после шага гидродинамики dt = 450 с к t = 0.0052 сут: в ячейке 0 (r = … м) S_g = 6.58518…; …, — 2 из 50.`, принятых подшагов 1 — то же место, что у эмуляции (замер 3). Аудит 1 прогнал пробу с правкой плана в памяти (`plan_apply.py`): `Нефизичное состояние после шага гидродинамики dt = 450 с к t = 0.0052 сут: в ячейке 0 (r = 0.1064 м) S_g = 6.585189352105805; ячеек, где газонасыщенность вне [0, 1] или не конечна, — 2 из 50.` (`real_scenario_real_emulated.out.txt`) — в worktree ожидается тот же текст.

**Проверка после шага:**
- Регресс: быстрый (`pytest tests/ -m "not slow" -q`): 1738 passed (база `3eee0d4`: 1720 + 18). Полный не нужен: проверка только читает состояние, а на примерах значений за пределами нет (замер 2); истории не меняются. Полный прогон — в конце `/implement` (§3.1).
- Регресс прототипа — не нужен (прототип не меняется).

**Подводные камни:** формат значения — `repr`, не `.6g` (чеклист). `on_call=0` у `_CorruptingEnergySolver` — счётчик без порчи: `n_calls` начинается с 1. В `test_raises_under_subdivision` порядок обёрток важен: `FailingHydroStub` снаружи — отказавший вызов не доходит до `_CorruptingHydroSolver` и не входит в его счёт.

**Зависимости:** требует — ничего; блокирует — шаг 2.

**Оценка:** ~45 строк кода, ~150 строк тестов, ~40 мин.

### Шаг 2: документы vault

**Цель:** перечень проверок времени расчёта и описание `Simulator` называют новую проверку.

**Файлы:**
- `vault/knowledge/decisions/P8-формат-ввода-json.md`
- `vault/knowledge/decisions/модули-simulator-оркестратор.md`

**Что сделать:**

1. `P8-формат-ввода-json.md`, таблица проверок — после строки `| расчёт | hydro/prototype_adapter.py: … warn_table_range | …` (`:223`) добавить строку:
   ```
   | | `simulator.py`: `Simulator._check_hydro_state`, `_check_temperature` (в `_advance`) | отказ `RuntimeError`: после шага гидродинамики $S_g \notin [0, 1]$, $p \le 0$, $R_s < 0$ или не конечные — точно, без допуска ([[DEBT-075]]); после шага энергии $T \le 0$ или не конечная ([[DEBT-047]]) |
   ```

2. `P8-формат-ввода-json.md` — после абзаца «Температура в расчёте — `Simulator._advance` …» (`:254`) добавить абзац:
   ```
   Состояние гидродинамики в расчёте — `Simulator._advance` сразу после каждого принятого `hydro.solve`, до баланса массы и энергии ([[DEBT-075]]): $S_g \notin [0, 1]$, $p \le 0$, $R_s < 0$ или не конечное значение → `RuntimeError` с $\Delta t$ подшага, временем его конца, ячейкой, $r$, величиной и значением. Порядок — $S_g$, $p$, $R_s$; сравнение точное (решение пользователя: на 6161 принятом подшаге 23 примеров нарушений нет, $\min S_g = \min R_s = 0$ ровно — `vault/issues/debt-075/probes/sg_range_scan.out.txt`). От $S_o < 0$ раньше защищал только порог $S_g \le 0.98$ в Ньютоне прототипа: без него пример 05 с таблицей ОФП до $S_g$ = 0.01 доходил до $S_g[0]$ = 311 без отказа ([[DEBT-073]]). Подшаг не дробится — дробление ловит только `HydroConvergenceError`.
   ```

3. `модули-simulator-оркестратор.md`:
   - строка `:10` (плашка «Обновлено …»): в конец перед `.` дописать `; [[DEBT-075]] — `_check_hydro_state``. Итог: «… и [[DEBT-047]] (`_check_temperature`); [[DEBT-075]] — `_check_hydro_state`.»
   - псевдокод `_advance`: после блока `except` (`:115-119`, строка `continue`) и пустой строки вставить:
     ```python
             # 1a. S_g вне [0, 1], p ≤ 0, R_s < 0 или не конечны → RuntimeError,
             #     не дробится (DEBT-075)
             self._check_hydro_state(hydro_result.state, h)

     ```
   - список отличий: после пункта о `_check_temperature` (`:180-186`) добавить пункт:
     ```
     - сразу после каждого принятого `hydro.solve`, до баланса массы и
       энергии, `_advance` проверяет состояние гидродинамики
       (`_check_hydro_state`, DEBT-075): $S_g \notin [0, 1]$, $p \le 0$,
       $R_s < 0$ или не конечное значение → `RuntimeError` с $\Delta t$
       подшага, временем его конца, ячейкой, $r$, величиной и значением.
       Сравнение точное. Проверка одна на любой `HydroSolver`; от $S_o < 0$
       раньше защищал только порог 0.98 в Ньютоне прототипа ([[DEBT-073]])
     ```

**Проверка после шага:** Регресс: `pytest tests/ --collect-only -q` — 2014 (шаг меняет только документы) и `pytest tests/test_eq_references.py -q` — зелёный: DEBT-074 (на `045228e` в реализации) добавляет в этот файл проверку заметок `vault/knowledge/` теми же шаблонами, что у кода; если он влит раньше, правки этого шага попадают под неё. Тексты шага 2 и комментарии шага 1 прогнаны шаблонами `FORBIDDEN` и `LABEL_REF` при аудите 2 — нарушений 0 (`plan_apply.py`, функция `check_eq_refs`).

**Зависимости:** требует шаг 1.

**Оценка:** ~20 строк, ~10 мин.

### Шаг 3: vault задачи

`/implement` делает сам: запись DEBT-075 в реестре (статус, поле «Решение»), `vault/issues/debt-075/05-comment-done.md` и комментарий в #124, «План» → статус «реализован». Отдельно в записи DEBT-075 — заменить строку «**Варианты (решить при планировании):**» итогом решений пользователя (§«Решения пользователя»).

## Тестовая стратегия

| Тест | Файл | Сценарий | Ожидание | Предотвращает |
|---|---|---|---|---|
| `TestNonphysicalHydroState::test_nonphysical_state_raises` (12 случаев) | `tests/test_simulator.py` (новый раздел J) | двойник гидродинамики, 24 ч по 1 ч, порча ячейки 3 на 2-м вызове | `RuntimeError` «Нефизичное состояние», `dt = 3600 с`, `t = 0.0833 сут`, ячейка 3 и её $r$, величина = repr значения, «— 1 из 10»; гидро 2 вызова, энергия 1 | молчаливый приём $S_o < 0$, $p \le 0$, $R_s < 0$; `ValueError` scipy без контекста на NaN/inf; проверку после энергии; допуск, добавленный без решения |
| `…::test_bounds_pass` (4) | там же | $S_g$ = 0, 1; $p$ = 1 Па; $R_s$ = 0 | расчёт до конца, 24 вызова, $t$ = 86400 с | строгие неравенства и окна правдоподобия |
| `…::test_first_violation_named` | там же | $p$ плохо в ячейке 2, $S_g$ — в 7 и 3 | отказ по $S_g$, ячейка 3, «2 из 10», про $p$ — ни слова | порядок величин и выбор ячейки |
| `…::test_raises_under_subdivision` | там же | `FailingHydroStub` отказывает при $dt > 1800$ с; порча — на первом принятом | `dt = 1800 с`, ячейка 0, `dt_calls == [3600, 1800]`, энергия 0 вызовов | дробление нефизичного подшага; проверку только на целом шаге |
| регрессия | `tests/` быстрый, в конце `/implement` полный | все примеры, тесты прототипа через адаптер | всё зелёное, 2014 / 1738 | ложное срабатывание на штатных данных (замер 2 — 0 нарушений) |

Реальный сценарий (DEBT-073 без порога) — проба, не тест: требует подмены исходника прототипа в памяти (`exec`), что для теста хрупко.

## Критерии завершения

- [ ] Шаги 1–2 выполнены; шаг 3 — `/implement`
- [ ] `pytest tests/ -q` (полный) — 2014 passed; быстрый — 1738 passed
- [ ] 18 новых тестов раздела J зелёные; до кода — 14 красных (записать фактическое)
- [ ] `real_scenario.py real` в worktree — отказ «Нефизичное состояние» при $t$ = 450 с, ячейка 0, 2 из 50; вывод — `real_scenario_real.out.txt`
- [ ] Прототип, адаптер, фабрика, конфиги, примеры, README не изменены (`git diff --stat` базы…ветки: только `simulator.py`, `hydro/base.py`, `report/pipeline.py` (комментарий), `tests/test_simulator.py` + 2 заметки vault + vault задачи)
- [ ] Истории примеров не изменились — следует из полного прогона (тесты примеров сверяют числа README)
- [ ] Vault: P8, `модули-simulator-оркестратор`, реестр, issue #124 прокомментирован

## Связь формула → код

Новых формул нет. Граница $S_g \le 1$ — тождество $S_o + S_g = 1$ (воды нет, CLAUDE.md «Фазы и насыщенности»), $S_o \ge 0$.

## Как начать работу по этому плану

1. Прочитай этот файл целиком.
2. Прочитай: запись DEBT-075 в `vault/roadmap/известные баги и технический долг.md`; issue #124 (`gh issue view 124 --repo ArturSalamatin/Oil_Gas`); `vault/plans/debt-047 temperature-sanity-check.md` (образец); выводы проб `vault/issues/debt-075/probes/*.out.txt`.
3. Worktree от базы (`/implement`): `git worktree add .worktrees/debt-075 -b refactor/debt-075/saturation-bounds-check numerical_scheme/implementation`.
4. Python — `numerical_solver/.venv/Scripts/python` основного каталога; в worktree pytest берёт код worktree (`pythonpath` в `pyproject.toml`), скрипты проб — только с `PYTHONPATH` на worktree (сверить напечатанный путь пакета).
5. Baseline из `numerical_solver/` worktree: `python -m pytest tests/ --collect-only -q` (ожидается 1996 на `3eee0d4`) и `python -m pytest tests/ -m "not slow" -q` (1720 passed, ~70 с). Если база ушла вперёд — числа сверить с `git log`, пересчитать ожидания (+18 тестов).
6. Шаг 1, затем шаг 2. После шага 1 — быстрый уровень, после шага 2 — `--collect-only`. Полный прогон — в конце.

## Связанные заметки

- [[DEBT-073]] — замер 2 (порог 0.98), план `debt-073 relperm-mobile-oil-edge`
- [[DEBT-047]] — проверка $T$, образец; заметка [[нефизичная температура доходила до истории молча — проверка T ловит грубые ошибки, остальное проверка ввода]]
- [[DEBT-048]] — память ступени 4 адаптера (довод за `RuntimeError`)
- [[BUG-020]] — порог 0.98 скопирован в ступень 4; [[BUG-014]] — нижняя граница $S_g$, метод отрицательных насыщенностей
- [[P8-формат-ввода-json]], [[модули-simulator-оркестратор]]
