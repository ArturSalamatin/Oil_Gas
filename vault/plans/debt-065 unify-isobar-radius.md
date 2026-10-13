---
tags:
  - план
  - рефакторинг
date: 2026-10-11
issue: DEBT-065
github: 106
branch: refactor/debt-065/unify-isobar-radius
status: реализован
worktree: .worktrees/debt-065; удалён после влития
merged: aff802a (2026-10-13)
audit:
  date: 2026-10-13
  found: 7
  auto-fixed: 7
  manual-required: 0
---

# DEBT-065: радиус изобары $p = p_b$ — одна функция `isobar_radius` с одним набором краевых случаев

Подтип: **рефакторинг** — три копии одной формулы сводятся в одну функцию. Поведение внутри сетки не меняется (побитово). Краевой случай «давление ниже $p_b$ во всех ячейках» меняется осознанно, по решению пользователя.

## 0. Решения пользователя (2026-10-11, при планировании)

1. **Давление ниже $p_b$ во всех ячейках** (изобара между последним центром и контуром, пример 11) — **узел контура $(R_{ext}, p_{ext})$**. Интерполяция между $(r_{N-1}, p_{N-1})$ и $(R_{ext}, p_{ext})$ по тем же правилам. NaN — только если $p_{ext} < p_b$ (изобары в области нет).
2. **Изобара между стенкой скважины и первым центром** ($p_{wf} < p_b \le p[0]$, $p[0]$ — давление в первой ячейке) — **NaN**: в ячейках газа нет. Узел $(r_w, p_{wf})$ не используется: при скине $S \ne 0$ $p_{wf}$ — давление за скином, а не давление пласта у стенки.
3. **Немонотонный профиль** (ячейки с $p < p_b$ не идут подряд от забоя) — **первое пересечение от забоя**: первый узел с $p \ge p_b$. На профиле, где ячейки с $p < p_b$ идут подряд, — тот же индекс, что у `np.searchsorted`, и то же значение побитово.

## 1. Сводка

- **Суть:** новая функция `isobar_radius(r, p, pb, R_ext, p_ext)` в `gpn_multiphase_solver/diagnostics/rs.py`. Через неё считают `rs.front_radius`, `two_phase.degassing_front["r_b_interp"]` и `closed_form.solve_closed["r_b"]`. Копия `closed_form._front_radius` удаляется, объяснение «почему не `np.interp`» остаётся в одном месте.
- **Числа:** внутри сетки — побитово как прежде (проба: 5 замкнутых профилей, 6 синтетических). Меняется только пример 11: печать `report_closed` и три рисунка (раздел 5.3).
- **Шагов:** 6 (0 — подготовка, 5 — итог).
- **Тесты:** +15 в новом `numerical_solver/tests/test_isobar_radius.py`, все быстрого уровня. Существующие не меняются.
- **Код:** ~35 строк новой функции (половина — комментарии), −30 строк копий, ~170 строк тестов, правки документов.
- **Прототип не меняется.**

## 2. Контекст

### 2.1. Что не так

Радиус изобары $p = p_b(R_{s,0})$ считали три функции одной формулой — интерполяция $\ln r$ по $p$ между соседними ячейками, индекс пары — `np.searchsorted(p, pb)`. На краях сетки ответы расходились:

| Функция (после DEBT-011) | Профиль | Газа в ячейках нет | Давление ниже $p_b$ во всех ячейках |
|---|---|---|---|
| `diagnostics/closed_form.py::_front_radius` | замкнутый | NaN | центр последней ячейки |
| `diagnostics/two_phase.py::degassing_front["r_b_interp"]` | численный, последняя запись | NaN | NaN |
| `diagnostics/rs.py::front_radius` | численный, последняя запись | NaN | NaN |

На примере 11 ($p_0 = 15.05$ МПа, $p_b = 15$ МПа, $N = 50$, $r_{N-1} = 46.9873$ м, $R_{ext} = 50$ м) расхождение есть на деле. Проба `vault/issues/debt-065/probes/edge_cases.py`, вывод — `edge_cases.txt`:
- на последней записи и у замкнутого профиля $p < p_b$ во всех 50 ячейках;
- `report_closed` печатает `фронт r_b = 46.9873 м (p = pb = 15.000 МПа)`, хотя давление там 14.983 МПа. Это центр последней ячейки; опорное значение — 47.7338 м (замкнутое решение на сетке из 20 001 узла до $R_{ext}$);
- на `rs_profiles.png` линии нет: `front_radius` вернул NaN.

Внутри сетки интерполяция по центрам точна: на сетке примера и на мелкой сетке r_b замкнутого решения отличаются на +0.01 % (03), +0.02 % (04) и +0.04 % (04a). Поэтому корень замкнутого решения без сетки (вариант 4 issue) не нужен.

### 2.2. Почему узел контура корректен

- Фабрика задаёт на контуре $p_{ext} = p_0$: `numerical_solver/gpn_multiphase_solver/factory.py`, строка с `p_ext=ic.p0` (на `4473cd4` — `:645`).
- Прототип ставит это давление на саму грань $R_{ext}$: проводимость последней полуячейки — `2*np.pi*kh/np.log(self.re_m/self.centers_m[-1])` (`numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/grid.py:17`). Так же — сетка GPN, по которой `fluxes.py` пересчитывает потоки для энергии: `_trans_ext = 2πkh/ln(R_ext/r_{N-1})` (`numerical_solver/gpn_multiphase_solver/grid/log_radial.py:79-82`). Другой гидродинамики, кроме `PrototypeHydroAdapter`, в пакете нет (сверено аудитом 1).
- Замкнутое решение интегрирует уравнение (2) от $(R_e, p_e)$, где $p_e = p_0$ (`diagnostics/closed_form.py`, `solve_closed`).

Значит, узел $(R_{ext}, p_0)$ — точка профиля, а не экстраполяция. На примере 11 с этим узлом (проба `vault/issues/debt-065/probes/isobar_new.py`, вывод — `isobar_new.txt`):

| Профиль | Было | Стало | Опорное |
|---|---|---|---|
| замкнутый | 46.9873 м (центр ячейки) | **47.7342 м** | 47.7338 м |
| численный, последняя запись | NaN | **47.7659 м** | — |

### 2.3. Почему не узел забоя

Проводимость забойной грани прототипа — `2πkh/(ln(r_0/r_w) + S)` (`grid.py:21`). При $S \ne 0$ $p_{wf}$ — давление за скином, и узел $(r_w, p_{wf})$ дал бы неверный радиус. Скин во всех 23 примерах равен 0, но функция будет в пакете. Край у забоя не встречается ни в одном примере: при останове $p_{wf} = p[0]$ (`numerical_solver/gpn_multiphase_solver/state.py`, комментарий к `HydroResult.p_wf`), у остальных пересечение лежит внутри сетки.

### 2.4. Где срабатывает краевой случай

Снимок вывода всех 23 примеров до DEBT-011 (`.worktrees/debt-011/vault/issues/debt-011/probes/out/snap_before.json`, разбор — проба `vault/issues/debt-065/probes/scan_snapshot.py`):

- **Численный профиль, последняя запись** (`report_rs`: «ячейки с газом», «ниже pb (недонасыщена)»). Давление ниже $p_b$ во всех ячейках — только у 11 (газ в 50 из 50). Газа нет ни в одной ячейке — у 16 (останов; $p_{wf} = p[0]$, решение 2 — NaN, как и прежде). У остальных пересечение внутри сетки; ячейки с $p < p_b$ идут подряд от забоя (замер аудита DEBT-026 на 18 примерах, включая 13b).
- **Замкнутый профиль** (`report_closed`, строка `фронт r_b = …`): центр последней ячейки — только у 11 (46.9873 м = $r_{N-1}$). Остальные — внутри сетки: 03 0.1971, 04 2.5937, 04a 1.4764, 05 0.2022, 06 2.4378, 07–09 2.5937, 10 3.5149, 12 и 13a 117.5764, 15 114.4784 м.

**Ожидаемое изменение вывода — только пример 11** (раздел 5.3).

### 2.5. Зависимость от DEBT-011

Функции переехали в `gpn_multiphase_solver/diagnostics/` в [[DEBT-011]] (#91). **DEBT-011 влита 2026-10-13** (`7f8d879`, vault `4dc9165`). Номера строк ниже записаны по её ветке на `4473cd4`; на базе `4dc9165` файлы `diagnostics/`, `grid_convergence.py` и `test_rs_analytics.py` с `4473cd4` не менялись, и все места правки шага 0.2 совпали строка в строку (сверено 2026-10-13). Шаг 0 всё равно сверяет их поиском: в базу могут прийти другие задачи.

## 3. Как начать работу по этому плану

1. Прочитай этот файл целиком.
2. Прочитай запись DEBT-065 в `vault/roadmap/известные баги и технический долг.md` и тело issue `vault/issues/debt-065/01-issue-body.md`.
3. **Предусловие — DEBT-011 влита** в `numerical_scheme/implementation` (шаг 0.1). Выполнено 2026-10-13: `7f8d879`.
4. Worktree по контракту `/implement`: `.worktrees/debt-065`, ветка `refactor/debt-065/unify-isobar-radius` от `numerical_scheme/implementation`. Ниже `<W>` — корень worktree, `<M>` — основной каталог `D:\Lessons\Grants\2026\GPN\Oil_Gas`.
5. Python — из основного каталога (в worktree `.venv` нет):
   ```powershell
   $PY = "D:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\.venv\Scripts\python.exe"
   cd <W>\numerical_solver
   ```
   pytest берёт пакет worktree сам (`pythonpath` в `pyproject.toml`). Скрипты вне pytest без `PYTHONPATH` берут пакет **основного каталога**. Проба снимка (шаги 0 и 5) ставит `PYTHONPATH` сама и проверяет путь пакета.
6. Базовый вариант:
   ```powershell
   & $PY -m pytest tests/ --collect-only -q          # N0 — всего тестов
   & $PY -m pytest tests/ -m "not slow" -q           # N0f — быстрый уровень, время
   ```
   Записать N0, N0f и время. Ориентир: **1826 на `4dc9165`** (база после влития DEBT-011, сверено 2026-10-13; ветка DEBT-011 отходила от базы до DEBT-054, отсюда 1799 на ветке + 27 тестов DEBT-054). Если в базу пришли другие задачи (BUG-025, FEAT-032 добавляют тесты), число будет больше — критерий плана считается от N0, а не от константы.
7. Условия сравнения снимков — шаг 0.4, снимок «до» — шаг 0.5. Затем шаг 1. После каждого шага — тест шага и регресс по полю «Регресс».

## 4. Шаги

### Шаг 0: подготовка — предусловие, сверка строк, снимок «до»

**Цель:** убедиться, что DEBT-011 влита и функции лежат там, где их ждёт план; снять эталон вывода примеров на неизменённом коде.

**Файлы:** `vault/issues/debt-011/probes/snapshot_examples.py` (в базе с DEBT-011, не меняется).

**Что сделать:**
1. Предусловие:
   ```powershell
   git log --oneline numerical_scheme/implementation | Select-String "DEBT-011"
   ```
   Должен быть merge-коммит DEBT-011. Нет — стоп.
2. Сверить места правки (номера строк плана — на `4473cd4`):
   ```powershell
   cd <W>\numerical_solver
   git grep -n -P "def (front_radius|degassed_cells|degassing_front|_front_radius|solve_closed)\b|_front_radius\(|np\.searchsorted\(p, pb\)|^from \.closed_form|^from \.rs" -- gpn_multiphase_solver/diagnostics
   git grep -n -E "front_radius|degassing_front|_front_radius|isobar_radius" -- examples tests ../vault/knowledge
   ```
   Ожидание первой команды на `4473cd4`:
   - `rs.py:118` `degassed_cells`, `:125` `front_radius`, `:141` `searchsorted`;
   - `two_phase.py:89` `from .closed_form import kr_max_Sg`, `:211` `degassing_front`, `:229` `searchsorted`;
   - `closed_form.py:176` `solve_closed`, `:228` вызов `_front_radius(`, `:235` `def _front_radius`, `:244` `searchsorted`.

   Ожидание второй: вызовы `front_radius` — `examples/rs_analytics.py` (в `_draw_rs`) и `examples/04_table_table/grid_convergence.py`; `degassing_front` — `examples/two_phase_analytics.py`, `examples/03_standing_corey/main.py`, `examples/05_standing_table_rp/main.py`; `_front_radius` — только `vault/knowledge/numerics/порог-подвижности-Кори-портит-обусловленность-замыкания.md:62`; `isobar_radius` — нигде.

   Ключ `-P` (регулярные выражения Perl) — потому что в шаблоне `\b`: с `-E` git его не поддерживает. Сдвиг строк — не повод останавливаться, править по именам. Новый вызов или изменённое тело функции — сверить шаги 2–3 с кодом заново.
3. Базовые числа (раздел 3, п. 6).
4. Два условия чистого сравнения снимков (найдено аудитом 1):
   - **Пример 18 пишет время выполнения прототипа** в `output/prototype/results.xlsx`, `run_summary.json`, `run_summary.txt`, `summary.json`. Эти файлы различаются от прогона к прогону при одном и том же коде. DEBT-011 исправила это в пробе — множество `TIME_FILES`, `compare` их пропускает; исправление вошло в базу с влитием DEBT-011 (`snapshot_examples.py:48` на `4dc9165`). Проверить, что оно на месте:
     ```powershell
     git grep -n "TIME_FILES" -- vault/issues/debt-011/probes/snapshot_examples.py
     ```
     Есть — ничего не делать. Нет — в шаге 5 четыре файла 18 будут «содержимое»: это не дефект, на остальные файлы 18 и его печать правило «только 11» действует.
   - **Прототип для снимка берётся из основного каталога.** Скрипты примеров видят пакет worktree через `PYTHONPATH`, который ставит проба. Но `radial_blackoil` установлен в venv из `<M>\numerical_solver\HydroSolverPrototype\Prototype_1.0.3` (editable). Если между снимками «до» и «после» основной каталог перейдёт на другой коммит с правкой прототипа (параллельные задачи: BUG-025 меняет допуск Ньютона прототипа), разойдутся все примеры. Записать:
     ```powershell
     git -C <M> rev-parse HEAD                       # P0 — коммит основного каталога при снимке «до»
     git -C <M> status --short -- numerical_solver/HydroSolverPrototype   # пусто
     ```
5. Снимок «до» (в фоне, ~20 мин):
   ```powershell
   New-Item -ItemType Directory -Force <W>\vault\issues\debt-065\probes\out
   & $PY <W>\vault\issues\debt-011\probes\snapshot_examples.py snap --tree <W>\numerical_solver --out <W>\vault\issues\debt-065\probes\out\snap_before.json
   ```
   Проба печатает путь пакета, он должен лежать под `<W>`; иначе проба остановится сама. Все 23 примера — «код 0». Файлы `probes/out/` не коммитить.

   ⚠️ Снимок запускает `main.py` из `<W>\numerical_solver\examples` с пакетом worktree, каждый пример — отдельным процессом, который импортирует пакет заново. **Пакет (`gpn_multiphase_solver/`) не трогать, пока в выводе пробы нет строки `снимок: …`.** Иначе пример, стартовавший после правки, снимется уже с ней, а запущенный в момент записи файла может упасть на импорте. Пока снимок идёт, можно писать новый файл тестов шага 1 (`tests/` снимок не читает).

**Проверка:** предусловие выполнено; места правки найдены; N0, N0f записаны; наличие `TIME_FILES` и коммит P0 записаны; `snap_before.json` есть, коды возврата 0.

**Подводные камни:** если в ветку позже вливается новая база — снимок «до» снять заново на ней. Иначе сравнение в шаге 5 покажет чужие изменения.

**Зависимости:** блокирует все шаги (файл тестов шага 1 можно писать параллельно со снимком, правку пакета — нет).

**Оценка:** ~25 мин (из них ~20 — снимок в фоне).

---

### Шаг 1: `isobar_radius` в `diagnostics/rs.py` + тесты краёв

**Цель:** одна функция радиуса изобары с краевыми случаями из раздела 0; вызовов ещё нет, вывод не меняется.

**Файлы:**
- `numerical_solver/gpn_multiphase_solver/diagnostics/rs.py` — новая функция между `degassed_cells` (`:118-122`) и `front_radius` (`:125`);
- `numerical_solver/tests/test_isobar_radius.py` — новый.

**Контекст.** `rs.py` — модуль «равновесие $R_s$ без кинетики, радиус изобары $p_b$» (докстринг `diagnostics/__init__.py`; заметка `архитектура библиотеки numerical_solver.md`: `rs.py — Равновесие R_s, радиус изобары p_b`). Модуль импортирует только `numpy`, поэтому `closed_form` и `two_phase` могут импортировать из него без цикла (`two_phase` уже импортирует из `closed_form`; `closed_form` — ни из кого).

Почему условие «первый узел с $p \ge p_b$» даёт тот же индекс, что `np.searchsorted(p, pb)`. `searchsorted` с `side='left'` — двоичный поиск, который сравнивает только `a[mid] < v`. Если ячейки с $p < p_b$ идут подряд от забоя, предикат `p < pb` имеет вид «True…True False…False», и двоичный поиск находит ту же границу, что и линейный, даже на неупорядоченном массиве. Значения $p$, $r$ в формуле те же, порядок операций тот же, поэтому результат совпадает побитово. Проба `isobar_new.py`: 5 замкнутых профилей (03, 04, 04a, 10, 12) и 5 синтетических — побитово.

**Что сделать:**
1. В `rs.py` после `degassed_cells` вставить:

```python
def isobar_radius(r, p, pb, R_ext, p_ext):
    """Радиус изобары p = pb: интерполяция ln r по p в центрах ячеек и на контуре (R_ext, p_ext)."""
    # Узлы — центры ячеек и грань контура R_ext. На контуре давление задано
    # условием Дирихле на самой грани: фабрика ставит p_ext = p0, проводимость
    # последней полуячейки 2πkh/ln(R_ext/r_{N-1}) (radial_blackoil/grid.py).
    # Поэтому изобара между последним центром и контуром (давление ниже pb во
    # всех ячейках, пример 11) находится той же интерполяцией, а не центром
    # последней ячейки (DEBT-065).
    #
    # Забой узлом не служит: при скине S != 0 p_wf — давление за скином, а не
    # давление пласта у стенки. Изобару между r_w и первым центром ячейки не
    # разрешают: nan, как «газа в ячейках нет».
    r_n = np.append(np.asarray(r, float), float(R_ext))
    p_n = np.append(np.asarray(p, float), float(p_ext))

    # Первый узел с p >= pb, считая от забоя. Если ячейки с p < pb идут подряд
    # от забоя, это тот же индекс, что np.searchsorted(p, pb) прежнего кода,
    # и то же значение побитово. На немонотонном профиле — граница зоны
    # p < pb, примыкающей к скважине: двоичный поиск searchsorted попал бы в
    # произвольное пересечение.
    above = np.flatnonzero(p_n >= pb)
    if above.size == 0:
        return np.nan            # p_ext < pb: разгазирована вся область, изобары в ней нет
    j = int(above[0])
    if j == 0:
        return np.nan            # p[0] >= pb: газа в ячейках нет
    if j == r_n.size - 1 and not r_n[-2] < r_n[-1]:
        raise ValueError(
            f"узел контура R_ext = {R_ext} м не дальше последнего центра "
            f"r[-1] = {r_n[-2]} м: сетка задана не для этого контура")

    # Интерполяция ln r, а не r: профиль логарифмичен. np.interp здесь не
    # годится: он требует возрастающих узлов, а p и ln r монотонны в
    # противоположные стороны — молча вернул бы мусор.
    w = (pb - p_n[j - 1]) / (p_n[j] - p_n[j - 1])
    return float(np.exp(np.log(r_n[j - 1]) + w * (np.log(r_n[j]) - np.log(r_n[j - 1]))))
```

   Проверка `R_ext > r[-1]` стоит только на ветке узла контура. Синтетическая сетка `tests/test_rs_analytics.py` (`R = np.geomspace(0.1, 100.0, 6)` при $R_{ext} = 50$ м примера 04) шире контура, но её профили до этой ветки не доходят: у всех пересечение внутри сетки или газа нет. Безусловная проверка уронила бы четыре теста рисунка.

2. Создать `numerical_solver/tests/test_isobar_radius.py` с одиннадцатью тестами функции (с учётом параметризации; тесты мест вызова — в шагах 2 и 3):

```python
"""Радиус изобары p = pb: одна функция diagnostics.rs.isobar_radius и три места вызова (DEBT-065).

Изобару считали три функции — rs.front_radius, two_phase.degassing_front и
closed_form._front_radius — одной формулой с разными краевыми случаями.
Теперь функция одна; края (решения пользователя 2026-10-11):
  * давление ниже pb во всех ячейках — изобара между последним центром и
    контуром, узел (R_ext, p_ext): на контуре задано p = p_ext (Дирихле);
  * pb не выше давления в первой ячейке — nan: ячейки изобару между r_w и
    первым центром не разрешают, а p_wf при скине — давление за скином;
  * профиль немонотонен — первое пересечение от забоя.
Расчёта нет, кроме замкнутого решения примера 11 (~2 с) — быстрый уровень.
"""

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from gpn_multiphase_solver.diagnostics.rs import isobar_radius

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
MPA = 1e6
PB = 15.0 * MPA                     # pb синтетики, Па
R_EXT, P_EXT = 50.0, 20.0 * MPA     # контур синтетики — как у примера 04
R = np.geomspace(0.1, 45.0, 6)      # центры ячеек синтетики, м; R[-1] = 45 < R_EXT


def _r_log(r1, p1, r2, p2, pb):
    """Интерполяция ln r по p между узлами (r1, p1), (r2, p2) — ожидаемое значение."""
    w = (pb - p1) / (p2 - p1)
    return float(np.exp(np.log(r1) + w * (np.log(r2) - np.log(r1))))


# ── isobar_radius на синтетических профилях ──

@pytest.mark.parametrize("p_mpa, j", [
    ([14, 16, 17, 18, 19, 19.5], 1),       # первая пара ячеек 0–1 (тест краёв из реестра)
    ([10, 12, 14, 16, 18, 19.5], 3),       # середина, пара 2–3
    ([10, 11, 12, 13, 14, 16.0], 5),       # последняя пара 4–5, узел контура не нужен
])
def test_crossing_between_neighbour_cells(p_mpa, j):
    """Пересечение внутри сетки — между ячейками j-1 и j; значение побитово прежнее."""
    p = np.array(p_mpa, float) * MPA
    # Та же формула, те же числа: прежние три функции давали ровно это значение.
    assert isobar_radius(R, p, PB, R_EXT, P_EXT) == _r_log(R[j - 1], p[j - 1], R[j], p[j], PB)


def test_logarithmic_profile_is_exact():
    """На профиле p = a + b·ln r интерполяция по ln r точна — внутри сетки и до контура."""
    a, b = 14.0 * MPA, 0.5 * MPA
    p = a + b * np.log(R)
    p_ext = a + b * np.log(R_EXT)
    # 2.7 м — между центрами; 48 м — между последним центром (45 м) и контуром (50 м).
    for r_star in (2.7, 48.0):
        pb = a + b * np.log(r_star)
        assert isobar_radius(R, p, pb, R_EXT, p_ext) == pytest.approx(r_star, rel=1e-12)


def test_gas_to_contour_uses_contour_node():
    """Давление ниже pb во всех ячейках (как в примере 11): изобара между последним центром и контуром.

    Прежде: rs.front_radius и degassing_front — nan, closed_form._front_radius —
    центр последней ячейки R[-1]. Теперь — интерполяция до узла (R_EXT, P_EXT).
    """
    p = np.array([10, 11, 12, 13, 14, 14.5]) * MPA
    r_b = isobar_radius(R, p, PB, R_EXT, P_EXT)
    assert R[-1] < r_b < R_EXT
    assert r_b == _r_log(R[-1], p[-1], R_EXT, P_EXT, PB)


def test_contour_below_pb_is_nan():
    """p_ext < pb: разгазирована вся область вместе с контуром — изобары в области нет."""
    p = np.array([10, 11, 12, 13, 14, 14.5]) * MPA
    assert np.isnan(isobar_radius(R, p, PB, R_EXT, 14.8 * MPA))


@pytest.mark.parametrize("p0_mpa", [15.0, 15.5])
def test_no_cell_below_pb_is_nan(p0_mpa):
    """pb не выше давления в первой ячейке — nan.

    Изобара, если есть, лежит между r_w и первым центром: ячейки её не
    разрешают, а узел (r_w, p_wf) не используется — при скине p_wf —
    давление за скином. 15.0 — граница: p[0] = pb ровно, газа в ячейке нет
    (прежние три функции давали nan и здесь).
    """
    p = np.array([p0_mpa, 16, 17, 18, 19, 19.5]) * MPA
    assert np.isnan(isobar_radius(R, p, PB, R_EXT, P_EXT))


def test_nonmonotone_profile_takes_first_crossing_from_well():
    """Немонотонный профиль: граница зоны p < pb, примыкающей к скважине (ячейки 0–1).

    np.searchsorted прежнего кода дал бы здесь пару 3–4: двоичный поиск на
    неупорядоченном массиве попадает в произвольное пересечение.
    """
    p = np.array([10, 16, 14, 14.5, 18, 19.5]) * MPA
    assert isobar_radius(R, p, PB, R_EXT, P_EXT) == _r_log(R[0], p[0], R[1], p[1], PB)


def test_cell_at_pb_returns_its_center():
    """p = pb точно в ячейке 2: радиус — её центр (вес w = 1)."""
    p = np.array([10, 12, 15, 16, 18, 19.5]) * MPA
    assert isobar_radius(R, p, PB, R_EXT, P_EXT) == pytest.approx(R[2], rel=1e-15)


def test_contour_node_not_beyond_grid_raises():
    """R_ext не дальше последнего центра — сетка не от этого контура: ошибка, а не мусор."""
    p = np.array([10, 11, 12, 13, 14, 14.5]) * MPA
    with pytest.raises(ValueError, match="узел контура"):
        isobar_radius(R, p, PB, 40.0, P_EXT)
```

   Импорты `Path`, `SimpleNamespace`, `EXAMPLES` понадобятся в шагах 2–3. Если линтер на шаге 1 ругается на неиспользуемые — добавить их в шаге 2.

**Проверка после шага:**
- `& $PY -m pytest tests/test_isobar_radius.py -q` — 11 passed.
- Регресс: быстрый — N0f + 11 passed.

**Подводные камни:**
- `test_crossing_between_neighbour_cells` и `test_gas_to_contour_uses_contour_node` сравнивают на точное равенство. Если падают на последнем бите, значит формула в функции записана не так, как в `_r_log` (порядок операций). Привести к виду из плана: побитовое совпадение со старым кодом — критерий раздела 5.3.
- `pytest.approx(R[2], rel=1e-15)` в `test_cell_at_pb_returns_its_center`: при $w = 1$ результат $\exp(\ln r_1 + (\ln r_2 - \ln r_1))$ может отличаться от $r_2$ на 1–2 ULP. При падении ослабить до `rel=1e-14`.

**Зависимости:** требует шаг 0 целиком (правка `rs.py` — после конца снимка «до»); блокирует шаги 2, 3.

**Оценка:** ~90 строк (функция ~35, тесты ~120 со вступлением), ~20 мин.

---

### Шаг 2: численный профиль — `rs.front_radius` и `two_phase.degassing_front` через `isobar_radius`

**Цель:** обе функции численного профиля дают одно число, включая края.

**Файлы:**
- `numerical_solver/gpn_multiphase_solver/diagnostics/rs.py` — `front_radius` (`:125-145`);
- `numerical_solver/gpn_multiphase_solver/diagnostics/two_phase.py` — импорт (`:89`), комментарий `dupuit_check` (`:195`), `degassing_front` (`:211-251`);
- `numerical_solver/tests/test_isobar_radius.py` — +3 теста.

**Контекст.** `front_radius` рисует линию на `rs_profiles.png` (`examples/rs_analytics.py`, `_draw_rs`) и печатает столбец в `examples/04_table_table/grid_convergence.py`. `degassing_front` нужен пункту C отчёта `examples/two_phase_analytics.py::report` (примеры 03, 04, 05) и линии фронта на рисунке $T$ у 03 и 05 (`main.py`). Сигнатуры не меняются. Давление на контуре берётся из `config.initial_conditions.p0` — так его задаёт фабрика (`factory.py`, `p_ext=ic.p0`). На то же допущение опирается `diagnostics/temperature.py` (докстринг: «Если ГУ по давлению когда-нибудь отделят от начального давления…»).

**Что сделать:**
1. `rs.py`, `front_radius`.

   До (`:125-145`):
   ```python
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
       _below, pb = degassed_cells(config, history, pvt)

       j = int(np.searchsorted(p, pb))          # p возрастает с ростом r
       if not (0 < j < len(p)):
           return np.nan
       w = (pb - p[j - 1]) / (p[j] - p[j - 1])
       return float(np.exp(np.log(r[j - 1]) + w * (np.log(r[j]) - np.log(r[j - 1]))))
   ```
   После:
   ```python
   def front_radius(config, history, grid, pvt):
       """Радиус изобары p = pb (фронта разгазирования при падающем давлении).

       Брать центр последней ячейки с p < pb нельзя: фронт лежит ВНУТРИ ячейки,
       и такая оценка систематически занижает r_b. На логарифмической сетке
       ячейки к периферии широкие, и при фронте в несколько метров занижение
       доходит до ~10 %. Интерполяция ln r по p и краевые случаи — isobar_radius.
       """
       _below, pb = degassed_cells(config, history, pvt)
       # Давление на контуре — p0: фабрика задаёт p_ext = ic.p0 (factory.py).
       return isobar_radius(grid.r_centers, history.states[-1].p, pb,
                            config.geometry.R_ext, config.initial_conditions.p0)
   ```

2. `two_phase.py`, импорт. После `from .closed_form import kr_max_Sg` (`:89`):
   ```python
   from .rs import isobar_radius
   ```

3. `two_phase.py`, `degassing_front`. Докстринг: `r_b_interp (интерполяция численного профиля)` → `r_b_interp (радиус изобары численного профиля, rs.isobar_radius)`. Тело (`:224-233`).

   До:
   ```python
       # Интерполяция r(p = pb): ищем пару соседних ячеек, между которыми
       # давление пересекает pb, и интерполируем линейно по ln r (профиль
       # логарифмичен). np.interp здесь не годится: он требует возрастающие
       # узлы, а p и ln r монотонны в противоположные стороны.
       r_b_interp = np.nan
       j = int(np.searchsorted(p, pb))          # p возрастает с ростом r
       if 0 < j < len(p):
           w = (pb - p[j - 1]) / (p[j] - p[j - 1])
           r_b_interp = float(np.exp(np.log(r[j - 1])
                                     + w * (np.log(r[j]) - np.log(r[j - 1]))))
   ```
   После:
   ```python
       # Радиус изобары — общая функция с rs.front_radius и замкнутым решением
       # (DEBT-065): интерполяция ln r по p; если давление ниже pb во всех
       # ячейках — до контура, где p = p0 (factory.py: p_ext = ic.p0).
       r_b_interp = isobar_radius(r, p, pb, config.geometry.R_ext,
                                  config.initial_conditions.p0)
   ```
   Переменная `r` нужна ниже (`r_b_formula`) — не удалять.

4. `two_phase.py`, `dupuit_check`, комментарий `:195`. Сейчас: `# Профиль Дюпюи, привязанный к самой дальней ячейке (там ГУ Дирихле)`. Это неточно: условие Дирихле стоит на грани $R_{ext}$, а не в ячейке (раздел 2.2). Заменить на `# Профиль Дюпюи, привязанный к самой дальней однофазной ячейке (ближайшей к контуру, где задано p = p0)`. Код не меняется.

5. `tests/test_isobar_radius.py` — дописать после тестов шага 1:

```python
# ── Численный профиль: rs.front_radius и two_phase.degassing_front — одно число ──

def _case04():
    """(config, pvt) примера 04 без расчёта: pb = 15 МПа, R_ext = 50 м, p0 = 20 МПа."""
    from gpn_multiphase_solver.factory import create_pvt
    from gpn_multiphase_solver.io.config import load_config
    cfg = load_config(EXAMPLES / "04_table_table" / "config.json")
    return cfg, create_pvt(cfg)


def _history(p_mpa):
    """История из одного состояния: газ (Sg = 0.1) в ячейках с p < 15 МПа.

    hydro_results — для dupuit_check внутри degassing_front: G_o — потоки
    нефти через грани [N+1], < 0 (к скважине, конвенция знаков).
    """
    from gpn_multiphase_solver.state import SimulationState
    p = np.asarray(p_mpa, float) * MPA
    gas = p < PB
    st = SimulationState(p=p, Sg=np.where(gas, 0.1, 0.0), Rs=np.full(p.size, 30.0),
                         T=np.full(p.size, 350.0), regime=np.where(gas, 1, 2), t=0.0)
    hr = SimpleNamespace(G_o=np.full(p.size + 1, -1e-5))
    return SimpleNamespace(states=[st], hydro_results=[hr])


@pytest.mark.parametrize("p_mpa", [
    [10, 12, 14, 16, 18, 19.5],      # пересечение внутри сетки
    [10, 11, 12, 13, 14, 14.5],      # газ до контура: прежде nan у обеих
    [15.5, 16, 17, 18, 19, 19.5],    # газа в ячейках нет: nan
])
def test_numeric_profile_functions_agree(p_mpa):
    """rs.front_radius и degassing_front['r_b_interp'] — одно число, равное isobar_radius."""
    from gpn_multiphase_solver.diagnostics.rs import front_radius
    from gpn_multiphase_solver.diagnostics.two_phase import degassing_front
    cfg, pvt = _case04()
    pb = float(pvt.pb(np.array([cfg.initial_conditions.Rs0]))[0])
    hist = _history(p_mpa)
    grid = SimpleNamespace(r_centers=R)
    expected = isobar_radius(R, np.asarray(p_mpa, float) * MPA, pb,
                             cfg.geometry.R_ext, cfg.initial_conditions.p0)
    # assert_equal считает nan равным nan
    np.testing.assert_equal(front_radius(cfg, hist, grid, pvt), expected)
    np.testing.assert_equal(degassing_front(hist, grid, cfg, pvt)["r_b_interp"], expected)
```

   Импорты внутри функций — по образцу `tests/test_examples.py` (там `from gpn_multiphase_solver.diagnostics.closed_form import solve_closed` внутри тестов). Можно поднять их в начало файла, если так короче. Тогда `from pathlib import Path` и `SimpleNamespace` из шага 1 уже используются.

**Проверка после шага:**
- `& $PY -m pytest tests/test_isobar_radius.py tests/test_rs_analytics.py -q` — 14 + все тесты `test_rs_analytics.py` passed. Тесты рисунка (`test_overlay_*`) должны пройти без правок: их профили не доходят до ветки узла контура.
- Регресс: быстрый — N0f + 14 passed.

**Подводные камни:**
- `dupuit_check` (зовётся из `degassing_front`) читает `history.hydro_results[-1]` ещё до проверки числа однофазных ячеек. Поэтому `hydro_results` в синтетической истории обязателен. При ≥ 3 однофазных ячейках он берёт `hr.G_o[-1]`.
- `pvt.pb` таблицы примера 04 при $R_{s,0} = 30$ — ровно 15 МПа (README 04). Тест всё равно берёт `pb` из PVT, а не константу `PB`.
- Сигнатуры `front_radius(config, history, grid, pvt)` и `degassing_front(history, grid, config, pvt)` не меняются: вызовы в `examples/` не трогаем.

**Зависимости:** требует шаг 1 и конец снимка «до» (шаг 0.5); блокирует шаг 5.

**Оценка:** ~25 строк кода, ~45 строк тестов, ~20 мин.

---

### Шаг 3: замкнутое решение — `solve_closed` через `isobar_radius`, `_front_radius` удаляется

**Цель:** замкнутое решение считает радиус той же функцией; копия удалена.

**Файлы:**
- `numerical_solver/gpn_multiphase_solver/diagnostics/closed_form.py` — докстринг модуля (`:69-77`), импорт (после `:84`), вызов (`:226-228`), функция `_front_radius` (`:235-248`) — удалить;
- `numerical_solver/examples/04_table_table/grid_convergence.py` — текст печати (`:109-110`);
- `numerical_solver/tests/test_isobar_radius.py` — +1 тест.

**Контекст.** `solve_closed` интегрирует уравнение (2) от контура $(R_e, p_e)$ внутрь и интерполирует $p(r_b) = p_b$ по центрам `r`. В примере 11 замкнутый профиль ниже $p_b$ во всех ячейках, и `_front_radius` возвращал центр последней ячейки, 46.9873 м. С узлом $(R_e, p_e)$ — тем самым, откуда начато интегрирование, — получается 47.7342 м при опорном 47.7338 м.

**Что сделать:**
1. Импорт: после `from scipy.optimize import brentq` (`:84`) — пустая строка и
   ```python
   from .rs import isobar_radius
   ```
2. Вызов (`:226-228`).

   До:
   ```python
       # Фронт — по условию p = pb, а не по обнулению Sg_ana: см. docstring
       # модуля, у Кори с порогом S_gc второй критерий занижает r_b на 13 %.
       r_b = _front_radius(r, p_ana, pb)
   ```
   После:
   ```python
       # Фронт — по условию p = pb, а не по обнулению Sg_ana: см. docstring
       # модуля, у Кори с порогом S_gc второй критерий занижает r_b на 13 %.
       # Узел контура (R_e, p_e) — точка, от которой интегрировалось (2): если
       # профиль ниже pb во всех ячейках (пример 11), фронт между последним
       # центром и контуром, а не в центре последней ячейки (DEBT-065).
       r_b = isobar_radius(r, p_ana, pb, R_e, p_e)
   ```
3. Удалить `def _front_radius(r, p, pb): …` целиком (`:235-248`) вместе с пустыми строками после него — между `solve_closed` и `saturation_from_numeric` остаются две пустые строки.
4. Докстринг модуля, раздел «Фронт разгазирования» (`:69-77`): после «Критерий по давлению от этого свободен.» дописать абзац:
   ```
   Радиус — rs.isobar_radius: интерполяция ln r по p между соседними
   центрами; если профиль ниже pb во всех ячейках — между последним центром
   и контуром, где p = p_e.
   ```
5. `examples/04_table_table/grid_convergence.py:109-110`. Сейчас печатается `r_b = … м (от сетки не зависят)`, но r_b — интерполяция по центрам последней сетки ряда. Отличие от мелкой сетки небольшое (у 04 при $N = 50$ +0.02 %, раздел 2.1), но в четвёртом знаке печати видно: 2.5937 против 2.5933. Заменить:

   До:
   ```python
       print(f"Замкнутое решение: q_o = {cl['q_o']:.6e} м³ст/с, "
             f"r_b = {cl['r_b']:.4f} м (от сетки не зависят)")
   ```
   После:
   ```python
       # q_o — квадратура, от сетки не зависит; r_b — интерполяция по центрам
       # последней сетки ряда (на мелкой сетке отличие ≤ 0.04 %, DEBT-065).
       print(f"Замкнутое решение: q_o = {cl['q_o']:.6e} м³ст/с (от сетки не зависит), "
             f"r_b = {cl['r_b']:.4f} м (по центрам последней сетки)")
   ```
   Скрипт не входит в снимок (там только `main.py`) и тестами не проверяется. README 04 его вывод не цитирует; проверить: `git grep -n "от сетки не зависят" -- examples`. Если цитирует — поправить там же.
6. `tests/test_isobar_radius.py` — дописать:

```python
# ── Замкнутое решение: пример 11 ──

def test_closed_form_front_beyond_last_center_example11():
    """Пример 11: замкнутый профиль ниже pb во всех ячейках — фронт между последним центром и контуром.

    Прежде _front_radius возвращал центр последней ячейки, 46.9873 м, и
    report_closed печатал его с подписью «p = pb», хотя давление там
    14.983 МПа. Опорное значение 47.7338 м — то же замкнутое решение на
    сетке из 20 001 узла до R_ext (проба vault/issues/debt-065/probes/
    edge_cases.py); с узлом контура на сетке примера — 47.7342 м.
    """
    from gpn_multiphase_solver.diagnostics.closed_form import solve_closed
    from gpn_multiphase_solver.factory import SimulatorFactory
    from gpn_multiphase_solver.io.config import load_config
    cfg = load_config(EXAMPLES / "11_degassing_at_boundary" / "config.json")
    sim, _ = SimulatorFactory.from_config(cfg)
    r = sim.grid.r_centers
    cl = solve_closed(cfg, sim.pvt, sim.relperm, r)
    assert np.all(cl["p"] < cl["pb"])                  # край: газ во всех ячейках
    assert r[-1] < cl["r_b"] < cfg.geometry.R_ext
    assert cl["r_b"] == pytest.approx(47.7338, rel=1e-4)
```

**Проверка после шага:**
- `git grep -n "_front_radius" -- numerical_solver` — пусто.
- `& $PY -m pytest tests/test_isobar_radius.py -q` — 15 passed; время теста примера 11 ~2 с (проба планирования: `solve_closed` 1.76 с; аудит на пакете DEBT-011 — 1.79 с).
- Регресс: быстрый — N0f + 15 passed.

**Подводные камни:**
- Кэш `_CACHE` в `solve_closed`: ключ — параметры задачи и концы сетки, `r_b` хранится в значении. В одном процессе тестов `solve_closed` для 11 считается заново: ключ новый, старых значений нет.
- `rel=1e-4` в тесте — ±0.005 м. Шире, чем расхождение с опорным (8·10⁻⁶), но в 300 раз уже прежней ошибки (1.6 %): возврат к центру ячейки тест поймает.
- `sim.relperm` для 11 не `None`: ОФП табличная (`relperm.csv`), фабрика передаёт её `Simulator` (DEBT-011, свойство `relperm`). Если всё же `None` — взять `create_relperm(cfg)` из `gpn_multiphase_solver.factory`.

**Зависимости:** требует шаг 1 и конец снимка «до»; блокирует шаг 5.

**Оценка:** ~10 строк кода, −15 строк, ~25 строк тестов, ~15 мин.

---

### Шаг 4: документы — README примеров, vault

**Цель:** описание линии на `rs_profiles.png` и ссылки vault соответствуют новому коду; решение о краях записано.

**Файлы:**
- `numerical_solver/examples/README.md` — абзац о `rs_profiles.png` (на ветке DEBT-011 — около `:487-490`; искать по тексту `«изобара $p_b$» иначе.`);
- `vault/knowledge/numerics/порог-подвижности-Кори-портит-обусловленность-замыкания.md:62`;
- `vault/knowledge/decisions/радиус изобары p_b — одна функция, за последним центром до контура, у забоя nan.md` — новая;
- `vault/00-home/index.md` — строка новой заметки в разделе решений.

**Что сделать:**
1. `examples/README.md`. После предложения «Она подписана «фронт $r_b$», если свободный газ есть ровно в ячейках с $p < p_b$, и «изобара $p_b$» иначе.» дописать:
   ```
   Если давление ниже $p_b$ во всех ячейках (пример 11), изобара ищется между
   последним центром и контуром, где $p = p_0$; если $p_b$ не выше давления в
   первой ячейке — линии нет.
   ```
2. Заметка `порог-подвижности-…md:62`: «Реализован в `examples/closed_form.py::_front_radius`.» → «Реализован в `gpn_multiphase_solver/diagnostics/rs.py::isobar_radius` (вызов — `diagnostics/closed_form.py::solve_closed`).»
3. Новая заметка решения (имя — утверждение, по правилу vault). Содержание:
   ```markdown
   ---
   name: радиус изобары p_b — одна функция, за последним центром до контура, у забоя nan
   description: Радиус изобары p = p_b считает одна функция diagnostics.rs.isobar_radius; за последним центром — узел контура (R_ext, p0), у забоя — nan, на немонотонном профиле — первое пересечение от забоя
   metadata:
     type: project
   ---

   # Радиус изобары $p_b$ — одна функция, за последним центром до контура, у забоя nan

   **Решение (DEBT-065, пользователь, 2026-10-11).** `gpn_multiphase_solver/diagnostics/rs.py::isobar_radius(r, p, pb, R_ext, p_ext)` —
   единственная реализация радиуса изобары $p = p_b$. Её зовут `rs.front_radius` (линия на `rs_profiles.png`),
   `two_phase.degassing_front` (пункт C отчёта) и `closed_form.solve_closed` (фронт замкнутого решения).

   | Случай | Результат | Почему |
   |---|---|---|
   | пересечение между центрами | интерполяция $\ln r$ по $p$ | профиль логарифмичен |
   | $p < p_b$ во всех ячейках | интерполяция до узла $(R_{ext}, p_{ext})$ | на контуре Дирихле на самой грани: $p_{ext} = p_0$ (фабрика), проводимость полуячейки $2\pi kh/\ln(R_{ext}/r_{N-1})$ |
   | $p_{ext} < p_b$ | nan | изобары в области нет |
   | $p[0] \ge p_b$ | nan | изобару между $r_w$ и первым центром ячейки не разрешают; узел $(r_w, p_{wf})$ неверен при скине — $p_{wf}$ за скином |
   | немонотонный профиль | первое пересечение от забоя | граница зоны $p < p_b$ у скважины; на профиле-префиксе — тот же индекс, что `searchsorted` |

   **Было:** три копии; за краем сетки `closed_form._front_radius` давал центр последней ячейки, две другие — nan.
   В примере 11 замкнутое решение печатало «фронт r_b = 46.9873 м (p = pb)» при давлении 14.983 МПа
   (опорное 47.7338 м), а `rs_profiles.png` линии не имел. Стало: 47.7342 м и 47.7659 м (численный профиль).

   Внутри сетки значения побитово прежние. Корень замкнутого решения без сетки не нужен:
   интерполяция по центрам отличается от мелкой сетки на ≤ 0.04 % (03, 04, 04a).

   Тесты: `numerical_solver/tests/test_isobar_radius.py`. Связано: [[DEBT-065]], [[DEBT-011]], [[DEBT-026]].
   ```
4. `vault/00-home/index.md` — в разделе заметок решений (`knowledge/decisions`) строка-ссылка на новую заметку в формате соседних строк.

**Проверка после шага:**
- `git grep -n "_front_radius" -- numerical_solver vault/knowledge` — пусто.
- Регресс: `& $PY -m pytest tests/ --collect-only -q` — N0 + 15. Общий `examples/README.md` тесты проверяют только на существование файла (`tests/test_examples.py::...::test_runner_and_run_all_exist`); `TestReadme` смотрит README отдельных примеров, и правку шага его прогон не проверяет. Ссылки на уравнения в README примеров проверяет `tests/test_eq_references.py`: `& $PY -m pytest tests/test_eq_references.py -q` — passed. Дописанное предложение перечитать глазами.

**Подводные камни:** правка README — только дописать предложение. Числа README 11 не меняются: r_b там не цитируется (`git grep -n "r_b\|фронт" -- examples/11_degassing_at_boundary/README.md` на `4473cd4` — пусто).

**Зависимости:** требует шаги 2, 3.

**Оценка:** ~40 строк текста, ~15 мин.

---

### Шаг 5: итог — снимок «после», сравнение, полный прогон, vault

**Цель:** доказать, что вывод примеров изменился только там, где ожидалось; закрыть задачу в vault.

**Что сделать:**
1. Снимок «после» и сравнение (~20 мин в фоне). Сначала — тот же прототип, что при снимке «до» (шаг 0.4):
   ```powershell
   git -C <M> diff --stat <P0> HEAD -- numerical_solver/HydroSolverPrototype   # пусто
   git -C <M> status --short -- numerical_solver/HydroSolverPrototype         # пусто
   ```
   Не пусто — снять снимок «до» заново на текущем прототипе: отдельный worktree в состоянии detached на базе задачи, проба с `--tree` на него. Иначе сравнение покажет чужие изменения.
   ```powershell
   & $PY <W>\vault\issues\debt-011\probes\snapshot_examples.py snap --tree <W>\numerical_solver --out <W>\vault\issues\debt-065\probes\out\snap_after.json
   & $PY <W>\vault\issues\debt-011\probes\snapshot_examples.py compare <W>\vault\issues\debt-065\probes\out\snap_before.json <W>\vault\issues\debt-065\probes\out\snap_after.json
   ```
   **Ожидание** (раздел 5.3): `расхождения в 1 примерах` — только `11_degassing_at_boundary`:
   - `stdout: строк K → K, различий 1`: `  фронт r_b = 46.9873 м (p = pb = 15.000 МПа)` → `  фронт r_b = 47.7342 м (p = pb = 15.000 МПа)`;
   - `файл pressure_profiles.png: содержимое`, `файл saturation_profiles.png: содержимое` — линия фронта замкнутого решения сдвинулась с 46.987 на 47.734 м;
   - `файл rs_profiles.png: содержимое` — появилась линия «фронт $r_b$ = 47.766 м» (газ во всех 50 ячейках и $p < p_b$ во всех — подпись «фронт»).

   Остальные 22 примера — «совпадает». Исключение — четыре файла с временем выполнения прототипа у 18, если в пробе нет `TIME_FILES` (шаг 0.4). Любое другое расхождение — стоп, разобрать: значит, где-то ещё срабатывал край или нарушен префикс. Ожидаемые числа сверены пробой на `015a297` (до DEBT-011); DEBT-011 числа не меняет.
2. Глазами — три рисунка примера 11 (`<W>\numerical_solver\examples\11_degassing_at_boundary\output\`): вертикальная линия у правого края области между последним центром и 50 м. На `rs_profiles.png` подпись «фронт $r_b$ = 47.766 м».
3. Полный прогон: `& $PY -m pytest tests/ -q` — N0 + 15 passed (контракт `/implement`, §3.1).
4. Vault:
   - реестр DEBT-065 — статус ✅ ГОТОВО, итог (числа тестов, итог сравнения снимков);
   - заметка решения — шаг 4;
   - комментарий к #106 `vault/issues/debt-065/05-comment-done.md`: что сделано, итог сравнения, числа тестов.

**Проверка:** сравнение снимков — ровно ожидаемое; полный прогон зелёный; рисунки 11 просмотрены.

**Зависимости:** требует шаги 1–4.

**Оценка:** ~35 мин (из них ~20 — снимок в фоне, ~10 — полный прогон).

## 5. Тестовая стратегия

### 5.1. Новые тесты (`numerical_solver/tests/test_isobar_radius.py`, все быстрого уровня)

| Тест | Шаг | Сценарий | Ожидание | Предотвращает |
|---|---|---|---|---|
| `test_crossing_between_neighbour_cells[×3]` | 1 | пересечение в первой паре (0–1), в середине (2–3), в последней (4–5) | точное равенство формуле прежнего кода | сдвиг чисел внутри сетки; ошибку индекса на краях массива |
| `test_logarithmic_profile_is_exact` | 1 | $p = a + b\ln r$, изобара на 2.7 м и на 48 м (за последним центром) | rel 1e-12 | ошибку интерполяции (по $r$ вместо $\ln r$), неверный узел контура |
| `test_gas_to_contour_uses_contour_node` | 1 | $p < p_b$ во всех ячейках | $r_{N-1} < r_b < R_{ext}$, равенство интерполяции до $(R_{ext}, p_{ext})$ | возврат к nan или центру ячейки |
| `test_contour_below_pb_is_nan` | 1 | $p_{ext} = 14.8 < p_b$ | nan | экстраполяцию за контур |
| `test_no_cell_below_pb_is_nan[15.0, 15.5]` | 1 | $p[0] = p_b$ и $p[0] > p_b$ | nan | узел забоя, ложный фронт у стенки |
| `test_nonmonotone_profile_takes_first_crossing_from_well` | 1 | `[10, 16, 14, 14.5, 18, 19.5]` МПа | пара 0–1 (searchsorted дал бы 3–4) | двоичный поиск на неупорядоченном профиле |
| `test_cell_at_pb_returns_its_center` | 1 | $p_2 = p_b$ | $r_2$, rel 1e-15 | ошибку на границе `>=` / `>` |
| `test_contour_node_not_beyond_grid_raises` | 1 | $R_{ext} = 40 < r_{N-1} = 45$ | `ValueError` «узел контура» | мусор при сетке не от этого контура |
| `test_numeric_profile_functions_agree[×3]` | 2 | внутри, газ до контура, газа нет; PVT примера 04 | `front_radius` = `degassing_front["r_b_interp"]` = `isobar_radius` | расхождение мест вызова |
| `test_closed_form_front_beyond_last_center_example11` | 3 | замкнутое решение примера 11 | $r_{N-1} < r_b < R_{ext}$, $47.7338$ ± 0.01 % | возврат к центру ячейки (46.9873) |

Итого +15: N0 → N0 + 15, N0f → N0f + 15 (шаг 1 — 11, шаг 2 — 3, шаг 3 — 1). Тесты шага 1 прогнаны на копии кода плана (проба `check_plan_tests.py`, при планировании); тела тестов шагов 2–3 — на пакете ветки DEBT-011 `f0ad91a` (проба `audit_checks.py`, аудит 1): 5 passed.

### 5.2. Существующие тесты (должны пройти без правок)

- `tests/test_rs_analytics.py` — проверка $R_s$ и рисунок `rs_profiles.png` (`_draw_rs` → `front_radius`): подписи «фронт» / «изобара», линия без газа. Профили — внутри сетки или без газа, ветки узла контура не касаются.
- `tests/test_examples.py` — `report_closed`, наложения давления (пример 15, `:1980-2014` на `4473cd4`; r_b внутри сетки), `two_phase_analytics.report` у 03, 04, 05 через фикстуру `results` (медленный уровень, полный прогон шага 5).
- `tests/test_eq_references.py` — новые комментарии без «eq. N» и «ур. N»; в плане их нет («уравнение (2)» в `closed_form` — местная нумерация модуля, шаблоном не ловится).
- `tests/test_example_scripts.py`, `tests/test_public_api.py` (страж приватного доступа DEBT-011): примеры не меняют импортов; `grid_convergence.py` меняет только текст печати.

### 5.3. Неизменность вывода примеров

Снимок «до» и «после» (проба DEBT-011 `snapshot_examples.py`): печать всех 23 `main.py` и побайтно все файлы `output/`. Ожидаемое отличие — только пример 11 (шаг 5.1). Основание: внутри сетки значение побитово прежнее (раздел 2.4, проба `isobar_new.py`); край со стороны контура — только у 11; край у забоя — nan, как и прежде.

## 6. Подводные камни (чеклист 2.5)

| Пункт | Статус | Комментарий |
|---|---|---|
| Все места вызова найдены | ✅ | `front_radius`: `examples/rs_analytics.py::_draw_rs`, `examples/04_table_table/grid_convergence.py`; `degassing_front`: `examples/two_phase_analytics.py::report`, `examples/03_standing_corey/main.py`, `examples/05_standing_table_rp/main.py`; `_front_radius`: только `solve_closed` (+ ссылка в vault). Шаг 0.2 перепроверяет |
| Зависимости пакетов | ✅ | новых нет |
| Обратная совместимость API | ✅ | сигнатуры `front_radius`, `degassing_front`, `solve_closed` прежние; `_front_radius` — закрытая, внешних вызовов нет; `isobar_radius` — новая |
| Состояние при ошибке | ✅ | функции без состояния; `ValueError` только при $R_{ext} \le r_{N-1}$ на ветке узла контура |
| Тесты | ✅ | существующие не меняются (5.2) |
| Циклы импорта | ✅ | `rs` импортирует только `numpy`; `closed_form → rs`, `two_phase → closed_form, rs` |
| Ссылки на уравнения | ✅ | меток `.tex` не добавляется; «eq. N» нет |
| Конфиги | ✅ | не меняются |
| Связь с другими задачами | ⚠️ | [[DEBT-011]] — предусловие (шаг 0.1). [[FEAT-030]] (#104) переносит наложения и печать из `examples/` в пакет — DEBT-065 их не меняет, правит только `diagnostics/`, текст `grid_convergence.py` и README; конфликт возможен лишь в абзаце `examples/README.md`. [[DEBT-026]] — префикс $p < p_b$: решение 3 с ним согласовано |
| Производительность | ✅ | `np.append` двух массивов длины $N + 1$ — пренебрежимо; тест 11 — ~2 с |
| Прототип | ✅ | не меняется |
| Сравнение снимков | ⚠️ | (аудит 1) у 18 четыре файла прототипа с временем выполнения — без `TIME_FILES` в пробе они расходятся при любом коде; прототип для скриптов примеров — из основного каталога (editable), между снимками основной каталог не должен менять прототип. Оба условия — шаг 0.4, проверка — шаг 5.1 |
| Допущение $p_{ext} = p_0$ | ⚠️ | так в фабрике сейчас (`factory.py`, `p_ext=ic.p0`), на этом же держится `diagnostics/temperature.py`. Если ГУ по давлению когда-нибудь отделят от $p_0$, `front_radius` и `degassing_front` надо будет перевести на новое поле — тем же поиском, что для `temperature.py` (`initial_conditions.p0` в `diagnostics/`) |

## 7. Варианты (итог issue и планирования)

| Вариант | Суть | Решение |
|---|---|---|
| 1 | за краем — nan (как у двух из трёх) | отклонён: в 11 теряется фронт, который в области есть |
| 2 | за краем — центр последней ячейки | отклонён: центр выдаётся за изобару, −1.6 % в 11, ложная подпись «p = pb» |
| **3** | граничные узлы | **принят частично**: узел контура — да; узел забоя — нет (скин), у забоя nan |
| 4 | корень замкнутого решения без сетки (событие `solve_ivp`) | отклонён: внутри сетки выигрыш ≤ 0.04 %, на краю вариант 3 даёт то же; снова две реализации |

## 8. Критерии завершения

- [ ] `isobar_radius` в `diagnostics/rs.py`; три места вызова — через неё; `_front_radius` удалена (`git grep _front_radius -- numerical_solver` пусто).
- [ ] Объяснение «np.interp не годится» — одно (в `isobar_radius`).
- [ ] +15 тестов, все зелёные; существующие без правок.
- [ ] Полный прогон: N0 + 15 passed.
- [ ] Сравнение снимков — расхождение только у 11 (печать r_b и три PNG), рисунки просмотрены.
- [ ] README примеров, заметка `порог-подвижности-…`, новая заметка решения, `index.md`.
- [ ] Реестр: статус, итог; комментарий к #106.
- [ ] Прототип не тронут.

## 9. Обнаруженные проблемы

1. **Комментарий `dupuit_check` (`two_phase.py:195`)**: «привязанный к самой дальней ячейке (там ГУ Дирихле)» — условие Дирихле стоит на грани $R_{ext}$, а не в ячейке. Исправляется в шаге 2.4 (только комментарий).
2. **Печать `grid_convergence.py:110`**: «r_b … (от сетки не зависят)» — r_b интерполируется по центрам последней сетки ряда, в четвёртом знаке видно (2.5937 против 2.5933 у 04). Исправляется в шаге 3.5 (только текст печати).

Новых записей в реестр нет: оба пункта — на той же теме и в тех же файлах.

## 10. Оценка

- Файлов кода: 3 (`diagnostics/rs.py`, `two_phase.py`, `closed_form.py`) + 1 скрипт примера (текст печати) + 1 новый файл тестов.
- Строк: ~+70 / −35 кода (с комментариями), ~+190 тестов, ~+40 текста документов.
- Время: ~2.5 ч, из них ~40 мин — два снимка в фоне и ~10 мин — полный прогон.

## 11. Связанные заметки

- [[DEBT-065]] — запись реестра; issue [#106](https://github.com/ArturSalamatin/Oil_Gas/issues/106), тело — `vault/issues/debt-065/01-issue-body.md`.
- [[debt-011 diagnostics-into-package]] — перенос функций в `diagnostics/`, проба снимка `vault/issues/debt-011/probes/snapshot_examples.py`.
- [[debt-026 rs-check-any-pressure-history]] — замер префикса $p < p_b$ на примерах, подписи «фронт» / «изобара».
- Пробы: `vault/issues/debt-065/probes/edge_cases.py` (+ `.txt`) — пример 11 и синтетика; `isobar_new.py` (+ `.txt`) — код плана против старых функций; `scan_snapshot.py` — строки про фронт в снимке DEBT-011; `check_plan_tests.py` — тесты шага 1 на копии кода плана; `audit_checks.py` — тела тестов шагов 2–3 на пакете ветки DEBT-011 (запуск — в докстринге пробы, с `PYTHONPATH` на worktree DEBT-011).
- `vault/knowledge/numerics/порог-подвижности-Кори-портит-обусловленность-замыкания.md` — почему фронт по $p = p_b$, а не по $S_g$.
