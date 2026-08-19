---
tags:
  - план
  - физика
date: 2026-08-03
issue: FEAT-010
github: 13
branch: feat/feat-010/beta-ode-variable
model_level: М.4
status: реализован
audit:
  date: 2026-08-03
  found: 3
  auto-fixed: 3
  manual-required: 0
  round: 3
---

# FEAT-010: Показатель формы β как ODE-переменная

## Как начать работу по этому плану

1. Прочитай этот файл целиком
2. Прочитай `moments_method.tex` §5.5 (строки ~1420–1800) — формулы A₄ⱼ, F₄, A_{2,β}
3. Прочитай текущий код: `src/coefficients.py` (assemble_ode_system), `src/ode_system.py`, `src/solver.py`
4. Создай ветку: `git checkout -b feat/feat-010/beta-ode-variable`
5. Baseline тесты: `cd method_of_moments && .venv/Scripts/python -m pytest tests/ -v`
6. Начни с шага 1

## Контекст

### Текущая система 3×3

y = [r_b, Sg_w, dT_w]. Матрица A (3×3) в `assemble_ode_system()`. β — фиксированный параметр `s_profile.beta`.

### Целевая система 4×4

y = [r_b, Sg_w, beta, dT_w]. Матрица A (4×4). β — ODE-переменная, читается из `y[2]`.

### Ключевые формулы (§5.5 moments_method.tex)

**Новые элементы матрицы:**

A_{2,β} = −Sg_w ∫r·η^β·ln(η)·dr (eq:A2beta) — при β̇ во 2-й строке

A₄₁ = Sg_w·β/(r_b·L_b) ∫r·η^{2β}·dr − ∫r·η^β·So·(cr+co^sat)·(∂p/∂r_b)·dr (eq:A41)

A₄₂ = ∫r·η^β·(1−η^β)·dr (eq:A42)

A₄₃ = −Sg_w ∫r·η^{2β}·ln(η)·dr (eq:A43)

A₄₄ = −∫r·η^β·So·βo^sat·Ψ(ζ)·dr (eq:A44)

F₄ = −(Bo/φ)·r·(λo/Bo)·p'|_{r=rb} + F₄^(V) + I_{pwf}^(4)·ṗ_wf (eq:F4)

F₄^(V) = (Bo/φ)·(β/L_b) ∫r·η^{β−1}·(λo/Bo)·p'·dr (eq:F4_volume)

**Матрица 4×4 (eq:ode_system_4x4):**
```
     ṙ_b    Ṡg_w    β̇       ΔṪ_w
1  [ A₁₁    0       0        A₁₃  ]
2  [ A₂₁    A₂₂     A_{2β}   A₂₃  ]
3  [ A₃₁    0       0        A₃₃  ]
4  [ A₄₁    A₄₂     A₄₃      A₄₄  ]
```

Нумерация столбцов: [0]=ṙ_b, [1]=Ṡg_w, [2]=β̇, [3]=ΔṪ_w.
Старый A₁₃ → A[0,3], старый A₂₃ → A[1,3], старый A₃₃ → A[2,3].

---

## Шаг 1: Флаг beta_fixed в конфиге и OdeState

**Цель:** добавить beta в OdeState и флаг в конфиге для обратной совместимости.
**Файлы:** `method_of_moments/src/coefficients.py`, `method_of_moments/configs/baseline.json`

**Что сделать:**
1. В OdeState добавить поле `beta: float = 2.0` (default=2.0 критичен для обратной совместимости — 3 существующих вызова OdeState не передают beta)
2. В baseline.json добавить `"beta_fixed": false`

**Изменения:**

До (coefficients.py:10–17):
```python
@dataclasses.dataclass
class OdeState:
    r_b: float
    Sg_w: float
    dT_w: float
    p_wf: float
    dp_wf_dt: float = 0.0
```

После:
```python
@dataclasses.dataclass
class OdeState:
    r_b: float
    Sg_w: float
    dT_w: float
    p_wf: float
    dp_wf_dt: float = 0.0
    beta: float = 2.0
```

**Важно:** beta ставится ПОСЛЕ dp_wf_dt (оба с default), чтобы не нарушать правило dataclass (поля без default не могут идти после полей с default). Порядок переменных в ODE-векторе y = [r_b, Sg_w, beta, dT_w] отличается от порядка полей OdeState — это нормально, маппинг делается в ode_system.py.

**Проверка:** существующие тесты — обновить все создания OdeState, добавив `beta=2.0`.
**Оценка:** ~30 строк изменений в тестах (grep по `OdeState(`).

---

## Шаг 1.5: Рефакторинг gas_A21/A22 — state.beta вместо s_profile.beta

**Цель:** существующие gas_A21 и gas_A22 берут beta из state (не из s_profile).
**Файлы:** `method_of_moments/src/coefficients.py`

**Что сделать:**

В gas_A22 (строка 216) и gas_A21 (строка 236): заменить `beta = s_profile.beta` → `beta = state.beta`.

Только эти 2 функции используют `s_profile.beta`. gas_A23 и gas_F2 НЕ используют β показатель формы (они используют βo_sat — PVT-свойство, это другое).

При beta_fixed=True: state.beta = s_profile.beta (устанавливается в ode_system.py) — поведение не меняется.

**ВАЖНО:** этот шаг должен быть ДО шага 4 (assemble 4×4), иначе gas_A21/A22 в 4×4 матрице будут использовать фиксированный β из s_profile, а не ODE-переменный из state.

**Проверка:** все существующие тесты зелёные (state.beta = 2.0 по default = s_profile.beta).
**Оценка:** 2 строки.

---

## Шаг 2: Новые коэффициенты gas_A2beta, gas_A41–A44, gas_F4

**Цель:** реализовать 6 новых функций из §5.5.
**Файлы:** `method_of_moments/src/coefficients.py`

**Что сделать:**

Добавить 6 функций после `gas_F2()`:

1. `gas_A2beta(fluid, rock, p_profile, t_profile, s_profile, state)` → float
   - A_{2,β} = −Sg_w ∫r·η^β·ln(η)·dr
   - eq:A2beta

2. `gas_A41(fluid, rock, p_profile, t_profile, s_profile, state)` → float
   - eq:A41, два отличия от gas_A21: (1) геометрический интеграл ∫r·η^{2β}·dr вместо ∫r·η^β·dr; (2) давленческий интеграл ∫r·**η^β**·So·(cr+co^sat)·dp_drb·dr — добавлен множитель η^β

3. `gas_A42(fluid, rock, p_profile, t_profile, s_profile, state)` → float
   - ∫r·η^β·(1−η^β)·dr, геометрический
   - eq:A42

4. `gas_A43(fluid, rock, p_profile, t_profile, s_profile, state)` → float
   - −Sg_w·∫r·η^{2β}·ln(η)·dr
   - eq:A43

5. `gas_A44(fluid, rock, p_profile, t_profile, s_profile, state)` → float
   - −∫r·η^β·So·βo^sat·Ψ(ζ)·dr, аналог gas_A23 с весом η^β
   - eq:A44

6. `gas_F4(fluid, rock, p_profile, t_profile, s_profile, state)` → float
   - Граничный поток на r_b (без r_w!) + объёмный интеграл F₄^(V)
   - eq:F4, eq:F4_volume
   - Ключевое: поток на r_w НЕ вычисляется (η^β=0 подавляет)

**Каждая функция:** docstring с \eqref{}, одна строка. Используют `state.beta` вместо `s_profile.beta`.

**Шаблон** (по аналогии с gas_A22):
```python
def gas_A42(fluid, rock, p_profile, t_profile, s_profile, state):
    """Коэффициент A₄₂ при Ṡg,w в 4-м уравнении. Ур. (eq:A42) moments_method.tex."""
    r_b = state.r_b
    r_w = s_profile.r_w
    beta = state.beta

    def integrand(r):
        eta = s_profile.eta(r, r_b)
        return r * eta**beta * (1.0 - eta**beta)

    I, _ = quad(integrand, r_w, r_b)
    return I
```

**Оценка:** ~200 строк (6 функций × ~30 строк каждая).

---

## Шаг 3: Тесты новых коэффициентов

**Цель:** unit-тесты для gas_A2beta, gas_A41–A44, gas_F4.
**Файлы:** `method_of_moments/tests/test_coefficients.py`

**Тесты:**
- `test_A2beta_positive` — A_{2,β} > 0 при Sg_w > 0
- `test_A2beta_zero_at_Sg0` — A_{2,β} = 0 при Sg_w = 0
- `test_A42_positive` — геометрический, > 0
- `test_A42_equals_A22_structure` — аналог A₂₂ с весом η^β
- `test_A43_positive` — > 0 при Sg_w > 0 (Галёркин, однозначный знак)
- `test_A43_zero_at_Sg0` — = 0 при Sg_w = 0
- `test_A41_finite` — конечен при типичных параметрах
- `test_A44_sign_consistent` — знак согласован с A₂₃
- `test_F4_no_rw_singularity` — F₄ конечен при γ < 1 (сингулярность подавлена)
- `test_F4_finite` — конечен при типичных параметрах

**Оценка:** ~150 строк.

---

## Шаг 4: Расширение assemble_ode_system до 4×4

**Цель:** при beta_fixed=False собирать матрицу 4×4.
**Файлы:** `method_of_moments/src/coefficients.py`

**Что сделать:**

Добавить функцию `assemble_ode_system_4x4()` (или расширить существующую с флагом):

```python
def assemble_ode_system(fluid, rock, p_profile, t_profile, s_profile, state,
                        beta_fixed=True):
    if beta_fixed:
        # существующая 3×3 логика
        ...
    else:
        A = np.zeros((4, 4))
        # Строка 0: давление (без β̇)
        A[0, 0] = oil_A11(...)
        A[0, 3] = oil_A13(...)
        # Строка 1: газ (с β̇)
        A[1, 0] = gas_A21(...)
        A[1, 1] = gas_A22(...)
        A[1, 2] = gas_A2beta(...)
        A[1, 3] = gas_A23(...)
        # Строка 2: энергия (без β̇)
        A[2, 0] = energy_A31(...)
        A[2, 3] = energy_A33(...)
        # Строка 3: 4-й момент
        A[3, 0] = gas_A41(...)
        A[3, 1] = gas_A42(...)
        A[3, 2] = gas_A43(...)
        A[3, 3] = gas_A44(...)

        F = np.array([oil_F1(...), gas_F2(...), energy_F3(...), gas_F4(...)])
        return A, F
```

**Обратная совместимость:** при `beta_fixed=True` — текущее поведение (3×3).

**Подводный камень:** решён в шаге 1.5 — gas_A21/A22 уже используют state.beta к этому моменту.

**Оценка:** ~50 строк.

---

## Шаг 5: Расширение ode_system.py

**Цель:** make_rhs поддерживает 4 переменные.
**Файлы:** `method_of_moments/src/ode_system.py`

**Что сделать:**

```python
def make_rhs(fluid, rock, p_profile, t_profile, s_profile, p_wf, dp_wf_dt=0.0,
             beta_fixed=True):
    def rhs(t, y):
        if beta_fixed:
            r_b, Sg_w, dT_w = y
            beta = s_profile.beta
        else:
            r_b, Sg_w, beta, dT_w = y
        state = OdeState(r_b=r_b, Sg_w=Sg_w, beta=beta, dT_w=dT_w,
                         p_wf=p_wf, dp_wf_dt=dp_wf_dt)
        A, F = assemble_ode_system(fluid, rock, p_profile, t_profile,
                                    s_profile, state, beta_fixed=beta_fixed)
        return np.linalg.solve(A, F)
    return rhs
```

**Оценка:** ~15 строк.

---

## Шаг 6: Расширение solver.py

**Цель:** solve_moments поддерживает 4 переменные; начальное β₀ из конфига.
**Файлы:** `method_of_moments/src/solver.py`

**Что сделать:**

1. `_initial_conditions`: при beta_fixed=False возвращать `[r_b0, Sgw_eq, beta0, 0.0]`
2. `solve_moments`: передавать `beta_fixed` в `make_rhs`
3. `reconstruct_profiles`: добавить аргумент `beta=None`. При beta is not None — передавать в `s_profile(r, r_b, Sg_w, beta=beta)`. Обновить call sites: main.py (строка 76), test_solver.py (строка 178)
4. В main.py: `r_b, Sg_w, beta, dT_w = sol.y[:, -1]` при beta_fixed=False

**Подводный камень:** SaturationProfile.__call__ использует self.beta. При beta из ODE нужно либо:
- Передавать beta как аргумент: `s_profile(r, r_b, Sg_w, beta=beta)`
- Или мутировать `s_profile.beta = beta` перед вызовом

Первый вариант чище. Расширить SaturationProfile.__call__ с опциональным beta.

**Оценка:** ~30 строк.

---

## Шаг 7: Расширение SaturationProfile

**ВАЖНО:** выполнять ДО шага 6 (solver.py), т.к. solver вызывает `s_profile(r, r_b, Sg_w, beta=beta)`.

**Цель:** __call__ и dSg_dr принимают опциональный beta.
**Файлы:** `method_of_moments/src/profiles/saturation.py`

**Что сделать:**

```python
def __call__(self, r, r_b, Sg_w, beta=None):
    if beta is None:
        beta = self.beta
    ...
    return Sg_w * (1.0 - eta ** beta)

def dSg_dr(self, r, r_b, Sg_w, beta=None):
    if beta is None:
        beta = self.beta
    ...
```

**Обратная совместимость:** без beta — текущее поведение.

**Оценка:** ~10 строк.

---

## Шаг 8: Расширение main.py

**Цель:** CLI поддерживает beta_fixed из конфига.
**Файлы:** `method_of_moments/src/main.py`

**Что сделать:**
1. Читать `cfg["profiles"].get("beta_fixed", True)` из конфига
2. Передавать в `solve_moments`
3. В `reconstruct_profiles` передавать beta из решения

**Оценка:** ~15 строк.

---

## Шаг 9: Интеграционные тесты

**Цель:** проверить 4×4 систему целиком.
**Файлы:** `method_of_moments/tests/test_solver.py`

**Тесты:**
- `test_4x4_matches_3x3_at_beta_fixed` — при beta_fixed=True результаты идентичны
- `test_4x4_beta_stays_positive` — β(t) > 0 на суточном расчёте
- `test_4x4_Sgw_non_negative` — Sg_w ≥ 0 (или ≥ −ε) — ключевая мотивация FEAT-010
- `test_4x4_oscillations_reduced` — амплитуда осцилляций r_b меньше, чем в 3×3
- `test_4x4_steady_state` — стационар при t→∞ близок к 3×3

**Оценка:** ~100 строк.

---

## Шаг 10: Визуализация и сравнение 3×3 vs 4×4

**Цель:** построить графики динамики и профилей для 4×4 системы, сравнить с 3×3.
**Файлы:** `method_of_moments/results/plot_results.py`

**Что сделать:**
1. Запустить solve_moments с beta_fixed=False, t_eps=100, t_end=86400
2. Построить r_b(t), Sg_w(t), β(t), ΔTw(t) — 4 панели
3. Сравнить Sg_w(t) с 3×3 — показать отсутствие отрицательных значений

**Оценка:** ~50 строк.

---

## Критерии завершения

- [ ] OdeState содержит beta
- [ ] 6 новых функций: gas_A2beta, gas_A41, gas_A42, gas_A43, gas_A44, gas_F4
- [ ] assemble_ode_system поддерживает beta_fixed=False → 4×4
- [ ] make_rhs и solve_moments поддерживают 4 переменные
- [ ] SaturationProfile.__call__ принимает опциональный beta
- [ ] Все существующие тесты зелёные (обратная совместимость)
- [ ] Unit-тесты новых коэффициентов зелёные
- [ ] Интеграционный тест: 4×4 при beta_fixed=True = 3×3
- [ ] Интеграционный тест: Sg_w ≥ 0 на суточном расчёте
- [ ] Конфиг: beta_fixed: true/false

## Подводные камни

- ⚠️ gas_A21/A22 используют s_profile.beta — решено в шаге 1.5 (gas_A23 НЕ использует β)
- ⚠️ При Sg_w → 0: A₄₃ → 0, матрица вырождается — в ode_system.py (шаг 5) добавить clamp: при Sg_w < 1e-6 принудительно β̇=0 (решить 3×3, β = const на этом шаге)
- ⚠️ cond(A 4×4) ≈ 10¹² — плохая обусловленность, но float64 даёт 3–4 значащие цифры
- ⚠️ reconstruct_profiles должен передавать beta из ODE в SaturationProfile
- ✅ F₄ не содержит потока на r_w — сингулярность при γ < 1 подавлена

## Связанные заметки

- [[планируемые фичи]] — FEAT-010, FEAT-011
- [[feat-011 beta-moment-derivation]] — формулы
- `moments_method.tex` §5.5
- GitHub: #13 (FEAT-010), #14 (FEAT-011, закрыт)
