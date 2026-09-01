---
tags:
  - план
  - баг
  - energy-solver
date: 2026-09-01
issue: BUG-002
github: 19
branch: fix/bug-002/double-ln-conductive
status: в процессе
audit:
  date: 2026-09-01
  found: 0
  auto-fixed: 0
  manual-required: 0
  round: 2
---

# BUG-002: Двойной ln в кондуктивной проводимости TridiagEnergySolver

## Как начать работу по этому плану

1. Прочитай этот файл целиком
2. Прочитай `numerical_solver/gpn_multiphase_solver/energy/tridiag.py`, строки 148–177
3. Прочитай `numerical_solver/tests/test_energy.py`, строки 604–662
4. Создай ветку: `git checkout -b fix/bug-002/double-ln-conductive`
5. Прогони тесты (baseline): `cd numerical_solver && .venv\Scripts\python -m pytest tests/ -v`
   Ожидается: 576 тестов, все зелёные.
6. Начни с шага 1.

**Рабочая директория:** `numerical_solver/` (не `method_of_moments/`).

## Суть бага

`compute_conductive_transmissibility` в `tridiag.py:152–168` вычисляет кондуктивную проводимость грани как:

```python
lambda_face = 1.0 / (w_L / lam_L + w_R / lam_R)   # line 165
geom = 2.0 * np.pi * grid.h / np.log(r_c[1:] / r_c[:-1])  # line 166-167
Q_T_internal = geom * lambda_face                    # line 168
```

При однородном λ: `w_L + w_R = ln(r_{j+1}/r_j)`, поэтому `lambda_face = λ/ln`, а `geom = 2πh/ln`. Результат: `Q_T = 2πhλ/ln²` — **двойной ln**.

Правильная формула (последовательные кольцевые сопротивления):

```
Q_T = 1 / (R_left + R_right) = 2πh / (w_L/λ_L + w_R/λ_R)
```

При однородном λ: `Q_T = 2πhλ/ln` — **один ln**.

Контурная грань (`Q_T_ext`, строки 172–175) корректна: `geom_ext * λ[-1]` — один ln.

## Корневая причина

Формула eq:heat_cond_disc в `problem_statement.tex` записана как `Q = (2πh/ln) · λ_face`, подразумевая нормированное `λ_face` (с `w_L + w_R = 1`). Но `LogRadialGrid.log_weights_left/right` — **ненормированные** (`w_L + w_R = ln`). Код слепо подставляет ненормированные веса в формулу для нормированных — получается лишний `1/ln`.

## Влияние

- **VAL-002 кейс C:** порядок сходимости 0.5 вместо ≥ 2 (подтверждено)
- **Кейс D:** диффузия замедлена в ~ln раз
- **Кейс B:** незаметно (Pe ≫ 1, кондукция пренебрежима)
- Существующие тесты (`test_energy.py`) проверяют текущую формулу — они пройдут с двойным ln, но физически неверны

---

## Шаг 1: Фикс в tridiag.py

**Цель:** исправить формулу кондуктивной проводимости внутренних граней.

**Файлы:** `numerical_solver/gpn_multiphase_solver/energy/tridiag.py`

**Что сделать:**

В функции `compute_conductive_transmissibility`, строки 158–168: заменить `geom * lambda_face` на прямую формулу последовательных сопротивлений.

**Изменения:**

До (строки 158–168):
```python
        # Внутренние грани
        if N > 1:
            w_L = grid.log_weights_left
            w_R = grid.log_weights_right
            lam_L = lambda_eff[:-1]
            lam_R = lambda_eff[1:]
            # Гармоническое среднее с логарифмическими весами (eq. 21)
            lambda_face = 1.0 / (w_L / lam_L + w_R / lam_R)
            geom = 2.0 * np.pi * grid.h / np.log(
                grid.r_centers[1:] / grid.r_centers[:-1])
            Q_T_internal = geom * lambda_face
```

После:
```python
        # Внутренние грани
        if N > 1:
            w_L = grid.log_weights_left    # ln(r_face / r_center_left)
            w_R = grid.log_weights_right   # ln(r_center_right / r_face)
            lam_L = lambda_eff[:-1]
            lam_R = lambda_eff[1:]
            # Последовательные кольцевые сопротивления: R = w/λ, Q_T = 2πh / ΣR
            Q_T_internal = 2.0 * np.pi * grid.h / (w_L / lam_L + w_R / lam_R)
```

Также обновить docstring:

До:
```python
        """Q_T[f] = (2πh / ln(r_c[f]/r_c[f-1])) · λ_face (eq. 21, 25).
        Возвращает Q_T_internal [N-1] и Q_T_ext (скаляр).
        """
```

После:
```python
        """Кондуктивная проводимость: Q_T = 2πh / (w_L/λ_L + w_R/λ_R).

        Последовательные кольцевые сопротивления R_α = ln(r_face/r_center_α) / (2πh·λ_α).
        Возвращает Q_T_internal [N-1] и Q_T_ext (скаляр).
        """
```

**Проверка после шага:**
```
cd numerical_solver && .venv\Scripts\python -m pytest tests/test_energy.py -k "TestComputeConductiveTransmissibility" -v
```
Ожидается: `test_uniform_lambda` FAIL (ожидает старую формулу). Остальные — PASS.

**Зависимости:** нет.
**Оценка:** ~5 строк, ~5 мин.

---

## Шаг 2: Обновить тесты в test_energy.py

**Цель:** привести тесты в соответствие с правильной формулой.

**Файлы:** `numerical_solver/tests/test_energy.py`

**Что сделать:**

`TestComputeConductiveTransmissibility.test_uniform_lambda` (строки 607–629): обновить ожидаемое значение.

До (строки 622–629):
```python
        # При однородном lambda: lambda_face = lam / (w_L + w_R)
        w_L = grid.log_weights_left
        w_R = grid.log_weights_right
        lambda_face = lam_val / (w_L + w_R)
        geom = 2.0 * np.pi * grid.h / np.log(
            grid.r_centers[1:] / grid.r_centers[:-1])
        expected = geom * lambda_face
        np.testing.assert_allclose(Q_T_int, expected, rtol=1e-12)
```

После:
```python
        # Последовательные сопротивления: Q_T = 2πh / (w_L/λ + w_R/λ) = 2πhλ / (w_L + w_R)
        w_L = grid.log_weights_left
        w_R = grid.log_weights_right
        expected = 2.0 * np.pi * grid.h * lam_val / (w_L + w_R)
        np.testing.assert_allclose(Q_T_int, expected, rtol=1e-12)
```

**Проверка после шага:**
```
cd numerical_solver && .venv\Scripts\python -m pytest tests/test_energy.py -k "TestComputeConductiveTransmissibility" -v
```
Ожидается: все 3 теста PASS.

Затем полная регрессия:
```
cd numerical_solver && .venv\Scripts\python -m pytest tests/ -v
```

**Зависимости:** шаг 1.
**Оценка:** ~5 строк, ~5 мин.

---

## Шаг 3: Обновить тесты в test_val002.py

**Цель:** ужесточить тесты VAL-002, которые были ослаблены из-за BUG-002.

**Файлы:** `numerical_solver/tests/test_val002.py`

**Что сделать:**

1. `test_conductive_transmissibility_single_ln` (кейс D): тест должен теперь подтвердить ratio ≈ 1 (один ln). Упростить: убрать ветвление if/else, оставить `np.testing.assert_allclose(ratio, 1.0, rtol=0.05)`.

2. `test_convergence_order_positive` (кейс C): переименовать в `test_convergence_order_ge_2`, ужесточить `assert order >= 1.8`.

**Проверка после шага:**
```
cd numerical_solver && .venv\Scripts\python -m pytest tests/test_val002.py -v
```
Ожидается: все 18 тестов PASS (порядок сходимости теперь ≥ 2).

**Зависимости:** шаг 1.
**Оценка:** ~10 строк, ~10 мин.

---

## Шаг 4: Обновить problem_statement.tex

**Цель:** исправить формулу eq:heat_cond_disc.

**Файлы:** `numerical_solver/doc/problem_statement.tex`

**Что сделать:**

Найти eq:heat_cond_disc (grep `label{eq:heat_cond_disc}`). Текущая формула:

```latex
Q_{\lambda,j+\half} = \frac{2\pi\,h}{\ln(r_{j+1}/r_j)}\,
    {\leff}^{j+\half}\,(T_j - T_{j+1}),
```

Заменить на формулу последовательных сопротивлений:

```latex
Q_{\lambda,j+\half} = \frac{2\pi\,h}
    {\dfrac{\ln(r_{j+\half}/r_j)}{{\leff}_j}
    + \dfrac{\ln(r_{j+1}/r_{j+\half})}{{\leff}_{j+1}}}
    \,(T_j - T_{j+1}),
```

И обновить текст после формулы: убрать упоминание «отдельного гармонического среднего» — теперь оно встроено в формулу.

**Проверка после шага:**
```powershell
cd d:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\doc
pdflatex -interaction=nonstopmode problem_statement.tex
```
Проверить: формула корректно отображается, нет ошибок компиляции.

**Зависимости:** нет (независим от кода).
**Оценка:** ~10 строк LaTeX, ~15 мин.

---

## Чеклист подводных камней

- [x] **Побочные эффекты:** `compute_conductive_transmissibility` вызывается только из `solve()` того же класса — нет внешних зависимостей
- [x] **Q_T_ext:** контурная грань (`geom_ext * lambda_eff[-1]`) — один ln, корректна, **не менять**
- [x] **Граничные случаи:** λ=0 → Q_T=0 (деление на ноль обрабатывается numpy: inf в знаменателе → 0 в числителе при 1/(w/0+w/0) = 0). Тест `test_zero_lambda_gives_zero_Q_T` проверяет
- [x] **Обратная совместимость:** изменение **улучшает** точность, не ломает API
- [x] **Связь с другими задачами:** нет конфликтов — фикс на отдельной ветке
- [x] **Тесты diagonal dominance** (`test_energy.py:690+`): после фикса Q_T увеличится (один ln вместо двойного), коэффициенты a, b, c изменятся. Diagonal dominance сохраняется: Q_T входит симметрично в b и a+c, при конечном dt cap >> 0 гарантирует b > |a|+|c|
- [x] **Остальные тесты energy** (TestPureConduction, TestConvectionPlusConduction, TestStability и др.): проверяют свойства (T→T_ext, bounded, no NaN), не точные числа — должны пройти при увеличенном Q_T. Полная регрессия на шаге 2 это верифицирует

## Критерии завершения

- [ ] `test_uniform_lambda` — зелёный с правильной формулой
- [ ] `test_conductive_transmissibility_single_ln` — ratio ≈ 1
- [ ] `test_convergence_order_ge_2` — порядок ≥ 1.8
- [ ] Все 576 тестов зелёные
- [ ] `problem_statement.tex` компилируется
- [ ] Vault обновлён: BUG-002 → ИСПРАВЛЕНО
- [ ] GitHub issue #19 прокомментирован
