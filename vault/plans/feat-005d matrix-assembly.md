---
tags:
  - план
  - вычисление
date: 2026-07-31
issue: FEAT-005d
github: 8
branch: feat/feat-005d/matrix-assembly
model_level: М.6
status: в процессе
audit:
  date: 2026-07-31
  found: 0
  auto-fixed: 0
  manual-required: 0
  rounds: 10
---

# FEAT-005d: Сборка матрицы A и вектора F, проверка невырожденности

## Как начать работу по этому плану

1. Прочитай этот файл целиком
2. Прочитай `moments_method.tex` §5.2 «Уравнения для параметров» (строки 641–688) и §5.3 «Структура коэффициентов» (строки 690–820)
3. Создай ветку: `git checkout -b feat/feat-005d/matrix-assembly`
4. Прогони тесты (baseline): `cd method_of_moments && .venv/Scripts/python -m pytest tests/ -v`
5. Убедись: 273 теста, все зелёные
6. Начни с шага 1. После каждого шага: pytest

---

## Контекст

Коэффициенты трёх уравнений (масса нефти, масса газа, энергия) уже реализованы:
- **FEAT-005a:** `oil_A11`, `oil_A13`, `oil_F1` (сигнатура: `fluid, rock, p_profile, t_profile, state`, кроме F1 который принимает ещё `s_profile`)
- **FEAT-005b:** `gas_A21`, `gas_A22`, `gas_A23`, `gas_F2` (сигнатура: `fluid, rock, p_profile, t_profile, s_profile, state`)
- **FEAT-005c:** `energy_A31`, `energy_A33`, `energy_F3` (сигнатура: `fluid, rock, p_profile, t_profile, s_profile, state`)

Все 10 функций — в `method_of_moments/src/coefficients.py` (494 строки).

Задача — собрать их в матрицу A (3×3) и вектор F (3×1), проверить невырожденность.

---

## Формулы

### Матричная система (eq:ode_system, строки 673–688)

```latex
\begin{pmatrix}
  \mathcal{A}_{11} & \mathcal{A}_{12} & \mathcal{A}_{13} \\
  \mathcal{A}_{21} & \mathcal{A}_{22} & \mathcal{A}_{23} \\
  \mathcal{A}_{31} & \mathcal{A}_{32} & \mathcal{A}_{33}
\end{pmatrix}
\begin{pmatrix}
  \dot{r}_b \\ \dot{S}_{g,w} \\ \dot{\Delta T}_w
\end{pmatrix}
=
\begin{pmatrix}
  \mathcal{F}_1 \\ \mathcal{F}_2 \\ \mathcal{F}_3
\end{pmatrix}
```

Вектор неизвестных: **ẋ** = (ṙ_b, Ṡ_{g,w}, Δ̇T_w)ᵀ.

### Структура расщепления (eq:matrix_structure, строка 795)

```latex
\mathcal{A}_{12} = 0, \qquad \mathcal{A}_{32} = 0.
```

Матрица:
```
⎛ A₁₁   0    A₁₃ ⎞
⎜ A₂₁  A₂₂  A₂₃ ⎟
⎝ A₃₁   0    A₃₃ ⎠
```

Следствие (строки 806–808): из 1-го и 3-го уравнений определяются ṙ_b и Δ̇T_w (подсистема 2×2), после чего из 2-го — Ṡ_{g,w}.

### Определитель

```
det(A) = A₂₂ · (A₁₁·A₃₃ − A₁₃·A₃₁)
```

Невырожденность требует:
1. A₂₂ ≠ 0 (уже проверено в FEAT-005b: `test_A22_positive`)
2. A₁₁·A₃₃ − A₁₃·A₃₁ ≠ 0 (определитель подсистемы 2×2)

---

## Обратная совместимость

- [x] Существующие тесты (273) пройдут без изменений — добавляем новую функцию, не меняем старые
- [x] Существующие конфиги работают без изменений
- [x] API существующих функций не меняется
- [x] Не добавляет новых зависимостей

---

## Подводные камни

- ✅ **Сигнатуры функций:** oil_A11 и oil_A13 не принимают `s_profile`, остальные — принимают. Функция сборки должна принимать полный набор аргументов и передавать каждому коэффициенту нужное подмножество.
- ✅ **Численная устойчивость:** `np.linalg.solve` предпочтительнее ручного обращения матрицы. Но для FEAT-005d достаточно проверить det(A) ≠ 0; решение ẋ = A⁻¹·F будет в FEAT-007a.
- ✅ **Import-цепочки:** нет circular imports — всё внутри одного модуля.
- ✅ **Размерности:** A — безразмерная/[м·Па⁻¹], F — зависит от строки. Главное — det(A) ≠ 0 и ẋ конечно.
- ✅ **Аллокация в горячем цикле:** `np.zeros((3,3))` и `np.array([...])` создают новые массивы на каждый вызов. В FEAT-007a функция будет вызываться в правой части ODE (тысячи раз). Для текущей задачи допустимо; если профилирование покажет bottleneck — вынести аллокацию наружу.
- ⚠️ **Обусловленность матрицы:** при baseline cond(A) ≈ 10⁹, при малом Sg cond(A) ≈ 4×10¹¹. Причина — масштабы строк различаются на 8 порядков (уравнение давления ~10¹, уравнение энергии ~10⁹). `np.linalg.solve` (LAPACK dgesv с частичным выбором главного элемента) справляется, решение ẋ конечно и физически корректно. Но при переходе к FEAT-007a стоит рассмотреть масштабирование строк (row scaling) или использование подсистемы 2×2 с последующей подстановкой, что снижает cond до ~10⁵.

---

## Связь формула → код

| Формула | Уравнение в tex | Python-функция | Модуль | Статус |
|---|---|---|---|---|
| A (3×3) | `\eqref{eq:ode_system}` | `assemble_ode_system()` | `src/coefficients.py` | **новая** |
| A₁₂ = 0 | `\eqref{eq:matrix_structure}` | явно `A[0,1] = 0.0` | — | часть сборки |
| A₃₂ = 0 | `\eqref{eq:matrix_structure}` | явно `A[2,1] = 0.0` | — | часть сборки |
| det(A) | аналитическая формула | `np.linalg.det(A)` | тест | **новый тест** |
| ẋ = A⁻¹·F | `\eqref{eq:ode_system}` | `np.linalg.solve(A, F)` | тест | **новый тест** |

---

## Шаги реализации

### Шаг 1: Функция `assemble_ode_system`

**Цель:** создать функцию, собирающую матрицу A и вектор F из 10 коэффициентов.
**Файлы:** `method_of_moments/src/coefficients.py`

**Контекст:**
10 функций-коэффициентов уже реализованы (FEAT-005a/b/c). Нужно вызвать их и собрать результаты в numpy-массивы. Уравнение \eqref{eq:ode_system}, структура \eqref{eq:matrix_structure}.

**Что сделать:**

1. В конце файла `method_of_moments/src/coefficients.py` (после строки 494) добавить функцию:

```python
def assemble_ode_system(fluid, rock, p_profile, t_profile, s_profile, state):
    """Сборка A·ẋ=F. Ур. (eq:ode_system), (eq:matrix_structure) moments_method.tex."""
    A = np.zeros((3, 3))

    A[0, 0] = oil_A11(fluid, rock, p_profile, t_profile, state)
    # A[0, 1] = 0  — расщепление (eq:matrix_structure)
    A[0, 2] = oil_A13(fluid, rock, p_profile, t_profile, state)

    A[1, 0] = gas_A21(fluid, rock, p_profile, t_profile, s_profile, state)
    A[1, 1] = gas_A22(fluid, rock, p_profile, t_profile, s_profile, state)
    A[1, 2] = gas_A23(fluid, rock, p_profile, t_profile, s_profile, state)

    A[2, 0] = energy_A31(fluid, rock, p_profile, t_profile, s_profile, state)
    # A[2, 1] = 0  — расщепление (eq:matrix_structure)
    A[2, 2] = energy_A33(fluid, rock, p_profile, t_profile, s_profile, state)

    F = np.array([
        oil_F1(fluid, rock, p_profile, t_profile, s_profile, state),
        gas_F2(fluid, rock, p_profile, t_profile, s_profile, state),
        energy_F3(fluid, rock, p_profile, t_profile, s_profile, state),
    ])

    return A, F
```

2. Сигнатура — объединение всех аргументов (совпадает с `energy_F3`, наиболее полным). `oil_A11` и `oil_A13` не принимают `s_profile` — передаём им только нужные аргументы.

**Проверка после шага:**
- Регрессия: `.venv/Scripts/python -m pytest tests/ -v` — 273 теста зелёные (добавление функции не ломает ничего).

**Зависимости:** нет. Блокирует: шаги 2–7.
**Оценка:** ~25 строк, ~5 минут

---

### Шаг 2: Тест структуры расщепления

**Цель:** проверить, что A₁₂ = 0 и A₃₂ = 0.
**Файлы:** `method_of_moments/tests/test_coefficients.py`

**Контекст:**
Расщепление \eqref{eq:matrix_structure}: давление и температура не зависят от S_{g,w} напрямую, поэтому A₁₂ = A₃₂ = 0. Это — структурное свойство матрицы, гарантированное конструкцией. Тест фиксирует это ожидание.

**Что сделать:**

1. Добавить `import numpy as np` в блок third-party импортов (после `import pytest`, строка 7). Сейчас файл не импортирует numpy — он нужен для `np.linalg.det`, `np.linalg.solve`, `np.all`, `np.isfinite` в тестах шагов 3–7. По PEP8: numpy — сторонняя библиотека, размещается рядом с pytest, а не в блоке stdlib (json, math, pathlib).

2. Добавить `assemble_ode_system` в import из `src.coefficients` (строка 10–17):

```python
from src.coefficients import (
    frozen_pvt_zone1, frozen_pvt_zone2,
    dp_drb_numerical, dp_dpwf_numerical,
    oil_A11, oil_A13, oil_F1,
    gas_A21, gas_A22, gas_A23, gas_F2,
    energy_A31, energy_A33, energy_F3,
    assemble_ode_system,
    OdeState,
)
```

3. Добавить тестовый класс после `TestConsistency` (конец файла):

```python
class TestAssembly:
    """Тесты сборки матрицы A и вектора F — FEAT-005d."""

    def test_A12_zero(self, fluid, rock, p_profile, t_profile, s_profile):
        """A₁₂ = 0 — расщепление (eq:matrix_structure)."""
        state = _make_state()
        A, F = assemble_ode_system(fluid, rock, p_profile, t_profile, s_profile, state)
        assert A[0, 1] == 0.0, f"A₁₂ должен быть 0, получено {A[0, 1]:.6e}"

    def test_A32_zero(self, fluid, rock, p_profile, t_profile, s_profile):
        """A₃₂ = 0 — расщепление (eq:matrix_structure)."""
        state = _make_state()
        A, F = assemble_ode_system(fluid, rock, p_profile, t_profile, s_profile, state)
        assert A[2, 1] == 0.0, f"A₃₂ должен быть 0, получено {A[2, 1]:.6e}"
```

**Проверка после шага:**
- Тест: `.venv/Scripts/python -m pytest tests/test_coefficients.py -k "TestAssembly" -v`
- Регрессия: `.venv/Scripts/python -m pytest tests/ -v`

**Зависимости:** требует шаг 1. Блокирует: ничего.
**Оценка:** ~15 строк, ~5 минут

---

### Шаг 3: Тест невырожденности det(A) ≠ 0

**Цель:** проверить, что матрица A невырождена при baseline параметрах.
**Файлы:** `method_of_moments/tests/test_coefficients.py`

**Контекст:**
Для разрешимости системы A·ẋ = F необходимо det(A) ≠ 0. С учётом расщепления:

```
det(A) = A₂₂ · (A₁₁·A₃₃ − A₁₃·A₃₁)
```

Нужно проверить оба множителя. A₂₂ > 0 — уже есть тест `test_A22_positive`. Подсистему 2×2 нужно проверить отдельно.

**Что сделать:**

Добавить в `TestAssembly`:

```python
    def test_det_nonzero(self, fluid, rock, p_profile, t_profile, s_profile):
        """det(A) ≠ 0 при baseline параметрах."""
        state = _make_state()
        A, F = assemble_ode_system(fluid, rock, p_profile, t_profile, s_profile, state)
        det = np.linalg.det(A)
        assert det != 0.0, "det(A) = 0 — матрица вырождена"
        assert np.isfinite(det), f"det(A) не конечен: {det}"

    def test_2x2_subsystem_nonsingular(self, fluid, rock, p_profile, t_profile,
                                        s_profile):
        """Определитель подсистемы 2×2 (уравнения 1 и 3) ненулевой."""
        state = _make_state()
        A, F = assemble_ode_system(fluid, rock, p_profile, t_profile, s_profile, state)
        det_13 = A[0, 0] * A[2, 2] - A[0, 2] * A[2, 0]
        assert det_13 != 0.0, (
            f"A₁₁·A₃₃ − A₁₃·A₃₁ = {det_13:.6e} — подсистема 2×2 вырождена"
        )
```

**Проверка после шага:**
- Тест: `.venv/Scripts/python -m pytest tests/test_coefficients.py -k "test_det or test_2x2" -v`
- Регрессия: `.venv/Scripts/python -m pytest tests/ -v`

**Зависимости:** требует шаг 1. Блокирует: ничего.
**Оценка:** ~15 строк, ~5 минут

---

### Шаг 4: Тест конечности элементов A и F

**Цель:** проверить, что все элементы A и F конечны (не NaN, не ±∞).
**Файлы:** `method_of_moments/tests/test_coefficients.py`

**Контекст:**
Функции-коэффициенты вычисляют интегралы через `scipy.integrate.quad`. При некорректных параметрах могут возникнуть NaN/Inf. Тест гарантирует целостность сборки.

**Что сделать:**

Добавить в `TestAssembly`:

```python
    def test_all_finite(self, fluid, rock, p_profile, t_profile, s_profile):
        """Все элементы A и F конечны."""
        state = _make_state()
        A, F = assemble_ode_system(fluid, rock, p_profile, t_profile, s_profile, state)
        assert np.all(np.isfinite(A)), f"A содержит NaN/Inf:\n{A}"
        assert np.all(np.isfinite(F)), f"F содержит NaN/Inf: {F}"
```

**Проверка после шага:**
- Тест: `.venv/Scripts/python -m pytest tests/test_coefficients.py -k "test_all_finite" -v`
- Регрессия: `.venv/Scripts/python -m pytest tests/ -v`

**Зависимости:** требует шаг 1. Блокирует: ничего.
**Оценка:** ~8 строк, ~3 минуты

---

### Шаг 5: Тест решения ẋ = A⁻¹·F

**Цель:** проверить, что система разрешима и ẋ имеет физический смысл.
**Файлы:** `method_of_moments/tests/test_coefficients.py`

**Контекст:**
При baseline параметрах ожидаем:
- ṙ_b > 0 (зона разгазирования растёт)
- Ṡ_{g,w} — знак зависит от динамики, но конечен
- Δ̇T_w — охлаждение (обычно < 0 или ≈ 0 при малых dT_w)
Все три — конечны. Тест `TestConsistency.test_dot_rb_positive` уже проверяет ṙ_b > 0 через F₁/A₁₁ (без энергии). Новый тест — через полную матрицу.

**Что сделать:**

Добавить в `TestAssembly`:

```python
    def test_solve_finite(self, fluid, rock, p_profile, t_profile, s_profile):
        """ẋ = A⁻¹·F — все компоненты конечны."""
        state = _make_state()
        A, F = assemble_ode_system(fluid, rock, p_profile, t_profile, s_profile, state)
        x_dot = np.linalg.solve(A, F)
        assert np.all(np.isfinite(x_dot)), f"ẋ содержит NaN/Inf: {x_dot}"

    def test_solve_dot_rb_positive(self, fluid, rock, p_profile, t_profile,
                                    s_profile):
        """ṙ_b > 0 из полной матричной системы."""
        state = _make_state()
        A, F = assemble_ode_system(fluid, rock, p_profile, t_profile, s_profile, state)
        x_dot = np.linalg.solve(A, F)
        assert x_dot[0] > 0, (
            f"ṙ_b = {x_dot[0]:.6e} должен быть > 0 (зона разгазирования растёт)"
        )
```

**Проверка после шага:**
- Тест: `.venv/Scripts/python -m pytest tests/test_coefficients.py -k "test_solve" -v`
- Регрессия: `.venv/Scripts/python -m pytest tests/ -v`

**Зависимости:** требует шаг 1. Блокирует: ничего.
**Оценка:** ~15 строк, ~5 минут

---

### Шаг 6: Тест согласованности с покомпонентными тестами

**Цель:** проверить, что `assemble_ode_system` возвращает те же значения, что и отдельные функции.
**Файлы:** `method_of_moments/tests/test_coefficients.py`

**Контекст:**
Функция `assemble_ode_system` вызывает те же `oil_A11`, `gas_A22` и т.д. Тест-регрессия: значения из сборки совпадают с прямыми вызовами.

**Что сделать:**

Добавить в `TestAssembly`:

```python
    def test_assembly_matches_components(self, fluid, rock, p_profile,
                                         t_profile, s_profile):
        """Элементы A и F из сборки совпадают с прямыми вызовами."""
        state = _make_state()
        A, F = assemble_ode_system(fluid, rock, p_profile, t_profile, s_profile, state)

        assert A[0, 0] == pytest.approx(oil_A11(fluid, rock, p_profile, t_profile, state))
        assert A[0, 2] == pytest.approx(oil_A13(fluid, rock, p_profile, t_profile, state))
        assert A[1, 0] == pytest.approx(gas_A21(fluid, rock, p_profile, t_profile, s_profile, state))
        assert A[1, 1] == pytest.approx(gas_A22(fluid, rock, p_profile, t_profile, s_profile, state))
        assert A[1, 2] == pytest.approx(gas_A23(fluid, rock, p_profile, t_profile, s_profile, state))
        assert A[2, 0] == pytest.approx(energy_A31(fluid, rock, p_profile, t_profile, s_profile, state))
        assert A[2, 2] == pytest.approx(energy_A33(fluid, rock, p_profile, t_profile, s_profile, state))

        assert F[0] == pytest.approx(oil_F1(fluid, rock, p_profile, t_profile, s_profile, state))
        assert F[1] == pytest.approx(gas_F2(fluid, rock, p_profile, t_profile, s_profile, state))
        assert F[2] == pytest.approx(energy_F3(fluid, rock, p_profile, t_profile, s_profile, state))
```

**Проверка после шага:**
- Тест: `.venv/Scripts/python -m pytest tests/test_coefficients.py -k "test_assembly_matches" -v`
- Регрессия: `.venv/Scripts/python -m pytest tests/ -v`

**Зависимости:** требует шаг 1. Блокирует: ничего.
**Оценка:** ~15 строк, ~5 минут

---

### Шаг 7: Тест при малом Sg_w (предельный случай)

**Цель:** проверить работоспособность сборки при Sg_w → 0 (начало разгазирования).
**Файлы:** `method_of_moments/tests/test_coefficients.py`

**Контекст:**
В начале процесса Sg_w ≈ 0 и rb ≈ rw. Матрица должна оставаться невырожденной и ẋ — конечным. Это критический предельный случай для FEAT-006 (начальная асимптотика) и FEAT-007b (solve_ivp).

**Что сделать:**

Добавить в `TestAssembly`:

```python
    def test_small_Sg(self, fluid, rock, p_profile, t_profile, s_profile):
        """Сборка работает при малом Sg_w ≈ 0.01 и rb ≈ rw."""
        state = _make_state(r_b=0.2, Sg_w=0.01, dT_w=0.1)
        A, F = assemble_ode_system(fluid, rock, p_profile, t_profile, s_profile, state)
        assert np.all(np.isfinite(A)), f"A при Sg≈0:\n{A}"
        assert np.all(np.isfinite(F)), f"F при Sg≈0: {F}"
        det = np.linalg.det(A)
        assert det != 0.0, f"det(A) = 0 при Sg≈0"
```

> **Примечание:** R_W = 0.1 в тестах, поэтому r_b = 0.2 — зона разгазирования толщиной r_b − r_w = 0.1 м.

**Проверка после шага:**
- Тест: `.venv/Scripts/python -m pytest tests/test_coefficients.py -k "test_small_Sg" -v`
- Регрессия: `.venv/Scripts/python -m pytest tests/ -v`

**Зависимости:** требует шаг 1. Блокирует: ничего.
**Оценка:** ~10 строк, ~5 минут

---

## Тестовая стратегия

| Категория | Тест | Шаг | Что предотвращает |
|---|---|---|---|
| Unit | `test_A12_zero`, `test_A32_zero` | 2 | нарушение структуры расщепления |
| Unit | `test_det_nonzero`, `test_2x2_subsystem_nonsingular` | 3 | вырождение матрицы |
| Unit | `test_all_finite` | 4 | NaN/Inf в коэффициентах |
| Unit | `test_solve_finite`, `test_solve_dot_rb_positive` | 5 | некорректное решение системы |
| Согласованность | `test_assembly_matches_components` | 6 | рассогласование сборки с компонентами |
| Граничные | `test_small_Sg` | 7 | отказ при начальных условиях |
| Регрессия | все 273 существующих | каждый шаг | обратная совместимость |

---

## Критерии завершения

- [ ] Функция `assemble_ode_system` реализована
- [ ] Docstring с ссылкой на `\eqref{eq:ode_system}`, `\eqref{eq:matrix_structure}`
- [ ] 9 новых тестов зелёные
- [ ] Все 273 существующих теста зелёные
- [ ] Vault обновлён (статус FEAT-005d)
- [ ] GitHub issue #8 прокомментирован

---

## Обнаруженные проблемы

Нет блокирующих проблем. Задача полностью покрыта готовыми зависимостями.
