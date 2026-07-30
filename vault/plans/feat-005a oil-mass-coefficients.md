---
tags:
  - план
  - физика
date: 2026-07-30
issue: FEAT-005a
github: 5
branch: feat/feat-005a/oil-mass-coefficients
model_level: М.6
status: в процессе
audit:
  date: 2026-07-30
  found: 0
  auto-fixed: 0
  manual-required: 0
  rounds: 7
---

# FEAT-005a: Уравнение массы нефти — коэффициенты A₁₁, A₁₃, F₁

## Как начать работу по этому плану

1. Прочитай этот файл целиком
2. Прочитай `moments_method.tex` §2.1 (eq:p_eq — eq:D_operator), §4.1 (eq:moment0), §5 (eq:ode1 — eq:matrix_structure)
3. Создай ветку: `git checkout -b feat/feat-005a/oil-mass-coefficients`
4. Прогони тесты (baseline): `cd method_of_moments && .venv/Scripts/python -m pytest tests/ -v`
5. Начни с шага 1. После каждого шага: pytest

---

## Связь формула → код

| Формула | Уравнение в tex | Python-функция | Модуль | Тест |
|---|---|---|---|---|
| $C_p$ | `\eqref{eq:Cp}` | `Cp()` | `src/coefficients.py` | `test_Cp_*` |
| $C_T$ | `\eqref{eq:CT}` | `CT()` | `src/coefficients.py` | `test_CT_*` |
| Замораживание PVT | §5.4 | `frozen_pvt()` | `src/coefficients.py` | `test_frozen_pvt_*` |
| $\mathcal{A}_{11}$ | `\eqref{eq:ode1}` via `\eqref{eq:moment0}` + `\eqref{eq:dp_dt}` | `oil_A11()` | `src/coefficients.py` | `test_oil_A11_*` |
| $\mathcal{A}_{12}=0$ | `\eqref{eq:matrix_structure}` | (нет — проверяется в тесте) | — | `test_A12_zero` |
| $\mathcal{A}_{13}$ | `\eqref{eq:ode1}` via `\eqref{eq:moment0}` + `\eqref{eq:dT_dt}` | `oil_A13()` | `src/coefficients.py` | `test_oil_A13_*` |
| $\mathcal{F}_1$ | `\eqref{eq:ode1}` via `\eqref{eq:moment0}` | `oil_F1()` | `src/coefficients.py` | `test_oil_F1_*` |

---

## Вывод явных формул

### Исходное уравнение

Нулевой момент давления `\eqref{eq:moment0}`:

$$\int_{r_w}^{R_\text{ext}} r\,C_p\,\frac{\partial p}{\partial t}\,dr + \int_{r_w}^{R_\text{ext}} r\,C_T\,\frac{\partial T}{\partial t}\,dr = \left[r\,\Lambda\,\frac{\partial p}{\partial r}\right]_{r_w}^{R_\text{ext}} + Q_\text{quad}$$

где квадратичный интеграл:

$$Q_\text{quad} = \int_{r_w}^{r_b} r\,\frac{\lambda_o}{B_o}\left(\frac{\partial R_s}{\partial p}\frac{\partial p}{\partial r} + \frac{\partial R_s}{\partial T}\frac{\partial T}{\partial r}\right)\frac{\partial p}{\partial r}\,dr$$

> Пределы $[r_w, r_b]$, а не $[r_w, R_\text{ext}]$: в однофазной зоне $\partial R_s/\partial p = 0$ и $\partial R_s/\partial T = 0$, подынтегральная обнуляется.

### Подстановка производных по времени

Из `\eqref{eq:dp_dt}`:
$$\frac{\partial p}{\partial t} = \frac{\partial p}{\partial r_b}\dot{r}_b + \frac{\partial p}{\partial p_{wf}}\dot{p}_{wf}$$

Из `\eqref{eq:dT_dt}`:
$$\frac{\partial T}{\partial t} = \frac{\partial T}{\partial r_b}\dot{r}_b + \frac{\partial T}{\partial \Delta T_w}\dot{\Delta T}_w$$

Давление не зависит от $S_{g,w}$ ⟹ $\mathcal{A}_{12} = 0$ `\eqref{eq:matrix_structure}`.

### Сбор по производным

Коэффициент при $\dot{r}_b$ (элемент $\mathcal{A}_{11}$):

$$\mathcal{A}_{11} = \int_{r_w}^{R_\text{ext}} r\,C_p\,\frac{\partial p}{\partial r_b}\,dr + \int_{r_w}^{R_\text{ext}} r\,C_T\,\frac{\partial T}{\partial r_b}\,dr$$

Коэффициент при $\dot{\Delta T}_w$ (элемент $\mathcal{A}_{13}$):

$$\mathcal{A}_{13} = \int_{r_w}^{R_\text{ext}} r\,C_T\,\frac{\partial T}{\partial \Delta T_w}\,dr$$

Правая часть $\mathcal{F}_1$ (всё, что не содержит $\dot{r}_b$, $\dot{S}_{g,w}$, $\dot{\Delta T}_w$):

$$\mathcal{F}_1 = \left[r\,\Lambda\,\frac{\partial p}{\partial r}\right]_{r_w}^{R_\text{ext}} + Q_\text{quad} - \int_{r_w}^{R_\text{ext}} r\,C_p\,\frac{\partial p}{\partial p_{wf}}\,dr \cdot \dot{p}_{wf}$$

> **Замечание:** член с $\dot{p}_{wf}$ переносится в правую часть, т.к. $p_{wf}(t)$ — заданная функция.

### Двухзонное вычисление интегралов

Область разбивается на зону разгазирования $[r_w, r_b]$ и однофазную зону $[r_b, R_\text{ext}]$.

**Замена переменных:**
- Зона 1 ($r \in [r_w, r_b]$): $\eta = \ln(r/r_w)/L_b$, $dr = r\,L_b\,d\eta$, $r\,dr = r^2 L_b\,d\eta$.
  Но $r^2$ не выражается через $\eta$ замкнуто. Однако при замороженных PVT подынтегральные выражения зависят только от $\eta$ (через степенные функции $\Phi(\eta) = \eta^\gamma$, $S_g(\eta) = S_{g,w}(1-\eta^\beta)$), а множитель $r\,dr = r_w^2 e^{2\eta L_b} L_b\,d\eta$.

Ключевое упрощение: в замороженном приближении PVT-свойства выносятся из-под интеграла. Однако множитель $r\,dr$ вносит экспоненту: в зоне 1 $r\,dr = r_w^2 L_b e^{2\eta L_b}\,d\eta$, в полной области $r\,dr = R_\text{ext}^2 L_0 e^{-2\zeta L_0}\,d\zeta$. Эти экспоненциальные весовые функции **не сводятся** к степенным интегралам $I_\Phi^{(n)}$, $I_S^{(n)}$, $J^{(m)}$ без дополнительных приближений.

**Стратегия:** на первом проходе — `scipy.integrate.quad` (точно). Аналитическая оптимизация возможна только через аппроксимацию экспоненты рядом Тейлора ($e^{2\eta L_b} \approx 1 + 2\eta L_b + \ldots$) или иное приближение (см. заметку [[интегральная нормировка нелинейных коэффициентов]]).

### Производные профилей по параметрам

**Давление в зоне разгазирования** (`\eqref{eq:p_inner}`):
$$p = p_{wf} + \Delta p_1 \cdot \eta^\gamma$$

Частные производные:
- $\partial p/\partial r_b$: через зависимость $\eta(r, r_b)$ и $\Delta p_1(r_b)$, $\gamma(r_b)$
- $\partial p/\partial p_{wf}$: в зоне 1 НЕ просто $1 - \eta^\gamma$ — нужно учесть зависимость $\gamma(p_{wf})$ через $\Delta p_1 = p_b^* - p_{wf}$. Полная формула: $\partial p/\partial p_{wf} = (1 - \eta^\gamma) + \Delta p_1 \eta^\gamma \ln\eta \cdot \partial\gamma/\partial p_{wf}$, где $\partial\gamma/\partial p_{wf} = \gamma/\Delta p_1$ (из $\gamma = \Delta p_2 L_b/(\Delta p_1 L_e)$). В зоне 2: $= 0$

**Давление в однофазной зоне** (`\eqref{eq:p_outer}`):
$$p = p_b^* + \Delta p_2 \cdot \frac{\ln(r/r_b)}{L_e}$$

**Температура** (`\eqref{eq:T_profile}`):
$$T = T_0 - \Delta T_w \cdot \Psi(\zeta)$$

- $\partial T/\partial \Delta T_w = -\Psi(\zeta)$
- $\partial T/\partial r_b$: через $\zeta(r, R_\text{ext})$ — $\zeta$ **не зависит от $r_b$** (т.к. $\zeta = \ln(R_\text{ext}/r)/L_0$). Но $p_b^*$ зависит от $r_b$ через $T(r_b)$, что влияет на давление, а не на температуру напрямую. Поэтому **$\partial T/\partial r_b = 0$**.

> Это важно: температурный профиль параметризован через $\Delta T_w$ и $\zeta$, которая привязана к $R_\text{ext}$, а не к $r_b$. Влияние $r_b$ на температуру идёт только через $p_b^*$.

### Итоговые формулы (при замороженных PVT)

Обозначения:
- Зона 1: $\bar{C}_p^{(1)} = C_p(\bar{p}_1, \bar{T}_1, \bar{S}_{g,1})$, $\bar{C}_T^{(1)} = C_T(\bar{p}_1, \bar{T}_1, \bar{S}_{g,1})$
- Зона 2: $\bar{C}_p^{(2)} = C_p(\bar{p}_2, \bar{T}_2, 0)$, $\bar{C}_T^{(2)} = C_T(\bar{p}_2, \bar{T}_2, 0)$
- $\bar{\Lambda}_1 = \Lambda(\bar{p}_1, \bar{T}_1, \bar{S}_{g,1}, k)$, $\bar{\Lambda}_2 = \Lambda(\bar{p}_2, \bar{T}_2, 0, k)$

Средние значения (§5.4):
- $\bar{p}_1 = (p_{wf} + p_b^*)/2$, $\bar{T}_1 = T_0 - \Delta T_w \cdot \bar{\Psi}_1$, $\bar{S}_{g,1} = S_{g,w}/2$
- $\bar{p}_2 = (p_b^* + p_0)/2$, $\bar{T}_2 \approx T_0$, $S_g = 0$

#### $\mathcal{A}_{11}$

Компонента от $C_p \cdot \partial p/\partial r_b$ в обеих зонах. Требуется вычислить $\partial p/\partial r_b$ — нетривиальная производная, т.к. $\eta$, $\gamma$, $\Delta p_1$, $L_b$, $L_e$ все зависят от $r_b$.

> Конкретная формула будет выведена при реализации (шаг 3). Здесь фиксируем структуру: $\mathcal{A}_{11}$ — интеграл замороженных PVT-коэффициентов, умноженных на $\partial p/\partial r_b$, по обеим зонам. Плюс $C_T \cdot \partial T/\partial r_b = 0$.

#### $\mathcal{A}_{13}$

$$\mathcal{A}_{13} = -\int_{r_w}^{R_\text{ext}} r\,\bar{C}_T\,\Psi(\zeta)\,dr$$

Зона 1 (замороженный $\bar{C}_T^{(1)}$):
$$\mathcal{A}_{13}^{(1)} = -\bar{C}_T^{(1)} \int_{r_w}^{r_b} r\,\Psi(\zeta)\,dr$$

Зона 2 (замороженный $\bar{C}_T^{(2)}$):
$$\mathcal{A}_{13}^{(2)} = -\bar{C}_T^{(2)} \int_{r_b}^{R_\text{ext}} r\,\Psi(\zeta)\,dr$$

Интегралы $\int r\,\Psi(\zeta)\,dr$ содержат экспоненту $r^2 = R_\text{ext}^2 e^{-2\zeta L_0}$ и **не сводятся** к $J^{(m)}$ напрямую. Вычислять через `scipy.integrate.quad`.

#### $\mathcal{F}_1$

$$\mathcal{F}_1 = \underbrace{\Lambda_\text{ext}\,\frac{\Delta p_2}{L_e}}_{\text{на контуре}} - \underbrace{\Lambda_w\,\frac{\Delta p_1\,\gamma}{L_b}\cdot \lim_{\eta\to 0}\eta^{\gamma-1}}_{\to 0 \text{ при } \gamma>1;\;+\infty\text{ при }\gamma<1} + Q_\text{quad} - I_{p_{wf}}$$

где $\Lambda_\text{ext} = \Lambda(p_0, T_0, 0, k)$ и $\Lambda_w = \Lambda(p_{wf}, T_w, S_{g,w}, k)$ — **точечные** (не замороженные) значения на границах.

Граничный поток на контуре: $\Lambda_\text{ext} \cdot \Delta p_2 / L_e$.
Граничный поток на забое: при $\gamma > 1$ → 0; при $\gamma = 1$ → конечен; при $\gamma < 1$ → $+\infty$ (сингулярность, см. подводные камни).

---

## Обратная совместимость

- ✅ Новый модуль `coefficients.py` — не затрагивает существующий код
- ✅ Существующие тесты не меняются
- ✅ `BlackOilFluid` расширяется совместимо (добавление методов `Cp`, `CT`)
- ✅ Конфиг `baseline.json` не требует изменений

## Подводные камни

- ✅ **Размерности:** $C_p$ [1/Па], $C_T$ [1/К], $\Lambda$ [м²/(Па·с)], $\mathcal{A}_{11}$ [м], $\mathcal{A}_{13}$ [м²/К], $\mathcal{F}_1$ [м²/с]. Проверка: $\mathcal{A}_{11}\dot{r}_b$ [м·м/с] = [м²/с] = $[\mathcal{F}_1]$ ✓; $\mathcal{A}_{13}\dot{\Delta T}_w$ [м²/К·К/с] = [м²/с] = $[\mathcal{F}_1]$ ✓
- ⚠️ **$\gamma < 1$:** давление имеет бесконечную производную на забое; граничный поток на $r_w$ расходится. **При baseline $\gamma < 1$ всегда** ($\Delta p_2/\Delta p_1 = 2/3$, $L_b/L_e < 1$ для реалистичных $r_b$). Это ограничение модели параметризации: при $\gamma < 1$ граничный член $[r\Lambda dp/dr]_{r_w}$ расходится. Решение для $\mathcal{F}_1$: при $\gamma < 1$ поток на забое вычисляется как $\lim_{\eta\to 0} r_w \Lambda_1 \Delta p_1 \gamma \eta^{\gamma-1}/(r_w L_b) = +\infty$. Пока: **отсечка** — при $\gamma < 1$ вычислять поток на забое через `PressureProfile.dp_dr(r_w + eps, ...)` с малым `eps`, или пропускать (если $Q_\text{quad}$ доминирует). Фундаментальное решение — за рамками FEAT-005a
- ⚠️ **$S_g = 0$ (однофазный случай):** зона разгазирования отсутствует, интегралы по зоне 1 обнуляются. Адресовано: предельный тест
- ⚠️ **$\Delta T_w = 0$ (изотермический случай):** $\mathcal{A}_{13} \neq 0$ (функция формы $\Psi(\zeta)$ не зависит от $\Delta T_w$). При $\Delta T_w = 0$: $\partial T/\partial r = 0$, поэтому температурные члены в $Q_\text{quad}$ и граничных потоках обнуляются, но $\mathcal{A}_{13}$ остаётся конечным. Адресовано: предельный тест
- ✅ **Import-цепочки:** `coefficients.py` импортирует `integrals`, `profiles/*`, `pvt/black_oil` — без циклов
- ⚠️ **$\partial p/\partial r_b$:** нетривиальная производная, требует аккуратного вывода. Адресовано: шаг 3 + верификация конечными разностями
- ⚠️ **$\partial p/\partial p_{wf}$:** зависимость $\gamma$ от $p_{wf}$ через $\Delta p_1$. Полная производная содержит дополнительный член $\Delta p_1 \eta^\gamma \ln\eta \cdot \partial\gamma/\partial p_{wf}$, где $\partial\gamma/\partial p_{wf} = \gamma/\Delta p_1$. Адресовано: исправлено в секции «Производные профилей»
- ⚠️ **Экспоненциальные весовые функции:** интегралы $\int r\,f(\eta)\,dr$ содержат $e^{2\eta L_b}$, не сводятся к $I_\Phi^{(n)}$. Адресовано: `scipy.integrate.quad` как основной путь
- ⚠️ **Интегрируемая сингулярность $Q_\text{quad}$ при $\gamma < 1/2$:** подынтегральная $(dp/dr)^2$ содержит $\eta^{2(\gamma-1)}$, расходящуюся при $\eta \to 0$. При $\gamma > 1/2$ — сходится; при $\gamma \leq 1/2$ — расходится. При baseline начальном $r_b$: $\gamma \ll 1$. Но зона 1 вырождается ($L_b \to 0$), и интеграл $Q_\text{quad}^{(1)} \propto L_b \to 0$. При конечном $r_b$ с $\gamma \in (0, 1/2)$: `scipy.integrate.quad` может столкнуться с плохой сходимостью. Решение: при $\gamma < 1/2$ передавать `quad(..., points=[r_w])` или использовать замену переменных, устраняющую сингулярность
- ⚠️ **$\partial p/\partial \Delta T_w \neq 0$:** давление зависит от $\Delta T_w$ через $p_b^*(T(r_b))$, поэтому $\partial p/\partial t$ формально содержит $(\partial p/\partial \Delta T_w)\dot{\Delta T}_w$. Этот вклад в $\mathcal{A}_{13}$ (т.е. $\int r C_p \partial p/\partial \Delta T_w\,dr$) пренебрежимо мал. Оценка в однофазной зоне: $C_p \approx \phi\,(c_r + c_o)/B_g \sim 10^{-8}$ [1/Па] (при $c_o = 0$ по Стендингу), $\partial p/\partial \Delta T_w \sim dp_b/dT \cdot \Psi(\zeta_b) \sim 5\times10^4$ [Па/К], $C_T \approx -\phi\beta_o/B_g \sim 2\times10^{-2}$ [1/К]. Отношение $C_p \cdot |\partial p/\partial \Delta T_w| / |C_T| \sim 2.5\%$. Пренебрежение обосновано. Совпадает с tex (eq:dp_dt опускает $\dot{\Delta T}_w$)

---

## Шаги реализации

### Шаг 1: Методы Cp и CT в BlackOilFluid

**Цель:** реализовать PVT-коэффициенты ёмкости $C_p$ и $C_T$.

**Файлы:** `method_of_moments/src/pvt/black_oil.py`

**Формулы:**

$C_p$ `\eqref{eq:Cp}`:
$$C_p = \phi\left[S_o(c_r + c_o^{\text{sat}})\left(\frac{1}{B_g} - \frac{R_s}{B_o}\right) + \xi_o\left(\frac{\partial R_s}{\partial p} + R_s(c_r + c_o^{\text{sat}})\right) + \frac{S_g}{B_g}(c_g + c_r)\right]$$

$C_T$ `\eqref{eq:CT}`:
$$C_T = \phi\left[-S_o\,\beta_o^{\text{sat}}\left(\frac{1}{B_g} - \frac{R_s}{B_o}\right) + \xi_o\left(\frac{\partial R_s}{\partial T} - R_s\,\beta_o^{\text{sat}}\right) - \frac{S_g}{B_g}\beta_g\right]$$

где $S_o = 1 - S_g$, $\xi_o = S_o/B_o$.

**Что сделать:**

1. В `black_oil.py` добавить два метода:

```python
def Cp(self, p, T, Sg, phi, cr):
    """Коэффициент ёмкости C_p. Ур. (eq:Cp) moments_method.tex."""
    So = 1.0 - Sg
    Bo_val = self.Bo(p, T)
    Bg_val = self.Bg(p, T)
    Rs_val = self.Rs(p, T)
    co_sat_val = self.co_sat(p, T)
    cg_val = self.cg(p, T)
    dRs_dp_val = self.dRs_dp(p, T)
    xi_o_val = So / Bo_val
    inv_Bg_minus_Rs_over_Bo = 1.0 / Bg_val - Rs_val / Bo_val
    return phi * (
        So * (cr + co_sat_val) * inv_Bg_minus_Rs_over_Bo
        + xi_o_val * (dRs_dp_val + Rs_val * (cr + co_sat_val))
        + Sg / Bg_val * (cg_val + cr)
    )

def CT(self, p, T, Sg, phi):
    """Температурный коэффициент C_T. Ур. (eq:CT) moments_method.tex."""
    So = 1.0 - Sg
    Bo_val = self.Bo(p, T)
    Bg_val = self.Bg(p, T)
    Rs_val = self.Rs(p, T)
    beta_o_sat_val = self.beta_o_sat(p, T)
    beta_g_val = self.beta_g(p, T)
    dRs_dT_val = self.dRs_dT(p, T)
    xi_o_val = So / Bo_val
    inv_Bg_minus_Rs_over_Bo = 1.0 / Bg_val - Rs_val / Bo_val
    return phi * (
        -So * beta_o_sat_val * inv_Bg_minus_Rs_over_Bo
        + xi_o_val * (dRs_dT_val - Rs_val * beta_o_sat_val)
        - Sg / Bg_val * beta_g_val
    )
```

**Проверка после шага:**
- Регрессия: `cd method_of_moments && .venv/Scripts/python -m pytest tests/ -v` (тесты Cp/CT создаются в шаге 2; на этом шаге — только проверка, что существующие тесты не сломались)

**Зависимости:** нет. Блокирует: шаги 2, 3, 4.
**Оценка:** ~30 строк, ~15 минут.

---

### Шаг 2: Функция замороженных PVT + тесты Cp/CT

**Цель:** реализовать двухзонное замораживание PVT (§5.4) и тесты для Cp, CT.

**Файлы:** `method_of_moments/src/coefficients.py` (создать), `method_of_moments/tests/test_coefficients.py` (создать)

**Формулы замораживания** (§5.4):

Зона 1 (разгазирование):
- $\bar{p}_1 = (p_{wf} + p_b^*)/2$
- $\bar{T}_1 = T_0 - \Delta T_w \cdot \bar{\Psi}_1$ (при $L_b \ll L_0$: $\bar{T}_1 \approx T_0 - \Delta T_w$)
- $\bar{S}_{g,1} = S_{g,w}/2$

Зона 2 (однофазная):
- $\bar{p}_2 = (p_b^* + p_0)/2$
- $\bar{T}_2 \approx T_0$
- $S_g = 0$

**Что сделать:**

1. Создать `method_of_moments/src/coefficients.py`:

```python
"""Коэффициенты ODE метода моментов — §5 moments_method.tex."""

import numpy as np


def frozen_pvt_zone1(p_wf, pb_star, T_0, dT_w, Sg_w):
    """Средние PVT-параметры зоны разгазирования. §5.4 moments_method.tex."""
    p_bar = 0.5 * (p_wf + pb_star)
    T_bar = T_0 - dT_w  # приближение bar{Psi}_1 ≈ 1 при L_b << L_0
    Sg_bar = 0.5 * Sg_w
    return p_bar, T_bar, Sg_bar


def frozen_pvt_zone2(pb_star, p_0, T_0):
    """Средние PVT-параметры однофазной зоны. §5.4 moments_method.tex."""
    p_bar = 0.5 * (pb_star + p_0)
    T_bar = T_0
    Sg_bar = 0.0
    return p_bar, T_bar, Sg_bar
```

2. Создать `method_of_moments/tests/test_coefficients.py` с тестами:

**Тесты Cp:**

| Тест | Сценарий | Ожидание |
|---|---|---|
| `test_Cp_positive` | baseline: p=15 МПа, T=350 К, Sg=0.1 | $C_p > 0$ (ёмкость положительна) |
| `test_Cp_single_phase` | Sg=0, p > pb | $C_p > 0$, нет газовых членов |
| `test_Cp_dimension` | baseline | $C_p$ ~ $10^{-10}$ — $10^{-8}$ [1/Па] (порядок пористого объёма × сжимаемости) |

**Тесты CT:**

| Тест | Сценарий | Ожидание |
|---|---|---|
| `test_CT_negative` | baseline: p < pb, Sg > 0 | $C_T < 0$ (нагрев снижает газонасыщение, увеличивает давление) |
| `test_CT_single_phase` | Sg=0, p > pb | $C_T = -\phi\beta_o/B_g \neq 0$ (остаётся температурное расширение нефти; при $p>p_b$: $\partial R_s/\partial T = 0$, $\beta_o^{\text{sat}} = \beta_o$, и $C_T = \phi[-\beta_o(1/B_g - R_s/B_o) - R_s\beta_o/B_o] = -\phi\beta_o/B_g$) |

**Тесты замораживания:**

| Тест | Сценарий | Ожидание |
|---|---|---|
| `test_frozen_zone1_averages` | baseline | $\bar{p}_1 = (15+18)/2 = 16.5$ МПа |
| `test_frozen_zone2_Sg_zero` | baseline | $\bar{S}_{g,2} = 0$ |

**Проверка после шага:**
- `.venv/Scripts/python -m pytest tests/test_coefficients.py -v`
- Регрессия: `.venv/Scripts/python -m pytest tests/ -v`

**Зависимости:** Требует: шаг 1 (Cp, CT в BlackOilFluid). Блокирует: шаги 3, 4.
**Оценка:** ~80 строк код + ~100 строк тесты, ~30 минут.

---

### Шаг 3: Производные профиля давления по $r_b$

**Цель:** вычислить $\partial p/\partial r_b$ для обеих зон — нужно для $\mathcal{A}_{11}$.

**Файлы:** `method_of_moments/src/coefficients.py`

**Формулы:**

Зона 1 (`\eqref{eq:p_inner}`): $p = p_{wf} + \Delta p_1 \cdot \eta^\gamma$

$\eta = \ln(r/r_w)/L_b$, $L_b = \ln(r_b/r_w)$, $\gamma = \Delta p_2 \cdot L_b / (\Delta p_1 \cdot L_e)$.

При фиксированном $r$ и изменении $r_b$:
- $\partial \eta / \partial r_b = -\eta / (r_b \cdot L_b)$ (т.к. $\partial L_b / \partial r_b = 1/r_b$)
- $\partial \gamma / \partial r_b$ — через дифференцирование `\eqref{eq:gamma_constraint}`
- $\partial \Delta p_1 / \partial r_b = \partial p_b^* / \partial r_b$ (при постоянном $p_{wf}$)
- $\partial p_b^* / \partial r_b$ — через зависимость $p_b^*(T(r_b)) = p_b(T_0 - \Delta T_w \Psi(\zeta_b))$, где $\zeta_b = L_e/L_0$:
  $$\frac{\partial p_b^*}{\partial r_b} = \frac{dp_b}{dT}\bigg|_{T(r_b)} \cdot \frac{\Delta T_w \Psi'(\zeta_b)}{r_b L_0}$$
  (из $\partial\zeta_b/\partial r_b = -1/(r_b L_0)$ и $\partial T/\partial\zeta < 0$)

**Полная производная:**
$$\frac{\partial p}{\partial r_b}\bigg|_\text{inner} = \frac{\partial \Delta p_1}{\partial r_b}\eta^\gamma + \Delta p_1 \eta^\gamma \left(\ln\eta \cdot \frac{\partial \gamma}{\partial r_b} + \frac{\gamma}{\eta}\frac{\partial \eta}{\partial r_b}\right)$$

Зона 2 (`\eqref{eq:p_outer}`): $p = p_b^* + \Delta p_2 \cdot \ln(r/r_b)/L_e$

$$\frac{\partial p}{\partial r_b}\bigg|_\text{outer} = \frac{\partial p_b^*}{\partial r_b}\left(1 - \frac{\ln(r/r_b)}{L_e}\right) + \Delta p_2 \left(\frac{-1}{r_b L_e} + \frac{\ln(r/r_b)}{r_b L_e^2}\right)$$

> **Знак:** первый член в скобке отрицателен ($-1/(r_b L_e)$), т.к. увеличение $r_b$ при фиксированном $r > r_b$ уменьшает $\ln(r/r_b)$ и $L_e$.

> **Рекомендация:** эти производные сложны для аналитического вывода. Использовать **численное дифференцирование** (конечная разность по $r_b$) как основной путь, аналитику — для верификации в предельных случаях.

**Что сделать:**

1. В `coefficients.py` реализовать `dp_drb_numerical(p_profile, r, r_b, fluid, temp_profile, dT_w, dr_b_rel=1e-5)` — центральная конечная разность. **Важно:** `pb_star` и `gamma` НЕ передаются как аргументы — они пересчитываются внутри для каждого $r_b \pm dr_b$ (через `p_profile.pb_star(...)` и `p_profile.gamma(...)`), иначе производная учитывает только явную зависимость $\eta(r, r_b)$ и пропускает зависимость $p_b^*(r_b)$, $\gamma(r_b)$. Шаг `dr_b = r_b * dr_b_rel` — относительный, для корректной работы при разных масштабах $r_b$.

2. Альтернативно: реализовать аналитически, но верифицировать конечными разностями.

**Проверка:** тест `test_dp_drb_vs_finite_diff` — аналитика vs конечная разность, tolerance < 1e-4.

**Зависимости:** Требует: шаг 2. Блокирует: шаг 4.
**Оценка:** ~50 строк, ~30 минут.

---

### Шаг 4: Элементы A₁₁, A₁₃, F₁

**Цель:** реализовать основные функции `oil_A11`, `oil_A13`, `oil_F1`.

**Файлы:** `method_of_moments/src/coefficients.py`

**Что сделать:**

1. `oil_A13(fluid, rock, p_profile, t_profile, state)`:
   - Интеграл $-\int r\,C_T\,\Psi(\zeta)\,dr$ по обеим зонам
   - Замороженные $\bar{C}_T^{(1)}$, $\bar{C}_T^{(2)}$
   - Численное интегрирование (`scipy.integrate.quad`) по каждой зоне

2. `oil_A11(fluid, rock, p_profile, t_profile, state)`:
   - Интеграл $\int r\,C_p\,\partial p/\partial r_b\,dr$ по обеим зонам
   - Используем численный $\partial p/\partial r_b$ из шага 3
   - Численное интегрирование

3. `oil_F1(fluid, rock, p_profile, t_profile, s_profile, state)`:
   - Граничные потоки: $\Lambda \cdot \Delta p_2/L_e$ (контур) − поток на забое
   - Квадратичный интеграл $Q_\text{quad}$
   - Член с $\dot{p}_{wf}$ (если $p_{wf}$ нестационарно — пока $\dot{p}_{wf} = 0$)

**Импорты:** добавить `import dataclasses` и `from scipy.integrate import quad` в начало `coefficients.py` (рядом с `import numpy as np`).

**Сигнатура `state`:**
```python
@dataclasses.dataclass
class OdeState:
    r_b: float      # радиус зоны разгазирования [м]
    Sg_w: float     # газонасыщенность на забое
    dT_w: float     # отклонение температуры [К]
    p_wf: float     # забойное давление [Па]
    dp_wf_dt: float = 0.0  # скорость изменения забойного давления [Па/с]
```

**Стратегия интегрирования:**
- **Единственный путь на этом этапе:** `scipy.integrate.quad` для всех интегралов (экспоненциальные весовые функции $r^2$ не сводятся к $I_\Phi$, $I_S$, $J$)
- **Оптимизация (позже, не в FEAT-005a):** аппроксимация $e^{2\eta L_b}$ рядом Тейлора, см. [[интегральная нормировка нелинейных коэффициентов]]

**Проверка после шага:**
- Регрессия: `.venv/Scripts/python -m pytest tests/ -v` (тесты oil_A11/A13/F1 создаются в шаге 5; на этом шаге — только проверка, что модуль импортируется без ошибок и существующие тесты не сломались)

**Зависимости:** Требует: шаги 1–3. Блокирует: шаг 5.
**Оценка:** ~120 строк, ~60 минут.

---

### Шаг 5: Полные тесты и верификация

**Цель:** покрыть тестами все граничные случаи и проверить физическую корректность.

**Файлы:** `method_of_moments/tests/test_coefficients.py`

**Тесты:**

| Тест | Категория | Сценарий | Ожидание |
|---|---|---|---|
| `test_A12_zero` | Инвариант | Любое состояние | $\mathcal{A}_{12} = 0$ (нет функции, проверяем, что API не предоставляет A12; или вычисляем матрицу и проверяем элемент) |
| `test_A11_sign` | Знак | baseline | $\mathcal{A}_{11} < 0$: $C_p > 0$ и $\partial p/\partial r_b < 0$ (расширение зоны снижает давление при фиксированном $r$), поэтому $\int r\,C_p\,\partial p/\partial r_b\,dr < 0$. Физически: рост $r_b$ распределяет перепад давления на большую область → давление в каждой точке уменьшается |
| `test_A13_sign` | Знак | baseline, $C_T < 0$ | $\mathcal{A}_{13} > 0$ (т.к. $\mathcal{A}_{13} = -\int r C_T \Psi\,dr$, при $C_T < 0$ и $\Psi > 0$: $-C_T\Psi > 0$) |
| `test_F1_sign` | Знак | baseline, стационарный p_wf | $\mathcal{F}_1 < 0$ (отток на забое доминирует над притоком на контуре; при $\mathcal{A}_{11} < 0$: $\dot{r}_b > 0$) |
| `test_isothermal_limit` | Предельный | $\Delta T_w = 0$ | $\mathcal{A}_{13} > 0$ (функция формы $\Psi \neq 0$, $C_T < 0$); $Q_\text{quad}$ не содержит температурных членов ($\partial T/\partial r = 0$) |
| `test_single_phase_limit` | Предельный | $r_b \to r_w$, $S_g = 0$ | Зона 1 вырождается; интегралы по зоне 1 → 0 |
| `test_dimension_A11` | Размерность | baseline | $\mathcal{A}_{11}$ [м] — конечное **отрицательное** число (качественная оценка порядка; размерность следует из $\int r\,C_p\,\partial p/\partial r_b\,dr$: [м×1/Па×Па/м×м] = [м]; знак < 0 подтверждён в `test_A11_sign`) |
| `test_F1_vs_quad` | Верификация | baseline | $Q_\text{quad}$ с замороженными PVT vs $Q_\text{quad}$ с точечным вычислением PVT в каждой точке (1D `quad`, не `dblquad` — интеграл одномерный) |

**Проверка:**
- `.venv/Scripts/python -m pytest tests/test_coefficients.py -v`
- Полная регрессия: `.venv/Scripts/python -m pytest tests/ -v`

**Зависимости:** Требует: шаг 4. Блокирует: ничего (завершающий шаг).
**Оценка:** ~150 строк тестов, ~45 минут.

---

## Критерии завершения

- [ ] `Cp`, `CT` реализованы в `BlackOilFluid`
- [ ] `frozen_pvt_zone1`, `frozen_pvt_zone2` в `coefficients.py`
- [ ] `oil_A11`, `oil_A13`, `oil_F1` в `coefficients.py`
- [ ] `OdeState` dataclass определён
- [ ] Каждая функция имеет docstring с `\eqref{}`
- [ ] Unit-тесты: Cp, CT, frozen_pvt, A11, A13, F1
- [ ] Предельные тесты: Sg=0, ΔTw=0, rb→rw
- [ ] Тест: A12=0
- [ ] Все существующие тесты зелёные
- [ ] GitHub issue #5 прокомментирован
- [ ] Vault обновлён

## Обнаруженные проблемы

1. **`PressureProfile` использует `math` вместо `numpy`** — при будущем переходе на массивы потребуется рефакторинг. Не блокирует FEAT-005a (работаем со скалярами). → DEBT-кандидат.
2. **Производная $\partial p/\partial r_b$ аналитически сложна** — решение: численные конечные разности на первом проходе, аналитика как оптимизация позже.
3. **Приближение $\bar{\Psi}_1 \approx 1$** — валидно при $L_b \ll L_0$ (типично), но может дать ошибку на больших зонах разгазирования. → Мониторить при VAL-001. Замечание: формальное определение в tex ($\bar{\Psi}_1 = L_b^{-1}\int_{\zeta_b}^1 \Psi\,d\zeta$) даёт $\bar{\Psi}_1 \approx 1/L_0 \approx 0.12$ при малом $L_b$, а не $\approx 1$. По смыслу нужно среднее $\Psi$ по зоне 1 ($\frac{1}{1-\zeta_b}\int_{\zeta_b}^1 \Psi\,d\zeta \to 1$). Физика верна, в определении tex — возможная опечатка.
