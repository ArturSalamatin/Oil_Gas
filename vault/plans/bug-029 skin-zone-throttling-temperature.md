---
tags:
  - план
  - баг
date: 2026-10-15
issue: BUG-029
github: 120
branch: fix/bug-029/skin-zone-throttling-temperature
status: реализован
worktree: .worktrees/bug-029; удалён после влития
merged: fcbf274 (2026-10-15)
audit:
  date: 2026-10-15
  found: 4
  auto-fixed: 3
  manual-required: 1
---

# BUG-029: скин не входит в уравнение энергии — предупреждение пользователю

**Задача:** [[известные баги и технический долг#BUG-029]], issue [#120](https://github.com/ArturSalamatin/Oil_Gas/issues/120).

**Решение пользователя (2026-10-14, после открытия #120):** только вариант 1 issue — уведомить пользователя, что скин в тепловой модели не учитывается. Проба $\Delta T_s$ и варианты 2 (поправка вывода $T_{wf}$), 3 (вклад скин-перепада в схему) не делаются. Расчётный код не меняется.

## Кратко

- **Что не так.** Скин-фактор $s$ входит только в гидродинамику — сопротивлением забойной грани прототипа. В уравнении энергии забойная грань при добыче вклада не даёт: JT — с весом $\Phi^+_{1/2} = 0$ (`eq:QJT_disc`), перенос $R_s$ — без состава за гранью (`eq:mdot_disc`). Поэтому дросселирование и разгазирование на перепаде скин-зоны в $T$ не входят ни при каком $N$, и $T_{wf} = T[0]$ их не содержит. Постановка это фиксирует (`ssec:bc_disc`, абзац об источниковых членах на граничных гранях, последняя фраза о забое), но пользователь, задавший `numerics.skin` > 0, об этом не узнаёт: `load_config` при $0 < s \le 50$ молчит.
- **Что делается.**
  - `io/config.py`: новая функция `_warn_skin_not_in_energy` — предупреждение в журнале при $s > 0$, после `_validate`, рядом с `_warn_large_skin`. В сообщении — доля депрессии на скин-зоне в установившемся однофазном притоке $s/(\ln(R_{ext}/r_w) + s)$.
  - Комментарии: `NumericsConfig.skin`, `WellData.T_wf`.
  - Тесты `TestValidationWell`: один тест «$0 \le s \le 50$ без предупреждений» больше не верен — заменяется; два теста скина выше 50 уточняются (теперь два предупреждения).
  - vault: P8 §5, `json-config-schema.md`, заметка о температуре ячейки 0.
- **Численно побитово.** Во всех конфигах проекта $s = 0$ (33 JSON с полем `skin`, остальные — умолчание 0), расчётный код не меняется.
- **Не трогаются** `problem_statement.tex` и `energy/tridiag.py` — их правит [[DEBT-070]] (план готов, не реализован), см. раздел 8.
- **Шагов:** 5 (0 — подготовка, 4 — vault). Тестов: 1987 → 1989 на `a7b0dc0` и `758cab1` (после `a7b0dc0` — только vault) (`test_config.py` 317 → 319, `TestValidationWell` 22 → 24).
- **Аудит 1 (2026-10-15):** блоки «До/После» шагов 1–3 применены к копии дерева пробой `vault/issues/bug-029/probes/plan_check.py` (вывод `plan_check.out.txt`): каждое «До» найдено ровно один раз; шаг 1 — 7 failed / 17 passed (`test_config.py` — 7 / 312); шаг 2 — 24 passed, `test_config.py` 319 passed, `test_eq_references.py` 10 passed; шаг 3 — 329 passed; проба `warn_visible.py` плана — $s = 0$ молча, $s = 2$ — одно сообщение с 24.3 %, $s = 100$ — два (5.9 % притока, 94.1 % депрессии); новых строк длиннее 100 символов нет.

## Как начать работу по этому плану

1. Прочитай этот файл целиком.
2. Прочитай: запись [[известные баги и технический долг#BUG-029]]; [[P8-формат-ввода-json]] §5 («Скважина»); заметку [[температура ячейки 0 — центр, не забой]].
3. Worktree от базовой ветки (из корня проекта):
   ```powershell
   git worktree add .worktrees/bug-029 -b fix/bug-029/skin-zone-throttling-temperature numerical_scheme/implementation
   ```
4. Python — `numerical_solver/.venv/Scripts/python` основного каталога; pytest в worktree берёт пакет worktree. Скрипт пробы (шаг 3) — с `PYTHONPATH` на `numerical_solver/` worktree, проба печатает путь пакета.
5. Исходное состояние (из `numerical_solver/` worktree):
   ```powershell
   ..\..\..\numerical_solver\.venv\Scripts\python -m pytest tests/ --collect-only -q          # 1987 на a7b0dc0
   ..\..\..\numerical_solver\.venv\Scripts\python -m pytest tests/ -m "not slow" -q           # быстрый уровень
   ..\..\..\numerical_solver\.venv\Scripts\python -m pytest tests/test_config.py -q -k TestValidationWell   # 22 passed
   ```
   (путь к venv — от `.worktrees/bug-029/numerical_solver/`; при другой раскладке — абсолютный путь `D:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\.venv\Scripts\python`).
6. Шаги 1–4 по порядку. После каждого — проверка шага и регресс по полю «Регресс»; полный прогон — в конце (`/implement` §3.1).

## 1. Контекст

### 1.1. Цепочка

1. Конфиг: `numerics.skin` = $s \ge 0$ (`NumericsConfig.skin`, `numerical_solver/gpn_multiphase_solver/io/config.py:153`; $s < 0$ — отказ в `_validate`, `:559-578`, [[DEBT-056]]).
2. Фабрика передаёт $s$ прототипу: `factory.py:442`, `skin=nc.skin`. Прототип: проводимость забойной грани $T_w = 2\pi kh/(\ln(r_1/r_w) + s)$ (`HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/grid.py:20-21`, `well_transmissibility_m3`). Перепад $p[0] - p_{wf}$ включает перепад скин-зоны $\Delta p_s = (p[0] - p_{wf})\,s/(\ln(r_0/r_w) + s)$, от $N$ не зависящий.
3. Энергия (`energy/tridiag.py`): `compute_jt` (`:412-482`) — слагаемое грани 0 с весом `Phi_o_p[0]`, `Phi_g_p[0]`, при добыче ноль; `compute_degassing` (`:504-572`) — `Rs_left[0] = Rs[0]` (`:565`), вклад грани 0 ноль при любом знаке потока.
4. Вывод: `T_wf = state.T[0]` — `simulator.py:253` и `:457` (начальная запись); `WellData.T_wf` (`state.py:104`) → `io/output.py:59, 137` (`.npz`, CSV).
5. Пользователь: при $0 < s \le 50$ сообщений нет; при $s > 50$ — только о доле притока (`_warn_large_skin`, `:761-778`).

### 1.2. Воспроизведение

Ошибки в расчёте нет — есть молчание. Воспроизводит его существующий тест, который фиксирует молчание как норму:

```powershell
..\..\..\numerical_solver\.venv\Scripts\python -m pytest tests/test_config.py -q -k "test_skin_up_to_threshold_silent"
```
`numerical_solver/tests/test_config.py:923-933`: $s$ = 0, 5, 50 → `_warning_messages(caplog) == []` — 3 passed. После исправления $s = 5$ и $s = 50$ дают одно предупреждение; тест заменяется (шаг 1).

### 1.3. Как предупреждение доходит до пользователя

`load_config` вызывается до фабрики (`report/pipeline.py:95` — команда `run`; скрипты примеров — так же), а обработчик журнала ставит `setup_logging` в `SimulatorFactory` (`factory.py:45`). В свежем процессе обработчиков у `gpn_multiphase_solver` ещё нет, и запись уровня WARNING печатает резервный обработчик `logging` (`logging.lastResort`) в stderr — текст без префикса. Так работают предупреждения DEBT-056 и DEBT-008; новое идёт тем же путём. Проба шага 3 проверяет это в отдельном процессе.

## 2. Целевое состояние

- $s = 0$: ни отказа, ни предупреждений (все конфиги проекта).
- $0 < s \le 50$: одно предупреждение — скин учитывается только в гидродинамике, дросселирование и разгазирование на перепаде скин-зоны в температуру не входят, $T_{wf}$ их не содержит; доля депрессии на скин-зоне в установившемся однофазном притоке.
- $s > 50$: два предупреждения — о доле притока (DEBT-056, текст прежний) и о температуре.
- Конфиг с ошибкой в любом поле — отказ без предупреждений (как сейчас: предупреждения после `_validate`).
- Истории, графики, матрица энергии — побитово прежние.

## 3. Варианты

Все — в рамках решения пользователя (только уведомление).

| | Суть | Плюсы | Минусы | Решение |
|---|---|---|---|---|
| **А** | Отдельная функция `_warn_skin_not_in_energy` в `io/config.py`, вызов после `_warn_large_skin`; комментарии; P8 §5 и схема конфига | Одно предупреждение — один факт; текст DEBT-056 не меняется; место — там же, где прочие предупреждения о конфиге (P8 §5) | При $s > 50$ два сообщения о `numerics.skin` | ✅ |
| Б | Объединить с `_warn_large_skin` в одну `_warn_skin`: при $s > 0$ — абзац о температуре, при $s > 50$ — ещё абзац о притоке, одно сообщение | Одно сообщение на поле | Два несвязанных факта в одном тексте; переписывается функция и тексты DEBT-056, тесты DEBT-056 меняются сильнее | ❌ |
| В | Только документы (P8, README пакета, постановка), без предупреждения | Ноль кода | Пользователь конфига документ не читает — не уведомление | ❌ |
| Г | Предупреждение в фабрике или в `Simulator` (при первом интервале с добычей) | Можно не предупреждать, если добычи нет | Проверки скалярных полей конфига — в `load_config` (P8 §5), фабрика — для таблиц; при останове перепада скин-зоны нет, но скин и тогда не входит в энергию — условие «есть добыча» лишнее | ❌ |
| Д (аудит 1) | А + строка-напоминание в итоговой сводке команды `run` (`report/pipeline.py`, `_print_summary`, `:354-367`) рядом с «T(r_w) финал» при $s > 0$ | Напоминание там, где пользователь читает $T_{wf}$: предупреждение `load_config` печатается до строки «=== <заголовок> ===» и уходит вверх под журналом интервалов | Расширение: правка `report/pipeline.py` и тест сводки; сводка печатается `print`, а не журналом | ❌ (решение пользователя 2026-10-15: план как есть, только А) |

**Выбор: А.** Порог — строго $s > 0$: решение пользователя — уведомлять, что скин в тепловой модели не учитывается, при любом скине. Доля депрессии в тексте даёт пользователю порядок величины упущенного перепада без расчёта; формула та же, что в `_warn_large_skin` ($1 -$ доля притока).

**Почему не правится постановка.** Фраза есть: `ssec:bc_disc`, абзац «Источниковые члены на граничных гранях», конец пункта о забое («При скин-факторе $s > 0$ перепад $p_0 - p_{wf}$ включает перепад на скин-зоне; дросселирование и разгазирование на нём в температуру не входят ни при каком $N$»). Перенос или повтор её в абзаце о скине (после `eq:transmissibility`) — правка в том же разделе, который переписывает [[DEBT-070]] (обозначения граней и $p_0$, $T_0$; правки T26–T28 — тот же абзац о забое). Решение пользователя (2026-10-15): не повторять — раздел 9, п. 1.

## 4. Подводные камни (чеклист 2.6)

- ✅ **Побочные эффекты.** Новая функция вызывается только из `load_config`. Конфигов с $s > 0$ в проекте нет (grep `"skin"` по `numerical_solver/**/*.json`: 33 файла с полем, все 0.0, включая `deliverables/` и `tests/data/`; без поля — умолчание 0) → ни один пример, ни один тест на конфигах примеров предупреждения не получает. `examples/18_prototype_input/prototype_input.py:187` переносит `Well skin` книги прототипа в конфиг — в `INPUT_TEMPLATE.xlsx` и в новой `configs/INPUT_TEMPLATE_THERMAL_v1_14.10.2026.xlsx` (не в git) `Well skin` = 0.
- ⚠️ **Существующие тесты, которые меняются** (`numerical_solver/tests/test_config.py`, класс `TestValidationWell`):
  - `test_skin_up_to_threshold_silent` (`:923-933`, $s$ = 0, 5, 50 без предупреждений) — неверен по новому поведению; заменяется на `test_zero_skin_silent` и `test_positive_skin_warns_energy`;
  - `test_large_skin_warns` (`:935-944`, `len(msgs) == 1`) — теперь два сообщения;
  - `test_large_skin_warning_gives_inflow_ratio` (`:946-952`, `msgs[0]`) — по порядку вызова проходил бы, но сообщение выбирается по признаку, а не по индексу: порядок функций не должен решать исход;
  - `test_no_warning_before_error` (`:1004-1022`, $s$ = 1e3 + ошибка `max_retries`) — не меняется и теперь покрывает и новое предупреждение.
- ✅ **Граничные случаи.** $s = 0$ — без сообщения (строго $>$). $s$ = 1e300 (конечное, проходит DEBT-051): $\ln(R_{ext}/r_w) + s$ = 1e300, доля 100.0 %, переполнения нет — `np.exp` не используется. $s$ = 1e-12 — сообщение с долей 0.0 % (предупреждение формальное, но по решению пользователя — при любом $s > 0$).
- ✅ **Производительность.** Один раз при загрузке конфига.
- ✅ **Обратная совместимость.** Сигнатура `load_config` и `SimulationConfig` не меняются; расчёт побитово прежний.
- ✅ **Порядок вызовов.** После `_validate`: $r_w > 0$ и $R_{ext} > r_w$ проверены (`config.py:508-511`), логарифм положителен.
- ✅ **Состояние при ошибке.** Функция только пишет в журнал.
- ✅ **Численная устойчивость.** Не применимо.
- ⚠️ **Связь с задачами.** [[DEBT-070]] правит `problem_statement.tex` (`ssec:bc_disc`), докстринг `compute_jt` (`tridiag.py:427-431`, правка C1) и заметку о температуре ячейки 0 (строки 21, 36). BUG-029 эти места не трогает: в `tridiag.py` — ничего, в заметке — только строка 66. [[DEBT-071]] правит `prototype_adapter.py`, `factory.py`, тест с `caplog` на `configs/baseline.json` ($s = 0$ — новое предупреждение его не задевает). README пакета `numerical_solver/README.md` ([[FEAT-031]]) в git нет (на `a7b0dc0` — неотслеживаемый файл основного каталога) → строка `skin` там не правится этой задачей, см. раздел 9.
- ✅ **Import-цепочки.** Новых импортов нет: `np`, `user_log` в `io/config.py` уже есть.
- ✅ **Ссылки на уравнения** (`tests/test_eq_references.py`, DEBT-010, DEBT-062): в новых комментариях и докстринге — только метки (`eq:QJT_disc`, `eq:mdot_disc`, `ssec:bc_disc`), без номеров уравнений и строк `.tex`.
- ✅ **Прототип** не меняется.

## 5. Шаги

### Шаг 0: Подготовка

**Цель:** worktree, исходное число тестов, красный тест не нужен (воспроизведение — п. 1.2).
**Файлы:** —

**Что сделать:**
1. Worktree и ветка — «Как начать», п. 3. Проверить, что база содержит `numerical_solver/`: `git ls-tree numerical_scheme/implementation --name-only | Select-String numerical_solver`.
2. Исходное состояние — «Как начать», п. 5. Записать: число тестов (1987 на `a7b0dc0`; если база ушла — число на ней), итог быстрого уровня, `TestValidationWell` 22 passed.
3. Сверить строки плана с базой (инструмент Grep или из `numerical_solver/` worktree):
   ```powershell
   Select-String -Path gpn_multiphase_solver\io\config.py, gpn_multiphase_solver\state.py -Pattern "_warn_large_skin|skin: float|T_wf: float"
   Select-String -Path tests\test_config.py -Pattern "def test_skin_up_to_threshold_silent|def test_large_skin_warns|def test_large_skin_warning_gives_inflow_ratio"
   ```
   Ожидание: `config.py:153, 452, 761`, `state.py:104`; `test_config.py:926, 936, 946`. Если сдвинулись — работать по именам, номера в плане — ориентир.

**Проверка после шага:** числа записаны.
**Регресс:** быстрый (исходное состояние).
**Оценка:** ~5 минут.

### Шаг 1: Тесты нового поведения (красные)

**Цель:** тесты фиксируют: $s = 0$ — молча; $0 < s \le 50$ — одно предупреждение о температуре; $s > 50$ — два.
**Файлы:** `numerical_solver/tests/test_config.py`

**Контекст.** Тест пишется до реализации (CLAUDE.md, «Тестирование»). Сообщения различаются по признакам — фрагментам текста, которых нет в другом сообщении: у предупреждения DEBT-056 — «от притока без скина» (`config.py:776`), у нового — «В уравнении энергии его нет» (шаг 2).

**Что сделать:**

1. Докстринг модуля, строки 13–14:

   До:
   ```python
   - Скважина: skin ≥ 0 (отказ с обходом через r_well), предупреждения при skin > 50
     и при p_wf / min_bhp ≥ p0 в объекте истории (DEBT-056).
   ```
   После:
   ```python
   - Скважина: skin ≥ 0 (отказ с обходом через r_well), предупреждения при skin > 50
     и при p_wf / min_bhp ≥ p0 в объекте истории (DEBT-056); при skin > 0 —
     скин не входит в уравнение энергии (BUG-029).
   ```

2. После хелпера `_history_raw` (`:880-885`), перед `class TestValidationWell`, добавить признаки:
   ```python
   # Признаки двух предупреждений о скине — фрагменты, которых нет в другом
   # сообщении: доля притока при s > 50 (DEBT-056) и скин вне уравнения
   # энергии при s > 0 (BUG-029)
   _INFLOW = "от притока без скина"
   _ENERGY = "В уравнении энергии его нет"
   ```

3. Докстринг класса (`:889`):

   До:
   ```python
       """Скин ≥ 0; предупреждения при skin > 50 и при p_wf, min_bhp ≥ p0 (DEBT-056)."""
   ```
   После:
   ```python
       """Скин ≥ 0; предупреждения при skin > 0 (BUG-029), > 50 и p_wf, min_bhp ≥ p0 (DEBT-056)."""
   ```

4. Заменить `test_skin_up_to_threshold_silent` (`:923-933`, вместе с комментарием над ним) на три теста:

   До:
   ```python
       # 50 — граница: предупреждение строго при s > 50 (решение пользователя)
       @pytest.mark.parametrize("skin", [0.0, 5.0, 50.0],
                                ids=["zero", "damaged", "threshold"])
       def test_skin_up_to_threshold_silent(self, tmp_path, caplog, skin):
           """0 ≤ s ≤ 50 — без отказа и без предупреждения."""
           raw = _minimal_raw()
           raw["numerics"] = {"skin": skin}
           with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
               cfg = load_config(_write_json(tmp_path, raw))
           assert cfg.numerics.skin == skin
           assert _warning_messages(caplog) == []
   ```
   После:
   ```python
       def test_zero_skin_silent(self, tmp_path, caplog):
           """s = 0 (все конфиги проекта) — без отказа и без предупреждений."""
           raw = _minimal_raw()
           raw["numerics"] = {"skin": 0.0}
           with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
               cfg = load_config(_write_json(tmp_path, raw))
           assert cfg.numerics.skin == 0.0
           assert _warning_messages(caplog) == []

       # Скин входит только в гидродинамику (проводимость забойной грани); в
       # уравнении энергии забойная грань при добыче вклада не даёт (eq:QJT_disc,
       # eq:mdot_disc). Решение пользователя (BUG-029): предупреждать при любом
       # s > 0. О доле притока — строго при s > 50 (DEBT-056): здесь его нет
       @pytest.mark.parametrize("skin", [0.01, 5.0, 50.0],
                                ids=["small", "damaged", "threshold"])
       def test_positive_skin_warns_energy(self, tmp_path, caplog, skin):
           """0 < s ≤ 50 — одно предупреждение: скин не входит в уравнение энергии."""
           raw = _minimal_raw()
           raw["numerics"] = {"skin": skin}
           with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
               cfg = load_config(_write_json(tmp_path, raw))
           assert cfg.numerics.skin == skin
           msgs = _warning_messages(caplog)
           assert len(msgs) == 1
           assert _ENERGY in msgs[0]
           assert "numerics.skin" in msgs[0] and "T_wf" in msgs[0]

       # Установившийся однофазный приток: p_e − p_wf = qμ/(2πkh)·(ln(R_ext/r_w) + s),
       # из них qμ/(2πkh)·s — на скин-зоне; эта часть перепада в T не входит.
       # У _minimal_raw R_ext/r_w = 50/0.1 = 500, ln 500 = 6.2146
       def test_skin_energy_warning_gives_drawdown_share(self, tmp_path, caplog):
           """s = 2: доля депрессии на скин-зоне 2 / (ln 500 + 2) = 24.3 %."""
           raw = _minimal_raw()
           raw["numerics"] = {"skin": 2.0}
           with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
               load_config(_write_json(tmp_path, raw))
           energy = [m for m in _warning_messages(caplog) if _ENERGY in m]
           assert len(energy) == 1 and "24.3%" in energy[0]
   ```

5. `test_large_skin_warns` (`:935-944`):

   До:
   ```python
       @pytest.mark.parametrize("skin", [50.5, 1e3, 1e6], ids=["above", "1e3", "1e6"])
       def test_large_skin_warns(self, tmp_path, caplog, skin):
           """s > 50 — предупреждение с именем поля; расчёт допускается."""
           raw = _minimal_raw()
           raw["numerics"] = {"skin": skin}
           with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
               cfg = load_config(_write_json(tmp_path, raw))
           assert cfg.numerics.skin == skin
           msgs = _warning_messages(caplog)
           assert len(msgs) == 1 and "numerics.skin" in msgs[0]
   ```
   После:
   ```python
       @pytest.mark.parametrize("skin", [50.5, 1e3, 1e6], ids=["above", "1e3", "1e6"])
       def test_large_skin_warns(self, tmp_path, caplog, skin):
           """s > 50 — два предупреждения: о доле притока (DEBT-056) и о температуре (BUG-029)."""
           raw = _minimal_raw()
           raw["numerics"] = {"skin": skin}
           with caplog.at_level(logging.WARNING, logger="gpn_multiphase_solver"):
               cfg = load_config(_write_json(tmp_path, raw))
           assert cfg.numerics.skin == skin
           msgs = _warning_messages(caplog)
           # По одному каждого вида, оба называют поле
           assert len(msgs) == 2
           assert sum(_INFLOW in m for m in msgs) == 1
           assert sum(_ENERGY in m for m in msgs) == 1
           assert all("numerics.skin" in m for m in msgs)
   ```

6. `test_large_skin_warning_gives_inflow_ratio` (`:946-952`), последняя строка:

   До:
   ```python
           assert "0.6%" in _warning_messages(caplog)[0]
   ```
   После:
   ```python
           # Сообщение о притоке — по признаку, не по порядку: при s > 0 есть и второе
           inflow = [m for m in _warning_messages(caplog) if _INFLOW in m]
           assert len(inflow) == 1 and "0.6%" in inflow[0]
   ```

**Проверка после шага:**
- `..\..\..\numerical_solver\.venv\Scripts\python -m pytest tests/test_config.py -q -k TestValidationWell` → **7 failed, 17 passed** (24 теста). Падают: `test_positive_skin_warns_energy` ×3 (сообщений 0), `test_skin_energy_warning_gives_drawdown_share` (сообщения нет), `test_large_skin_warns` ×3 (сообщение одно). Проходят `test_zero_skin_silent`, `test_large_skin_warning_gives_inflow_ratio` и прежние.
- Иной состав красных — остановиться и разобрать (опечатка в признаке, порядок вызова).

**Регресс:** только `test_config.py` (остальные файлы не менялись) — `pytest tests/test_config.py -q` → 7 failed, 312 passed.
**Подводные камни:** раздел 4, «Существующие тесты».
**Зависимости:** Требует: шаг 0. Блокирует: шаг 2.
**Оценка:** ~60 строк, ~20 минут.

### Шаг 2: Предупреждение в `load_config`

**Цель:** при $s > 0$ `load_config` пишет в журнал, что скин не входит в уравнение энергии.
**Файлы:** `numerical_solver/gpn_multiphase_solver/io/config.py`

**Контекст.** Предупреждения о конфиге — после `_validate` (`:447-454`): конфиг с ошибкой в любом поле не даёт предупреждения перед отказом (DEBT-056, тест `test_no_warning_before_error`). Новая функция — рядом с `_warn_large_skin`, тем же образцом.

**Что сделать:**

1. `NumericsConfig.skin` (`:153`):

   До:
   ```python
       skin: float = 0.0                      # скин-фактор: ≥ 0, > 50 — предупреждение (DEBT-056)
   ```
   После:
   ```python
       # Скин-фактор: ≥ 0 (DEBT-056). Входит только в гидродинамику — сопротивлением
       # забойной грани; в уравнение энергии не входит (BUG-029). Предупреждения:
       # s > 0 — о температуре (BUG-029), s > 50 — о доле притока (DEBT-056)
       skin: float = 0.0
   ```
   (`_check_numeric_fields` выбирает поля по аннотации `float` — комментарий на это не влияет.)

2. `load_config` (`:452`):

   До:
   ```python
       _warn_large_skin(config)
   ```
   После:
   ```python
       _warn_large_skin(config)
       _warn_skin_not_in_energy(config)
   ```

3. После `_warn_large_skin` (конец — `:778`), перед `_warn_well_shut`, вставить:
   ```python
   def _warn_skin_not_in_energy(cfg: SimulationConfig) -> None:
       """Предупреждение при s > 0: скин не входит в уравнение энергии (BUG-029). Ур. (eq:QJT_disc)."""
       # Скин в модели — только сопротивление забойной грани в гидродинамике:
       # проводимость 2πkh/(ln(r_1/r_w) + s) (прототип, well_transmissibility_m3).
       # В уравнении энергии забойная грань при добыче вклада не даёт: JT — с весом
       # Φ⁺ = 0 (eq:QJT_disc), перенос R_s — без состава за гранью (eq:mdot_disc).
       # Поэтому JT-нагрев нефти, охлаждение газа и теплота разгазирования на
       # перепаде скин-зоны в T не входят ни при каком N, и T_wf = T[0] их не
       # содержит (ssec:bc_disc). Знак потери без расчёта не известен: на
       # полуячейке у забоя примера 12 JT (+0.033 К) и дегазация (−0.032 К) почти
       # гасят друг друга (BUG-015). Модель не меняется — только предупреждение
       # (решение пользователя, BUG-029).
       # Доля депрессии на скин-зоне в установившемся однофазном притоке:
       # p_e − p_wf = qμ/(2πkh)·(ln(R_ext/r_w) + s), из них qμ/(2πkh)·s — на скин-зоне.
       s = cfg.numerics.skin
       if s > 0:
           g = cfg.geometry
           ln_re_rw = np.log(g.R_ext / g.r_well)
           share = s / (ln_re_rw + s)
           user_log.warning(
               f"numerics.skin = {s} > 0: скин учитывается только в гидродинамике "
               f"(сопротивление забойной грани). В уравнении энергии его нет: "
               f"дросселирование (эффект Джоуля–Томсона) и разгазирование на перепаде "
               f"давления скин-зоны в температуру не входят, и температура забоя T_wf "
               f"их не содержит. В установившемся однофазном притоке на скин-зону "
               f"приходится {share:.1%} депрессии (s / (ln(R_ext/r_w) + s), "
               f"ln(R_ext/r_w) = {ln_re_rw:.3g}).")
   ```

   Доли для тестов и пробы (проверено на `a7b0dc0`, $R_{ext}/r_w = 500$): $s$ = 0.01 → 0.2 %, 2 → 24.3 %, 5 → 44.6 %, 50 → 88.9 %, 100 → 94.1 %, 1e3 → 99.4 %, 1e6 и 1e300 → 100.0 %.

**Проверка после шага:**
- `pytest tests/test_config.py -q -k TestValidationWell` → 24 passed.
- `pytest tests/test_eq_references.py -q` → passed (метки `eq:QJT_disc`, `eq:mdot_disc` объявлены в `problem_statement.tex`).

**Регресс:** быстрый.
**Подводные камни:** раздел 4 — граничные случаи, ссылки на уравнения.
**Зависимости:** Требует: шаг 1. Блокирует: шаг 3.
**Оценка:** ~35 строк, ~15 минут.

### Шаг 3: Комментарий `WellData.T_wf` и проба видимости

**Цель:** ограничение видно и там, где читают историю; предупреждение видно при обычном запуске, без `caplog`.
**Файлы:** `numerical_solver/gpn_multiphase_solver/state.py`; новый `vault/issues/bug-029/probes/warn_visible.py` (+ вывод `warn_visible.out.txt`, конфиги `baseline_skin*.json` — текстовые, в git).

**Что сделать:**

1. `state.py:104` — существующий хвостовой комментарий не трогать, строку комментария добавить над полем:

   До:
   ```python
       p_wf: float        # забойное давление, Па
       T_wf: float        # забойная температура, К: T[0] — центр r_0 ячейки 0 (BUG-015)
   ```
   После:
   ```python
       p_wf: float        # забойное давление, Па
       # При скине s > 0 T_wf не содержит дросселирования и разгазирования на
       # перепаде скин-зоны: скин входит только в гидродинамику (BUG-029)
       T_wf: float        # забойная температура, К: T[0] — центр r_0 ячейки 0 (BUG-015)
   ```

2. Проба `vault/issues/bug-029/probes/warn_visible.py`:
   ```python
   """BUG-029: предупреждение о скине видно при загрузке конфига в свежем процессе (без caplog)."""
   import json
   import os
   import subprocess
   import sys
   from pathlib import Path

   SOLVER = Path.cwd()  # запуск из numerical_solver/ worktree
   HERE = Path(__file__).resolve().parent
   base = json.loads((SOLVER / "configs" / "baseline.json").read_text(encoding="utf-8"))
   # Дочерний процесс пишет stderr в UTF-8 — кириллица сообщения без порчи
   env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
   out = []

   for s in (0.0, 2.0, 100.0):
       raw = {**base, "numerics": {**base.get("numerics", {}), "skin": s}}
       cfg = HERE / f"baseline_skin{s:g}.json"
       cfg.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
       # Свежий процесс: обработчиков журнала нет (setup_logging — в фабрике),
       # запись WARNING печатает резервный обработчик logging в stderr
       code = ("import gpn_multiphase_solver as g; print(g.__file__); "
               "from gpn_multiphase_solver.io.config import load_config; "
               f"load_config(r'{cfg}')")
       r = subprocess.run([sys.executable, "-c", code], capture_output=True,
                          text=True, encoding="utf-8", env=env, cwd=SOLVER)
       out += [f"--- skin = {s:g}: код возврата {r.returncode}",
               f"stdout: {r.stdout.strip()}",
               f"stderr: {r.stderr.strip() or '(пусто)'}"]

   # Вывод — файлом в UTF-8: конвейер PowerShell 5.1 портит кириллицу
   (HERE / "warn_visible.out.txt").write_text("\n".join(out) + "\n", encoding="utf-8")
   print(f"записано: {HERE / 'warn_visible.out.txt'}")
   ```
   Запуск из `numerical_solver/` worktree — одной командой (переменные окружения между вызовами инструмента не сохраняются):
   ```powershell
   $env:PYTHONPATH = (Get-Location).Path; ..\..\..\numerical_solver\.venv\Scripts\python ..\vault\issues\bug-029\probes\warn_visible.py
   ```
   Результат читать из `vault/issues/bug-029/probes/warn_visible.out.txt`.

**Проверка после шага:**
- Проба: `stdout` каждого случая — путь пакета **worktree** (`.worktrees\bug-029\numerical_solver\gpn_multiphase_solver\__init__.py`); иначе проба смотрит основной каталог — исправить `PYTHONPATH`.
- $s = 0$: код 0, stderr пуст. $s = 2$: код 0, в stderr одно сообщение с «В уравнении энергии его нет» и «24.3%». $s = 100$: код 0, два сообщения — о притоке («5.9% от притока без скина») и о температуре («94.1%»).
- `pytest tests/ -m "not slow" -q` — быстрый уровень, число тестов = исходное + 2.

**Регресс:** быстрый.
**Зависимости:** Требует: шаг 2. Блокирует: шаг 4.
**Оценка:** ~35 строк, ~15 минут.

### Шаг 4: vault

**Цель:** документы конфига и заметки говорят о предупреждении; задача закрыта в реестре.
**Файлы:**
- `vault/knowledge/decisions/P8-формат-ввода-json.md`
- `vault/knowledge/decisions/json-config-schema.md`
- `vault/knowledge/numerics/температура ячейки 0 — центр, не забой.md`
- `vault/roadmap/известные баги и технический долг.md` (BUG-029; заметка к FEAT-031 — `vault/roadmap/планируемые фичи.md`)
- `vault/issues/bug-029/05-comment-done.md`

**Что сделать:**

1. P8 §5, таблица «Кто проверяет» (`:220`), строка предупреждений `load_config`:
   - столбец «Где»: `предупреждения об удалённых полях, _warn_large_skin, _warn_skin_not_in_energy, _warn_well_shut (после _validate)`;
   - столбец «Что»: после «удалённые поля (DEBT-008);» добавить «`skin` > 0 — скин не входит в уравнение энергии ([[BUG-029]]);».
2. P8 §5, блок «Скважина» (`:246-249`): в заголовке блока добавить `_warn_skin_not_in_energy` к перечню предупреждений; после пункта «$s > 50$ — предупреждение…» добавить пункт:
   > - $s > 0$ — предупреждение: скин учитывается только в гидродинамике (сопротивление забойной грани), в уравнение энергии не входит — дросселирование и разгазирование на перепаде скин-зоны в $T$ не входят, $T_{wf}$ их не содержит (`ssec:bc_disc`; [[BUG-029]], решение пользователя — модель не меняется). В сообщении — доля депрессии на скин-зоне в установившемся однофазном притоке $s/(\ln(R_{ext}/r_w) + s)$ (у baseline при $s = 2$ — 24.3 %). При $s > 50$ — оба предупреждения (о притоке и о температуре)
3. `json-config-schema.md:176`, строка `skin, jacobian_mode, linear_solver`, столбец «Описание»: «Передаются прототипу; `skin` ≥ 0 входит только в гидродинамику (сопротивление забойной грани), в уравнение энергии — нет: при `skin` > 0 — предупреждение (BUG-029), при > 50 — о доле притока (DEBT-056)».
4. Заметка «температура ячейки 0 — центр, не забой», строка 66 (пункт о скине): дописать «Модель не меняется (решение пользователя): при $s > 0$ `load_config` предупреждает (`_warn_skin_not_in_energy`, [[BUG-029]]).» Строки 21 и 36 не трогать — их правит [[DEBT-070]].
5. Реестр, BUG-029: статус ✅ ИСПРАВЛЕНО (дата) с итогом (тесты до/после, проба, побитовость), поле **План** уже указывает на этот план.
6. Реестр фич, FEAT-031: заметка «README пакета (`numerical_solver/README.md`): в строке `numerics.skin` — "только гидродинамика; в температуре не учитывается, при $s > 0$ — предупреждение ([[BUG-029]])"» (README в git нет — правит FEAT-031).
7. `05-comment-done.md` — итог для issue #120 (пишет `/implement`).

**Проверка после шага:** `pytest tests/ --collect-only -q` — число как после шага 3 (шаг меняет только документы).
**Регресс:** число тестов.
**Зависимости:** Требует: шаг 3.
**Оценка:** ~20 строк, ~20 минут.

## 6. Тестовая стратегия

| Тест | Файл | Сценарий | Ожидание | Предотвращает |
|---|---|---|---|---|
| `test_zero_skin_silent` (новый) | `tests/test_config.py`, `TestValidationWell` | `_minimal_raw`, `numerics.skin` = 0 | `skin == 0`, предупреждений нет | ложное предупреждение во всех конфигах проекта |
| `test_positive_skin_warns_energy[small,damaged,threshold]` (новый) | там же | $s$ = 0.01, 5, 50 | ровно одно сообщение, с «В уравнении энергии его нет», `numerics.skin`, `T_wf`; сообщения о притоке нет | молчание при $0 < s \le 50$ (сам BUG-029); сдвиг порога DEBT-056 |
| `test_skin_energy_warning_gives_drawdown_share` (новый) | там же | $s = 2$, $R_{ext}/r_w = 500$ | в сообщении «24.3%» $= 2/(\ln 500 + 2)$ | неверная формула доли (обратная доля, $\ln$ не того отношения) |
| `test_large_skin_warns[above,1e3,1e6]` (изменён) | там же | $s$ = 50.5, 1e3, 1e6 | два сообщения: одно о притоке, одно о температуре, оба с `numerics.skin` | потеря одного из двух предупреждений; дубли |
| `test_large_skin_warning_gives_inflow_ratio` (изменён) | там же | $s$ = 1000 | сообщение о притоке — одно, с «0.6%» | зависимость от порядка вызова функций |
| `test_no_warning_before_error[skin_and_max_retries]` (без изменений) | там же | $s$ = 1e3 + `max_retries` = 25 | `ValueError` по `max_retries`, предупреждений нет — теперь и нового | предупреждение до отказа |
| `test_skin_up_to_threshold_silent[zero,damaged,threshold]` | там же | — | **удаляется**: фиксировал молчание при $0 < s \le 50$ — это и есть дефект | — |

Число тестов: −3 + 1 + 3 + 1 = **+2** (1987 → 1989 на `a7b0dc0`).

Проба `warn_visible.py` (шаг 3) — не тест: проверяет путь до пользователя (резервный обработчик `logging` в свежем процессе), который `caplog` обходит.

## 7. Критерии завершения

- [ ] `TestValidationWell`: 24 passed (шаг 1 — 7 failed / 17 passed, шаг 2 — 24 passed)
- [ ] Быстрый уровень после шагов 2 и 3 — зелёный, число = исходное + 2
- [ ] Полный прогон в конце (`/implement` §3.1) — зелёный, 1989 (или исходное + 2)
- [ ] Проба `warn_visible.py`: путь пакета — worktree; $s = 0$ — stderr пуст; $s = 2$ — одно сообщение с 24.3 %; $s = 100$ — два
- [ ] Истории примеров не менялись: во всех конфигах $s = 0$, расчётный код не тронут (`git diff --stat` ветки: `io/config.py`, `state.py`, `tests/test_config.py`, vault)
- [ ] `problem_statement.tex`, `energy/tridiag.py` не изменены (раздел 8)
- [ ] vault обновлён (шаг 4), issue #120 прокомментирован

## 8. Связь с задачами и порядок влития

| Задача | Состояние на `a7b0dc0` | Общие файлы с BUG-029 | Порядок |
|---|---|---|---|
| [[DEBT-070]] (#119) | план готов, не реализован | заметка «температура ячейки 0» — разные строки (21, 36 против 66) | любой; BUG-029 не трогает `problem_statement.tex` и `tridiag.py` именно поэтому |
| [[DEBT-071]] (#122) | план готов | нет (`factory.py`, `prototype_adapter.py`, прототип) | любой |
| [[FEAT-031]] | README пакета вне git | `numerical_solver/README.md` — строка `skin` | правит FEAT-031 (шаг 4, п. 6) |
| [[DEBT-056]] (#87) | влит | `_warn_large_skin`, `TestValidationWell` — основа этой задачи | — |
| [[BUG-015]] (#115) | влит | фраза о скин-зоне в постановке | — |

## 9. Новые проблемы и вопросы

1. **Фраза о скине в абзаце о скине `ssec:bc_disc`** (после формулы проводимости забойной грани со скином) — **решено 2026-10-15: не повторять**. Ограничение остаётся только в конце пункта о забое абзаца «Источниковые члены на граничных гранях» (BUG-015); `problem_statement.tex` задача не меняет.
2. **Напоминание в итоговой сводке `run`** (вариант Д, раздел 3; вопрос аудита 1) — **решено 2026-10-15: не делать**, план как есть (только предупреждение `load_config`). `report/pipeline.py` не меняется.
3. **README пакета** ([[FEAT-031]], вне git) — строка `skin` (≥ 0) без оговорки о температуре. Не новая задача: заметка в записи FEAT-031 (шаг 4, п. 6).

Новых записей реестра план не создаёт.

## Ссылки

[[известные баги и технический долг#BUG-029]], [[BUG-015]], [[DEBT-056]], [[DEBT-070]], [[DEBT-071]], [[FEAT-031]], [[P8-формат-ввода-json]], [[json-config-schema]], [[температура ячейки 0 — центр, не забой]], [[bug-015 well-face-jt-docs]], [[debt-056 skin-bhp-range-check]]; `numerical_solver/doc/problem_statement.tex` — `ssec:bc_disc`, `eq:QJT_disc`, `eq:mdot_disc`; issue [#120](https://github.com/ArturSalamatin/Oil_Gas/issues/120).
