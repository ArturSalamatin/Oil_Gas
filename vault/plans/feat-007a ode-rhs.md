---
tags:
  - план
  - вычисление
date: 2026-07-31
issue: FEAT-007a
github: 9
branch: feat/feat-007a/ode-rhs
model_level: М.6
status: в процессе
audit:
  date: 2026-07-31
  found: 0
  auto-fixed: 0
  manual-required: 0
  rounds: 7
  note: раунд 4 — прогон np.float64 совместимости, solve_ivp(Radau) интеграция, cond(A) при rb→rw
---

# FEAT-007a: Правая часть ODE — rhs(t, y) для solve_ivp

## Как начать работу по этому плану

1. Прочитай этот файл целиком
2. Прочитай `moments_method.tex`, строки 673–688 (уравнение `\eqref{eq:ode_system}`) и 1580–1663 (жёсткость, обезразмеривание)
3. Прочитай `method_of_moments/src/coefficients.py`, строки 1–18 (`OdeState`) и 497–519 (`assemble_ode_system`)
4. Прочитай `method_of_moments/tests/test_coefficients.py`, строки 626–708 (класс `TestAssembly`)
5. Создай ветку: `git checkout -b feat/feat-007a/ode-rhs`
6. Прогони тесты (baseline): `cd method_of_moments && .venv/Scripts/python -m pytest tests/ -v`
   - Ожидаемый baseline: **282 теста**, все зелёные
7. Начни с шага 1. После каждого шага: pytest

---

## Подтип

**Вычисление** — клей между `assemble_ode_system()` (FEAT-005d) и `solve_ivp` (FEAT-007b).

## Зависимости

- **FEAT-005d** ([#8](https://github.com/ArturSalamatin/Oil_Gas/issues/8)) ✅ реализован — `assemble_ode_system()` в `coefficients.py`
- **FEAT-007b** — зависит от этой задачи (обёртка solver)

## Формулы → код

| Формула | Уравнение в tex | Python-функция | Модуль | Тест |
|---|---|---|---|---|
| A·ẋ = F → ẋ = A⁻¹·F | `\eqref{eq:ode_system}` | `make_rhs()` → `rhs(t, y)` | `method_of_moments/src/ode_system.py` | `test_rhs_*` |

Единственная «формула» — решение линейной системы. Всё содержательное вычисление (A, F) уже в `coefficients.py`.

## Физика / математика

Система \eqref{eq:ode_system} из `moments_method.tex`:

```
┌                         ┐ ┌       ┐   ┌      ┐
│ A₁₁   0    A₁₃         │ │ ṙ_b   │   │ F₁   │
│ A₂₁   A₂₂  A₂₃        │·│ Ṡg_w  │ = │ F₂   │
│ A₃₁   0    A₃₃         │ │ Δ̇T_w  │   │ F₃   │
└                         ┘ └       ┘   └      ┘
```

Структура \eqref{eq:matrix_structure}: A₁₂ = 0, A₃₂ = 0.

**Жёсткость** (§7.2 moments_method.tex, строка 1625): отношение масштабов χ₀/a ~ 10⁶–10⁷, со смягчением до 10³–10⁴. Необходим неявный интегратор — Radau или BDF.

**Обусловленность** (§7.2, строка 1647): без обезразмеривания cond(A) ~ 10¹⁵. Обезразмеривание — отдельная задача (не в скоупе FEAT-007a, но `rhs` должен работать и без него — `np.linalg.solve` справится при условии, что матрица не вырождена, что проверено в FEAT-005d).

## Обратная совместимость

- [x] Существующие тесты не затрагиваются — создаётся **новый** модуль и **новый** файл тестов
- [x] Существующие конфиги не меняются
- [x] API `coefficients.py` не меняется — `OdeState` и `assemble_ode_system` используются как есть
- [x] Нет circular imports: `ode_system.py` → `coefficients.py` (однонаправленная зависимость)

## Варианты решения

### Вариант A: Фабрика make_rhs() с замыканием (рекомендуемый)

```python
def make_rhs(fluid, rock, p_profile, t_profile, s_profile, p_wf, dp_wf_dt=0.0):
    def rhs(t, y):
        r_b, Sg_w, dT_w = y
        state = OdeState(r_b=r_b, Sg_w=Sg_w, dT_w=dT_w, p_wf=p_wf, dp_wf_dt=dp_wf_dt)
        A, F = assemble_ode_system(fluid, rock, p_profile, t_profile, s_profile, state)
        return np.linalg.solve(A, F)
    return rhs
```

- **Плюсы:** чистая функция, совместима с `solve_ivp(fun=rhs, ...)` без дополнительных обёрток, замыкание фиксирует параметры задачи
- **Минусы:** `p_wf` фиксируется при создании; для переменного `p_wf(t)` нужна модификация
- **Трудоёмкость:** ~20 строк

### Вариант B: Класс OdeRHS с __call__

```python
class OdeRHS:
    def __init__(self, fluid, rock, ...):
        self.fluid = fluid; ...
    def __call__(self, t, y):
        ...
```

- **Плюсы:** расширяемость (можно добавить кэширование, счётчик вызовов)
- **Минусы:** избыточная абстракция для текущей задачи; CLAUDE.md: «не добавляй абстракции сверх задачи»
- **Трудоёмкость:** ~30 строк

### Выбор: **Вариант A**

Критерий: простота, достаточная для FEAT-007b. Расширение до `p_wf(t)` — через callable check в `make_rhs`.

## Подводные камни

- ✅ **Численная устойчивость:** `np.linalg.solve` стабилен при cond(A) ≤ 10¹⁵ (float64 имеет ~15 значащих цифр). Тест FEAT-005d подтверждает: det(A) ≠ 0 при baseline. Для плохо обусловленных систем потеря точности возможна, но при baseline параметрах — безопасно.
- ✅ **Граничные случаи:** при `r_b ≈ r_w` или `Sg_w ≈ 0` матрица может ухудшить обусловленность. Тест `test_small_Sg` в FEAT-005d показал — A и F конечны и det(A) ≠ 0.
- ✅ **Import-цепочки:** `ode_system.py` → `coefficients.py` → `profiles/`, `pvt/` — линейная цепочка, без циклов.
- ⚠️ **p_wf(t):** issue упоминает «скаляр или callable». В FEAT-007a реализуем **только скаляр** (стационарный p_wf). Callable `p_wf(t)` — расширение для FEAT-007b или отдельная задача. Причина: в `OdeState.p_wf` — скаляр, `dp_wf_dt` — скаляр. Для переменного p_wf нужно менять API OdeState.
- ✅ **Аллокация:** `OdeState` (dataclass) + `np.zeros((3,3))` + `np.array([...])` на каждый вызов. Для Radau (~100–1000 вызовов rhs) — пренебрежимо. Профилирование — в FEAT-007b.
- ✅ **Формулы vs код:** единственная «формула» — `np.linalg.solve(A, F)`. Всё остальное делегировано в `coefficients.py`.

## Новые обнаруженные проблемы

Нет блокирующих проблем.

Неблокирующие (после завершения):
- Обезразмеривание (§7.2 moments_method.tex, строка 1647) — cond(A) ~ 10¹⁵ без масштабирования. Потенциальная потеря точности при экстремальных параметрах. Рекомендация: создать FEAT по обезразмериванию, если валидация (VAL-001) покажет проблемы.

---

## Этапы реализации

### Шаг 1: Создать модуль `ode_system.py` с `make_rhs()`

**Цель:** реализовать фабрику правой части ODE.

**Файлы:** `method_of_moments/src/ode_system.py` (новый)

**Контекст:**

`solve_ivp` из scipy ожидает callable `fun(t, y) → dy_dt`, где `y` — вектор состояния (ndarray). Функция `assemble_ode_system()` в `coefficients.py:497` принимает 6 аргументов (fluid, rock, p_profile, t_profile, s_profile, state) и возвращает `(A, F)` — матрицу 3×3 и вектор 3. Фабрика `make_rhs()` замыкает все параметры задачи и возвращает функцию с сигнатурой `(t, y) → ndarray(3)`.

Вектор состояния: `y = [r_b, Sg_w, dT_w]` — индексы 0, 1, 2.

**Формулы:**

Матричная форма \eqref{eq:ode_system}:

```
A · ẋ = F
```

Решение:

```
ẋ = A⁻¹ · F = np.linalg.solve(A, F)
```

Компоненты ẋ:
- ẋ[0] = ṙ_b  (скорость движения фронта разгазирования, м/с)
- ẋ[1] = Ṡg_w (скорость изменения насыщенности газа на забое, 1/с)
- ẋ[2] = Δ̇T_w (скорость изменения температуры на забое, К/с)

**Что сделать:**

1. Создать файл `method_of_moments/src/ode_system.py`
2. Импорты:
   ```python
   import numpy as np
   from .coefficients import OdeState, assemble_ode_system
   ```
3. Реализовать `make_rhs(fluid, rock, p_profile, t_profile, s_profile, p_wf, dp_wf_dt=0.0)`:
   - Docstring: одна строка + ссылка на `\eqref{eq:ode_system}`
   - Внутри определить `rhs(t, y)`:
     - `r_b, Sg_w, dT_w = y`
     - Создать `OdeState(r_b=r_b, Sg_w=Sg_w, dT_w=dT_w, p_wf=p_wf, dp_wf_dt=dp_wf_dt)`
     - `A, F = assemble_ode_system(fluid, rock, p_profile, t_profile, s_profile, state)`
     - `return np.linalg.solve(A, F)`
   - Вернуть `rhs`

**Изменения:**

Новый файл, ~20 строк:

```python
"""Правая часть ODE метода моментов — §5 moments_method.tex."""

import numpy as np

from .coefficients import OdeState, assemble_ode_system


def make_rhs(fluid, rock, p_profile, t_profile, s_profile, p_wf, dp_wf_dt=0.0):
    """Фабрика rhs(t, y) для solve_ivp. Ур. (eq:ode_system) moments_method.tex."""

    def rhs(t, y):
        r_b, Sg_w, dT_w = y
        state = OdeState(
            r_b=r_b, Sg_w=Sg_w, dT_w=dT_w,
            p_wf=p_wf, dp_wf_dt=dp_wf_dt,
        )
        A, F = assemble_ode_system(
            fluid, rock, p_profile, t_profile, s_profile, state,
        )
        return np.linalg.solve(A, F)

    return rhs
```

**Проверка после шага:**
- Импорт без ошибок: `.venv/Scripts/python -c "from src.ode_system import make_rhs"`
- Регрессия: `.venv/Scripts/python -m pytest tests/ -v`

**Подводные камни:** нет — шаг тривиален.
**Зависимости:** Требует: ничего. Блокирует: шаг 2.
**Оценка:** ~20 строк, ~5 минут.

---

### Шаг 2: Тесты правой части

**Цель:** написать тесты для `make_rhs()` / `rhs()`.

**Файлы:** `method_of_moments/tests/test_ode_system.py` (новый)

**Контекст:**

Тестовая инфраструктура из `test_coefficients.py`:
- Фикстуры: `baseline_config`, `fluid`, `rock`, `p_profile`, `t_profile`, `s_profile`
- Константы: `P_WF = 15e6`, `P_0 = 20e6`, `P_B = 18e6`, `T_0 = 350.0`, `SG_BASELINE = 0.1`, `R_W = 0.1`, `R_EXT = 500.0`, `SIGMA = 2.0`, `BETA = 2.0`
- Хелпер: `_make_state(r_b=5.0, Sg_w=0.1, dT_w=2.0, p_wf=P_WF, dp_wf_dt=0.0)`

Фикстуры дублируем — тесты должны быть самодостаточны (файл-уровень, не зависеть от другого тест-файла). Можно извлечь в conftest.py, но это рефакторинг (DEBT), не в скоупе.

**Что сделать:**

1. Создать `method_of_moments/tests/test_ode_system.py`
2. Импорты: pytest, numpy, json, Path, BlackOilFluid, PressureProfile, TemperatureProfile, SaturationProfile, make_rhs, OdeState, assemble_ode_system
3. Дублировать фикстуры из `test_coefficients.py`: `baseline_config`, `fluid`, `rock`, `p_profile`, `t_profile`, `s_profile`, константы
4. Фикстура `rhs_func` — создаёт `make_rhs(fluid, rock, p_profile, t_profile, s_profile, P_WF)`
5. Реализовать тесты (ниже)

**Тесты:**

```
Тест: test_rhs_returns_ndarray
Файл: method_of_moments/tests/test_ode_system.py (новый)
Сценарий: rhs(0, y) возвращает ndarray длины 3
Setup: y = [5.0, 0.1, 2.0] (baseline)
Ожидание: isinstance(result, np.ndarray), len == 3
Предотвращает: несовместимость с solve_ivp (ожидает array-like)
```

```
Тест: test_rhs_all_finite
Файл: method_of_moments/tests/test_ode_system.py (новый)
Сценарий: все компоненты ẋ конечны при baseline
Setup: y = [5.0, 0.1, 2.0]
Ожидание: np.all(np.isfinite(result))
Предотвращает: NaN/Inf из-за вырожденной матрицы или некорректных PVT
```

```
Тест: test_rhs_dot_rb_positive
Файл: method_of_moments/tests/test_ode_system.py (новый)
Сценарий: ṙ_b > 0 — фронт разгазирования расширяется
Setup: y = [5.0, 0.1, 2.0]
Ожидание: result[0] > 0
Формула: \eqref{eq:ode_system} — при baseline A₁₁ < 0, F₁ < 0 ⟹ ṙ_b = F₁/A₁₁ > 0
Предотвращает: знаковая ошибка (перепутаны строки A или F)
```

```
Тест: test_rhs_matches_manual_solve
Файл: method_of_moments/tests/test_ode_system.py (новый)
Сценарий: ẋ из rhs() совпадает с ручным np.linalg.solve(A, F)
Setup: y = [5.0, 0.1, 2.0], state = OdeState(...)
Ожидание: rhs(0, y) == pytest.approx(np.linalg.solve(A, F))
Предотвращает: ошибка в распаковке y или передаче параметров в OdeState
```

```
Тест: test_rhs_small_Sg
Файл: method_of_moments/tests/test_ode_system.py (новый)
Сценарий: rhs конечен при малом Sg_w ≈ 0.01 и rb ≈ rw
Setup: y = [0.2, 0.01, 0.1]
Ожидание: np.all(np.isfinite(result))
Предотвращает: вырождение матрицы при граничных состояниях
```

```
Тест: test_rhs_pure_function
Файл: method_of_moments/tests/test_ode_system.py (новый)
Сценарий: два вызова rhs с одинаковым y дают одинаковый результат
Setup: y = [5.0, 0.1, 2.0]
Ожидание: rhs(0, y) == rhs(0, y) (покомпонентно approx)
Предотвращает: побочные эффекты (если кто-то добавит мутабельное состояние)
```

```
Тест: test_rhs_one_step_solve_ivp
Файл: method_of_moments/tests/test_ode_system.py (новый)
Сценарий: solve_ivp(method='Radau') делает один шаг без ошибки
Setup: y0 = [5.0, 0.1, 2.0], t_span = (0, 1.0), method='Radau', max_step=1.0
Ожидание: sol.success == True, sol.y[:, -1] конечны, sol.y[0, -1] > y0[0]
Предотвращает: несовместимость rhs с solve_ivp (формат, dtypes)
Важно: явно указать method='Radau' — система жёсткая, RK45 (по умолчанию) может не сойтись
```

**Изменения:**

Новый файл, ~120 строк.

**Проверка после шага:**
- `.venv/Scripts/python -m pytest tests/test_ode_system.py -v`
- Регрессия: `.venv/Scripts/python -m pytest tests/ -v`

**Подводные камни:**
- Дублирование фикстур. Допустимо для 2 файлов; рефакторинг в conftest.py — после стабилизации.
- `test_rhs_one_step_solve_ivp` использует Radau; если Radau требует Jacobian — тест может быть медленным. На одном шаге — безопасно.

**Зависимости:** Требует: шаг 1. Блокирует: ничего.
**Оценка:** ~120 строк, ~20 минут.

---

## Критерии завершения

- [x] Формула \eqref{eq:ode_system}: `ẋ = A⁻¹·F` реализована
- [ ] `make_rhs()` имеет docstring с `\eqref{eq:ode_system}`
- [ ] 7 тестов зелёные (конечность, знаки, совпадение с ручным, граничный, чистота, solve_ivp)
- [ ] Все существующие тесты зелёные (обратная совместимость)
- [ ] Vault обновлён
- [ ] GitHub issue #9 прокомментирован

## Связанные заметки в vault

- [[feat-005d matrix-assembly]] — план сборки матрицы (реализован)
- [[roadmap реализации]] — общий roadmap, фаза 5
