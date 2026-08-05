---
tags:
  - план
  - рефакторинг
date: 2026-08-05
issue: DEBT-004
github: 15
branch: refactor/debt-004/fixed-weight-4th-moment
status: в процессе
audit:
  date: 2026-08-05
  found: 0
  auto-fixed: 0
  manual-required: 0
  rounds: 3
  note: 3 раунда аудита. Формулы верифицированы от первого принципа. Проверено: линейная независимость строк 2 и 4, консистентность метода взвешенных невязок, обусловленность при β→∞, вырожденные случаи γ→0.
---

# DEBT-004: Замена весовой функции 4-го момента на фиксированную $w_4 = r\eta^2$

## Контекст

В системе 4×4 (FEAT-010) четвёртый интегральный момент уравнения насыщенности
получается умножением на $w_4 = r\eta^\beta$ и интегрированием от $r_w$ до $r_b$
(§5.5 `moments_method.tex`, ур. `eq:Sg_moment_beta`).

Весовая функция зависит от искомой переменной $\beta(t)$, что:
1. Порождает интегралы с $\eta^{2\beta}$ (удвоение степени), стремящиеся к нулю при $\beta \to \infty$ → вырождение 4-й строки матрицы $A$.
2. Создаёт положительную обратную связь: рост $\beta$ → вырождение → неточный $\dot\beta$ → дальнейший рост.
3. Нарушает каноническую структуру метода моментов (весовая должна быть фиксированной).

**Решение:** заменить $w_4 = r\eta^\beta$ на $w_4 = r\eta^2$ (фиксированное $q = 2$).

При этом:
- $A_{42}$, $A_{44}$, $F_4^{(V)}$, $I_{p_{wf}}^{(4)}$ перестанут зависеть от $\beta$ в весе (но $A_{42}$ по-прежнему содержит $\eta^\beta$ через профиль $S_g$).
- $A_{41}$, $A_{43}$ будут содержать $\eta^{\beta+2}$ вместо $\eta^{2\beta}$ — первый порядок по $\beta$, без вырождения.
- `gas_A2beta` (2-е уравнение) **не меняется** — он не использует весовую 4-го момента.

## Связь текущие формулы → новые формулы

### Производные $\partial S_g / \partial t$

Производные $\partial S_g / \partial r_b$, $\partial S_g / \partial S_{g,w}$, $\partial S_g / \partial \beta$
**не меняются** (ур. `eq:dSg_drb`, `eq:dSg_dbeta`). Меняется только то, на что они умножаются при
интегрировании.

Текущие (ур. `eq:eta_dSg_drb`–`eq:eta_dSg_dbeta`):
```
η^β · ∂Sg/∂r_b  = Sg_w · β · η^{2β} / (r_b · L_b)
η^β · ∂Sg/∂Sgw  = η^β · (1 − η^β)
η^β · ∂Sg/∂β    = −Sg_w · η^{2β} · ln η
```

Новые (вес $\eta^2$ вместо $\eta^\beta$):
```
η^2 · ∂Sg/∂r_b  = Sg_w · β · η^{β+2} / (r_b · L_b)
η^2 · ∂Sg/∂Sgw  = η^2 · (1 − η^β)
η^2 · ∂Sg/∂β    = −Sg_w · η^{β+2} · ln η
```

### Таблица замен в коэффициентах

| Элемент | Текущая формула (§5.5) | Новая формула | Что меняется в подынтегральном |
|---|---|---|---|
| $A_{41}$ `eq:A41` | $\frac{S_{g,w}\beta}{r_b L_b}\int r\,\eta^{2\beta}\,dr - \int r\,\eta^\beta\,S_o(c_r+c_o^{\text{sat}})\frac{\partial p}{\partial r_b}\,dr$ | $\frac{S_{g,w}\beta}{r_b L_b}\int r\,\eta^{\beta+2}\,dr - \int r\,\eta^2\,S_o(c_r+c_o^{\text{sat}})\frac{\partial p}{\partial r_b}\,dr$ | 1-й: $\eta^{2\beta}\to\eta^{\beta+2}$; 2-й: $\eta^\beta\to\eta^2$ |
| $A_{42}$ `eq:A42` | $\int r\,\eta^\beta(1-\eta^\beta)\,dr$ | $\int r\,\eta^2(1-\eta^\beta)\,dr$ | $\eta^\beta(1-\eta^\beta)\to\eta^2(1-\eta^\beta)$ |
| $A_{43}$ `eq:A43` | $-S_{g,w}\int r\,\eta^{2\beta}\ln\eta\,dr$ | $-S_{g,w}\int r\,\eta^{\beta+2}\ln\eta\,dr$ | $\eta^{2\beta}\to\eta^{\beta+2}$ |
| $A_{44}$ `eq:A44` | $-\int r\,\eta^\beta\,S_o\beta_o^{\text{sat}}\Psi\,dr$ | $-\int r\,\eta^2\,S_o\beta_o^{\text{sat}}\Psi\,dr$ | $\eta^\beta\to\eta^2$ |
| $F_4^{\text{bound}}$ `eq:F4_boundary` | $-\frac{B_o}{\phi}[\eta^\beta\frac{r\lambda_o}{B_o}p']_{r_w}^{r_b}$ | $-\frac{B_o}{\phi}[\eta^2\frac{r\lambda_o}{B_o}p']_{r_w}^{r_b}$ | $\eta^\beta\to\eta^2$; при $r_w$: $\eta^2=0$ (подавление) |
| $F_4^{(V)}$ `eq:F4_volume` | $\frac{B_o}{\phi}\frac{\beta}{L_b}\int\eta^{\beta-1}\frac{\lambda_o}{B_o}p'\,dr$ | $\frac{B_o}{\phi}\frac{2}{L_b}\int\eta\frac{\lambda_o}{B_o}p'\,dr$ | $\beta\eta^{\beta-1}\to 2\eta$; **не зависит от $\beta$** |
| $I_{p_{wf}}^{(4)}$ | $\int r\,\eta^\beta\,S_o(c_r+c_o^{\text{sat}})\frac{\partial p}{\partial p_{wf}}\,dr$ | $\int r\,\eta^2\,S_o(c_r+c_o^{\text{sat}})\frac{\partial p}{\partial p_{wf}}\,dr$ | $\eta^\beta\to\eta^2$ |

## Baseline

- 336 тестов, все зелёные (2026-08-05, коммит `3771877`)
- Тесты 4-го момента: `TestA41` (2), `TestA42` (2), `TestA43` (2), `TestA44` (2), `TestF4` (2) — 10 тестов
- Тесты 4×4 системы: `TestSolve4x4` (5 тестов)
- `gas_A2beta` (2-е уравнение) — **не затронут**

## Затронутые файлы

| Файл | Роль | Что менять |
|---|---|---|
| `method_of_moments/moments_method.tex` | §5.5 | Пересчёт ур. `eq:Sg_moment_beta`–`eq:F4` |
| `method_of_moments/src/coefficients.py` | строки 357–507 | `gas_A41`–`gas_F4`: подынтегральные |
| `method_of_moments/src/coefficients.py` | строки 662–709 | `assemble_ode_system`: без изменений (вызовы те же) |
| `method_of_moments/src/integrals.py` | строки 9–11 | `I_S`: проверить, используется ли в A4x — нет, не используется (A4x считают через `quad`) |
| `method_of_moments/tests/test_coefficients.py` | строки 737–819 | Обновить docstrings и ожидания тестов |

**Не затрагиваются:**
- `src/profiles/saturation.py` — профиль $S_g(r)$ не меняется
- `src/ode_system.py` — вызывает `assemble_ode_system`, не знает о весовых
- `src/integrals.py` — `I_S` используется только в `gas_A21`/`gas_A22` (2-й момент)
- `src/solver.py`, `src/initial.py`, `src/main.py` — не затрагиваются
- Все коэффициенты 1-го, 2-го, 3-го уравнений — не затрагиваются

## Как начать работу по этому плану

1. Прочитай этот файл целиком
2. Прочитай `moments_method.tex` §5.5 (строки 1487–1670) — текущие формулы
3. Создай ветку: `git checkout -b refactor/debt-004/fixed-weight-4th-moment`
4. Прогони тесты (baseline): `cd method_of_moments && .venv\Scripts\python -m pytest tests/ -v`
5. Запомни: 336 тестов, все зелёные — это baseline
6. Начни с шага 1. После каждого шага: pytest

---

## Шаг 1: Обновить формулы в `moments_method.tex`

**Цель:** пересчитать §5.5 — заменить все вхождения $\eta^\beta$ (как весовой функции) на $\eta^2$.

**Файлы:** `method_of_moments/moments_method.tex` (строки 1487–1670)

**Контекст:**
§5.5 содержит вывод 4-го момента уравнения насыщенности. Весовая функция задаётся в абзаце
«Выбор весовой функции 4-го момента» (строка 1487). Далее формулы `eq:Sg_moment_beta`,
`eq:dM4_dt`, `eq:eta_dSg_drb`–`eq:eta_dSg_dbeta`, `eq:A41`–`eq:A44`, `eq:F4_boundary`,
`eq:F4_volume`, `eq:F4` — все содержат $\eta^\beta$ как весовую.

**Что сделать:**

1. **Строки 1487–1498** — абзац «Выбор весовой функции 4-го момента»:
   - Заменить $w_4(r) = r\,\eta^\beta$ на $w_4(r) = r\,\eta^2$
   - Обосновать выбор: фиксированная весовая, подавляет сингулярность $p'$ при $r_w$,
     линейно независима от нулевого момента ($w = r$), не вырождается при $\beta \to \infty$
   - Убрать аргумент про «замкнутые интегралы (степенные по $\eta$)» — теперь интегралы
     с $\eta^{\beta+2}$ вычисляются численно через `quad` (как и A₁₁, A₁₃)

2. **Строки 1500–1506** — «Четвёртый момент» (ур. `eq:Sg_moment_beta`):
   - Заменить $r\,\eta^\beta$ на $r\,\eta^2$ в интегралах

3. **Строки 1516–1547** — «Левая часть» (ур. `eq:dM4_dt`, `eq:eta_dSg_drb`–`eq:eta_dSg_dbeta`):
   - `eq:dM4_dt`: заменить $r\,\eta^\beta$ на $r\,\eta^2$ в интеграле
   - `eq:eta_dSg_drb`: $\eta^\beta \cdot \partial S_g/\partial r_b = S_{g,w}\beta\eta^{2\beta}/(r_b L_b)$
     → $\eta^2 \cdot \partial S_g/\partial r_b = S_{g,w}\beta\eta^{\beta+2}/(r_b L_b)$
   - `eq:eta_dSg_dSgw`: $\eta^\beta(1-\eta^\beta)$
     → $\eta^2(1-\eta^\beta)$
   - `eq:eta_dSg_dbeta`: $-S_{g,w}\eta^{2\beta}\ln\eta$
     → $-S_{g,w}\eta^{\beta+2}\ln\eta$

4. **Строки 1549–1565** — $A_{41}$ (ур. `eq:A41`):
   - Геометрический интеграл: $\int r\,\eta^{2\beta}\,dr$ → $\int r\,\eta^{\beta+2}\,dr$
   - Давленческий интеграл: $\int r\,\eta^\beta\,S_o(c_r+c_o^{\text{sat}})\frac{\partial p}{\partial r_b}\,dr$
     → $\int r\,\eta^2\,S_o(c_r+c_o^{\text{sat}})\frac{\partial p}{\partial r_b}\,dr$

5. **Строки 1571–1578** — $A_{42}$ (ур. `eq:A42`):
   - $\int r\,\eta^\beta(1-\eta^\beta)\,dr$ → $\int r\,\eta^2(1-\eta^\beta)\,dr$

6. **Строки 1581–1593** — $A_{43}$ (ур. `eq:A43`):
   - $-S_{g,w}\int r\,\eta^{2\beta}\ln\eta\,dr$ → $-S_{g,w}\int r\,\eta^{\beta+2}\ln\eta\,dr$
   - Обновить замечание о знаке: $\ln\eta < 0$ при $\eta \in (0,1)$, множитель $\eta^{\beta+2} > 0$,
     значит $A_{43} > 0$ при $S_{g,w} > 0$ — знак сохраняется

7. **Строки 1595–1607** — $A_{44}$ (ур. `eq:A44`):
   - $-\int r\,\eta^\beta\,S_o\beta_o^{\text{sat}}\Psi\,dr$
     → $-\int r\,\eta^2\,S_o\beta_o^{\text{sat}}\Psi\,dr$

8. **Строки 1609–1665** — $F_4$ (ур. `eq:F4_boundary`, `eq:F4_volume`, `eq:F4`):
   - `eq:F4_boundary`: $[\eta^\beta \cdot r\lambda_o/B_o \cdot p']_{r_w}^{r_b}$
     → $[\eta^2 \cdot r\lambda_o/B_o \cdot p']_{r_w}^{r_b}$
   - Граничные значения: при $r_b$: $\eta^2 = 1$ (как было). При $r_w$: $\eta^2 = 0$ — сингулярность подавлена (как было).
   - `eq:F4_volume`: $d(\eta^\beta)/dr = \beta\eta^{\beta-1}/(rL_b)$
     → $d(\eta^2)/dr = 2\eta/(rL_b)$ — **фиксированная производная, не зависит от $\beta$**.
   - Объёмный интеграл: $\frac{B_o}{\phi}\frac{\beta}{L_b}\int\eta^{\beta-1}\frac{\lambda_o}{B_o}p'\,dr$
     → $\frac{B_o}{\phi}\frac{2}{L_b}\int\eta\frac{\lambda_o}{B_o}p'\,dr$
   - Сходимость: подынтегральное $\propto \eta^1 \cdot \eta^{\gamma-1} = \eta^{\gamma}$.
     Сходится при $\gamma > -1$ (тривиально всегда). Раньше: $\eta^{\beta+\gamma-2}$, сходимость при $\beta+\gamma > 1$.
   - Обновить `eq:F4`: $I_{p_{wf}}^{(4)}$ — заменить $\eta^\beta$ на $\eta^2$ в подынтегральном

9. **Строки 1667–1670** — базовый интеграл `eq:K_base`:
   - Формула $\int_0^1 \eta^m\ln\eta\,d\eta = -1/(m+1)^2$ — без изменений (общая формула)

10. **Строки 1676–1681** — замкнутая формула `eq:I_S_tilde` для $A_{42}$:
    - Было: $\widetilde{I}_S^{(n)}(\beta) = \int_0^1 \eta^{n+\beta}(1-\eta^\beta)\,d\eta = \frac{1}{n+\beta+1} - \frac{1}{n+2\beta+1}$
    - Станет (вес $\eta^2$ вместо $\eta^\beta$): $\widetilde{I}_S^{(n)}(\beta) = \int_0^1 \eta^{n+2}(1-\eta^\beta)\,d\eta = \frac{1}{n+3} - \frac{1}{n+\beta+3}$
    - При $n = 0$ (единственный используемый): $\frac{1}{3} - \frac{1}{\beta+3}$

11. **Строки 1683–1687** — замкнутая формула `eq:K_S` для $A_{43}$:
    - Было: $\int_0^1 \eta^{2\beta}\ln\eta\,d\eta = -\frac{1}{(2\beta+1)^2}$
    - Станет: $\int_0^1 \eta^{\beta+2}\ln\eta\,d\eta = -\frac{1}{(\beta+3)^2}$

12. **Строки 1689–1693** — формула `eq:K_A2beta` для $A_{2\beta}$:
    - **Без изменений** — $A_{2\beta}$ не затрагивается

**Проверка после этого шага:**
- LaTeX компилируется: `cd method_of_moments && pdflatex -interaction=nonstopmode moments_method.tex`
- Формулы непротиворечивы: проверить знаки, пределы при $\beta \to 1$, $\beta \to \infty$
- pytest: все 336 тестов зелёные (код не изменён)

**Подводные камни:**
- ⚠️ Не забыть обновить текст после формул (объяснения знаков, структурные комментарии)
- ⚠️ Проверить, нет ли ссылок на $\eta^\beta$ как весовую в других разделах `moments_method.tex`

**Зависимости:** нет

**Оценка:** ~50 строк LaTeX, ~30 минут

---

## Шаг 2: Переписать `gas_A41` в `coefficients.py`

**Цель:** заменить подынтегральные в `gas_A41`: $\eta^{2\beta} \to \eta^{\beta+2}$, $\eta^\beta \to \eta^2$.

**Файлы:** `method_of_moments/src/coefficients.py` (строки 357–386)

**Контекст:**
`gas_A41` — коэффициент при $\dot r_b$ в 4-м уравнении. Содержит два интеграла:
1. Геометрический: $\int r\,\eta^{2\beta}\,dr$ — степень $2\beta$ вырождается.
2. Давленческий: $\int r\,\eta^\beta\,S_o(c_r+c_o^{\text{sat}})\frac{\partial p}{\partial r_b}\,dr$ — вес $\eta^\beta$.

**Что сделать:**

1. В `integrand_eta` (строка 375): заменить `eta ** (2.0 * beta)` на `eta ** (beta + 2.0)`
2. В `integrand_pressure` (строка 382): заменить `eta**beta` на `eta**2`
3. Обновить docstring: ссылка на новое уравнение
4. Обновить комментарий в заголовке (строка 354): `η^{2β}` → `η^{β+2}`, `η^β` → `η^2`

**Изменения:**

До (строка 375):
```python
return r * eta ** (2.0 * beta)
```
После:
```python
return r * eta ** (beta + 2.0)
```

До (строка 382):
```python
return r * eta**beta * So1 * (cr + co_sat_1) * dp
```
После:
```python
return r * eta**2 * So1 * (cr + co_sat_1) * dp
```

**Проверка:** `pytest tests/test_coefficients.py::TestA41 -v` — тесты должны пройти (они проверяют конечность и знак, не абсолютные значения).

**Подводные камни:**
- ✅ `beta` всё ещё нужен в `integrand_eta` (степень $\beta + 2$)
- ✅ `beta` больше не нужен в `integrand_pressure` — но переменная используется в первом слагаемом `Sg_w * beta / (r_b * L_b) * I_eta`, так что оставить

**Зависимости:** шаг 1 (формулы пересчитаны)

**Оценка:** ~4 строки, ~5 минут

---

## Шаг 3: Переписать `gas_A42` в `coefficients.py`

**Цель:** заменить $\eta^\beta(1-\eta^\beta) \to \eta^2(1-\eta^\beta)$.

**Файлы:** `method_of_moments/src/coefficients.py` (строки 392–403)

**Что сделать:**

1. В `integrand` (строка 400): заменить `eta**beta * (1.0 - eta**beta)` на `eta**2 * (1.0 - eta**beta)`
2. Обновить комментарий и docstring

**Изменения:**

До (строка 400):
```python
return r * eta**beta * (1.0 - eta**beta)
```
После:
```python
return r * eta**2 * (1.0 - eta**beta)
```

**Проверка:** `pytest tests/test_coefficients.py::TestA42 -v`
- `test_A42_positive`: $\int r\,\eta^2(1-\eta^\beta)\,dr > 0$ — да, $\eta^2 \geq 0$, $(1-\eta^\beta) \geq 0$ при $\eta \in [0,1]$, $\beta > 0$.
- `test_A42_less_than_A22`: $A_{42}^{\text{new}} < A_{22}$? $A_{22} = \int r(1-\eta^\beta)\,dr$, $A_{42}^{\text{new}} = \int r\,\eta^2(1-\eta^\beta)\,dr$. Поскольку $\eta^2 \leq 1$, $A_{42} \leq A_{22}$. Строгое неравенство, т.к. $\eta^2 < 1$ на $(r_w, r_b)$.

**Подводные камни:**
- ✅ `beta` по-прежнему нужен для $(1-\eta^\beta)$ — это часть профиля $S_g$, не весовая

**Зависимости:** шаг 1

**Оценка:** ~2 строки, ~3 минуты

---

## Шаг 4: Переписать `gas_A43` в `coefficients.py`

**Цель:** заменить $\eta^{2\beta}\ln\eta \to \eta^{\beta+2}\ln\eta$.

**Файлы:** `method_of_moments/src/coefficients.py` (строки 409–423)

**Что сделать:**

1. В `integrand` (строка 420): заменить `eta ** (2.0 * beta)` на `eta ** (beta + 2.0)`
2. Обновить комментарий и docstring

**Изменения:**

До (строка 420):
```python
return r * eta ** (2.0 * beta) * np.log(eta)
```
После:
```python
return r * eta ** (beta + 2.0) * np.log(eta)
```

**Проверка:** `pytest tests/test_coefficients.py::TestA43 -v`
- `test_A43_positive`: $-S_{g,w}\int r\,\eta^{\beta+2}\ln\eta\,dr > 0$?
  $\ln\eta < 0$, $\eta^{\beta+2} > 0$ → интеграл $< 0$ → $-S_{g,w} \cdot (\text{отр.}) > 0$. Да.
- `test_A43_zero_at_Sg0`: $A_{43} = -0 \cdot I = 0$. Да.

**Зависимости:** шаг 1

**Оценка:** ~2 строки, ~3 минуты

---

## Шаг 5: Переписать `gas_A44` в `coefficients.py`

**Цель:** заменить $\eta^\beta \to \eta^2$ в весе.

**Файлы:** `method_of_moments/src/coefficients.py` (строки 429–449)

**Что сделать:**

1. В `integrand` (строка 446): заменить `eta**beta` на `eta**2`
2. Обновить docstring
3. Переменная `beta = state.beta` (строка 435) больше не нужна — удалить

**Изменения:**

До (строка 446):
```python
return r * eta**beta * So1 * beta_o_sat_1 * t_profile.Psi(zeta)
```
После:
```python
return r * eta**2 * So1 * beta_o_sat_1 * t_profile.Psi(zeta)
```

**Проверка:** `pytest tests/test_coefficients.py::TestA44 -v`
- `test_A44_sign_like_A23`: $A_{44}^{\text{new}} = -\int r\,\eta^2\,S_o\beta_o^{\text{sat}}\Psi\,dr$.
  $A_{23} = -\int r\,S_o\beta_o^{\text{sat}}\Psi\,dr$.
  Единственная разница — множитель $\eta^2 \geq 0$. Знак сохраняется.
- `test_A44_finite`: $\eta^2$ конечна всюду. Да.

**Зависимости:** шаг 1

**Оценка:** ~3 строки, ~3 минуты

---

## Шаг 6: Переписать `gas_F4` в `coefficients.py`

**Цель:** заменить весовую в объёмном интеграле и $I_{p_{wf}}^{(4)}$.

**Файлы:** `method_of_moments/src/coefficients.py` (строки 455–507)

**Контекст:**
`gas_F4` содержит три слагаемых:
1. `boundary`: граничный поток на $r_b$ — **не меняется** (при $r_b$: $\eta = 1$, $\eta^\beta = \eta^2 = 1$).
2. `F4_vol`: объёмный интеграл с $d(\eta^\beta)/dr = \beta\eta^{\beta-1}/(rL_b)$ → $d(\eta^2)/dr = 2\eta/(rL_b)$.
3. `I_pwf`: интеграл с $\eta^\beta$ → $\eta^2$.

**Что сделать:**

1. **Строки 482–490** — `integrand_vol` и `F4_vol`:
   - До: `eta ** (beta - 1.0)` в подынтегральном, `beta / L_b` в множителе
   - После: `eta` в подынтегральном, `2.0 / L_b` в множителе
   - Удалить зависимость от `beta` в этом блоке

2. **Строки 498–502** — `integrand_pwf`:
   - До: `eta**beta` в подынтегральном
   - После: `eta**2`

3. Переменная `beta = state.beta` (строка 463) больше не нужна — удалить

**Изменения:**

До (строка 487):
```python
return eta ** (beta - 1.0) * mob_o_Bo_frozen * dp_dr
```
После:
```python
return eta * mob_o_Bo_frozen * dp_dr
```

До (строка 490):
```python
F4_vol = (Bo_frozen / phi) * (beta / L_b) * I_vol
```
После:
```python
F4_vol = (Bo_frozen / phi) * (2.0 / L_b) * I_vol
```

До (строка 502):
```python
return r * eta**beta * So1 * (cr + co_sat_1) * dp
```
После:
```python
return r * eta**2 * So1 * (cr + co_sat_1) * dp
```

**Проверка:** `pytest tests/test_coefficients.py::TestF4 -v`
- `test_F4_finite`: $\eta$ конечна, $\eta^{\gamma-1}$ в `dp_dr` — сходимость $\eta \cdot \eta^{\gamma-1} = \eta^\gamma$, конечна при $\gamma > 0$ (всегда). Раньше: $\eta^{\beta+\gamma-2}$, тоже конечна, но теперь проще.
- `test_F4_no_rw_singularity`: сингулярность подавлена $\eta^2(r_w) = 0$. Да.

**Подводные камни:**
- ⚠️ Проверить условие `if eta <= 0.0: return 0.0` в `integrand_vol` (строка 484) — оно было для $\eta^{\beta-1}$, которая расходится при $\eta = 0$ и $\beta < 1$. Теперь подынтегральное — $\eta$, конечно при $\eta = 0$. Условие можно убрать, но безопаснее оставить как guard.

**Зависимости:** шаг 1

**Оценка:** ~6 строк, ~5 минут

---

## Шаг 7: Обновить тесты в `test_coefficients.py`

**Цель:** адаптировать тесты A41–F4 к новой весовой функции.

**Файлы:** `method_of_moments/tests/test_coefficients.py` (строки 737–819)

**Контекст:**
Тесты проверяют знак, конечность и структурные соотношения. Большинство пройдёт без изменений,
потому что свойства (знак, конечность) сохраняются. Нужно обновить docstring-ы и добавить
тест на устойчивость при большом $\beta$.

**Что сделать:**

1. **TestA41** (строки 737–749):
   - `test_A41_structure_like_A21`: обновить docstring — «дополнительный вес $\eta^2$» вместо «$\eta^\beta$»
   - Без изменений в логике

2. **TestA42** (строки 755–767):
   - `test_A42_less_than_A22`: docstring — «множитель $\eta^2 < 1$» вместо «$\eta^\beta < 1$»
   - Без изменений в логике (неравенство сохраняется)

3. **TestA43** (строки 773–784):
   - docstring: «Галёркин» → убрать (весовая фиксирована, это Петров–Галёркин, не Галёркин)
   - Без изменений в логике

4. **TestA44** (строки 790–803):
   - Без изменений в логике

5. **TestF4** (строки 809–819):
   - `test_F4_no_rw_singularity`: docstring — «подавлена весом $\eta^2$» вместо «$\eta^\beta$»
   - Без изменений в логике

6. **Добавить параметр `beta` в `_make_state`** (строка 218):
   ```python
   def _make_state(r_b=5.0, Sg_w=0.1, dT_w=2.0, p_wf=P_WF, dp_wf_dt=0.0, beta=BETA):
       return OdeState(r_b=r_b, Sg_w=Sg_w, dT_w=dT_w, p_wf=p_wf,
                       dp_wf_dt=dp_wf_dt, beta=beta)
   ```
   `OdeState` — dataclass (не NamedTuple), `_replace` не работает.
   Добавление `beta=BETA` по умолчанию не меняет поведение существующих тестов.

7. **Новый тест:** `test_A42_stable_at_large_beta`:
   ```python
   def test_A42_stable_at_large_beta(self, fluid, rock, p_profile, t_profile, s_profile):
       """A₄₂ конечен и > 0 при β = 100 (регрессия DEBT-004)."""
       state = _make_state(Sg_w=0.1, beta=100.0)
       val = gas_A42(fluid, rock, p_profile, t_profile, s_profile, state)
       assert np.isfinite(val), f"A₄₂ не конечен при β=100: {val}"
       assert val > 0, f"A₄₂ должен быть > 0 при β=100, получено {val:.6e}"
   ```

8. **Новый тест:** `test_A43_stable_at_large_beta`:
   ```python
   def test_A43_stable_at_large_beta(self, fluid, rock, p_profile, t_profile, s_profile):
       """A₄₃ конечен и > 0 при β = 100 (регрессия DEBT-004)."""
       state = _make_state(Sg_w=0.1, beta=100.0)
       val = gas_A43(fluid, rock, p_profile, t_profile, s_profile, state)
       assert np.isfinite(val), f"A₄₃ не конечен при β=100: {val}"
       assert val > 0, f"A₄₃ должен быть > 0 при β=100, получено {val:.6e}"
   ```

9. **Новый тест** в `TestF4`: `test_F4_stable_at_large_beta`:
   ```python
   def test_F4_stable_at_large_beta(self, fluid, rock, p_profile, t_profile, s_profile):
       """F₄ конечен при β = 100 (регрессия DEBT-004)."""
       state = _make_state(Sg_w=0.1, beta=100.0)
       val = gas_F4(fluid, rock, p_profile, t_profile, s_profile, state)
       assert np.isfinite(val), f"F₄ не конечен при β=100: {val}"
   ```

**Проверка:** `pytest tests/test_coefficients.py -v -k "A41 or A42 or A43 or A44 or F4"` — все тесты зелёные.

**Подводные камни:**
- ✅ `_make_state` не принимала `beta` — исправлено добавлением параметра в пункте 6
- ✅ `OdeState` — dataclass, не NamedTuple; `_replace` не работает — использован прямой параметр

**Зависимости:** шаги 2–6

**Оценка:** ~40 строк, ~10 минут

---

## Шаг 8: Прогнать полный набор тестов

**Цель:** убедиться, что 3×3 система (`beta_fixed=True`) не затронута, 4×4 работает с новыми формулами.

**Файлы:** нет изменений

**Что сделать:**

1. `cd method_of_moments && .venv\Scripts\python -m pytest tests/ -v`
2. Проверить:
   - Все 336 + 3 новых = 339 тестов зелёные (+ обновлённая `_make_state` — 0 новых)
   - `TestSolve4x4::test_4x4_runs` — проходит
   - `TestSolve4x4::test_4x4_all_finite` — проходит
   - `TestSolve4x4::test_4x4_beta_positive` — $\beta > 0$ на всём решении
   - `TestSolve4x4::test_4x4_Sgw_bounds` — $S_{g,w} \geq 0$

3. Если `TestSolve4x4` падает — это ожидаемо, т.к. динамика $\beta(t)$ изменится.
   Проверить вручную: запустить `src/main.py configs/baseline.json` и визуально оценить
   $r_b(t)$, $S_{g,w}(t)$, $\beta(t)$, $\Delta T_w(t)$.

**Проверка:**
- Все тесты зелёные
- Нет IntegrationWarning в stderr
- `TestSolve4x4` работает без ошибок

**Зависимости:** шаги 2–7

**Оценка:** ~2 минуты на pytest, ~5 минут на анализ если что-то упало

---

## Шаг 9: Обновить vault

**Цель:** зафиксировать результат в vault.

**Файлы:**
- `vault/roadmap/известные баги и технический долг.md` — DEBT-004
- `vault/plans/debt-004 fixed-weight-4th-moment.md` — этот файл

**Что сделать:**

1. В записи DEBT-004: статус 🔴 ОТКРЫТ → ✅ ГОТОВО (дата)
2. Обновить `status:` в frontmatter этого плана: `готов к реализации` → `реализован`
3. Прокомментировать GitHub issue:
   ```
   gh issue comment 15 --repo ArturSalamatin/Oil_Gas --body-file <scratchpad>/debt004_done.md
   ```
   Содержание: «Весовая функция заменена на $w_4 = r\eta^2$. Тесты: N passed. Ветка: ...»

**Зависимости:** шаг 8

**Оценка:** ~5 минут

---

## Чеклист подводных камней

- [x] **Все call sites найдены:** `gas_A41`–`gas_F4` вызываются только в `assemble_ode_system` (строки 697–706) — ✅ безопасно
- [x] **Зависимости пакетов:** не меняются — ✅ безопасно
- [x] **Обратная совместимость API:** сигнатуры `gas_A41`–`gas_F4` не меняются — ✅ безопасно
- [x] **Тесты:** 10 существующих тестов A4x/F4 + 5 тестов 4×4 — ⚠️ docstring-ы обновить, значения проверить
- [x] **Circular imports:** не меняется — ✅ безопасно
- [x] **Docstrings:** ссылки на `\eqref{}` остаются те же (labels в tex не меняются) — ✅ безопасно
- [x] **Configs:** не затрагиваются — ✅ безопасно
- [x] **Связь с другими задачами:** DEBT-003 (параметризация $\Phi$) — не конфликтует; FEAT-010 (β как ODE-переменная) — совместимо; `gas_A2beta` — не затрагивается — ✅ безопасно
- [x] **Производительность:** `quad` по-прежнему вычисляет интегралы, количество вызовов не меняется — ✅ безопасно

## Критерии завершения

- [ ] Все шаги 1–9 выполнены
- [ ] Формулы в `moments_method.tex` §5.5 обновлены, LaTeX компилируется
- [ ] `gas_A41`–`gas_F4` переписаны с фиксированной весовой $\eta^2$
- [ ] Все существующие тесты зелёные
- [ ] 3 новых теста (large_beta) зелёные
- [ ] `TestSolve4x4` зелёный
- [ ] Vault обновлён
- [ ] GitHub issue #15 прокомментирован

## Обнаруженные проблемы

Нет новых проблем. `_make_state` не имела параметра `beta` — добавлен в шаг 7 (пункт 6).
