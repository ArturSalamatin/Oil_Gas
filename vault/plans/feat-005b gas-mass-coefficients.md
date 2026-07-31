---
tags:
  - план
  - физика
date: 2026-07-30
issue: FEAT-005b
github: 6
branch: feat/feat-005b/gas-mass-coefficients
model_level: М.6
status: реализован
audit:
  date: 2026-07-30
  found: 1
  auto-fixed: 1
  manual-required: 0
  round: 6
---

# FEAT-005b: Уравнение массы газа — коэффициенты A₂₁, A₂₂, A₂₃, F₂

## Как начать работу по этому плану

1. Прочитай этот файл целиком
2. Прочитай `moments_method.tex`: §3.3 (eq:Sg_moment0, eq:Sg_flux), §4.3 (eq:Sg_profile), §5 (eq:ode2, eq:matrix_structure, eq:dp_dt, eq:dT_dt)
3. Прочитай `coefficients.py` целиком — шаблон из FEAT-005a
4. Создай ветку: `git checkout -b feat/feat-005b/gas-mass-coefficients`
5. Прогони тесты (baseline): `cd method_of_moments && .venv/Scripts/python -m pytest tests/ -v`
6. Начни с шага 1. После каждого шага: pytest

---

## Связь формула → код

| Формула | Уравнение в tex | Python-функция | Модуль | Тест |
|---|---|---|---|---|
| $\mathcal{A}_{21}$ | `\eqref{eq:ode2}` via `\eqref{eq:Sg_moment0}` + `\eqref{eq:dp_dt}` | `gas_A21()` | `src/coefficients.py` | `test_A21_*` |
| $\mathcal{A}_{22}$ | `\eqref{eq:ode2}` via `\eqref{eq:Sg_moment0}` + `\eqref{eq:Sg_profile}` | `gas_A22()` | `src/coefficients.py` | `test_A22_*` |
| $\mathcal{A}_{23}$ | `\eqref{eq:ode2}` via `\eqref{eq:Sg_moment0}` + `\eqref{eq:dT_dt}` | `gas_A23()` | `src/coefficients.py` | `test_A23_*` |
| $\mathcal{F}_2$ | `\eqref{eq:ode2}` via `\eqref{eq:Sg_moment0}` | `gas_F2()` | `src/coefficients.py` | `test_F2_*` |

---

## Вывод явных формул

### Исходное уравнение

Нулевой момент насыщенности `\eqref{eq:Sg_moment0}`:

$$\frac{d\mathcal{S}_0}{dt} = \int_{r_w}^{r_b} r\,S_o\,(c_r+c_o^{\text{sat}})\,\frac{\partial p}{\partial t}\,dr - \int_{r_w}^{r_b} r\,S_o\,\beta_o^{\text{sat}}\,\frac{\partial T}{\partial t}\,dr - \frac{B_o}{\phi}\left[\frac{r\lambda_o}{B_o}\frac{\partial p}{\partial r}\right]_{r_w}^{r_b}$$

### Левая часть: раскрытие $d\mathcal{S}_0/dt$

$$\mathcal{S}_0 = \int_{r_w}^{r_b(t)} r\,S_g(r,t)\,dr$$

По правилу Лейбница:

$$\frac{d\mathcal{S}_0}{dt} = \underbrace{r_b\,S_g(r_b)\,\dot{r}_b}_{= 0,\;\text{т.к. } S_g(r_b)=0} + \int_{r_w}^{r_b} r\,\frac{\partial S_g}{\partial t}\,dr$$

Профиль `\eqref{eq:Sg_profile}`: $S_g(r,t) = S_{g,w}(t)\,[1 - \eta^\beta]$, где $\eta = \ln(r/r_w)/L_b$, $L_b = \ln(r_b/r_w)$.

Производная по времени:

$$\frac{\partial S_g}{\partial t} = \dot{S}_{g,w}\,(1-\eta^\beta) + S_{g,w}\,\beta\,\eta^{\beta-1}\,\frac{\eta}{r_b\,L_b}\,\dot{r}_b$$

> Второй член: $\partial\eta/\partial r_b = -\eta/(r_b L_b)$, отсюда $\partial S_g/\partial r_b = S_{g,w}\beta\eta^{\beta-1}\cdot\eta/(r_b L_b)$.

Подставляя в интеграл:

$$\int_{r_w}^{r_b} r\,\frac{\partial S_g}{\partial t}\,dr = \dot{S}_{g,w}\underbrace{\int_{r_w}^{r_b} r\,(1-\eta^\beta)\,dr}_{I_{S_g}} + \dot{r}_b\,\frac{S_{g,w}\beta}{r_b L_b}\underbrace{\int_{r_w}^{r_b} r\,\eta^\beta\,dr}_{I_{\eta^\beta}}$$

### Подстановка $\partial p/\partial t$ и $\partial T/\partial t$

Из `\eqref{eq:dp_dt}`: $\partial p/\partial t \approx (\partial p/\partial r_b)\,\dot{r}_b + (\partial p/\partial p_{wf})\,\dot{p}_{wf}$

Из `\eqref{eq:dT_dt}`: $\partial T/\partial t = -\Psi(\zeta)\,\dot{\Delta T}_w$ (т.к. $\partial T/\partial r_b = 0$)

### Сбор коэффициентов

Переносим левую часть направо, собираем при $\dot{r}_b$, $\dot{S}_{g,w}$, $\dot{\Delta T}_w$:

#### $\mathcal{A}_{21}$ (при $\dot{r}_b$):

$$\boxed{\mathcal{A}_{21} = \underbrace{\frac{S_{g,w}\beta}{r_b L_b}\int_{r_w}^{r_b} r\,\eta^\beta\,dr}_{\text{вклад из } d\mathcal{S}_0/dt} - \underbrace{\int_{r_w}^{r_b} r\,S_o\,(c_r+c_o^{\text{sat}})\,\frac{\partial p}{\partial r_b}\,dr}_{\text{вклад давления (перенесён из RHS)}}}$$

> Знак: первый член (из $d\mathcal{S}_0/dt$, стоит в LHS) — положительный. Второй член (из $\int r S_o(c_r+c_o^{\text{sat}})\partial p/\partial t$, перенесён из RHS в LHS со сменой знака) — также положительный ($\partial p/\partial r_b < 0$, минус перед интегралом даёт $> 0$). Оба слагаемых одного знака, $\mathcal{A}_{21} > 0$.
> Первый интеграл — только по зоне разгазирования (в отличие от $\mathcal{A}_{11}$, который по всей области).
> Второй интеграл — вклад от зависимости $\eta(r, r_b)$ через $L_b(r_b)$.
> Замороженные PVT: $S_o = 1 - \bar{S}_{g,1}$, $(c_r+c_o^{\text{sat}})$ при $(\bar{p}_1, \bar{T}_1)$.

#### $\mathcal{A}_{22}$ (при $\dot{S}_{g,w}$):

$$\boxed{\mathcal{A}_{22} = \int_{r_w}^{r_b} r\,(1-\eta^\beta)\,dr}$$

> Коэффициент при $\dot{S}_{g,w}$: давление и температура не зависят от $S_{g,w}$, перенесённые из RHS члены не дают вклада. Остаётся только вклад из $d\mathcal{S}_0/dt$.
> **Знак:** $1 - \eta^\beta \geq 0$ при $\eta \in [0,1]$, $r > 0$ ⟹ $\mathcal{A}_{22} > 0$.

#### $\mathcal{A}_{23}$ (при $\dot{\Delta T}_w$):

$$\boxed{\mathcal{A}_{23} = -\int_{r_w}^{r_b} r\,S_o\,\beta_o^{\text{sat}}\,\Psi(\zeta)\,dr}$$

> Знак: из RHS стоит $-\int r S_o \beta_o^{\text{sat}} (\partial T/\partial t)\,dr$. Перенос в LHS даёт $+\int r S_o \beta_o^{\text{sat}} (\partial T/\partial t)\,dr$. Подстановка $\partial T/\partial t = -\Psi(\zeta)\dot{\Delta T}_w$: коэффициент при $\dot{\Delta T}_w$ = $-\int r S_o \beta_o^{\text{sat}} \Psi\,dr$.
> **Знак $\mathcal{A}_{23}$:** $\operatorname{sign}(\mathcal{A}_{23}) = -\operatorname{sign}(\beta_o^{\text{sat}})$, т.к. $S_o > 0$ и $\Psi > 0$. При baseline условиях ($\bar{p}_1 = 16.5$ МПа, $\bar{T}_1 = 348$ К) **$\beta_o^{\text{sat}} < 0$** (коррекция $dBo/dRs \cdot dRs/dT / Bo$ превышает тепловое расширение $\beta_o$), поэтому $\mathcal{A}_{23} > 0$.
> Замороженные PVT: $S_o = 1 - \bar{S}_{g,1}$, $\beta_o^{\text{sat}}$ при $(\bar{p}_1, \bar{T}_1)$.
> Только зона разгазирования (домен интегрирования $[r_w, r_b]$).

#### $\mathcal{F}_2$ (правая часть):

$$\boxed{\mathcal{F}_2 = -\frac{B_o}{\phi}\left[\frac{r\lambda_o}{B_o}\frac{\partial p}{\partial r}\right]_{r_w}^{r_b} + I_{p_{wf}}^{(2)}\dot{p}_{wf}}$$

Граничные потоки `\eqref{eq:Sg_flux}`:

$$\left[\frac{r\lambda_o}{B_o}\frac{\partial p}{\partial r}\right]_{r_w}^{r_b} = \frac{r_b\,\lambda_o(r_b)}{B_o(p_b, T_b)}\,p'_b - \frac{r_w\,\lambda_o(r_w)}{B_o(p_{wf}, T_w)}\,p'_w$$

Член с $\dot{p}_{wf}$ (аналог $I_{p_{wf}}$ из $\mathcal{F}_1$, но со знаком **+**: в eq:Sg_moment0 $I_{p_{wf}}^{(2)}$ находится в RHS и не переносится в LHS, в отличие от eq:moment0 где $I_{p_{wf}}$ в LHS и переносится со сменой знака):

$$I_{p_{wf}}^{(2)} = \int_{r_w}^{r_b} r\,S_o\,(c_r+c_o^{\text{sat}})\,\frac{\partial p}{\partial p_{wf}}\,dr$$

> При стационарном $p_{wf}$: $\dot{p}_{wf} = 0$, член обнуляется.
> Заметим: в $\mathcal{F}_2$ нет аналога $Q_\text{quad}$ — квадратичный интеграл $(dR_s/dp \cdot dp/dr + dR_s/dT \cdot dT/dr)\cdot dp/dr$ принадлежит уравнению давления, а не насыщенности.

### Ключевые отличия от первой строки

| | $\mathcal{A}_{1j}$, $\mathcal{F}_1$ (нефть) | $\mathcal{A}_{2j}$, $\mathcal{F}_2$ (газ) |
|---|---|---|
| Домен интегрирования | $[r_w, R_\text{ext}]$ | $[r_w, r_b]$ только |
| Второй столбец | $\mathcal{A}_{12} = 0$ | $\mathcal{A}_{22} \neq 0$ |
| Граничные потоки | $\Lambda \cdot dp/dr$ | $\lambda_o/B_o \cdot dp/dr$ |
| Квадратичный интеграл | Есть ($Q_\text{quad}$) | Нет |
| Дополнительный вклад в $\mathcal{A}_{21}$ | Нет | $+S_{g,w}\beta/(r_b L_b) \int r\eta^\beta dr$ (из $d\mathcal{S}_0/dt$) |

---

## Обратная совместимость

- ✅ Добавление новых функций в `coefficients.py` — не затрагивает существующий код
- ✅ Существующие тесты FEAT-005a не меняются
- ✅ `BlackOilFluid` не расширяется (все нужные методы уже есть: `co_sat`, `beta_o_sat`, `mobility_o_over_Bo`)
- ✅ Конфиг `baseline.json` не требует изменений
- ✅ `SaturationProfile` уже реализован (FEAT-003): `__call__`, `eta`, `dSg_dr`

## Подводные камни

- ✅ **Размерности:** $\mathcal{A}_{21}$ [м]: $\int r \cdot S_o \cdot (c_r+c_o^{\text{sat}}) [1/\text{Па}] \cdot (\partial p/\partial r_b) [\text{Па}/\text{м}]\,dr$ → [м · 1 · 1/м · м] = [м]. $\mathcal{A}_{22}$ [м²]: $\int r \cdot dr$ = [м²]. $\mathcal{A}_{23}$ [м²/К]: $\int r \cdot 1 \cdot (1/\text{К}) \cdot 1 \cdot dr$ = [м²/К]. $\mathcal{F}_2$ [м²/с]: $(B_o/\phi) \cdot r \cdot (\lambda_o/B_o) \cdot dp/dr$ → [1 · м · м²/(Па·с) · Па/м] = [м²/с]. Проверка: $\mathcal{A}_{21}\dot{r}_b$ [м·м/с] = [м²/с] = $[\mathcal{F}_2]$ ✓. $\mathcal{A}_{22}\dot{S}_{g,w}$ [м²·1/с] = [м²/с] ✓. $\mathcal{A}_{23}\dot{\Delta T}_w$ [м²/К·К/с] = [м²/с] ✓.
- ⚠️ **$\gamma < 1$:** производная $dp/dr$ на забое расходится. В $\mathcal{F}_2$ граничный поток на $r_w$ содержит $\lambda_o/B_o \cdot dp/dr|_{r_w}$. Решение: то же, что в FEAT-005a — отсечка $r_w + \varepsilon$ при $\gamma < 1$.
- ⚠️ **$S_g \to 0$:** при $S_{g,w} \to 0$ зона разгазирования формально существует ($r_b > r_w$), но интегралы содержат $S_o = 1 - S_g \to 1$. Все $\mathcal{A}_{2j}$ и $\mathcal{F}_2$ остаются конечными. $\mathcal{A}_{22} > 0$ всегда (чистая геометрия).
- ⚠️ **$r_b \to r_w$:** домен интегрирования вырождается, все интегралы $\to 0$. $\mathcal{A}_{22} \to 0$, что делает систему вырожденной. Но при $r_b = r_w$ газа нет ($S_g = 0$), и уравнение насыщенности не используется (начальная асимптотика FEAT-006 обеспечивает $r_b > r_w$).
- ✅ **Import-цепочки:** без циклов, те же импорты что в FEAT-005a.
- ⚠️ **$\partial p/\partial r_b$ в зоне разгазирования:** переиспользуем `dp_drb_numerical` из FEAT-005a.
- ✅ **Экспоненциальные весовые функции:** `scipy.integrate.quad`, как в FEAT-005a.
- ⚠️ **Tex hint (строка 738):** содержит ошибку знака: $\mathcal{A}_{23} \sim -\int r S_o \beta_o^{\text{sat}} (\partial T/\partial \Delta T_w) dr$, правильно $+\int$. После подстановки $\partial T/\partial \Delta T_w = -\Psi$ hint даёт неверный знак $+\int r S_o \beta_o^{\text{sat}} \Psi dr$. Формула в плане верна ($-\int r S_o \beta_o^{\text{sat}} \Psi dr$) — выведена через прямую подстановку. Исправить hint при написании §5.2.
- ⚠️ **Знак $I_{p_{wf}}^{(2)}$ в $\mathcal{F}_2$:** в отличие от $\mathcal{F}_1$ (eq:moment0, $I_{p_{wf}}$ в LHS → минус при переносе), в eq:Sg_moment0 $I_{p_{wf}}^{(2)}$ стоит в RHS → не переносится → знак **+** в $\mathcal{F}_2$.
- ⚠️ **Знак $\beta_o^{\text{sat}}$ при baseline:** при $\bar{p}_1 = 16.5$ МПа, $\bar{T}_1 = 348$ К получаем $\beta_o^{\text{sat}} = -4.4 \times 10^{-6}$ (отрицательный). Коррекция $dBo/dRs \cdot dRs/dT / Bo$ превышает $\beta_o$. Следствие: $\mathcal{A}_{23} > 0$ при baseline, а не $< 0$ как можно было бы ожидать. Тест должен проверять знаковую **согласованность** $\operatorname{sign}(A_{23}) = -\operatorname{sign}(\beta_o^{\text{sat}})$, не фиксированный знак.

---

## Шаги реализации

### Шаг 1: Функция `gas_A22`

**Цель:** реализовать простейший коэффициент — чистый геометрический интеграл без PVT.

**Файлы:** `method_of_moments/src/coefficients.py`

**Формула:**

$$\mathcal{A}_{22} = \int_{r_w}^{r_b} r\,(1 - \eta^\beta)\,dr, \quad \eta = \frac{\ln(r/r_w)}{\ln(r_b/r_w)}$$

**Что сделать:**

1. В `coefficients.py` после `oil_F1` добавить:

```python
def gas_A22(s_profile, state):
    """Коэффициент A₂₂ при Ṡg,w в уравнении массы газа. Ур. (eq:A22) moments_method.tex."""
    r_b = state.r_b
    r_w = s_profile.r_w
    beta = s_profile.beta

    def integrand(r):
        eta = s_profile.eta(r, r_b)
        return r * (1.0 - eta ** beta)

    I, _ = quad(integrand, r_w, r_b)
    return I
```

> Сигнатура минимальна: не нужны `fluid`, `rock`, `p_profile`, `t_profile` — чисто геометрический интеграл.

**Проверка после шага:**
- Регрессия: `.venv/Scripts/python -m pytest tests/ -v`

**Зависимости:** нет. Блокирует: шаг 4 (тесты).
**Оценка:** ~15 строк, ~10 минут.

---

### Шаг 2: Функция `gas_A21`

**Цель:** коэффициент при $\dot{r}_b$ — самый сложный элемент второй строки.

**Файлы:** `method_of_moments/src/coefficients.py`

**Формула:**

$$\mathcal{A}_{21} = \frac{S_{g,w}\beta}{r_b\,L_b}\int_{r_w}^{r_b} r\,\eta^\beta\,dr - \int_{r_w}^{r_b} r\,S_o\,(c_r+c_o^{\text{sat}})\,\frac{\partial p}{\partial r_b}\,dr$$

Замороженные PVT в зоне разгазирования: $S_o = 1 - \bar{S}_{g,1}$, $(c_r + c_o^{\text{sat}})$ при $(\bar{p}_1, \bar{T}_1)$.

**Что сделать:**

```python
def gas_A21(fluid, rock, p_profile, t_profile, s_profile, state):
    """Коэффициент A₂₁ при ṙ_b в уравнении массы газа. Ур. (eq:A21) moments_method.tex."""
    r_b = state.r_b
    dT_w = state.dT_w
    Sg_w = state.Sg_w
    r_w = p_profile.r_w
    cr = rock["c_r"]
    beta = s_profile.beta
    L_b = np.log(r_b / r_w)

    pbs = p_profile.pb_star(r_b, dT_w, fluid, t_profile)
    p1, T1, Sg1 = frozen_pvt_zone1(p_profile.p_wf, pbs, t_profile.T_0, dT_w, Sg_w)
    So1 = 1.0 - Sg1
    co_sat_1 = fluid.co_sat(p1, T1)

    # Интеграл 1: Sg_w·β/(r_b·L_b) · ∫r·η^β dr (из dS₀/dt)
    def integrand_eta(r):
        eta = s_profile.eta(r, r_b)
        return r * eta ** beta

    I_eta, _ = quad(integrand_eta, r_w, r_b)

    # Интеграл 2: ∫r·So·(cr+co_sat)·∂p/∂r_b dr (перенос из RHS)
    def integrand_pressure(r):
        dp = dp_drb_numerical(p_profile, r, r_b, fluid, t_profile, dT_w)
        return r * So1 * (cr + co_sat_1) * dp

    I_pressure, _ = quad(integrand_pressure, r_w, r_b)

    return Sg_w * beta / (r_b * L_b) * I_eta - I_pressure
```

**Проверка после шага:**
- Регрессия: `.venv/Scripts/python -m pytest tests/ -v`

**Зависимости:** использует `dp_drb_numerical`, `frozen_pvt_zone1` из FEAT-005a. Блокирует: шаг 4.
**Оценка:** ~30 строк, ~20 минут.

---

### Шаг 3: Функции `gas_A23` и `gas_F2`

**Цель:** температурный коэффициент и правая часть.

**Файлы:** `method_of_moments/src/coefficients.py`

#### `gas_A23`:

$$\mathcal{A}_{23} = -\int_{r_w}^{r_b} r\,S_o\,\beta_o^{\text{sat}}\,\Psi(\zeta)\,dr$$

```python
def gas_A23(fluid, rock, p_profile, t_profile, s_profile, state):
    """Коэффициент A₂₃ при Δ̇T_w в уравнении массы газа. Ур. (eq:A23) moments_method.tex."""
    r_b = state.r_b
    dT_w = state.dT_w
    Sg_w = state.Sg_w
    r_w = p_profile.r_w

    pbs = p_profile.pb_star(r_b, dT_w, fluid, t_profile)
    p1, T1, Sg1 = frozen_pvt_zone1(p_profile.p_wf, pbs, t_profile.T_0, dT_w, Sg_w)
    So1 = 1.0 - Sg1
    beta_o_sat_1 = fluid.beta_o_sat(p1, T1)

    def integrand(r):
        zeta = t_profile.zeta(r)
        return r * So1 * beta_o_sat_1 * t_profile.Psi(zeta)

    I, _ = quad(integrand, r_w, r_b)
    return -I
```

#### `gas_F2`:

$$\mathcal{F}_2 = -\frac{B_o}{\phi}\left(\frac{r_b\lambda_o(r_b)}{B_o(p_b,T_b)}p'_b - \frac{r_w\lambda_o(r_w)}{B_o(p_{wf},T_w)}p'_w\right) + I_{p_{wf}}^{(2)}\dot{p}_{wf}$$

Упрощая $B_o$:

$$\mathcal{F}_2 = -\frac{1}{\phi}\left(r_b\,\lambda_o(r_b)\,p'_b - r_w\,\lambda_o(r_w)\,p'_w\right) + I_{p_{wf}}^{(2)}\dot{p}_{wf}$$

> Заметим: $B_o/\phi \cdot \lambda_o/B_o = \lambda_o/\phi$, но из `\eqref{eq:Sg_flux}` множитель $B_o/\phi$ стоит перед всей скобкой, а скобка содержит $r\lambda_o/B_o \cdot dp/dr$. Итого: $(B_o/\phi)(r\lambda_o/B_o \cdot dp/dr) = r\lambda_o/\phi \cdot dp/dr$. Но это не совсем так — $B_o$ в множителе и $B_o$ в знаменателе потока — **разные** (замороженный vs точечный). Правильно: множитель $B_o/\phi$ — **замороженный** $\bar{B}_o^{(1)}$, поток $\lambda_o/B_o$ — **точечный**.

Пересмотр: из `\eqref{eq:Sg_eq2}` — `\eqref{eq:Sg_moment0}`:

$$-\frac{B_o}{\phi}\left[\frac{r\lambda_o}{B_o}\frac{\partial p}{\partial r}\right]_{r_w}^{r_b}$$

$B_o/\phi$ — это множитель из уравнения, но он зависит от положения. При замораживании: $\bar{B}_o^{(1)}/\phi$. Нет — в формуле `\eqref{eq:Sg_eq2}` $B_o/\phi$ стоит **перед** дивергенцией, т.е. это **один** множитель, не зависящий от $r$ при замораживании. При точном вычислении граничных потоков этот множитель нужно брать замороженным.

Но проще и корректнее: из `\eqref{eq:Sg_moment0}` видно, что интегрирование уже проведено, и результат — разность граничных потоков с множителем $B_o/\phi$.

Реализация:

```python
def gas_F2(fluid, rock, p_profile, t_profile, s_profile, state):
    """Правая часть F₂ уравнения массы газа. Ур. (eq:F2) moments_method.tex."""
    r_b = state.r_b
    dT_w = state.dT_w
    Sg_w = state.Sg_w
    r_w = p_profile.r_w
    phi = rock["phi"]
    cr = rock["c_r"]
    k = rock["k"]

    pbs = p_profile.pb_star(r_b, dT_w, fluid, t_profile)
    gam = p_profile.gamma(r_b, pbs)

    # Граничные потоки [r·λo/Bo·dp/dr]
    T_b = t_profile(r_b, dT_w)
    mob_o_Bo_b = fluid.mobility_o_over_Bo(pbs, T_b, 0.0, k)
    dp_dr_b = p_profile.dp_dr(r_b, r_b, pbs, gam)
    flux_rb = r_b * mob_o_Bo_b * dp_dr_b

    T_w = t_profile(r_w, dT_w)
    mob_o_Bo_w = fluid.mobility_o_over_Bo(p_profile.p_wf, T_w, Sg_w, k)
    if gam >= 1.0:
        dp_dr_w = p_profile.dp_dr(r_w, r_b, pbs, gam)
        flux_rw = r_w * mob_o_Bo_w * dp_dr_w
    else:
        eps_r = r_w * 1e-3
        dp_dr_w = p_profile.dp_dr(r_w + eps_r, r_b, pbs, gam)
        flux_rw = (r_w + eps_r) * mob_o_Bo_w * dp_dr_w

    p1, T1, Sg1 = frozen_pvt_zone1(p_profile.p_wf, pbs, t_profile.T_0, dT_w, Sg_w)
    Bo_frozen = fluid.Bo(p1, T1)

    boundary = -(Bo_frozen / phi) * (flux_rb - flux_rw)

    # I_pwf^(2): член с dp_wf/dt
    I_pwf = 0.0
    if state.dp_wf_dt != 0.0:
        So1 = 1.0 - Sg1
        co_sat_1 = fluid.co_sat(p1, T1)

        def integrand_pwf(r):
            dp = dp_dpwf_numerical(p_profile, r, r_b, fluid, t_profile, dT_w)
            return r * So1 * (cr + co_sat_1) * dp

        i, _ = quad(integrand_pwf, r_w, r_b)
        I_pwf = i * state.dp_wf_dt

    return boundary + I_pwf
```

**Проверка после шага:**
- Регрессия: `.venv/Scripts/python -m pytest tests/ -v`

**Зависимости:** Требует: шаги 1, 2. Блокирует: шаг 4.
**Оценка:** ~60 строк, ~30 минут.

---

### Шаг 4: Тесты

**Цель:** покрыть все коэффициенты второй строки тестами.

**Файлы:** `method_of_moments/tests/test_coefficients.py`

**Что сделать:**

Добавить в существующий файл тестов (после класса `TestF1`) новые классы.

#### Обновить импорт:

```python
from src.coefficients import (
    frozen_pvt_zone1, frozen_pvt_zone2,
    dp_drb_numerical, dp_dpwf_numerical,
    oil_A11, oil_A13, oil_F1,
    gas_A21, gas_A22, gas_A23, gas_F2,
    OdeState,
)
```

#### Расширить `_make_state`:

Текущий helper не принимает `dp_wf_dt`, а `test_F2_nonstationary_pwf` требует `dp_wf_dt=1e5`:

```python
def _make_state(r_b=5.0, Sg_w=0.1, dT_w=2.0, p_wf=P_WF, dp_wf_dt=0.0):
    return OdeState(r_b=r_b, Sg_w=Sg_w, dT_w=dT_w, p_wf=p_wf, dp_wf_dt=dp_wf_dt)
```

#### Тесты:

| Тест | Класс | Сценарий | Ожидание | Формула |
|---|---|---|---|---|
| `test_A22_positive` | `TestA22` | baseline: r_b=5, β=2 | $\mathcal{A}_{22} > 0$: подынтегральная $r(1-\eta^\beta) \geq 0$ | `\eqref{eq:A22}` |
| `test_A22_grows_with_rb` | `TestA22` | r_b=5 vs r_b=10 | $\mathcal{A}_{22}(r_b=10) > \mathcal{A}_{22}(r_b=5)$: больше домен | `\eqref{eq:A22}` |
| `test_A22_zero_at_rw` | `TestA22` | r_b = r_w·1.0001 | $\mathcal{A}_{22} \to 0$ при вырожденном домене | `\eqref{eq:A22}` |
| `test_A21_finite` | `TestA21` | baseline | $\mathcal{A}_{21}$ конечен и не NaN | `\eqref{eq:A21}` |
| `test_A21_single_phase` | `TestA21` | r_b=r_w·1.01, Sg_w=0 | $\mathcal{A}_{21}$ конечен (домен вырождается) | `\eqref{eq:A21}` |
| `test_A23_sign_consistent` | `TestA23` | baseline | $\operatorname{sign}(\mathcal{A}_{23}) = -\operatorname{sign}(\beta_o^{\text{sat}})$: при baseline $\beta_o^{\text{sat}} < 0$ (проверено численно) → $\mathcal{A}_{23} > 0$ | `\eqref{eq:A23}` |
| `test_A23_isothermal` | `TestA23` | dT_w=0 | $\mathcal{A}_{23}$ конечен (Ψ не зависит от ΔTw) | `\eqref{eq:A23}` |
| `test_F2_sign` | `TestF2` | baseline | $\mathcal{F}_2 > 0$: нефть притекает в зону разгазирования и дегазируется, Sg растёт | `\eqref{eq:F2}` |
| `test_F2_finite` | `TestF2` | baseline | $\mathcal{F}_2$ конечен и не NaN | `\eqref{eq:F2}` |
| `test_F2_single_phase` | `TestF2` | r_b=r_w·1.01, Sg_w=0 | $\mathcal{F}_2$ конечен | `\eqref{eq:F2}` |
| `test_F2_nonstationary_pwf` | `TestF2` | baseline, dp_wf_dt=1e5 | $\mathcal{F}_2$ конечен; отличается от значения при $\dot{p}_{wf}=0$ | `\eqref{eq:F2}` |
| `test_consistency_dot_rb_positive` | `TestConsistency` | baseline | $\dot{r}_b = F_1/A_{11} > 0$ (из первого уравнения при расщеплении) | `\eqref{eq:ode1}` |

**Структура теста (пример):**

```python
class TestA22:
    def test_A22_positive(self, s_profile):
        state = _make_state()
        val = gas_A22(s_profile, state)
        assert val > 0, f"A₂₂ должен быть > 0, получено {val:.6e}"

    def test_A22_grows_with_rb(self, s_profile):
        state1 = _make_state(r_b=5.0)
        state2 = _make_state(r_b=10.0)
        val1 = gas_A22(s_profile, state1)
        val2 = gas_A22(s_profile, state2)
        assert val2 > val1, f"A₂₂(rb=10) должен быть > A₂₂(rb=5)"

    def test_A22_zero_at_rw(self, s_profile):
        state = _make_state(r_b=R_W * 1.0001)
        val = gas_A22(s_profile, state)
        assert abs(val) < 1e-6, f"A₂₂ → 0 при rb→rw, получено {val:.6e}"
```

**Проверка после шага:**
- `.venv/Scripts/python -m pytest tests/test_coefficients.py -v`
- Полная регрессия: `.venv/Scripts/python -m pytest tests/ -v`

**Зависимости:** Требует: шаги 1–3. Блокирует: ничего.
**Оценка:** ~120 строк тестов, ~40 минут.

---

### Шаг 5: Секция §5.2 в `moments_method.tex`

**Цель:** зафиксировать вывод в документе.

**Файлы:** `method_of_moments/moments_method.tex`

**Что сделать:**

После строки 1067 (конец §5.1) и перед строкой 1069 (`%====` перед §6) вставить:

```latex
\subsubsection{Коэффициенты второго уравнения (масса газа)}
\label{sssec:gas_mass_coefficients}

Подставляя~\eqref{eq:dp_dt}--\eqref{eq:dT_dt}
в~\eqref{eq:Sg_moment0} и раскрывая $d\mathcal{S}_0/dt$
по правилу Лейбница (член с $\dot{r}_b$ обнуляется,
т.\,к.\ $S_g(r_b) = 0$), собираем коэффициенты.

\paragraph{Элемент $\mathcal{A}_{21}$.}
...
\paragraph{Элемент $\mathcal{A}_{22}$.}
...
\paragraph{Элемент $\mathcal{A}_{23}$.}
...
\paragraph{Правая часть $\mathcal{F}_2$.}
...
```

Формулы — из секции «Вывод явных формул» этого плана.

**Зависимости:** независим от шагов 1–4. Можно делать параллельно.
**Оценка:** ~80 строк LaTeX, ~30 минут.

---

## Критерии завершения

- [ ] `gas_A21`, `gas_A22`, `gas_A23`, `gas_F2` в `coefficients.py`
- [ ] Каждая функция имеет docstring с `\eqref{}`
- [ ] Unit-тесты: A₂₁, A₂₂, A₂₃, F₂ (знак, предельные случаи, конечность)
- [ ] Предельные тесты: rb→rw, Sg_w=0, ΔTw=0
- [ ] Все существующие тесты (FEAT-005a) зелёные
- [ ] §5.2 в `moments_method.tex` с явными формулами
- [ ] GitHub issue #6 прокомментирован
- [ ] Vault обновлён

## Обнаруженные проблемы

1. **Множитель $B_o/\phi$ в граничных потоках** — в `\eqref{eq:Sg_moment0}` $B_o/\phi$ стоит перед дивергентной скобкой. При замороженных PVT это $\bar{B}_o^{(1)}/\phi$. Но $\lambda_o/B_o$ в потоке берётся **точечно** на границе (не замороженно). Нужно аккуратно: $B_o^{\text{frozen}}/\phi \cdot [r \cdot \lambda_o^{\text{exact}}/B_o^{\text{exact}} \cdot dp/dr]$. Реализация учитывает это: `Bo_frozen` из `frozen_pvt_zone1`, а `mobility_o_over_Bo` — точечный.

2. **`SaturationProfile.eta` использует `math.log`** — для скалярного `quad` это нормально, но при будущей векторизации потребуется `np.log`. Не блокирует FEAT-005b. → DEBT-кандидат (аналогично `PressureProfile`).
