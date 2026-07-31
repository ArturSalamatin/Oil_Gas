---
tags:
  - план
  - вычисление
date: 2026-07-31
issue: FEAT-007b
github: 10
branch: feat/feat-007b/solver-wrapper
model_level: М.6
status: в процессе
audit:
  date: 2026-07-31
  found: 0
  auto-fixed: 0
  manual-required: 0
  rounds: 7
  note: раунд 7 — чистый проход, Ψ(1)=1 верифицирован, p(r_w)=p_wf/p(R_ext)=p_0 подтверждены, __init__.py/conftest/pyproject.toml без конфликтов
---

# FEAT-007b: Обёртка solver и постпроцессинг

## Как начать работу по этому плану

1. Прочитай этот файл целиком
2. Прочитай `moments_method.tex`:
   - строки 673–688: система \eqref{eq:ode_system}
   - строки 1425–1562: §6 — начальные условия
   - строки 1580–1663: §7.2 — жёсткость, обезразмеривание
3. Прочитай `method_of_moments/src/ode_system.py` (23 строки — `make_rhs`)
4. Прочитай `method_of_moments/src/coefficients.py`, строки 9–18 (`OdeState`)
5. Прочитай `method_of_moments/src/profiles/` — `pressure.py`, `saturation.py`, `temperature.py`
6. Прочитай `method_of_moments/tests/test_ode_system.py` — фикстуры baseline
7. Прочитай `method_of_moments/configs/baseline.json` — параметры задачи
8. Создай ветку: `git checkout -b feat/feat-007b/solver-wrapper`
9. Прогони тесты (baseline): `cd method_of_moments && .venv/Scripts/python -m pytest tests/ -v`
   - Ожидаемый baseline: **289 тестов**, все зелёные (включая 7 тестов FEAT-007a)
10. Начни с шага 1. После каждого шага: pytest

---

## Подтип

**Вычисление** — обёртка вокруг `solve_ivp`, связывающая начальные условия (§6), правую часть (§5) и постпроцессинг профилей (§4) в единый вычислительный конвейер.

## Зависимости

| ID | Описание | Статус | Блокирует |
|---|---|---|---|
| FEAT-007a ([#9](https://github.com/ArturSalamatin/Oil_Gas/issues/9)) | `make_rhs()` в `ode_system.py` | ✅ ГОТОВО | Шаги 1–2 используют `make_rhs` |
| FEAT-005d ([#8](https://github.com/ArturSalamatin/Oil_Gas/issues/8)) | `assemble_ode_system()` в `coefficients.py` | ✅ ГОТОВО | Транзитивно через FEAT-007a |
| FEAT-006 | Начальная асимптотика, `initial.py` | 🔴 ОТКРЫТ | Шаг 1 использует заглушку вместо `initial.py` |

**Решение по FEAT-006:** встроить минимальную заглушку начальных условий прямо в `solver.py` по формулам §6. Когда FEAT-006 будет реализован — заменить заглушку вызовом `initial.py`.

## Формулы → код

| Формула | Уравнение в tex | Python-функция | Модуль | Тест |
|---|---|---|---|---|
| y0 = [r_b(t_ε), S_{g,w}^eq, 0] | `\eqref{eq:ic_regularized}`, `\eqref{eq:delta_sqrt}`, `\eqref{eq:Sgw_equil}` | `_initial_conditions()` | `solver.py` | `test_initial_*` |
| Event: r_b ≥ r_e | — | `_event_rb_reached()` | `solver.py` | `test_event_*` |
| p(r), Sg(r), T(r) | §4.2–4.4 | `reconstruct_profiles()` | `solver.py` | `test_reconstruct_*` |

## Физика / математика

### Интегрирование ODE

Система \eqref{eq:ode_system} из `moments_method.tex` §5:

```
┌                         ┐ ┌       ┐   ┌      ┐
│ A₁₁   0    A₁₃         │ │ ṙ_b   │   │ F₁   │
│ A₂₁   A₂₂  A₂₃        │·│ Ṡg_w  │ = │ F₂   │
│ A₃₁   0    A₃₃         │ │ Δ̇T_w  │   │ F₃   │
└                         ┘ └       ┘   └      ┘
```

Правая часть `ẋ = A⁻¹·F` реализована в `ode_system.py:make_rhs`.

### Начальные условия (§6, \eqref{eq:ic_regularized})

```
r_b(t_ε)   = r_w + 2·α*·√(χ₀·t_ε)
S_{g,w}(t_ε) = S_{g,w}^{eq}
ΔT_w(t_ε) = 0
```

где:
- α* = erfinv((p_b - p_wf) / (p_0 - p_wf))  — из \eqref{eq:delta_sqrt}
- χ₀ = Λ₀ / Cp⁰ — пьезопроводность при Sg=0, T=T₀
- S_{g,w}^{eq} = [Rs(p_b, T₀) - Rs(p_wf, T₀)]·Bg(p_wf, T₀) / Bo(p_wf, T₀) — из \eqref{eq:Sgw_equil}

t_ε выбирается из условия δ/r_w ~ 10⁻²–10⁻¹. Типично t_ε ~ 10⁻⁵ с.

### Events

- **r_b ≥ r_e:** граница дренирования достигнута, terminal=True

### Постпроцессинг

По решению (r_b(t_k), S_{g,w}(t_k), ΔT_w(t_k)) восстанавливаем пространственные профили:
- p(r) — `PressureProfile.__call__(r, r_b, pb_star, gamma)`
- S_g(r) — `SaturationProfile.__call__(r, r_b, Sg_w)`
- T(r) — `TemperatureProfile.__call__(r, dT_w)`

### Жёсткость (§7.2)

Отношение масштабов χ₀/a ~ 10⁶–10⁷, с конвекцией — ~10³–10⁴. Необходим неявный интегратор: **Radau** (неявный Рунге–Кутта порядка 5, A- и L-стабильный).

Настройки по умолчанию из `baseline.json`: `rtol=1e-6`, `atol=1e-9`.

## Обратная совместимость

- [x] Создаётся **новый** модуль `solver.py` и **новый** файл тестов — существующий код не затрагивается
- [x] Существующие тесты не меняются
- [x] Конфиг `baseline.json` уже содержит секцию `solver` — используем её
- [x] Нет circular imports: `solver.py` → `ode_system.py` → `coefficients.py` (линейная цепочка)
- [x] Профили используются read-only через `__call__`

## Варианты решения

### Вариант A: Модульные функции (рекомендуемый)

```python
def _initial_conditions(fluid, rock, p_profile, t_profile, p_wf, t_eps):
    ...
    return y0  # ndarray(3)

def _event_rb_reached(r_e):
    def event(t, y):
        return r_e - y[0]
    event.terminal = True
    event.direction = -1
    return event

def solve_moments(fluid, rock, p_profile, t_profile, s_profile,
                  p_wf, r_e, t_end, t_eps=1e-5, dp_wf_dt=0.0, **ivp_kwargs):
    ...
    return sol  # OdeResult

def reconstruct_profiles(r_b, Sg_w, dT_w, p_profile, t_profile, s_profile,
                         fluid, r_grid):
    ...
    return p_arr, Sg_arr, T_arr
```

- **Плюсы:** простые функции, легко тестировать изолированно, минимум абстракций
- **Минусы:** нет объекта-состояния — параметры передаются явно
- **Трудоёмкость:** ~80 строк

### Вариант B: Класс MomentsSolver

```python
class MomentsSolver:
    def __init__(self, fluid, rock, ...): ...
    def solve(self, t_end, **ivp_kwargs): ...
    def profiles_at(self, t_k, r_grid): ...
```

- **Плюсы:** инкапсуляция, можно хранить промежуточные результаты
- **Минусы:** избыточная абстракция, CLAUDE.md: «не добавляй абстракции сверх задачи»
- **Трудоёмкость:** ~120 строк

### Выбор: **Вариант A**

Набор функций без класса. Достаточно для FEAT-008 (CLI) и VAL-001–003. Если потребуется расширение — рефакторинг в класс тривиален.

## Подводные камни

- ✅ **Размерности:** r_b в метрах, S_g безразмерная, ΔT_w в Кельвинах — совместимо с существующими профилями
- ✅ **Граничные случаи r_b → r_w:** обработаны в `_initial_conditions` через формулы §6; при t_ε = 1e-5 с получаем δ/r_w ~ 0.01
- ⚠️ **Граничный случай r_b → R_ext:** event `_event_rb_reached` останавливает интегрирование. Проверить, что `solve_ivp` корректно обрабатывает terminal event
- ✅ **Численная устойчивость:** `np.linalg.solve` в `make_rhs` обработает матрицу при baseline; Radau справится с жёсткостью ~10³–10⁴
- ⚠️ **PVT валидность:** начальные условия `_initial_Sgw` вычисляют Rs(p_wf, T₀), Bo(p_wf, T₀), Bg(p_wf, T₀) — корреляции Стендинга валидны при p_wf > 0, T₀ > 0. При p_wf = 0 — деление на ноль в Bg. Тест: p_wf > 0
- ✅ **Import-цепочки:** `solver.py` → `ode_system.py` → `coefficients.py` — линейная, без циклов
- 🔴 **Производительность и сходимость:** одна оценка rhs ~ 18 мс (10 quad-интегралов, верифицировано при baseline). Radau + Jacobian ~ 10 rhs/шаг → 180 мс/шаг. Но при cond(A)=1.2e13 конечно-разностный Jacobian имеет ошибку O(ε_mach·cond) ≈ 1e-2 — Radau **застревает** (уменьшает шаг без прогресса). Верифицировано: solve_ivp(Radau, t_span=(1e-5, 10.0)) не завершился за 120 с при baseline. Решение: обезразмеривание (DEBT) или аналитический Jacobian (FEAT). Для FEAT-007b: тесты с t_end ≤ 0.1, smoke-тест «хотя бы один шаг Radau», готовность к sol.success == False
- ✅ **Формулы vs код:** каждая функция ссылается на уравнение из tex
- ✅ **Связь с другими задачами:** не конфликтует. FEAT-006 заменит заглушку в `_initial_conditions`, FEAT-008 вызовет `solve_moments`
- ⚠️ **IntegrationWarning при y0:** `quad()` предупреждает о расходящихся интегралах при r_b ≈ r_w (gamma → 0, сингулярность dp/dr ~ η^{γ-1}). Значения конечны, но точность не гарантирована. В тестах: `@pytest.mark.filterwarnings("ignore::scipy.integrate.IntegrationWarning")`
- ⚠️ **Быстрая динамика Sg_w при старте:** Ṡg_w ≈ 20 при y0 — за ~0.05 с Sg_w удвоится. Radau должен автоматически уменьшить шаг. Если нет — задать `first_step=1e-8` в defaults

## Новые обнаруженные проблемы

Нет блокирующих проблем.

Неблокирующие (после завершения):
- Когда FEAT-006 реализован — заменить `_initial_conditions` в `solver.py` вызовом `initial.py`. Добавить TODO при реализации.
- Профилирование производительности `solve_moments` — для baseline.json определить время решения. Если > 10 с — создать DEBT по оптимизации quad-интегралов.
- Тест массового баланса: vault roadmap требует «массовый баланс», но это интегральная проверка (∫ρ·S·dV по профилям vs суммарный поток через r_w). Реализация — в VAL-001 или отдельном тесте после постпроцессинга, не в unit-тестах solver-обёртки.
- **Обезразмеривание (DEBT/FEAT):** cond(A) = 1.2e13 при baseline IC. Масштабы: A₁₁ ~ 260 (Cp, Па⁻¹-подобные), A₃₃ ~ 3e9 ((ρcp)_eff, Дж/(м³·К)). Обезразмеривание по [p] = p₀-p_wf = 5 МПа, [T] = 10 К, [r] = r_w снизит cond(A) до ~10³. Без этого Radau не сходится на длинных временах. Верифицированные числа при baseline: cond(A)=1.2e13, rhs=18 мс, масштабы Sgw~0.007 с / rb~17 с / dTw~229 с, gamma=0.0037.

---

## Этапы реализации

### Шаг 1: Начальные условия и events

**Цель:** реализовать вычисление начальных условий по формулам §6 и event-функцию остановки.

**Файлы:** `method_of_moments/src/solver.py` (новый)

**Контекст:**

Система \eqref{eq:ode_system} вырождается при t = 0 (L_b = 0, γ = 0). Регуляризация: запуск при t = t_ε > 0. Начальные условия из §6:
- r_b(t_ε): erfc-профиль давления → положение изобары p = p_b
- S_{g,w}^{eq}: flash-равновесие при p_wf, T₀
- ΔT_w = 0: температура не успела измениться

**Формулы:**

```latex
% \eqref{eq:delta_sqrt}
\delta(t) = r_b(t) - r_w = 2\,\alpha_*\,\sqrt{\chi_0\,t}

\alpha_* = \mathrm{erfinv}\!\left(\frac{p_b - p_{wf}}{p_0 - p_{wf}}\right)

% χ₀ — пьезопроводность однофазная
\chi_0 = \frac{\Lambda_0}{C_p^{(0)}}
% где Λ₀ = k·kro(0)/μ_o / Bg  при Sg=0, T=T₀
% C_p^{(0)} — коэффициент ёмкости при Sg=0, T=T₀

% \eqref{eq:Sgw_equil}
S_{g,w}^{\mathrm{eq}} = \frac{[R_s(p_b, T_0) - R_s(p_{wf}, T_0)] \cdot B_g(p_{wf}, T_0)}{B_o(p_{wf}, T_0)}
```

**Что сделать:**

1. Создать файл `method_of_moments/src/solver.py`
2. Импорты:
   ```python
   import numpy as np
   from scipy.integrate import solve_ivp
   from scipy.special import erfinv
   from .ode_system import make_rhs
   ```
3. Реализовать `_initial_conditions(fluid, rock, p_profile, t_profile, p_wf, t_eps)`:
   - Docstring: «Начальные условия ODE. Заглушка до FEAT-006. Ур. (eq:ic_regularized) moments_method.tex.»
   - Вычислить:
     - `p_0 = p_profile.p_0`
     - `p_b = fluid.p_b`
     - `T_0 = t_profile.T_0`
     - `alpha_star = erfinv((p_b - p_wf) / (p_0 - p_wf))`
     - `Cp0 = fluid.Cp(p_0, T_0, 0.0, rock["phi"], rock["c_r"])`  — ёмкость при Sg=0
     - `Lambda0 = fluid.Lambda(p_0, T_0, 0.0, rock["k"])`  — подвижность при Sg=0
     - `chi_0 = Lambda0 / Cp0`  — пьезопроводность
     - `r_b0 = p_profile.r_w + 2.0 * alpha_star * np.sqrt(chi_0 * t_eps)`
     - `Rs_pb = fluid.Rs(p_b, T_0)`, `Rs_pwf = fluid.Rs(p_wf, T_0)`
     - `Bg_pwf = fluid.Bg(p_wf, T_0)`, `Bo_pwf = fluid.Bo(p_wf, T_0)`
     - `Sgw_eq = (Rs_pb - Rs_pwf) * Bg_pwf / Bo_pwf`
     - `dT_w0 = 0.0`
   - `return np.array([r_b0, Sgw_eq, dT_w0])`

4. Реализовать `_event_rb_reached(r_e)`:
   - Docstring: «Event: r_b достиг r_e.»
   - Внутри:
     ```python
     def event(t, y):
         return r_e - y[0]
     event.terminal = True
     event.direction = -1
     return event
     ```

**Проверка после шага:**
- Импорт без ошибок: `.venv/Scripts/python -c "from src.solver import _initial_conditions, _event_rb_reached"`
- Регрессия: `.venv/Scripts/python -m pytest tests/ -v`

**Подводные камни:**
- `erfinv` из `scipy.special` — не из `math`. Проверить при baseline: (p_b - p_wf)/(p_0 - p_wf) = (18e6 - 15e6)/(20e6 - 15e6) = 0.6. erfinv(0.6) ≈ 0.5951. Корректно.
- `fluid.Cp` и `fluid.Lambda` принимают скалярные p, T — совместимо.
- `chi_0` при baseline: Λ₀ = k/(Bg·μ_o) при p₀=20 МПа, T₀=350 K, Sg=0. Порядок: k=1e-13, μ_o~1e-3, Bg~0.01 → Λ₀ ~ 1e-8. Cp ~ 1e-9. χ₀ ~ 10. При t_eps=1e-5: δ = 2·0.6·√(10·1e-5) ≈ 0.012 м. δ/r_w ≈ 0.12 — в пределах допустимого.

**Зависимости:** Требует: ничего (кроме существующих модулей). Блокирует: шаг 2, шаг 3, шаг 4.
**Оценка:** ~40 строк, ~10 минут.

---

### Шаг 2: Основная функция `solve_moments`

**Цель:** реализовать обёртку `solve_ivp(Radau)` с начальными условиями и events.

**Файлы:** `method_of_moments/src/solver.py` (дополнить)

**Контекст:**

`solve_ivp` из scipy принимает:
- `fun(t, y)` — правая часть (из `make_rhs`)
- `t_span = (t_eps, t_end)` — интервал интегрирования
- `y0` — начальные условия (из `_initial_conditions`)
- `method = 'Radau'` — неявный интегратор
- `events` — список event-функций
- `rtol, atol` — точности
- `dense_output=True` — для интерполяции между шагами

**Что сделать:**

1. Реализовать `solve_moments(fluid, rock, p_profile, t_profile, s_profile, p_wf, r_e, t_end, t_eps=1e-5, dp_wf_dt=0.0, **ivp_kwargs)`:
   - Docstring: «Интегрирование ODE метода моментов. §5–6 moments_method.tex.»
   - Вычислить начальные условия: `y0 = _initial_conditions(fluid, rock, p_profile, t_profile, p_wf, t_eps)`
   - Создать rhs: `rhs = make_rhs(fluid, rock, p_profile, t_profile, s_profile, p_wf, dp_wf_dt)`
   - Создать event: `event = _event_rb_reached(r_e)`
   - Настройки по умолчанию:
     ```python
     defaults = dict(method='Radau', rtol=1e-6, atol=1e-9, dense_output=True, first_step=1e-8)
     defaults.update(ivp_kwargs)
     ```
   - Вызвать:
     ```python
     sol = solve_ivp(rhs, (t_eps, t_end), y0, events=[event], **defaults)
     ```
   - `return sol`

**Сигнатура возвращаемого значения:**

`scipy.integrate.OdeResult` с полями:
- `sol.t` — массив времён, shape (N,)
- `sol.y` — массив состояний, shape (3, N): `sol.y[0]` = r_b(t), `sol.y[1]` = S_{g,w}(t), `sol.y[2]` = ΔT_w(t)
- `sol.t_events[0]` — время достижения r_e (если event сработал)
- `sol.success` — True если интегрирование завершилось без ошибок
- `sol.sol` — интерполянт (при `dense_output=True`)

**Проверка после шага:**
- Импорт: `.venv/Scripts/python -c "from src.solver import solve_moments"`
- Регрессия: `.venv/Scripts/python -m pytest tests/ -v`

**Подводные камни:**
- `t_span = (t_eps, t_end)`: начинаем с t_eps (не с 0). solve_ivp вернёт t-массив начинающийся с t_eps.
- `dense_output=True`: Radau поддерживает dense output — можно вычислять sol.sol(t) для любого t в [t_eps, t_end].
- Если event сработал, `sol.t[-1]` = момент срабатывания.

**Зависимости:** Требует: шаг 1. Блокирует: шаг 5.
**Оценка:** ~25 строк, ~10 минут.

---

### Шаг 3: Постпроцессинг — `reconstruct_profiles`

**Цель:** восстановить пространственные профили p(r), S_g(r), T(r) из параметров решения в момент t_k.

**Файлы:** `method_of_moments/src/solver.py` (дополнить)

**Контекст:**

Решение ODE даёт три скаляра в момент t_k: r_b, S_{g,w}, ΔT_w. Пространственные профили задаются параметризациями из §4:
- p(r) — `PressureProfile.__call__(r, r_b, pb_star, gamma)` — двухзонный, §4.2
- S_g(r) — `SaturationProfile.__call__(r, r_b, Sg_w)` — компактный носитель [r_w, r_b], §4.3
- T(r) — `TemperatureProfile.__call__(r, dT_w)` — Ψ(ζ), §4.4

Для p(r) нужно предварительно вычислить `pb_star` и `gamma`:
- `pb_star = p_profile.pb_star(r_b, dT_w, fluid, t_profile)`
- `gamma = p_profile.gamma(r_b, pb_star)`

**Что сделать:**

1. Реализовать `reconstruct_profiles(r_b, Sg_w, dT_w, p_profile, t_profile, s_profile, fluid, r_grid)`:
   - Docstring: «Восстановление p(r), Sg(r), T(r) из параметров решения. §4 moments_method.tex.»
   - Параметры:
     - `r_b, Sg_w, dT_w` — текущее состояние (скаляры)
     - `p_profile, t_profile, s_profile` — объекты профилей
     - `fluid` — BlackOilFluid (для pb_star)
     - `r_grid` — 1D массив радиусов, shape (M,)
   - Вычислить:
     ```python
     pb_star = p_profile.pb_star(r_b, dT_w, fluid, t_profile)
     gamma = p_profile.gamma(r_b, pb_star)

     p_arr = np.array([p_profile(r, r_b, pb_star, gamma) for r in r_grid])
     Sg_arr = np.array([s_profile(r, r_b, Sg_w) for r in r_grid])
     T_arr = np.array([t_profile(r, dT_w) for r in r_grid])
     ```
   - `return p_arr, Sg_arr, T_arr`

**Замечание:** профили используют `math.log` (скалярные). Цикл по `r_grid` — O(M). При M ~ 100–1000 — пренебрежимо по сравнению с ODE. Векторизация — потенциальный DEBT.

**Проверка после шага:**
- Импорт: `.venv/Scripts/python -c "from src.solver import reconstruct_profiles"`
- Регрессия: `.venv/Scripts/python -m pytest tests/ -v`

**Подводные камни:**
- `r_grid` должен быть в диапазоне [r_w, R_ext]. Профили определены на этом интервале.
- `pb_star` зависит от `dT_w` через температуру на фронте.
- При `r_b ≈ r_w` (начало) gamma → 0 и p(r) ~ η^0 = const = p_wf во всей зоне 1 — корректно.

**Зависимости:** Требует: шаг 1 (для pb_star, gamma). Блокирует: шаг 6.
**Оценка:** ~20 строк, ~5 минут.

---

### Шаг 4: Тесты начальных условий

**Цель:** проверить корректность `_initial_conditions` и `_event_rb_reached`.

**Файлы:** `method_of_moments/tests/test_solver.py` (новый)

**Контекст:**

Фикстуры аналогичны `test_ode_system.py`: `baseline_config`, `fluid`, `rock`, `p_profile`, `t_profile`, `s_profile`. Дублируем (как в FEAT-007a — тесты самодостаточны).

Параметры baseline:
- p_0 = 20 МПа, p_b = 18 МПа, p_wf = 15 МПа, T_0 = 350 К
- r_w = 0.1 м, R_ext = 500 м
- t_eps = 1e-5 с

**Что сделать:**

1. Создать `method_of_moments/tests/test_solver.py`
2. Дублировать фикстуры (константы, `baseline_config`, `fluid`, `rock`, `p_profile`, `t_profile`, `s_profile`)
3. Реализовать тесты:

```
Тест: test_initial_rb_greater_than_rw
Сценарий: r_b(t_ε) > r_w
Setup: baseline, t_eps = 1e-5
Ожидание: y0[0] > r_w = 0.1 м
Формула: \eqref{eq:delta_sqrt} — δ > 0 при t_ε > 0
Предотвращает: знаковая ошибка в α* или χ₀
```

```
Тест: test_initial_rb_close_to_rw
Сценарий: δ/r_w ~ 10⁻²–10⁻¹ при t_eps = 1e-5
Setup: baseline, t_eps = 1e-5
Ожидание: 0.001 < (y0[0] - 0.1) / 0.1 < 1.0
Формула: \eqref{eq:delta_sqrt}, §6 «δ/r_w ~ 10⁻²–10⁻¹»
Предотвращает: ошибка в порядке величины χ₀
```

```
Тест: test_initial_Sgw_in_01
Сценарий: S_{g,w}^{eq} ∈ (0, 1)
Setup: baseline
Ожидание: 0 < y0[1] < 1
Формула: \eqref{eq:Sgw_equil} — физически осмысленная насыщенность
Предотвращает: перепутаны Rs(pb) и Rs(pwf) или знак числителя
```

```
Тест: test_initial_dTw_zero
Сценарий: ΔT_w(t_ε) = 0
Setup: baseline
Ожидание: y0[2] == 0.0
Формула: \eqref{eq:ic_regularized}
Предотвращает: ненулевая инициализация
```

```
Тест: test_initial_conditions_all_finite
Сценарий: все компоненты y0 конечны
Setup: baseline
Ожидание: np.all(np.isfinite(y0))
Предотвращает: NaN/Inf из erfinv или PVT
```

```
Тест: test_event_positive_at_start
Сценарий: event(t, y0) > 0 при r_b(t_ε) < r_e
Setup: r_e = 500.0, y0 от baseline
Ожидание: event(0, y0) > 0
Предотвращает: event срабатывает сразу на старте
```

```
Тест: test_event_zero_at_re
Сценарий: event(t, y) = 0 когда r_b = r_e
Setup: y = [500.0, 0.1, 2.0], r_e = 500.0
Ожидание: event(0, y) == 0.0
Предотвращает: ошибка в знаке или формуле event
```

```
Тест: test_event_terminal
Сценарий: event.terminal == True
Ожидание: event.terminal == True
Предотвращает: интегрирование не остановится при достижении r_e
```

**Проверка после шага:**
- `.venv/Scripts/python -m pytest tests/test_solver.py -v`
- Регрессия: `.venv/Scripts/python -m pytest tests/ -v`

**Зависимости:** Требует: шаг 1. Блокирует: ничего.
**Оценка:** ~100 строк, ~15 минут.

---

### Шаг 5: Тесты `solve_moments`

**Цель:** проверить корректность полного интегрирования ODE.

**Файлы:** `method_of_moments/tests/test_solver.py` (дополнить)

**Контекст:**

Интеграционные тесты. `solve_moments` вызывает всю цепочку: начальные условия → make_rhs → solve_ivp(Radau) → OdeResult. Тесты проверяют физические инварианты на траектории.

**Что сделать:**

Добавить класс `TestSolveMoments` с тестами:

```
Тест: test_solve_runs_without_crash
Сценарий: solve_moments не падает с исключением при baseline
Setup: baseline.json, t_end = 0.1 с (короткий — cond(A)~1e13, Radau может застрять)
Ожидание: solve_moments завершается без raise; sol.t.size >= 2 (хотя бы один шаг). Не проверяем sol.success — при cond(A)~1e13 Radau может вернуть success=False из-за неточного Jacobian. Это ограничение текущей реализации (без обезразмеривания), не баг solver-обёртки.
Предотвращает: crash при запуске
```

```
Тест: test_rb_monotonic
Сценарий: r_b(t) монотонно растёт
Setup: baseline.json, t_end = 0.1
Ожидание: np.all(np.diff(sol.y[0]) >= 0)
Формула: физика — фронт разгазирования только расширяется
Предотвращает: знаковая ошибка в ṙ_b
```

```
Тест: test_Sgw_in_bounds
Сценарий: S_{g,w}(t) ∈ [0, 1] на всей траектории
Setup: baseline.json, t_end = 0.1
Ожидание: np.all(sol.y[1] >= 0) and np.all(sol.y[1] <= 1)
Предотвращает: нефизичная насыщенность
```

```
Тест: test_dTw_nonnegative
Сценарий: ΔT_w(t) ≥ 0 (охлаждение) на всей траектории
Setup: baseline.json, t_end = 0.1
Ожидание: np.all(sol.y[2] >= 0)
Конвенция: T(r) = T₀ - ΔT_w·Ψ(ζ), поэтому ΔT_w > 0 означает T_w < T₀ (охлаждение). Код использует dT_w=2.0 в baseline (test_ode_system.py:73).
Формула: физика — JT + дегазация охлаждают ПЗП
Предотвращает: инверсия знака температурного отклика
```

```
Тест: test_rb_stays_in_bounds
Сценарий: r_b(t) ∈ [r_w, R_ext]
Setup: baseline.json, t_end = 0.1
Ожидание: np.all(sol.y[0] >= r_w) and np.all(sol.y[0] <= R_ext)
Предотвращает: r_b выходит за пределы пласта
```

```
Тест: test_all_finite
Сценарий: все компоненты решения конечны
Setup: baseline.json, t_end = 0.1
Ожидание: np.all(np.isfinite(sol.y))
Предотвращает: blow-up
```

Примечание: интеграционный тест event (solve_ivp с r_e достигнутым за t_end) нереализуем при cond(A)=1e13 — Radau застревает задолго до r_b→r_e. Unit-тесты event-функции в шаге 4 (test_event_positive_at_start, test_event_zero_at_re, test_event_terminal) достаточны для верификации конфигурации event.

**Замечание по t_end:** для тестов используем `t_end = 0.1` с, а не `86400.0` (сутки) из baseline.json. Причина: одна оценка rhs ~ 1 с (10 quad-интегралов), Radau + Jacobian ~ 10 rhs/шаг → ~10 с/шаг. При t_end = 3600 тест не завершится. При t_end = 0.1 Radau должен сделать 1–5 шагов — достаточно для проверки инвариантов. Если тест слишком быстр (0 шагов) — увеличить до 1.0. Пометить `@pytest.mark.filterwarnings("ignore::scipy.integrate.IntegrationWarning")` из-за сингулярных quad при малом r_b.

**Замечание по тесту event:** `test_event_stops_at_small_re` использует `r_e = 1.0 м` и `t_end = 86400.0`. При такой скорости решения он может не завершиться. Альтернатива: проверять event **изолированно** (вызвать event-функцию напрямую, не через solve_ivp). Если интеграционный тест event нереализуем по производительности — заменить unit-тестом.

**Проверка после шага:**
- `.venv/Scripts/python -m pytest tests/test_solver.py -v`
- Регрессия: `.venv/Scripts/python -m pytest tests/ -v`

**Подводные камни:**
- Radau может быть медленным при жёстких системах. Если тест занимает > 30 с — уменьшить t_end или ослабить rtol.
- Знак ΔT_w: в moments_method.tex ΔT_w = T_0 - T_w (положительна при охлаждении). Убедиться в конвенции.

**Зависимости:** Требует: шаг 2. Блокирует: ничего.
**Оценка:** ~80 строк, ~20 минут.

---

### Шаг 6: Тесты `reconstruct_profiles`

**Цель:** проверить корректность восстановления пространственных профилей.

**Файлы:** `method_of_moments/tests/test_solver.py` (дополнить)

**Что сделать:**

Добавить класс `TestReconstructProfiles`:

```
Тест: test_pressure_at_rw_equals_pwf
Сценарий: p(r_w) = p_wf
Setup: r_b = 5.0, Sg_w = 0.1, dT_w = 2.0, r_grid включает r_w
Ожидание: p_arr[0] ≈ 15e6 Па (rtol=1e-6)
Формула: граничное условие \eqref{eq:p_inner}
Предотвращает: ошибка в pb_star/gamma
```

```
Тест: test_pressure_at_Rext_equals_p0
Сценарий: p(R_ext) = p_0
Setup: r_b = 5.0, r_grid включает R_ext
Ожидание: p_arr[-1] ≈ 20e6 Па (rtol=1e-6)
Формула: граничное условие \eqref{eq:p_outer}
Предотвращает: ошибка во внешней зоне
```

```
Тест: test_pressure_monotonic
Сценарий: p(r) монотонно растёт от r_w до R_ext
Setup: r_b = 5.0, r_grid от r_w до R_ext
Ожидание: np.all(np.diff(p_arr) >= 0)
Формула: физика — давление растёт от скважины к контуру питания
Предотвращает: немонотонность из-за ошибки в gamma
```

```
Тест: test_Sg_at_rw_equals_Sgw
Сценарий: Sg(r_w) = Sg_w
Setup: r_b = 5.0, Sg_w = 0.1, r_grid[0] = r_w
Ожидание: Sg_arr[0] ≈ 0.1
Формула: \eqref{eq:Sg_profile} при η=0
Предотвращает: ошибка в параметризации
```

```
Тест: test_Sg_zero_outside_rb
Сценарий: Sg(r) = 0 при r > r_b
Setup: r_b = 5.0, r_grid включает точки > 5.0
Ожидание: Sg_arr[r_grid > r_b] == 0
Формула: \eqref{eq:Sg_profile} — компактный носитель
Предотвращает: утечка газа за фронт разгазирования
```

```
Тест: test_T_at_rw
Сценарий: T(r_w) = T_0 - ΔT_w·Ψ(ζ_w)
Setup: r_b = 5.0, dT_w = 2.0
Ожидание: T_arr[0] ≈ T_0 - 2.0·Ψ(1.0) = 350.0 - 2.0·1.0 = 348.0 К
Формула: \eqref{eq:T_profile}, Ψ(1) = 1^σ·(2 - 1^σ) = 1 при σ=2: Ψ(1)=1·(2-1)=1
Предотвращает: ошибка в знаке ΔT_w
```

```
Тест: test_T_at_Rext
Сценарий: T(R_ext) = T_0
Setup: r_b = 5.0, dT_w = 2.0
Ожидание: T_arr[-1] ≈ 350.0 К
Формула: \eqref{eq:T_profile}, Ψ(0) = 0
Предотвращает: температурный отклик на контуре питания
```

```
Тест: test_profiles_shape
Сценарий: все массивы имеют ту же длину, что и r_grid
Setup: r_grid = np.linspace(r_w, R_ext, 50)
Ожидание: p_arr.shape == Sg_arr.shape == T_arr.shape == (50,)
Предотвращает: несовпадение размерностей
```

**Проверка после шага:**
- `.venv/Scripts/python -m pytest tests/test_solver.py -v`
- Регрессия: `.venv/Scripts/python -m pytest tests/ -v`

**Зависимости:** Требует: шаг 3. Блокирует: ничего.
**Оценка:** ~90 строк, ~15 минут.

---

## Критерии завершения

- [ ] Начальные условия \eqref{eq:ic_regularized}: `_initial_conditions()` реализована
- [ ] Event r_b ≥ r_e: `_event_rb_reached()` реализован
- [ ] `solve_moments()` запускает solve_ivp(Radau) и возвращает OdeResult
- [ ] `reconstruct_profiles()` восстанавливает p(r), Sg(r), T(r)
- [ ] Каждая функция имеет docstring с \eqref{}
- [ ] 8 тестов начальных условий/events зелёные
- [ ] 6 тестов solve_moments зелёные (физические инварианты)
- [ ] 8 тестов reconstruct_profiles зелёные (граничные значения, монотонность)
- [ ] Все существующие тесты зелёные (обратная совместимость)
- [ ] Vault обновлён
- [ ] GitHub issue #10 прокомментирован

## Связанные заметки в vault

- [[feat-007a ode-rhs]] — план предыдущей подзадачи (реализован)
- [[feat-005d matrix-assembly]] — план сборки матрицы (реализован)
- [[roadmap реализации]] — общий roadmap, фаза 5
