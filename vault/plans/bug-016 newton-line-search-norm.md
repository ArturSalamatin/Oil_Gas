---
tags:
  - план
  - баг
  - численные-методы
date: 2026-09-30
issue: BUG-016
github: 44
branch: fix/bug-016/newton-line-search-norm
status: готов к реализации
---

# BUG-016: третья ступень `advance` — Ньютон с линейным поиском по $\|F\|_2$ и ограничителем $|\Delta S_g| \le 0.2$

**Реестр:** [[известные баги и технический долг]] → BUG-016. **Issue:** [#44](https://github.com/ArturSalamatin/Oil_Gas/issues/44). **Попутно закрывает:** [[BUG-008]] (04a на подробной сетке), [[DEBT-025]] (дробление первого часа примера 12).

## Цель

Пример 14 (`numerical_solver/examples/14_high_gor_cooling/`, $R_{s,0} = 150$) должен проходить первый шаг (скачок $p_{wf}$ 24.5 → 6 МПа) на сетке $N \ge 100$. Сейчас отказ при любом дроблении шага: $N = 100$ — 512 × 169 с и 512 × 7 с; $N = 150$ — 4096 × 0.88 с при `max_retries = 12`.

Правка — **третья ступень** `RadialBlackOilModel.advance`: если не сошлись ни исходный алгоритм, ни запасной путь [[BUG-014]], запасной путь повторяется с глобализованным Ньютоном — линейный поиск по $\|F\|_2$ вместо $\|F\|_\infty$ и ограничитель $|\Delta S_g| \le 0.2$ за итерацию. Там, где сходится одна из первых двух ступеней, результат **побитово прежний**.

## 0. Решения пользователя

| № | Вопрос | Решение | Дата |
|---|---|---|---|
| 1 | Где включать правку | **Третья ступень** — после исходного алгоритма и запасного пути BUG-014, только при отказе обоих (по образцу варианта F BUG-014). Отвергнуты: «заменить запасной путь» (03 хуже: 0 → 3 отказа, $\lvert\Delta T\rvert$ до 0.21 К) и «всегда» (10 хуже: 1 → 6 отказов, отличия $\sim10^{-10}$ во всех примерах) | 2026-09-30 |
| 2 | Что делает третья ступень, кроме $\|F\|_2$ | **Ограничитель $\lvert\Delta S_g\rvert \le 0.2$ за итерацию Ньютона** (как `ds_max` в OPM Flow). Отвергнуто: ограничение начального $S_g$ активации ($\le 0.3$) — эмпирический порог, на 04a $N = 500$ хуже (16 подшагов против 8); на всех 16 примерах и на 14 при $N \le 200$ оба дают одинаковые числа | 2026-09-30 |
| 3 | `numerics.max_retries = 12` в конфиге 04a | **Оставить**; в README 04a переписать причину (первый шаг больше не дробится) | 2026-09-30 |

## 1. Измерения (2026-09-30)

Все пробы — `vault/issues/bug-016/probes/` (папка в `.gitignore`), запуск из `numerical_solver` основного каталога. Правки прототипа в пробах — подменой методов класса `RadialBlackOilModel` (`patch.py`), код прототипа не менялся.

| скрипт | что даёт |
|---|---|
| `patch.py` | копии `_newton_fixed_active_set`, `_advance_phases`, `advance` с переключателями: `none` (исходный), `always`, `fallback`, `tier3` (третья ступень); `cap` — $S_g$ активации, `chop` — ограничитель $\lvert\Delta S_g\rvert$; счётчики вызовов |
| `fine_grid_first_step.py N dt…` | отказ первого шага 14: журнал вызовов Ньютона, причины отклонения пробных точек |
| `fine_grid_newton_trace.py N dt` | итерации Ньютона: норма, принятый $\alpha$, ячейка с максимальной невязкой |
| `first_step_matrix.py пример N,… вариант,…` | первый шаг через адаптер (с дроблением A-retry) — сетка × вариант |
| `regress_examples.py метка режим cap chop` + `compare_regress.py A B` | все 16 примеров: история целиком, сравнение побитово / макс. / последняя запись, вызовы и отказы |
| `ex14_grid_tier3.py режим cap chop` | пример 14, $N$ = 50/100/150: первый шаг и год |
| `readme_claims.py режим cap chop` | утверждения README 11 и 12 о «несходящихся» режимах |
| `run_example_patched.py метка режим cap chop пример` | консоль `run_example` для сверки с README (`readme_runs/`) |
| `bug016_plugin.py` | pytest-плагин: патч до сбора тестов (`$env:BUG016_MODE`, `BUG016_CHOP`) |

### 1.1 Механизм отказа (пример 14, первый суточный шаг)

1. `_advance_phases` (`blackoil.py:264-282`) решает шаг при всех ячейках однофазных: давление падает почти по всему пласту, у забоя до 6.1 МПа (от $dt$ почти не зависит).
2. Ячейки с $p < p_b$ активируются разом ($N = 50$: 48, $N = 100$: 97) с $S_g$ «выделения в закрытом сосуде» (`blackoil.py:279`): 0.55–0.71 при решении 0.22.
3. Полный шаг Ньютона: $\max\lvert dS_g\rvert = 0.81$, $\max\lvert dp\rvert = 10.1$ МПа. Линейный поиск (`blackoil.py:218-225`) принимает шаг по уменьшению $\|F\|_\infty$, не более 12 делений. Направление Ньютона — направление спуска для $\|F\|_2^2$ ($\nabla\tfrac12\|F\|_2^2 \cdot d = -\|F\|_2^2 < 0$ при $J d = -F$), но не обязательно для $\|F\|_\infty$: принимаются $\alpha = 10^{-3}\ldots3\cdot10^{-2}$. $N = 50$: 8 таких итераций, на 9-й полный шаг случайно уменьшил $\|F\|_\infty$ — сходимость. $N = 100$: на 7-й итерации ни одно деление не уменьшает $\|F\|_\infty$ → отказ; запасной путь BUG-014 (без границы $S_g$) — тот же тупик.

### 1.2 Первый шаг, сетка × вариант (`first_step_matrix.py`, `max_retries = 9`; число — подшагов до успеха)

Пример 14, $dt = 86400$ с:

| $N$ | исходный | $\|F\|_2$ в запасном пути | $\|F\|_2$ + $S_g \le 0.3$ | $\lvert\Delta S_g\rvert \le 0.2$ без смены нормы | $\|F\|_2$ + $\lvert\Delta S_g\rvert \le 0.2$ | **третья ступень ($\|F\|_2$ + 0.2)** |
|---|---|---|---|---|---|---|
| 50 | 1 | 1 | 1 | 1 | 1 | 1 |
| 100 | отказ | отказ | 1 | отказ | 1 | **1** |
| 150 | отказ | 32 | 1 | отказ | 1 | **1** |
| 200 | отказ | 32 | 1 | отказ | 1 | **1** |

Норма $\|F\|_2$ обязательна; одна она мала без ограничителя (или ограничения $S_g$).

04a ([[BUG-008]]), $dt = 300$ с, третья ступень: $N$ = 150 / 200 / 300 / 500 → **1 / 1 / 2 / 8** подшагов (было 512 / 4096 / 4096 / 16384; $N = 500$ — 20 с против 1633 с).

Пример 12 ([[DEBT-025]]), первый час: **1** подшаг (было 128 × 28.125 с). Пример 03: 1 (как и сейчас — сходится запасной путь BUG-014).

### 1.3 Регрессия 16 примеров (`regress_examples.py`, `compare_regress.py orig tier3_chop02`)

| пример | побитово | $\max_t\lvert\Delta p\rvert$ | $\max_t\lvert\Delta T\rvert$, К | $\max_t\lvert\Delta q_o\rvert/q_o$ | конец истории: $\lvert\Delta p\rvert$ / $\lvert\Delta T\rvert$ / $\Delta q_o/q_o$ | вызовов advance (отказов) | время расчёта |
|---|---|---|---|---|---|---|---|
| 01–03, 04, 05–09, 10, 13a, 14, 15 | **да** | 0 | 0 | 0 | 0 | без изменений | без изменений |
| 04a | нет | 0.44 МПа | 0.54 | 14 % | 47 Па / $1.7\cdot10^{-4}$ / $1.1\cdot10^{-5}$ | 1896 (9) → 864 (0) | 99.8 → 39.8 с |
| 11 | нет | 0.30 МПа | 0.060 | 5.7 % | 190 Па / $1.5\cdot10^{-3}$ / $8\cdot10^{-5}$ | 107 (4) → 72 (0) | 6.6 → 3.6 с |
| 12 | нет | 3.0 кПа | 0.0027 | 0.064 % | 47 Па / $7.6\cdot10^{-4}$ / $1.8\cdot10^{-5}$ | 622 (7) → 360 (0) | 27.6 → 15.0 с |

У 04a, 11, 12 меняется не корень Ньютона, а **дискретизация старта по времени**: первый шаг теперь целиком ($dt$ конфига), а не 512 / 16 / 128 подшагами. Отличие велико на первых записях и затухает к концу. Время записано при параллельной нагрузке (3 процесса).

⚠️ **Точность первой записи 04a падает.** Первая запись (5 мин) — теперь один неявный шаг 300 с на резком старте вместо 512 подшагов по 0.59 с (дробление было побочным следствием отказа Ньютона, но давало почти точный переходный процесс). Таблица «Переходный процесс» README 04a (`readme_transient.py orig tier3_chop02`):

| $t$ | $S_g(r_w)$ | $q_o$, $10^{-3}$ м³ст/с | GOR | $T(r_w)$, К |
|---|---|---|---|---|
| 5 мин, было → стало | 0.639 → **0.620** | 7.49 → **8.54** | 20.8 → **18.6** | 350.51 → **349.97** |
| 1 ч | 0.670 → 0.670 | 5.58 → 5.58 | 25.0 → 25.0 | 350.99 → **350.97** |
| 6 ч | 0.695 → **0.694** | 5.02 → 5.02 | 29.0 → 29.0 | 351.43 → 351.43 |
| 12, 24 ч | без изменений в печатаемых знаках | | | |
| 72 ч | 0.700 | 4.94 | 30.006 | 352.239 → **352.238** |

На 5 мин забой теперь **ниже** $T_0$ (349.97 К): крупный шаг сильнее выражает адиабатическое охлаждение первого импульса. Для точного раннего переходного процесса нужен мелкий начальный шаг — это выбор данных (история конфига), а не решателя; в README 04a — оговорка (шаг 5). У 11: минимум $T(r_w)$ в первые сутки 349.37 → **349.31** К (через 1 ч).

### 1.4 Пример 14 по сетке с правкой (`ex14_grid_tier3.py tier3 - 0.2`)

| $N$ | первый шаг: подшагов, $S_g[0]$, $p[0]$ | год: $T(r_w)$, К | $S_g(r_w)$ | $q_o$, $10^{-3}$ м³ст/с | GOR | третья ступень, раз |
|---|---|---|---|---|---|---|
| 50 | 1, 0.223531, 6.392927 МПа | 344.231 | 0.2291 | 4.7485 | 146.36 | 0 (побитово как пример) |
| 100 | 1, 0.224200, 6.196104 МПа | 344.123 | 0.2296 | 4.7161 | 146.11 | 1 |
| 150 | 1, 0.224420, 6.130659 МПа | 344.087 | 0.2298 | 4.7055 | 146.01 | 2 |

### 1.5 Утверждения README, которые правка опровергает (`readme_claims.py tier3 - 0.2`)

| README | утверждение | с правкой |
|---|---|---|
| 12, «Как модифицировать» | «Сутки как шаг интегрирования не годятся: гидравлический решатель не сходится и после 512 подшагов» | сходится: 15 шагов, без отказов (третья ступень — 1 раз); $T(r_w) = 350.333$ К, $q_o = 3.2287\cdot10^{-3}$ м³ст/с на 15 сут |
| 11, «Как модифицировать» | «При $p_0 = 15.2$ МПа гидравлический решатель не сходится после 512 подшагов» | сходится: 72 шага, без отказов (третья ступень — 1 раз); $T(r_w) = 350.481$ К, $q_o = 3.8709\cdot10^{-3}$ м³ст/с |

### 1.6 Тесты с правкой

- `numerical_solver/tests` (патч `tier3`, `chop = 0.2`, `bug016_plugin.py`): **999 passed, 4 failed, 358 с** (baseline 1003 passed, ~557 с). Все четыре падения ожидаемые и исправляются в шаге 3:
  - `test_energy_matrix_examples.py::test_energy_substeps_preserve_total_time[11_degassing_at_boundary]` и `[12_large_drainage_radius]` — «ожидалось дробление A-retry»; у 11 и 12 дробления больше нет;
  - `test_prototype_well_branch.py::TestAdvanceBranchLogic::test_all_fail` и `::test_both_branches_inconsistent` — проверяют точную последовательность вызовов `_advance_phases`, третья ступень добавляет два вызова.
- Варианты `always` / `fallback` (с $S_g \le 0.3$): по 2 падения (SUBDIVIDING 11, 12); у них последовательность вызовов не меняется.
- Первый прогон `tier3` (1001 / 2) был недостоверен: в `patch.py` режим не восстанавливался после исключений тестов BUG-014, и файлы после `test_prototype_well_branch.py` шли без правки. Исправлено (`try/finally`), перемерено — цифры выше.
- Тесты прототипа (`HydroSolverPrototype/Prototype_1.0.3/tests`): 70 passed / 10 failed — **одинаково** без правки и с ней; 10 — [[DEBT-024]] (нет `xlsxwriter`).

## 2. Анализ

### 2.1 Воспроизведение

До фикса (из `numerical_solver`):
```powershell
.venv\Scripts\python ..\vault\issues\bug-016\probes\fine_grid_first_step.py 100 86400
```
→ `сошёлся = False, fallback = True`. Тест-воспроизводитель — шаг 1 (`test_example14_fine_grid_first_step[100]`): `RuntimeError: HydroSolver не сошёлся после 512 подшагов`.

### 2.2 Цепочка

Высокий $R_{s,0}$ + резкая депрессия → массовая активация фазы с далёким начальным $S_g$ → линейный поиск по $\|F\|_\infty$ стоит → `_newton_fixed_active_set` возвращает `converged = False` → `_advance_phases` → `advance` (обе ступени) → адаптер дробит шаг → на любом подшаге то же (начальное приближение от $dt$ не зависит) → `RuntimeError` адаптера.

### 2.3 Целевое состояние

- Пример 14 при $N$ = 100, 150, 200 — первый шаг без дробления; год считается.
- 13 примеров побитово прежние; 04a, 11, 12 — без дробления старта, README перемерены.
- Исходный алгоритм и запасной путь BUG-014 не меняются; атрибуты третьей ступени вне `advance` — по умолчанию, в том числе после исключения.

### 2.4 Варианты

| вариант | суть | + | − |
|---|---|---|---|
| **A. Третья ступень (выбран, решение 1)** | запасной путь BUG-014 повторяется с $\|F\|_2$ + ограничителем, только при отказе первых двух ступеней | 13 примеров побитово; 04a/11/12 быстрее и без дробления; BUG-008, DEBT-025 закрываются | три пути в `advance`; на трудном шаге — лишняя неудачная попытка (цена — секунды) |
| Б. Заменить запасной путь | правки внутри запасного пути BUG-014 | проще | пример 03: 0 → 3 отказа, $\lvert\Delta T\rvert$ до 0.21 К — запасной путь BUG-014 решает шаги, на которых новый путь отказывает |
| В. Всегда | правки на каждом шаге | один путь | пример 10: 1 → 6 отказов; отличия $\sim10^{-10}$ во всех примерах — побитовая регрессия потеряна |
| Г. Больше итераций / делений | `max_iter`, число делений | — | не лечит причину: $\|F\|_\infty$ не убывает ни при каком $\alpha$ |

Третья ступень: ограничитель (решение 2) против ограничения $S_g$ активации — одинаковые числа на 16 примерах и на 14 при $N \le 200$; ограничитель лучше на 04a $N = 500$ и не привязан к данным.

### 2.5 Подводные камни

| пункт | статус | комментарий |
|---|---|---|
| Побочные эффекты | ✅ | `_newton_fixed_active_set` вызывает только `_advance_phases`; `advance` — адаптер (`prototype_adapter.py:98`), `simulation.py`, тесты, пробы; сигнатуры не меняются |
| Побитовость первых двух ступеней | ✅ | при атрибутах по умолчанию сравнение в линейном поиске то же (`norm(ft, inf) < nrm`), ограничитель выключен (`None`); замер — 13 примеров побитово |
| Граничные случаи | ✅ | ограничитель масштабирует весь шаг ($p$ и $S_g$ вместе — направление Ньютона сохраняется); нет двухфазных ячеек → не срабатывает; $\|F\|_2$ — `np.linalg.norm` без переполнения на $\sim10^{-2}$ |
| Состояние при ошибке | ⚠️ | `try/finally` сбрасывает `_line_search_l2`, `_sg_step_max`; запасной путь сам сбрасывает `_sg_lower_bound`, `_well_branch` — тест шага 1 |
| Критерий сходимости | ✅ | остаётся $\|F\|_\infty \le$ atol + rtol·scale — точность решения не меняется |
| Производительность | ✅ | третья ступень только при отказе обеих; на всех примерах вызовов не больше, чем было (отказов меньше) |
| Связь с задачами | ⚠️ | [[BUG-008]], [[DEBT-025]] закрываются этим фиксом (шаг 6); [[DEBT-007]] (подсказка про `max_retries`) — не трогаем: подсказка остаётся верной там, где дробление помогает (пример 10) |
| Тесты, закрепляющие дробление | ⚠️ | `SUBDIVIDING_EXAMPLES` (11, 12 → убрать), `test_all_fail`, `test_both_branches_inconsistent` (последовательность вызовов) — шаг 3 |
| README с числами старта | ⚠️ | 04a, 11, 12 — перемерить `run_example` (шаг 5), сравнить с `readme_runs/` |
| Точность раннего переходного процесса | ⚠️ | первая запись 04a — один шаг 300 с вместо 512 подшагов: $T(r_w)$ на 5 мин 350.51 → 349.97 К (§1.3). Не регрессия решателя (корень тот же, меняется только $dt$ старта), но README 04a получает оговорку (шаг 5) |
| Общее рабочее дерево | ⚠️ | параллельные сессии правят vault в основном каталоге — работать в worktree (§6) |

### 2.6 Новые проблемы

Нет. Дефект пробы (режим не восстанавливался после исключения) исправлен в `patch.py`.

## 3. Шаги

### Шаг 0: Подготовка

```powershell
cd D:\Lessons\Grants\2026\GPN\Oil_Gas
git status --short -uno
git worktree add -b fix/bug-016/newton-line-search-norm .worktrees/bug-016 numerical_scheme/implementation
cd .worktrees\bug-016\numerical_solver
D:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\.venv\Scripts\python.exe -m pytest tests/ -q -p no:cacheprovider
```

Baseline: **1003 passed, 1 warning, ~557 с** (FEAT-024, 2026-09-30; база `5e2aec7`). venv — основного каталога (в worktree `.venv` нет). pytest в worktree берёт код worktree; скрипты примеров — только с `$env:PYTHONPATH = "<worktree>\numerical_solver"` (память проекта «Worktree и PYTHONPATH»).

### Шаг 1: Тесты-воспроизводители (красные)

**Файл (новый):** `numerical_solver/tests/test_prototype_globalization.py`

```python
"""BUG-016: третья ступень RadialBlackOilModel.advance — глобализованный Ньютон.

Исходный алгоритм advance и запасной путь BUG-014 принимают шаг Ньютона
только при уменьшении ||F||_inf. При массовой активации газовой фазы с
далёким начальным S_g («закрытый сосуд»: 0.55-0.71 при решении 0.22,
пример 14, R_s0 = 150) направление Ньютона не уменьшает ||F||_inf ни при
каком alpha — Ньютон стоит, дробление шага не помогает.

Третья ступень (только при отказе первых двух): запасной путь BUG-014 с
линейным поиском по ||F||_2 (направление Ньютона — направление спуска для
||F||_2^2) и ограничителем |dS_g| <= 0.2 за итерацию (как ds_max в OPM Flow).

План: vault/plans/bug-016 newton-line-search-norm.md.
"""

import copy
from pathlib import Path

import numpy as np
import pytest

from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.io.config import NumericsConfig, load_config
from radial_blackoil.blackoil import BlackOilNewtonReport
from radial_blackoil.state import BlackOilState

# Модель Nabor_1b и состояние после часа отбора — из тестов BUG-014.
# tests/ — пакет (как from ._doubles import ... в test_simulator.py), импорт
# относительный. Импорт фикстуры drawn_down делает её фикстурой и этого модуля.
from .test_prototype_well_branch import _build, _model, drawn_down  # noqa: F401

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"
SG_STEP_MAX = 0.2   # ограничитель третьей ступени, |dS_g| за итерацию


def _first_step(name, N=None, retries=None):
    """Первый шаг истории примера через адаптер (с дроблением A-retry)."""
    cfg = load_config(EXAMPLES_DIR / name / "config.json")
    if N is not None:
        cfg.grid.N = N
    if retries is not None:
        cfg.numerics.max_retries = retries
    sim, init = SimulatorFactory.from_config(cfg)
    _, dt = sim._schedule.substeps(0)
    return sim, sim._hydro.solve(init, dt, sim._schedule.intervals[0].bc)


def _assert_restored(model):
    """Вне advance атрибуты запасного пути и третьей ступени — по умолчанию."""
    assert model._well_branch is None
    assert model._sg_lower_bound == -0.05
    assert model._line_search_l2 is False
    assert model._sg_step_max is None


# ═══════════════════════════════════════════════════════════
# A. Реальный Ньютон: шаги, которые без третьей ступени не проходят
# ═══════════════════════════════════════════════════════════

class TestFirstStepConverges:
    @pytest.mark.parametrize("N, sg0, p0_MPa", [
        (100, 0.224200, 6.196104),
        (150, 0.224420, 6.130659),
    ])
    def test_example14_fine_grid_first_step(self, N, sg0, p0_MPa):
        """Пример 14 (R_s0 = 150), скачок p_wf 24.5 -> 6 МПа, сутки — без дробления.

        До фикса: RuntimeError после 512 подшагов (N = 100: 512 × 169 с;
        N = 150 не проходит и 4096 × 0.88 с). Замер плана BUG-016 (§1.4):
        S_g[0], p[0] ниже; N = 50 — 0.223531 / 6.392927 МПа (сходится и без
        третьей ступени). Допуски — порядка точности Ньютона.
        """
        _, res = _first_step("14_high_gor_cooling", N=N)
        assert res.n_substeps == 1
        assert res.state.Sg[0] == pytest.approx(sg0, abs=1e-5)
        assert res.state.p[0] == pytest.approx(p0_MPa * 1e6, abs=100.0)

    def test_04a_dense_grid_first_step(self):
        """04a, N = 200, шаг 300 с при ШТАТНОМ max_retries = 9 — без дробления.

        BUG-008: исходно нужно 4096 подшагов (12 удвоений) — при 9 отказ.
        Замер плана BUG-016 (§1.2): 1 подшаг; N = 300 — 2, N = 500 — 8.
        """
        _, res = _first_step("04a_high_gas_saturation", N=200,
                             retries=NumericsConfig().max_retries)
        assert res.n_substeps == 1

    def test_example12_first_hour_not_split(self):
        """Пример 12, первый час — без дробления (DEBT-025: было 128 × 28.125 с)."""
        _, res = _first_step("12_large_drainage_radius")
        assert res.n_substeps == 1

    def test_sg_step_limited_in_third_stage(self):
        """В третьей ступени |dS_g| между итерациями Ньютона <= 0.2.

        Пример 14, N = 100, первый суточный шаг прямо на модели прототипа:
        исходный путь и запасной отказывают, решает третья ступень. Точки, где
        считается якобиан, — итерации Ньютона; они собираются по вызовам
        _newton_fixed_active_set (набор фаз внутри вызова фиксирован) и только
        при включённом ограничителе, то есть в третьей ступени.
        """
        cfg = load_config(EXAMPLES_DIR / "14_high_gor_cooling" / "config.json")
        cfg.grid.N = 100
        sim, init = SimulatorFactory.from_config(cfg)
        model = sim._hydro._model
        _, dt = sim._schedule.substeps(0)
        model.set_bhp_control(cfg.time.history[0].p_wf / 1e5)   # Па -> бар

        calls = []
        orig_newton = model._newton_fixed_active_set
        orig_jac = model.finite_difference_jacobian

        def newton(z0, state_old, dt_s, gas_active, **kw):
            calls.append([])
            return orig_newton(z0, state_old, dt_s, gas_active, **kw)

        def jac(z, state_old, dt_s, gas_active, **kw):
            if model._sg_step_max is not None:
                calls[-1].append((z.copy(), gas_active.copy()))
            return orig_jac(z, state_old, dt_s, gas_active, **kw)

        # Подмена на экземпляре: _advance_phases и _newton_fixed_active_set
        # вызывают self.<метод>, поэтому перехватываются оба
        model._newton_fixed_active_set = newton
        model.finite_difference_jacobian = jac
        s0 = BlackOilState(pressure_bar=init.p / 1e5, rs_sm3_sm3=init.Rs.copy(),
                           sg=init.Sg.copy(), gas_active=(init.regime == 1))
        _, rep = model.advance(s0, dt)
        assert rep.converged and rep.globalized

        n = model.grid.n
        # |dS_g| двухфазных ячеек между соседними итерациями одного вызова
        steps = [np.abs(b[0][n:][b[1]] - a[0][n:][a[1]]).max()
                 for seq in calls for a, b in zip(seq, seq[1:]) if b[1].any()]
        assert steps, "третья ступень не сделала ни одной итерации"
        assert max(steps) <= SG_STEP_MAX + 1e-12, f"max|dS_g| = {max(steps)}"
        _assert_restored(model)


# ═══════════════════════════════════════════════════════════
# B. Управляющая логика advance без Ньютона
# ═══════════════════════════════════════════════════════════

def _install_fake_phases3(model, plan):
    """Подменить _advance_phases; ключ — (ветка, граница S_g, ||F||_2 включён).

    plan[key] — (converged, p0_bar) или "raise". Возвращает список ключей вызовов
    и снимки (_sg_step_max) в момент каждого вызова.
    """
    calls, chop = [], []

    def fake(state_old, dt_s, max_active_iter, max_newton):
        key = (model._well_branch, model._sg_lower_bound, model._line_search_l2)
        calls.append(key)
        chop.append(model._sg_step_max)
        answer = plan[key]
        if answer == "raise":
            raise RuntimeError("искусственный отказ")
        converged, p0_bar = answer
        new = state_old.copy()
        new.pressure_bar[0] = p0_bar
        return new, BlackOilNewtonReport(converged, 3, 0.0)

    model._advance_phases = fake
    return calls, chop


ORIG3 = (None, -0.05, False)


class TestThirdStageLogic:
    """Модель p_wf = 150 бар, state_old = drawn_down (p[0] = 111.7 < 150):
    запасной путь стартует с «закрыта»."""

    def test_third_stage_after_fallback_fails(self, drawn_down):
        # Исходный и запасной (обе ветки) — отказ; третья ступень на «закрыта»
        # сходится с p[0] = 149 <= 150 — согласована.
        model = _model(150.0)
        calls, chop = _install_fake_phases3(model, {
            ORIG3: (False, 0.0), ("shut", None, False): (False, 0.0),
            ("open", None, False): (False, 0.0), ("shut", None, True): (True, 149.0)})
        _, rep = model.advance(drawn_down, 3600.0)
        assert calls == [ORIG3, ("shut", None, False), ("open", None, False),
                         ("shut", None, True)]
        assert chop == [None, None, None, SG_STEP_MAX]
        assert rep.converged and rep.fallback and rep.globalized
        assert rep.well_branch == "shut"
        _assert_restored(model)

    def test_no_third_stage_when_fallback_converges(self, drawn_down):
        # Запасной путь BUG-014 сошёлся — третьей ступени нет, globalized = False
        model = _model(150.0)
        calls, _ = _install_fake_phases3(model, {
            ORIG3: (False, 0.0), ("shut", None, False): (False, 0.0),
            ("open", None, False): (True, 151.0)})
        _, rep = model.advance(drawn_down, 3600.0)
        assert calls == [ORIG3, ("shut", None, False), ("open", None, False)]
        assert rep.converged and rep.fallback and not rep.globalized
        _assert_restored(model)

    def test_no_third_stage_when_original_converges(self, drawn_down):
        model = _model(150.0)
        calls, _ = _install_fake_phases3(model, {ORIG3: (True, 151.0)})
        _, rep = model.advance(drawn_down, 3600.0)
        assert calls == [ORIG3]
        assert not rep.fallback and not rep.globalized
        _assert_restored(model)

    def test_all_three_stages_fail(self, drawn_down):
        # Отказ везде: converged = False, globalized = True — адаптер раздробит шаг
        model = _model(150.0)
        plan = {k: (False, 0.0) for k in (ORIG3, ("shut", None, False), ("open", None, False),
                                          ("shut", None, True), ("open", None, True))}
        calls, _ = _install_fake_phases3(model, plan)
        _, rep = model.advance(drawn_down, 3600.0)
        assert len(calls) == 5
        assert not rep.converged and rep.globalized
        _assert_restored(model)

    def test_exception_in_third_stage(self, drawn_down):
        # Исключение в третьей ступени пробрасывается; атрибуты — по умолчанию
        model = _model(150.0)
        _install_fake_phases3(model, {
            ORIG3: (False, 0.0), ("shut", None, False): (False, 0.0),
            ("open", None, False): (False, 0.0), ("shut", None, True): "raise"})
        with pytest.raises(RuntimeError):
            model.advance(drawn_down, 3600.0)
        _assert_restored(model)

    def test_rate_control_third_stage(self):
        # Управление по дебиту: запасной путь без ветки; третья ступень — тот же
        # повтор с ||F||_2 и ограничителем
        model, state = _build(150.0)
        model.set_oil_rate_control(2.0, 100.0)
        calls, chop = _install_fake_phases3(model, {
            ORIG3: (False, 0.0), (None, None, False): (False, 0.0),
            (None, None, True): (True, 190.0)})
        _, rep = model.advance(state, 60.0)
        assert calls == [ORIG3, (None, None, False), (None, None, True)]
        assert chop == [None, None, SG_STEP_MAX]
        assert rep.converged and rep.globalized
        _assert_restored(model)
```

Импорт из `test_prototype_well_branch` работает: `tests/` без `__init__.py`, pytest кладёт каталог теста в `sys.path` (проверить при реализации одним прогоном; если импорт не находится — вынести `_build`, `_model` и фикстуру `drawn_down` в `tests/conftest.py` не нужно, достаточно `sys.path.insert(0, str(Path(__file__).parent))` в начале модуля).

**Проверка (до фикса):**
```powershell
D:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\.venv\Scripts\python.exe -m pytest tests/test_prototype_globalization.py -q -p no:cacheprovider
```
Ожидание: красные все, кроме ничего — A: `RuntimeError` (14, 04a) / `n_substeps == 128` (12) / `AttributeError: globalized`; B: `AttributeError: _line_search_l2`. `test_04a_dense_grid_first_step` до фикса идёт долго (до 512 подшагов на $N = 200$) — допустимо один раз.

**Оценка:** ~230 строк, 30 мин.

### Шаг 2: Прототип — атрибуты, отчёт, линейный поиск, третья ступень

**Файл:** `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/blackoil.py` (стиль файла — плотный, `;` в строке; сохранить).

**2.1 Отчёт** (строки 25-27). До:
```python
    well_branch: str = ''     # BHP control: branch of the accepted step ('open'/'shut'), BUG-014
    well_switches: int = 0    # branch changes in advance's fallback, BUG-014
    fallback: bool = False    # step solved by advance's fallback, BUG-014
```
После — добавить строку:
```python
    well_branch: str = ''     # BHP control: branch of the accepted step ('open'/'shut'), BUG-014
    well_switches: int = 0    # branch changes in advance's fallback, BUG-014
    fallback: bool = False    # step solved by advance's fallback, BUG-014
    globalized: bool = False  # advance's third stage ran (||F||_2 line search, Sg step limit), BUG-016
```

**2.2 Атрибуты** (строки 43-46). До:
```python
        # BUG-014: set by advance's fallback only.  _well_branch forces the BHP
        # well branch for the whole nonlinear solve (None -> chosen from p0);
        # _sg_lower_bound is the line-search bound on Sg of two-phase cells.
        self._well_branch=None; self._sg_lower_bound=-0.05
```
После:
```python
        # BUG-014: set by advance's fallback only.  _well_branch forces the BHP
        # well branch for the whole nonlinear solve (None -> chosen from p0);
        # _sg_lower_bound is the line-search bound on Sg of two-phase cells.
        self._well_branch=None; self._sg_lower_bound=-0.05
        # BUG-016: set by advance's third stage only.  _line_search_l2 accepts a
        # Newton step on a decrease of ||F||_2 instead of ||F||_inf (the Newton
        # direction is a descent direction of ||F||_2^2, not of ||F||_inf);
        # _sg_step_max limits |dSg| of two-phase cells per Newton update by
        # scaling the whole update (Appleyard-type chop, as ds_max in OPM Flow).
        self._line_search_l2=False; self._sg_step_max=None
```

**2.3 Линейный поиск** (`_newton_fixed_active_set`, строки 211-226). До:
```python
    def _newton_fixed_active_set(self,z0,state_old,dt_s,gas_active,max_iter=15,rtol=1e-8,atol_sm3s=1e-11):
        z=np.asarray(z0,float).copy(); f_initial=self.residual(z,state_old,dt_s,gas_active); scale=max(np.linalg.norm(f_initial,np.inf),1e-9)
        for it in range(1,max_iter+1):
            J,f=self.finite_difference_jacobian(z,state_old,dt_s,gas_active); nrm=np.linalg.norm(f,np.inf)
            if nrm<=atol_sm3s+rtol*scale: return z,BlackOilNewtonReport(True,it-1,float(nrm))
            try: dz=self._linear_solve(J,-f)
            except Exception: return z,BlackOilNewtonReport(False,it,float(nrm))
            alpha=1.0; accepted=False
            for _ in range(12):
                trial=z+alpha*dz
                if self._trial_is_reasonable(trial,gas_active):
                    ft=self.residual(trial,state_old,dt_s,gas_active)
                    if np.linalg.norm(ft,np.inf)<nrm: z=trial; accepted=True; break
                alpha*=0.5
            if not accepted: return z,BlackOilNewtonReport(False,it,float(nrm))
```
После:
```python
    def _newton_fixed_active_set(self,z0,state_old,dt_s,gas_active,max_iter=15,rtol=1e-8,atol_sm3s=1e-11):
        z=np.asarray(z0,float).copy(); f_initial=self.residual(z,state_old,dt_s,gas_active); scale=max(np.linalg.norm(f_initial,np.inf),1e-9)
        # BUG-016: norm of the line search; the convergence test stays on ||F||_inf.
        # With defaults the comparison is norm(ft,inf)<nrm, bitwise as before.
        merit=(lambda v: np.linalg.norm(v)) if self._line_search_l2 else (lambda v: np.linalg.norm(v,np.inf))
        for it in range(1,max_iter+1):
            J,f=self.finite_difference_jacobian(z,state_old,dt_s,gas_active); nrm=np.linalg.norm(f,np.inf)
            if nrm<=atol_sm3s+rtol*scale: return z,BlackOilNewtonReport(True,it-1,float(nrm))
            try: dz=self._linear_solve(J,-f)
            except Exception: return z,BlackOilNewtonReport(False,it,float(nrm))
            if self._sg_step_max is not None:
                # BUG-016: scale the whole update (p and Sg together, the Newton
                # direction is kept) so that |dSg| of two-phase cells <= limit
                dsg=np.abs(dz[self.grid.n:][gas_active])
                if dsg.size and dsg.max()>self._sg_step_max: dz=dz*(self._sg_step_max/dsg.max())
            mf=merit(f); alpha=1.0; accepted=False
            for _ in range(12):
                trial=z+alpha*dz
                if self._trial_is_reasonable(trial,gas_active):
                    ft=self.residual(trial,state_old,dt_s,gas_active)
                    if merit(ft)<mf: z=trial; accepted=True; break
                alpha*=0.5
            if not accepted: return z,BlackOilNewtonReport(False,it,float(nrm))
```
Строка 226 (`f=self.residual(z,…); return z,BlackOilNewtonReport(False,max_iter,…)`) — без изменений. При атрибутах по умолчанию `mf = norm(f, inf) = nrm` — сравнение то же, что было.

**2.4 `advance` и `_fallback`** (строки 227-263). Тело запасного пути BUG-014 (от `self._sg_lower_bound=None` до `finally`) **переносится без изменений** в новый метод `_fallback`; `advance` вызывает его один раз обычным и, при отказе, второй раз с атрибутами BUG-016. До (строки 227-240 — начало; 241-263 — переносимое тело):
```python
    def advance(self,state_old,dt_s,max_active_iter=12,max_newton=15):
        """One implicit step: the original algorithm; on failure a fallback with the
        BHP well branch as an outer constraint and no lower bound on Sg (BUG-014)."""
        new,rep=self._advance_phases(state_old,dt_s,max_active_iter,max_newton)
        if rep.converged:
            if self.control_mode=='BHP':
                # branch the automatic rule takes on the accepted state
                p0=float(new.pressure_bar[0])
                rep.well_branch='shut' if p0<=float(self.p_bhp_bar) else 'open'
            return new,rep
        # Fallback only: where the original algorithm converges, results stay
        # bitwise; with the bound removed always, deep drawdowns needed more
        # step splitting than before (BUG-014 audit).
        self._sg_lower_bound=None
        try:
```
После:
```python
    def advance(self,state_old,dt_s,max_active_iter=12,max_newton=15):
        """One implicit step: the original algorithm; on failure a fallback with the
        BHP well branch as an outer constraint and no lower bound on Sg (BUG-014);
        if that fails too, the fallback again with a globalized Newton (BUG-016)."""
        new,rep=self._advance_phases(state_old,dt_s,max_active_iter,max_newton)
        if rep.converged:
            if self.control_mode=='BHP':
                # branch the automatic rule takes on the accepted state
                p0=float(new.pressure_bar[0])
                rep.well_branch='shut' if p0<=float(self.p_bhp_bar) else 'open'
            return new,rep
        # Fallback only: where the original algorithm converges, results stay
        # bitwise; with the bound removed always, deep drawdowns needed more
        # step splitting than before (BUG-014 audit).
        new,rep=self._fallback(state_old,dt_s,max_active_iter,max_newton)
        if rep.converged: return new,rep
        # Third stage (BUG-016), only where the fallback fails too, so every step
        # the first two stages solve stays bitwise.  Mass phase activation with a
        # closed-flash Sg guess (0.55-0.71 at Rs0 = 150 against 0.22 in the
        # solution) stalls the ||F||_inf line search; step splitting does not help.
        # Measured alternatives: in the fallback itself example 03 got worse, in
        # every step example 10 got worse (plan BUG-016, 1.3).
        self._line_search_l2=True; self._sg_step_max=0.2
        try:
            new,rep=self._fallback(state_old,dt_s,max_active_iter,max_newton)
            rep.globalized=True; return new,rep
        finally:
            self._line_search_l2=False; self._sg_step_max=None
    def _fallback(self,state_old,dt_s,max_active_iter,max_newton):
        """BUG-014 fallback: no lower bound on Sg; BHP control fixes the well branch
        (start from the old state's branch, accept a consistent result only, try the
        other branch once); OIL_RATE control: a plain retry without the Sg bound."""
        self._sg_lower_bound=None
        try:
```
Остальное (от `            if self.control_mode!='BHP':` до `            self._sg_lower_bound=-0.05; self._well_branch=None`) — **без изменений, те же отступы** (12 пробелов в `try`, 16 — в `while`): текст уже принадлежит телу `_fallback`, потому что стоит после его заголовка.

**Проверка после шага:**
```powershell
D:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\.venv\Scripts\python.exe -m pytest tests/test_prototype_globalization.py tests/test_prototype_well_branch.py -q -p no:cacheprovider
```
Ожидание: `test_prototype_globalization.py` — все зелёные; `test_prototype_well_branch.py` — **2 красных** (`test_all_fail`, `test_both_branches_inconsistent`) — шаг 3.

**Зависимости:** требует шаг 1. **Оценка:** ~25 строк, 20 мин.

### Шаг 3: Тесты, закреплявшие старое поведение

**3.1** `numerical_solver/tests/test_prototype_well_branch.py`, `TestAdvanceBranchLogic`:

- `test_all_fail` (строки ~351-360): третья ступень повторяет запасной путь — ещё два вызова с теми же ключами (ключ здесь — (ветка, граница), флаг $\|F\|_2$ в него не входит). До:
  ```python
          # Отказ везде: после двух веток запасной путь сдаётся, converged = False —
          # адаптер раздробит шаг, как раньше.
          ...
          assert calls == [ORIGINAL, ("shut", None), ("open", None)]
  ```
  После:
  ```python
          # Отказ везде: после двух веток запасной путь сдаётся; третья ступень
          # (BUG-016) повторяет его с ||F||_2 и ограничителем dS_g — тоже отказ.
          # converged = False — адаптер раздробит шаг, как раньше.
          ...
          assert calls == [ORIGINAL, ("shut", None), ("open", None), ("shut", None), ("open", None)]
  ```
  `_fields(rep) == (False, "open", 1, True)` — без изменений (поля последнего вызова запасного пути).
- `test_both_branches_inconsistent` (~362-372): то же — `calls` из пяти элементов; комментарий дополнить: «третья ступень (BUG-016) повторяет обе ветки — снова несогласованы».

**3.2** `numerical_solver/tests/test_energy_matrix_examples.py`, строки 701-707. До:
```python
# Примеры, где A-retry реально срабатывает (замерено):
#   10_deep_degassing        — один шаг 3600 с раздроблен на 2 × 1800 с
#   11_degassing_at_boundary — один шаг 3600 с раздроблен на 16 × 225 с
#   12_large_drainage_radius — один шаг 3600 с раздроблен на 128 × 28.125 с
# На остальных конфигах дробления нет и проверять нечего.
SUBDIVIDING_EXAMPLES = ["10_deep_degassing", "11_degassing_at_boundary",
                        "12_large_drainage_radius"]
```
После:
```python
# Примеры, где A-retry реально срабатывает (замерено):
#   10_deep_degassing        — один шаг 3600 с раздроблен на 2 × 1800 с
# У 11 (16 × 225 с) и 12 (128 × 28.125 с) дробление снято третьей ступенью
# advance (BUG-016): первый шаг сходится целиком.
# На остальных конфигах дробления нет и проверять нечего.
SUBDIVIDING_EXAMPLES = ["10_deep_degassing"]
```
Экземпляров теста становится на 2 меньше.

**3.3** `numerical_solver/tests/test_examples.py`, `test_dense_grid_converges_at_default_retries` (строки 1281-1302, 1312-1316): тест остаётся (проверяет $N = 80$ на штатном лимите), меняется только обоснование. Заменить в докстринге «Здесь нужно ровно 9 удвоений (512 подшагов, замер 2026-09-25) — весь штатный лимит. Дробится только первый шаг: … (механизм — BUG-008). Уменьшение dt_integration не помогает: A-retry дробит шаг внутри.» на «До BUG-016 здесь требовались все 9 удвоений (512 подшагов, замер 2026-09-25): первый шаг — скачок p_wf 20 -> 4 МПа переводит под pb около половины ячеек разом (BUG-008). С третьей ступенью advance (BUG-016) шаг сходится без дробления; тест держит достаточность умолчания и для этого класса задач.»; фразы «Запаса нет и при N = 80: первый шаг использует все 9 удвоений, с лимитом 8 тест упадёт.» и в комментарии «Запаса нет и здесь: при N = 80 нужны все 9.» — удалить. Утверждения теста не менять.

**Проверка:**
```powershell
D:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\.venv\Scripts\python.exe -m pytest tests/test_prototype_well_branch.py tests/test_prototype_globalization.py tests/test_energy_matrix_examples.py -k "not matrix_matches_reference" -q -p no:cacheprovider
```
**Зависимости:** шаг 2. **Оценка:** ~20 строк, 15 мин.

### Шаг 4: Полная регрессия

```powershell
D:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\.venv\Scripts\python.exe -m pytest tests/ -q -p no:cacheprovider
```
Ожидание: **1003 − 2 (`SUBDIVIDING_EXAMPLES` без 11 и 12) + 11 новых (A: 2 экземпляра примера 14 + 04a + 12 + ограничитель = 5; B: 6) = 1012** — пересчитать по факту; все зелёные; время ≈ 350–400 с (было ~557: 04a и 12 без дробления). Если упал тест с числами 04a, 11 или 12 — это ожидаемое изменение старта (§1.3): сверить с `readme_runs/` и поправить ожидание **только** если отличие объясняется дискретизацией старта (не корнем Ньютона).

Тесты прототипа:
```powershell
D:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\.venv\Scripts\python.exe -m pytest HydroSolverPrototype/Prototype_1.0.3/tests -q -p no:cacheprovider
Remove-Item -Recurse -Force HydroSolverPrototype/Prototype_1.0.3/OUTPUT/short_run -ErrorAction SilentlyContinue
```
Ожидание: 70 passed, 10 failed ([[DEBT-024]], как до правки).

Побитовость 13 примеров (из `numerical_solver` **основного** каталога — пробы ставят патч сами; для реализованного кода — режим `orig` в worktree с `PYTHONPATH`):
```powershell
$env:PYTHONPATH = "D:\Lessons\Grants\2026\GPN\Oil_Gas\.worktrees\bug-016\numerical_solver"
D:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\.venv\Scripts\python.exe ..\..\..\vault\issues\bug-016\probes\regress_examples.py impl orig
D:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\.venv\Scripts\python.exe ..\..\..\vault\issues\bug-016\probes\compare_regress.py tier3_chop02 impl
```
(`regress_examples.py` берёт примеры из `patch.NS` — основного каталога; прототип — через `PYTHONPATH` worktree. Проверить печатью `radial_blackoil.__file__`, при расхождении — поправить `NS` в пробе.) Ожидание: **все 16 — побитово** с прогоном пробы `tier3_chop02` (реализация = проба).

**Зависимости:** шаг 3. **Оценка:** 25 мин (в основном ожидание).

### Шаг 5: README примеров

Числа — прогоном `main.py` в worktree (`$env:PYTHONPATH` на worktree). Сверка «до / после» уже снята (`readme_runs/{orig,t3chop}/<пример>.txt`, консоль `run_example`); отличаются только последние знаки:

| пример | строка консоли | до | после |
|---|---|---|---|
| 04a | $T(r_w)$ финал | 352.239 | 352.238 |
| 04a | $q_o$ / $q_g$ финал | 4.9408e-03 / 1.4825e-01 | 4.9409e-03 / 1.4826e-01 |
| 04a | замкнутое решение: $q_o$ расчёт, расхождение | 4.940813e-03, 0.549 % | 4.940866e-03, 0.550 % |
| 04a | $\max\lvert p_{ана} - p_{чис}\rvert$ | 35.90 кПа | 35.87 кПа |
| 04a | невязка баланса | 1.47e-12 | 3.89e-14 |
| 04a | асимптотика, $\max\lvert\Delta T\rvert$ | 1.2394 К | 1.2395 К |
| 11 | $T(r_w)$ / $S_g^{max}$ | 350.422 / 0.02010 | 350.421 / 0.02012 |
| 11 | $q_o$ / $q_g$ | 3.7695e-03 / 1.1722e-01 | 3.7692e-03 / 1.1733e-01 |
| 11 | замкнутое решение: $q_o$ расчёт, расхождение; $\max\lvert\Delta p\rvert$ | 3.769496e-03, 0.186 %; 13.92 кПа | 3.769194e-03, 0.178 %; 14.11 кПа |
| 11 | невязка баланса | 1.01e-12 | 1.16e-13 |
| 12 | $S_g^{max}$ / $q_g$ | 0.02393 / 1.1869e-01 | 0.02394 / 1.1871e-01 |
| 12 | замкнутое решение: расхождение; $\max\lvert\Delta p\rvert$ | 1.427 %; 63.35 кПа | 1.429 %; 63.39 кПа |
| 12 | невязка баланса | 1.54e-11 | 2.50e-11 |

Известные вхождения (grep 2026-09-30): README 04a — строки 182 (352.239), 195–198 (таблица «Переходный процесс», §1.3), 220 (4.940813e-3, 0.549 %), 384 (строка $N = 150$ сеточной таблицы: 4.940813e-3); сводный README — строки 275 (04a: $4.9408\cdot10^{-3}$), 280 (11: $3.7695\cdot10^{-3}$, 0.19 % → 0.18 %) и таблица баланса энергии (невязки 04a, 11, 12). Остальные — поиском по значениям «до» из таблицы выше во всех README примеров.

**5.1** `numerical_solver/examples/04a_high_gas_saturation/README.md`:
- строка 153 (таблица параметров): `| numerics.max_retries | **12** (по умолчанию 9) | см. «Первый шаг» |` — оставить (решение 3), текст ссылки не менять;
- раздел «Первый шаг» (строки 167-173): «Решатель дробит этот шаг на 512 подшагов по 0.59 с (9 удвоений) — ровно штатный предел `max_retries = 9`, поэтому в конфиге стоит 12. К концу первого шага газ есть в 60 ячейках.» → «Исходный алгоритм и запасной путь BUG-014 этот шаг не решают; третья ступень `advance` (BUG-016 — линейный поиск по $\|F\|_2$ и ограничитель $\lvert\Delta S_g\rvert \le 0.2$) решает его целиком, без дробления. До BUG-016 шаг дробился на 512 подшагов по 0.59 с — ровно штатный предел, поэтому в конфиге стоит `max_retries = 12`; значение оставлено, на расчёт оно больше не влияет. К концу первого шага газ есть в NN ячейках.» (NN — из `run_example`/`profiles.csv` записи 1);
- строка 412 (таблица «как модифицировать» или отличий — сверить контекст): `max_retries` 12 — оставить;
- строка 445: `| grid.N | 25…150 считаются при max_retries = 12; при бо́льших N первый шаг требует больше удвоений (BUG-008) |` → `| grid.N | первый шаг при штатном max_retries = 9: N ≤ 200 — без дробления, 300 — 2 подшага, 500 — 8 (BUG-016; до него — до 16384 подшагов, BUG-008) |`;
- таблица «Переходный процесс» (строки 193–198) — значения §1.3; под таблицей одна фраза: «Столбец 5 мин — первый шаг решателя (300 с) целиком; до BUG-016 этот шаг дробился на 512 подшагов, и столбец давал почти точный переходный процесс ($T(r_w) = 350.51$ К против 349.97 К теперь). Для точного раннего отклика нужен мелкий начальный шаг в `time.history`.»; проверить текст под таблицей («отклонение $q_o$ от финального — 13 % через 1 ч…») — пересчитать по новым значениям;
- ранние профили (`plot_profiles_50k.py`) — перерисовываются из `profiles.csv`, текстом не описаны числами — проверить.

**5.2** `numerical_solver/examples/11_degassing_at_boundary/README.md`:
- строка 75: «минимум 349.37 К через 1 ч» → «минимум 349.31 К через 1 ч» (§1.3; первый шаг теперь 3600 с целиком вместо 16 × 225 с); строки 74–76 таблицы — $T(r_w)$ 350.42 без изменений (350.421), $q_o$ $3.769\cdot10^{-3}$ без изменений;
- строки 78-79: «На первом интервале гидравлический шаг дробится на 16 подшагов по 225 с, дальше идёт без дробления.» → «Первый шаг сходится целиком (третья ступень `advance`, BUG-016); до BUG-016 он дробился на 16 подшагов по 225 с.»;
- строки 128-130: «При $p_0 = 15.05$ и $15.1$ МПа расчёт проходит. При $p_0 = 15.2$ МПа гидравлический решатель не сходится после 512 подшагов (`numerics.max_retries = 9`, значение по умолчанию).» → «При $p_0 = 15.05$, $15.1$ и $15.2$ МПа расчёт проходит (15.2 МПа — с BUG-016: $T(r_w) = 350.481$ К, $q_o = 3.871\cdot10^{-3}$ м³ст/с на 3 сут; до него — отказ после 512 подшагов).»;
- строки 134-135 («При $p \approx p_b$ решатель дробит шаг; на более мелкой сетке может потребоваться увеличить `numerics.max_retries`.») — оставить, если прогон на $N = 100$ это подтверждает, иначе убрать первую половину (проверить одним прогоном `readme_claims.py`-подобной правкой `grid.N = 100`).

**5.3** `numerical_solver/examples/12_large_drainage_radius/README.md`:
- строки 99-100: «На первом подшаге гидравлический шаг дробится на 128 подшагов по 28.125 с, дальше идёт без дробления.» → «Первый шаг сходится целиком (третья ступень `advance`, BUG-016); до BUG-016 он дробился на 128 подшагов по 28.125 с.»;
- строки 205-206: «Сутки как шаг интегрирования не годятся: гидравлический решатель не сходится и после 512 подшагов.» → «Суточный шаг интегрирования сходится (с BUG-016; до него — отказ после 512 подшагов): $T(r_w) = 350.333$ К против 350.351 К при часовом шаге, $q_o = 3.2287\cdot10^{-3}$ м³ст/с на 15 сут.» (часовое значение — из README 12, сверить);
- строки 209-210 — оставить;
- числа таблиц по суткам — по сверке `readme_runs` (конец истории: $\lvert\Delta p\rvert$ 47 Па, $\lvert\Delta T\rvert$ $7.6\cdot10^{-4}$ К — в печатаемых знаках скорее всего без изменений).

**5.4** `numerical_solver/examples/README.md`, таблица времени (строки ~147-157): 04a, 11, 12 — замерить `main.py` (без параллельной нагрузки); итог «около 9 мин» и строка ~505 «(~9 мин)» — пересчитать (ожидается около 8 мин: 04a −60…70 с, 12 −15 с).

**Проверка:** `pytest tests/test_examples.py -k "Readme or required_files" -q -p no:cacheprovider`.

**Зависимости:** шаг 4. **Оценка:** 40 мин.

### Шаг 6: Документация прототипа, vault, issue

1. `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/CHANGELOG_1.0.3.md` — после раздела BUG-014:
   ```markdown
   ## Local changes — GPN project (BUG-016)
   - Problem: with a high initial Rs (Rs0 = 150) and a sharp BHP drop, the first step did not converge on grids N >= 100 at any step split. The phase active set activates tens of cells at once with a closed-flash Sg guess (0.55-0.71 against 0.22 in the solution); the Newton direction then does not decrease ||F||_inf for any alpha, and the line search (12 halvings) stalls. The BUG-014 fallback fails the same way.
   - `advance()`: a third stage, only when the original algorithm and the BUG-014 fallback both fail — the fallback (moved verbatim into `_fallback()`) is run again with `_line_search_l2 = True` (a Newton step is accepted on a decrease of ||F||_2; the convergence test stays on ||F||_inf) and `_sg_step_max = 0.2` (the whole update is scaled so that |dSg| of two-phase cells <= 0.2, as ds_max in OPM Flow). Wherever the first two stages converge, results are bitwise the same as before.
   - Outside `advance()` both attributes keep their defaults (`False`, `None`), also after an exception (`try/finally`).
   - `BlackOilNewtonReport`: new field `globalized` (the third stage ran), default `False`.
   - Effect on the GPN examples: 13 of 16 bitwise; 04a, 11, 12 no longer split their first step (99.8 -> 40 s, 6.6 -> 3.6 s, 27.6 -> 15 s); first-step splitting of 04a on N = 150...500 drops from 512...16384 to 1...8 substeps.
   - Physics, residual equations, tolerances and well semantics are unchanged. `PACKAGE_MANIFEST_SHA256.txt` is not updated.
   - Issue: https://github.com/ArturSalamatin/Oil_Gas/issues/44; plan: `vault/plans/bug-016 newton-line-search-norm.md` of the GPN project.
   ```
2. `vault/roadmap/известные баги и технический долг.md`:
   - BUG-016: **Результат**, **Отклонения от плана**, **Статус** ✅ ИСПРАВЛЕНО <дата>;
   - [[BUG-008]]: статус ✅ ИСПРАВЛЕНО <дата> — «закрыт BUG-016: первый шаг 04a при штатном `max_retries = 9` — $N \le 200$ без дробления, 300 — 2, 500 — 8 подшагов (было 512…16384)»;
   - [[DEBT-025]]: статус ✅ ЗАКРЫТ <дата> — «первый час примера 12 без дробления (BUG-016)».
3. `vault/00-home/index.md` — план в секции планов.
4. Комментарий в #44 — `vault/issues/bug-016/05-comment-done.md`.
5. Коммиты (без упоминания Claude): `fix: третья ступень advance — Ньютон с поиском по ||F||_2 и ограничителем dSg (BUG-016)` (шаги 1–3), `docs: README 04a, 11, 12 и сводный — первый шаг без дробления (BUG-016)` (шаг 5 + CHANGELOG), `vault: BUG-016 исправлен; BUG-008, DEBT-025 закрыты`.

**Зависимости:** шаг 5. **Оценка:** 25 мин.

## 4. Тестовая стратегия

| тест | файл | сценарий | ожидание | предотвращает |
|---|---|---|---|---|
| `test_example14_fine_grid_first_step[100,150]` | новый | пример 14, первый суточный шаг | 1 подшаг; $S_g[0]$, $p[0]$ по §1.4 | возврат отказа BUG-016 |
| `test_04a_dense_grid_first_step` | новый | 04a $N = 200$, штатный `max_retries` | 1 подшаг | возврат BUG-008 |
| `test_example12_first_hour_not_split` | новый | 12, первый час | 1 подшаг | возврат DEBT-025 |
| `test_sg_step_limited_in_third_stage` | новый | 14 $N = 100$, итерации третьей ступени | $\max\lvert\Delta S_g\rvert \le 0.2$, `globalized` | потерю ограничителя |
| `TestThirdStageLogic` (6) | новый | подмена `_advance_phases` | порядок ступеней, флаги, сброс атрибутов, исключение, дебит | третью ступень не там, утечку атрибутов |
| `test_all_fail`, `test_both_branches_inconsistent` | BUG-014 | обновлены | 5 вызовов | — |
| весь `tests/` | — | регрессия | зелёные; числа 13 примеров — побитово (фикстура `results`) | — |
| `compare_regress.py tier3_chop02 impl` | проба | 16 примеров | побитово с пробой | расхождение реализации с измеренным вариантом |

## 5. Критерии завершения

- [ ] Тесты шага 1 — сначала красные, после шага 2 — зелёные
- [ ] `test_all_fail`, `test_both_branches_inconsistent`, `SUBDIVIDING_EXAMPLES` обновлены
- [ ] Полный `tests/` зелёный; тесты прототипа — 70 / 10, как до правки
- [ ] Реализация побитово совпадает с пробой `tier3_chop02` на 16 примерах
- [ ] README 04a, 11, 12 и сводный — перемерены, утверждения §1.5 исправлены
- [ ] CHANGELOG прототипа, реестр (BUG-016, BUG-008, DEBT-025), index, #44

## 6. Как начать работу по этому плану

1. Прочитай план целиком; запись BUG-016 в реестре; issue #44 (тело — `vault/issues/bug-016/01-issue-body.md`).
2. Прочитай [[bug-014 well-shutin-active-set]] §2 (вариант F — образец «ступени только при отказе») и `CHANGELOG_1.0.3.md`, раздел BUG-014.
3. Шаг 0: worktree `.worktrees/bug-016` (рабочее дерево основного каталога делят параллельные сессии), baseline.
4. Шаг 1 → красные; шаг 2 → зелёные; дальше по порядку.
5. Пробы — `vault/issues/bug-016/probes/` (в `.gitignore`, в worktree их нет — запускать из основного каталога, с `PYTHONPATH` на worktree, когда нужен реализованный код).

## 7. Связанные

- [[BUG-008]] — 04a на подробной сетке; закрывается этим фиксом
- [[DEBT-025]] — дробление первого часа примера 12; закрывается
- [[BUG-014]], [[bug-014 well-shutin-active-set]] — запасной путь `advance`, образец варианта «только при отказе»
- [[DEBT-007]] — подсказка адаптера про `max_retries` (не меняется)
- [[FEAT-024]] — пример 14; [[feat-024 high-gor-cooling-example]]
- [[DEBT-024]] — 10 падений тестов прототипа без `xlsxwriter`
