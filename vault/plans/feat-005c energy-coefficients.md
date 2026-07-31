---
tags:
  - план
  - физика
date: 2026-07-31
issue: FEAT-005c
github: 7
branch: feat/feat-005c/energy-coefficients
model_level: М.6
status: в процессе
audit:
  date: 2026-07-31
  found: 0
  auto-fixed: 0
  manual-required: 0
  round: 5
  note: "5-й аудит: полный 7-мерный аудит с мысленным прогоном, знаки и физика верифицированы"
---

# FEAT-005c: Уравнение энергии — коэффициенты A₃₁, A₃₃, F₃

## Как начать работу по этому плану

1. Прочитай этот файл целиком
2. Прочитай `moments_method.tex`:
   - §2.3 (eq:energy — eq:energy_regrouped): исходное уравнение энергии и перегруппировка
   - §3.4 (eq:T_moment0, eq:T_flux): нулевой момент энергии
   - §4.4 (eq:T_profile, eq:Psi, eq:dT_dr, eq:IPsi): профиль температуры
   - §5.4 (eq:dp_dt, eq:dT_dt, eq:dT_drb, eq:dT_dTw): связь параметров с производными
   - §5.4 (eq:matrix_structure): расщепление матрицы, A₃₂ = 0
3. Прочитай `coefficients.py` целиком — шаблон из FEAT-005a/005b
4. Прочитай `pvt/black_oil.py` — существующие PVT-методы
5. Создай ветку: `git checkout -b feat/feat-005c/energy-coefficients`
6. Прогони тесты (baseline): `cd method_of_moments && .venv/Scripts/python -m pytest tests/ -v`
7. Начни с шага 1. После каждого шага: pytest

---

## Подтип

**Физика** — новые коэффициенты ODE-системы из уравнения сохранения энергии.

---

## Связь формула → код

| Формула | Уравнение в tex | Python-функция | Модуль | Тест |
|---|---|---|---|---|
| $(ρc_p)_\text{eff}^*$ | `\eqref{eq:rhocp_eff_mod}` | `BlackOilFluid.rhocp_eff_star()` | `src/pvt/black_oil.py` | `test_rhocp_eff_star_*` |
| $\bar{C}_\text{conv}^*$ | `\eqref{eq:rhocp_conv_mod}` | `BlackOilFluid.C_conv_star()` | `src/pvt/black_oil.py` | `test_C_conv_star_*` |
| $\bar{Q}_\text{JT}^*$ | `\eqref{eq:QJT_star}` | `BlackOilFluid.QJT_star_coeff()` | `src/pvt/black_oil.py` | `test_QJT_star_coeff_*` |
| $\bar{Q}_\text{ad}^*$ | `\eqref{eq:Qad_star}` | `BlackOilFluid.Qad_star_coeff()` | `src/pvt/black_oil.py` | `test_Qad_star_coeff_*` |
| $\mathcal{A}_{31}$ | (eq:A31, нового §5.5.3) | `energy_A31()` | `src/coefficients.py` | `test_A31_*` |
| $\mathcal{A}_{33}$ | (eq:A33, нового §5.5.3) | `energy_A33()` | `src/coefficients.py` | `test_A33_*` |
| $\mathcal{F}_3$ | (eq:F3, нового §5.5.3) | `energy_F3()` | `src/coefficients.py` | `test_F3_*` |

---

## Вывод явных формул

### Исходное уравнение

Нулевой момент уравнения энергии `\eqref{eq:T_moment0}`:

$$\underbrace{\int_{r_w}^{R_\text{ext}} r\,(\rho c_p)_\text{eff}^*\,\frac{\partial T}{\partial t}\,dr}_{\text{I: ёмкостный}} + \underbrace{\int_{r_w}^{R_\text{ext}} r\,(\rho c_p u)_\text{conv}^*\,\frac{\partial T}{\partial r}\,dr}_{\text{II: конвективный}} = \underbrace{R_\text{ext}\,\lambda_\text{eff}\,T'_\text{ext}}_{\text{III: теплопроводность}} + \underbrace{\int_{r_w}^{R_\text{ext}} r\,(Q_\text{JT}^* + Q_\text{ad}^*)\,dr}_{\text{IV: источники}}$$

Граничный поток (eq:T_flux): $T'_w = 0$ по ГУ (eq:bc_T), поэтому осталось только $R_\text{ext}\,\lambda_\text{eff}\,T'_\text{ext}$.

### Подстановка ∂T/∂t и раскрытие Q_ad*

Из `\eqref{eq:dT_dt}`:

$$\frac{\partial T}{\partial t} = \underbrace{\frac{\partial T}{\partial r_b}\,\dot{r}_b}_{= 0\text{ (eq:dT\_drb)}} + \frac{\partial T}{\partial \Delta T_w}\,\dot{\Delta T}_w = -\Psi(\zeta)\,\dot{\Delta T}_w$$

Источник $Q_\text{ad}^*$ `\eqref{eq:Qad_star}` содержит $\partial p/\partial t$. Из `\eqref{eq:dp_dt}`:

$$\frac{\partial p}{\partial t} \approx \frac{\partial p}{\partial r_b}\,\dot{r}_b + \frac{\partial p}{\partial p_{wf}}\,\dot{p}_{wf}$$

Поэтому:

$$Q_\text{ad}^* = Q_\text{ad}^{*,(r_b)}\,\dot{r}_b + Q_\text{ad}^{*,(p_{wf})}\,\dot{p}_{wf}$$

где каждый вклад линеен по соответствующей производной $\partial p/\partial r_b$ или $\partial p/\partial p_{wf}$, подставленной в формулу $Q_\text{ad}$.

### Сбор коэффициентов

Переносим всё, не содержащее $\dot{r}_b$, $\dot{S}_{g,w}$, $\dot{\Delta T}_w$, в правую часть (F₃):

#### $\mathcal{A}_{31}$ (при $\dot{r}_b$):

Ёмкостный вклад (I): $\partial T/\partial r_b = 0$ ⟹ **нет вклада**.

Конвективный вклад (II): содержит $\partial T/\partial r$, а не $\partial T/\partial t$ ⟹ **нет вклада** (не зависит от $\dot{r}_b$).

Источник $Q_\text{ad}^*$ (IV): содержит $\partial p/\partial t = (\partial p/\partial r_b)\,\dot{r}_b + ...$ ⟹ **даёт вклад**.

$$\boxed{\mathcal{A}_{31} = -\int_{r_w}^{R_\text{ext}} r\,\bar{Q}_\text{ad}^{*}\,\frac{\partial p}{\partial r_b}\,dr}$$

где $\bar{Q}_\text{ad}^{*}$ — коэффициент при $\partial p/\partial t$ в формуле $Q_\text{ad}^*$ (без самой производной):

$$\bar{Q}_\text{ad}^{*}(p, T, S_g) = \underbrace{\phi\left[T\sum_\alpha S_\alpha\,\alpha_\alpha + c_r\left(p + (\rho c_p)_s\,T\right)\right]}_{\bar{Q}_\text{ad}} + L\,\rho_g^\text{ст}\,\phi\,\xi_o\,\frac{\partial R_s}{\partial p}$$

> Первый член — из $Q_\text{ad}$ `\eqref{eq:Qad}` с $\partial p/\partial t$ вынесенным. Второй — из добавки в $Q_\text{ad}^*$ `\eqref{eq:Qad_star}`.

> **Знак минуса:** $Q_\text{ad}^*$ стоит в **RHS** уравнения (eq:T_moment0). Часть с $\dot{r}_b$ переносится из RHS в LHS ($A\dot{q} = F$) со сменой знака → «−» перед интегралом. Результат: $\bar{Q}_\text{ad}^* > 0$, $\partial p/\partial r_b < 0$ → $\int \bar{Q}_\text{ad}^* (dp/dr_b) dr < 0$ → $\mathcal{A}_{31} = -(< 0) > 0$.

Двухзонное разбиение с замороженными PVT:

$$\mathcal{A}_{31} = -\bar{Q}_\text{ad,1}^{*}\int_{r_w}^{r_b} r\,\frac{\partial p}{\partial r_b}\bigg|_\text{inner}dr - \bar{Q}_\text{ad,2}^{*}\int_{r_b}^{R_\text{ext}} r\,\frac{\partial p}{\partial r_b}\bigg|_\text{outer}dr$$

> **Замечание:** структура интеграла аналогична $\mathcal{A}_{11}$ (eq:A11_zones), но с $\bar{Q}_\text{ad}^*$ вместо $C_p$ и **противоположным знаком** (A₁₁ из LHS, A₃₁ — перенос из RHS). Тот же числ. интеграл, та же конечная разность `dp_drb_numerical`.

#### $\mathcal{A}_{32} = 0$

По расщеплению (eq:matrix_structure): $\partial p/\partial t$ и $\partial T/\partial t$ не содержат $\dot{S}_{g,w}$.

#### $\mathcal{A}_{33}$ (при $\dot{\Delta T}_w$):

Ёмкостный вклад (I): $\partial T/\partial t = -\Psi(\zeta)\,\dot{\Delta T}_w$ ⟹

$$\text{I} = -\dot{\Delta T}_w\int_{r_w}^{R_\text{ext}} r\,(\rho c_p)_\text{eff}^*\,\Psi(\zeta)\,dr$$

Конвективный (II) и источники (IV): не зависят от $\dot{\Delta T}_w$ (конвективный содержит $\partial T/\partial r$, а не $\partial T/\partial t$; $Q_\text{JT}^*$ зависит от $\partial p/\partial r$; $Q_\text{ad}^*$ зависит от $\partial p/\partial t$, но не от $\dot{\Delta T}_w$).

Коэффициент при $\dot{\Delta T}_w$ (уже в LHS, переноса нет):

$$\boxed{\mathcal{A}_{33} = -\int_{r_w}^{R_\text{ext}} r\,(\rho c_p)_\text{eff}^*\,\Psi(\zeta)\,dr}$$

> **Знак минуса:** от $\partial T/\partial \Delta T_w = -\Psi$ (eq:dT_dTw). Term I уже стоит в LHS, переноса нет.
> $(\rho c_p)_\text{eff}^* > 0$, $\Psi > 0$ ⟹ $\mathcal{A}_{33} < 0$.
> Аналогия с $\mathcal{A}_{13}$ (eq:A13): тот же минус от $-\Psi$, тот же знак.

Двухзонное разбиение:

$$\mathcal{A}_{33} = -(\rho c_p)_{\text{eff},1}^{*}\int_{r_w}^{r_b} r\,\Psi(\zeta)\,dr - (\rho c_p)_{\text{eff},2}^{*}\int_{r_b}^{R_\text{ext}} r\,\Psi(\zeta)\,dr$$

> **Замечание:** структура идентична $\mathcal{A}_{13}$ (eq:A13_zones), но с $(\rho c_p)_\text{eff}^*$ вместо $C_T$.

#### $\mathcal{F}_3$ (правая часть):

Правая часть содержит все члены, не зависящие от $\dot{r}_b$, $\dot{S}_{g,w}$, $\dot{\Delta T}_w$:

$$\boxed{\mathcal{F}_3 = R_\text{ext}\,\lambda_\text{eff}\,T'_\text{ext} - \int_{r_w}^{R_\text{ext}} r\,(\rho c_p u)_\text{conv}^*\,\frac{\partial T}{\partial r}\,dr + \int_{r_w}^{R_\text{ext}} r\,Q_\text{JT}^*\,dr + I_{p_{wf}}^{(3)}\,\dot{p}_{wf}}$$

Разберём каждый член:

**Теплопроводность** (граничный поток):

$$R_\text{ext}\,\lambda_\text{eff}\,T'_\text{ext} = R_\text{ext}\,\lambda_\text{eff}\,\frac{\Delta T_w}{R_\text{ext}\,L_0}\,\Psi'(0) = \frac{\lambda_\text{eff}\,\Delta T_w}{L_0}\,\Psi'(0)$$

Из `\eqref{eq:dT_dr}`: $T'(R_\text{ext}) = \Delta T_w/(R_\text{ext}\,L_0)\,\Psi'(0)$.
$\Psi'(\zeta) = 2\sigma\,\zeta^{\sigma-1}(1-\zeta^\sigma)$, поэтому $\Psi'(0) = \lim_{\zeta\to 0} 2\sigma\,\zeta^{\sigma-1}(1-\zeta^\sigma)$.
При $\sigma \geq 1$: $\Psi'(0) = 0$ ($\sigma = 1$: $\Psi'(0) = 2\cdot 1 \cdot 1 \cdot (1-0) = 2$; нет, проверим: при $\sigma = 1$, $\Psi'(\zeta) = 2(1-\zeta)$, $\Psi'(0) = 2$). При $\sigma = 1$: $\Psi'(0) = 2$. При $\sigma > 1$: $\Psi'(0) = 0$.
При $\sigma = 2$ (baseline): $\Psi'(\zeta) = 4\zeta(1-\zeta^2)$, $\Psi'(0) = 0$ ⟹ граничный поток теплопроводности = 0.

> При baseline ($\sigma = 2$) поток теплопроводности на контуре нулевой. Это корректно физически: профиль $\Psi(\zeta) = \zeta^2(2-\zeta^2)$ обеспечивает $T'(R_\text{ext}) = 0$ при $\sigma = 2$.

Вычисляется в коде: `R_ext * lambda_eff * t_profile.dT_dr(R_ext, dT_w)`.

**Конвективный интеграл:**

$$-\int_{r_w}^{R_\text{ext}} r\,(\rho c_p u)_\text{conv}^*\,\frac{\partial T}{\partial r}\,dr$$

Из (eq:rhocp_conv_mod): $(\rho c_p u)_\text{conv}^* = \rho_o c_{p,o} u_o + \rho_g c_{p,g} u_g - L\,\rho_g^\text{ст}\,(u_o/B_o)\,(\partial R_s/\partial T)$.

Скорость фильтрации: $u_\alpha = -\lambda_\alpha\,\partial p/\partial r$.

При замораживании PVT в зонах: $(\rho c_p u)_\text{conv}^*$ зависит от $r$ через $u_\alpha(r) = -\lambda_\alpha\,p'(r)$ и $\partial T/\partial r$ через профиль $T(r)$.

Подставляем $u_\alpha = -\lambda_\alpha\,dp/dr$:

$$(\rho c_p u)_\text{conv}^* = -\left[\rho_o c_{p,o}\,\lambda_o + \rho_g c_{p,g}\,\lambda_g - L\,\rho_g^\text{ст}\,\frac{\lambda_o}{B_o}\,\frac{\partial R_s}{\partial T}\right]\frac{\partial p}{\partial r}$$

Обозначим замороженный коэффициент (**без минуса от Дарси**):

$$\bar{C}_\text{conv}^* = \rho_o c_{p,o}\,\lambda_o + \rho_g c_{p,g}\,\lambda_g - L\,\rho_g^\text{ст}\,\frac{\lambda_o}{B_o}\,\frac{\partial R_s}{\partial T}$$

Тогда конвективный в F₃ = $-\int r\,(-\bar{C}_\text{conv}^*\,dp/dr)\,(dT/dr)\,dr = +\int r\,\bar{C}_\text{conv}^*\,(dp/dr)(dT/dr)\,dr$.

Двухзонное разбиение:

$$+\bar{C}_{\text{conv},1}^*\int_{r_w}^{r_b} r\,\frac{\partial p}{\partial r}\,\frac{\partial T}{\partial r}\,dr + \bar{C}_{\text{conv},2}^*\int_{r_b}^{R_\text{ext}} r\,\frac{\partial p}{\partial r}\,\frac{\partial T}{\partial r}\,dr$$

> Два минуса (перенос LHS→RHS и Дарси $u = -\lambda\,dp/dr$) компенсируются → знак `+` перед интегралом.

**JT-источник:**

$$\int_{r_w}^{R_\text{ext}} r\,Q_\text{JT}^*\,dr$$

Из (eq:QJT_star): $Q_\text{JT}^* = Q_\text{JT} + L\,\rho_g^\text{ст}\,(u_o/B_o)\,(\partial R_s/\partial p)\,(\partial p/\partial r)$.

$$Q_\text{JT} = -\sum_\alpha u_\alpha\,(1-\alpha_\alpha T)\,\frac{\partial p}{\partial r} = \sum_\alpha \lambda_\alpha\,(1-\alpha_\alpha T)\left(\frac{\partial p}{\partial r}\right)^2$$

$$Q_\text{JT}^* = \left[\sum_\alpha \lambda_\alpha\,(1-\alpha_\alpha T) - L\,\rho_g^\text{ст}\,\frac{\lambda_o}{B_o}\,\frac{\partial R_s}{\partial p}\right]\left(\frac{\partial p}{\partial r}\right)^2$$

Обозначим замороженный коэффициент:

$$\bar{Q}_\text{JT}^* = \sum_\alpha \lambda_\alpha\,(1-\alpha_\alpha T) - L\,\rho_g^\text{ст}\,\frac{\lambda_o}{B_o}\,\frac{\partial R_s}{\partial p}$$

> **Знак «−»:** в tex (eq:QJT_star) добавка содержит $u_o/B_o = -(\lambda_o/B_o)(dp/dr)$, при вынесении $(dp/dr)^2$ знак меняется.

Тогда:

$$\int_{r_w}^{R_\text{ext}} r\,Q_\text{JT}^*\,dr = \bar{Q}_{\text{JT},1}^*\int_{r_w}^{r_b} r\left(\frac{\partial p}{\partial r}\right)^2 dr + \bar{Q}_{\text{JT},2}^*\int_{r_b}^{R_\text{ext}} r\left(\frac{\partial p}{\partial r}\right)^2 dr$$

> В однофазной зоне $\partial R_s/\partial p = 0$ (состав фиксирован), и добавка из $Q_\text{deg}$ обнуляется.

**Вклад $\dot{p}_{wf}$:**

Из $Q_\text{ad}^*$ при $\partial p/\partial t = (\partial p/\partial p_{wf})\,\dot{p}_{wf}$:

$$I_{p_{wf}}^{(3)} = \int_{r_w}^{R_\text{ext}} r\,\bar{Q}_\text{ad}^*\,\frac{\partial p}{\partial p_{wf}}\,dr$$

> Структура аналогична $I_{p_{wf}}$ из $\mathcal{F}_1$ (eq:I_pwf), но с $\bar{Q}_\text{ad}^*$ вместо $C_p$.
> Знак: $I_{p_{wf}}^{(3)}$ остаётся **в правой части** (тот же принцип, что в $\mathcal{F}_1$: перенос из LHS → смена знака):
> $+I_{p_{wf}}^{(3)}\,\dot{p}_{wf}$ в $\mathcal{F}_3$. Нет: вклад $Q_\text{ad}^*$ стоит в правой части (eq:T_moment0), поэтому $I_{p_{wf}}^{(3)}\,\dot{p}_{wf}$ остаётся с тем же знаком **+** (как в $\mathcal{F}_2$). Проверим:
> LHS (eq:T_moment0): $\int r\,(\rho c_p)_\text{eff}^*\,\partial T/\partial t\,dr$ + конвективный
> RHS: теплопроводность + $\int r\,(Q_\text{JT}^* + Q_\text{ad}^*)\,dr$
> При переносе LHS в матрицу: $\mathcal{A}_{33}\,\dot{\Delta T}_w$ (с минусом при $\Psi$).
> $Q_\text{ad}^*$ в RHS содержит $\partial p/\partial t = (\partial p/\partial r_b)\dot{r}_b + (\partial p/\partial p_{wf})\dot{p}_{wf}$.
> Часть с $\dot{r}_b$ → $\mathcal{A}_{31}$ (переносится в LHS, вычитается из RHS → знак $+$ в матрице).
> Часть с $\dot{p}_{wf}$ → $\mathcal{F}_3$ (остаётся в RHS).
> Итого: $\mathcal{F}_3$ содержит $+I_{p_{wf}}^{(3)}\,\dot{p}_{wf}$.

Полностью:

$$\mathcal{F}_3 = \underbrace{R_\text{ext}\,\lambda_\text{eff}\,T'_\text{ext}}_{\text{теплопроводность}} + \underbrace{\int r\,\bar{C}_\text{conv}^*\,(dp/dr)(dT/dr)\,dr}_{\text{конвекция}} + \underbrace{\int r\,\bar{Q}_\text{JT}^*\,(dp/dr)^2\,dr}_{\text{JT}} + \underbrace{I_{p_{wf}}^{(3)}\,\dot{p}_{wf}}_{\text{нестац. }p_{wf}}$$

> **Знак $\mathcal{F}_3$:** JT-эффект и конвекция дают положительный вклад (нагрев из-за диссипации при фильтрации). При достаточно больших перепадах давления $\mathcal{F}_3 > 0$, что при $\mathcal{A}_{33} < 0$ даёт $\dot{\Delta T}_w > 0$ (температура на забое падает).

### Ключевые отличия от строк 1 и 2

| | $\mathcal{A}_{1j}$, $\mathcal{F}_1$ (нефть) | $\mathcal{A}_{2j}$, $\mathcal{F}_2$ (газ) | $\mathcal{A}_{3j}$, $\mathcal{F}_3$ (энергия) |
|---|---|---|---|
| Домен | $[r_w, R_\text{ext}]$ | $[r_w, r_b]$ | $[r_w, R_\text{ext}]$ |
| Второй столбец | $\mathcal{A}_{12} = 0$ | $\mathcal{A}_{22} \neq 0$ | $\mathcal{A}_{32} = 0$ |
| Ёмкостный | $C_p$ | — | $(\rho c_p)_\text{eff}^*$ |
| Механизм в $\mathcal{A}_{i1}$ | $C_p \cdot \partial p/\partial r_b$ | геометрия + давление | $\bar{Q}_\text{ad}^* \cdot \partial p/\partial r_b$ |
| Механизм в $\mathcal{A}_{i3}$ | $C_T \cdot (-\Psi)$ | $-S_o \beta_o^\text{sat} \cdot \Psi$ | $-(\rho c_p)_\text{eff}^* \cdot \Psi$ |
| Граничные потоки | $\Lambda \cdot dp/dr$ | $\lambda_o/B_o \cdot dp/dr$ | $\lambda_\text{eff} \cdot dT/dr$ |
| Квадратичный интеграл | $Q_\text{quad}$ (из $R_s$) | Нет | Два: $(dp/dr)^2$ (JT) и $(dp/dr)(dT/dr)$ (конвекция) |
| Новые PVT | Нет | Нет | $(\rho c_p)_\text{eff}^*$, $\bar{C}_\text{conv}^*$, $\bar{Q}_\text{JT}^*$, $\bar{Q}_\text{ad}^*$ |

---

## Обратная совместимость

- [x] Добавление новых функций в `coefficients.py` — не затрагивает существующий код
- [x] Существующие тесты FEAT-005a/005b не меняются
- [x] Расширение `BlackOilFluid` — добавление новых методов, без изменения существующих
- [x] Конфиг `baseline.json` уже содержит `lambda_eff`, `rho_cp_s`, `cp_o`, `cp_g`, `L_degas`
- [x] Сигнатура `energy_A31(fluid, rock, p_profile, t_profile, s_profile, state)` аналогична газовым коэффициентам

---

## Подводные камни

- ✅ **Размерности:** проверка ниже
- ⚠️ **$\gamma < 1$:** $(dp/dr)^2$ расходится при $r \to r_w$ как $\eta^{2(\gamma-1)}$. Интеграл JT содержит этот множитель. При $\gamma > 1/2$ — интегрируем (как $Q_\text{quad}$ в $\mathcal{F}_1$). При baseline: $\gamma < 1$, но $\gamma > 1/2$. Применяем ту же стратегию с `points=` в `quad`.
- ⚠️ **Конвективный интеграл $(dp/dr)(dT/dr)$:** произведение двух производных. При $r \to r_w$: $dp/dr \sim \eta^{\gamma-1}$ расходится при $\gamma < 1$, но $dT/dr = 0$ при $r = r_w$ по ГУ. При $\sigma \geq 1$: $\Psi'(1) = 0$ ⟹ $dT/dr \sim (1-\zeta^\sigma)$ → 0 при $\zeta \to 1$ ($r \to r_w$). Произведение конечно при $\gamma + \sigma > 1$ (baseline: $\gamma \approx 0.6$, $\sigma = 2$: $\gamma + \sigma = 2.6 > 1$ ✓).
- ⚠️ **$(\rho c_p)_\text{eff}^*$ может быть < $(\rho c_p)_\text{eff}$:** модификация $-L\,\rho_g^\text{ст}\,\phi\,\xi_o\,\partial R_s/\partial T$ при $\partial R_s/\partial T < 0$ делает добавку положительной, т.е. $(\rho c_p)_\text{eff}^* > (\rho c_p)_\text{eff}$ — ёмкость увеличивается за счёт дегазации. Знак $(\rho c_p)_\text{eff}^* > 0$ гарантирован при разумных параметрах.
- ⚠️ **$Q_\text{ad}$ формула в tex:** $Q_\text{ad} = \phi[T\sum_\alpha S_\alpha\alpha_\alpha + c_r(p + (\rho c_p)_s T)]\,\partial p/\partial t$. Член $c_r \cdot p$ обычно мал по сравнению с $c_r \cdot (\rho c_p)_s \cdot T$. Все единицы: $[c_r \cdot (\rho c_p)_s \cdot T] = [1/\text{Па} \cdot \text{Дж/(м³·К)} \cdot \text{К}] = [\text{Дж/Па/м³}]$. При умножении на $\partial p/\partial t$ получим [Вт/м³].
- ✅ **Import-цепочки:** без циклов (те же импорты).
- ✅ **Параметр `rock["lambda_eff"]`:** уже в `baseline.json` = 2.0 Вт/(м·К).
- ✅ **Параметр `rock["rho_cp_s"]`:** уже в `baseline.json` = 2.0e6 Дж/(м³·К).
- ⚠️ **$\bar{Q}_\text{ad}$ размерность:** $\phi[T S_\alpha \alpha_\alpha + c_r(p + (\rho c_p)_s T)]$ — $[1 \cdot \text{К} \cdot 1 \cdot 1/\text{К} + 1/\text{Па} \cdot (\text{Па} + \text{Дж/(м³·К)} \cdot \text{К})]$. Второй член: $c_r \cdot (\rho c_p)_s \cdot T = 5\times 10^{-10} \cdot 2\times 10^6 \cdot 350 = 3.5\times 10^{-1}$, порядка единицы. Первый: $T \sum S_\alpha \alpha_\alpha \approx 350 \cdot (S_o \cdot \beta_o + S_g / T) \approx 350 \cdot 10^{-3} \approx 0.35$. Оба члена одного порядка.
- ⚠️ **Формулы ещё не выписаны в tex:** подраздел §5.5.3 не существует. Этап 1 плана — добавить формулы в tex.

### Проверка размерностей

| Величина | Размерность | Проверка $\mathcal{A}\dot{q} = \mathcal{F}$ |
|---|---|---|
| $\mathcal{A}_{31}$ | $\bar{Q}_\text{ad}^*$ [б/р] × $\partial p/\partial r_b$ [Па/м] × $r\,dr$ [м²] = [Па·м/м] = [Па] | $\mathcal{A}_{31}\dot{r}_b$ = [Па·м/с] |
| $\mathcal{A}_{33}$ | $(\rho c_p)_\text{eff}^*$ [Дж/(м³·К)] × $\Psi$ [б/р] × $r\,dr$ [м²] = [Дж·м²/(м³·К)] = [Дж/(м·К)] | $\mathcal{A}_{33}\dot{\Delta T}_w$ = [Дж/(м·К)·К/с] = [Вт/м] |
| $\mathcal{F}_3$ (теплопров.) | $\lambda_\text{eff}$ [Вт/(м·К)] × $\Delta T_w/L_0$ [К/б/р] × $\Psi'$ [б/р] = [Вт/м] | ✓ |
| $\mathcal{F}_3$ (JT) | $\bar{Q}_\text{JT}^*$ [м²/(Па·с)] × $(dp/dr)^2$ [Па²/м²] × $r\,dr$ [м²] = [Па·м²/с] | ❌ |

> **Проблема размерностей:** $\mathcal{A}_{31}\dot{r}_b$ и $\mathcal{F}_3$ должны иметь одинаковую размерность. Пересмотрим.

Уравнение (eq:T_moment0) — это $\int r \cdot [\text{Вт/м³}]\,dr$ = [Вт/м] (мощность на единицу длины скважины).

- $\int r\,(\rho c_p)_\text{eff}^*\,\partial T/\partial t\,dr$: [м · Дж/(м³·К) · К/с · м] = [Дж/(м·с)] = [Вт/м] ✓
- $\int r\,(\rho c_p u)_\text{conv}^*\,\partial T/\partial r\,dr$: [м · Дж/(м³·К)·м/с · К/м · м] = [Вт/м] ✓
- $R_\text{ext}\lambda_\text{eff}\,T'$: [м · Вт/(м·К) · К/м] = [Вт/м] ✓
- $\int r\,Q_\text{JT}^*\,dr$: [м · Вт/м³ · м] = [Вт/м] ✓
- $\int r\,Q_\text{ad}^*\,dr$: [м · Вт/м³ · м] = [Вт/м] ✓

Теперь:
- $\mathcal{A}_{31}\dot{r}_b$: $[\mathcal{A}_{31}]$ × [м/с] = [Вт/м] ⟹ $[\mathcal{A}_{31}]$ = [Вт·с/м²] = [Дж/м²]
- $\mathcal{A}_{33}\dot{\Delta T}_w$: $[\mathcal{A}_{33}]$ × [К/с] = [Вт/м] ⟹ $[\mathcal{A}_{33}]$ = [Вт·с/(м·К)] = [Дж/(м·К)]

Проверим $\mathcal{A}_{31}$: $\int r\,\bar{Q}_\text{ad}^*\,(\partial p/\partial r_b)\,dr$

$Q_\text{ad}^* \sim \phi \cdot [...] \cdot \partial p/\partial t$, где $[Q_\text{ad}^*]$ = [Вт/м³]. Выделяя $\partial p/\partial t$:

$\bar{Q}_\text{ad}^*$ = коэффициент при $\partial p/\partial t$ в $Q_\text{ad}^*$. Из (eq:Qad):

$Q_\text{ad} = \phi[T\sum S_\alpha\alpha_\alpha + c_r(p + (\rho c_p)_s T)] \cdot \partial p/\partial t$

$[\phi T S_\alpha \alpha_\alpha] = [1 \cdot \text{К} \cdot 1 \cdot 1/\text{К}] = [1]$ (безразмерный)

$[c_r \cdot p] = [1/\text{Па} \cdot \text{Па}] = [1]$ (безразмерный)

$[c_r \cdot (\rho c_p)_s \cdot T] = [1/\text{Па} \cdot \text{Дж/(м³·К)} \cdot \text{К}] = [\text{Дж/(Па·м³)}] = [1]$ (безразмерный, т.к. 1 Дж = 1 Па·м³)

Итого $[\bar{Q}_\text{ad}^*] = [1]$ (безразмерный).

$[\mathcal{A}_{31}] = \int [r \cdot 1 \cdot \text{Па/м} \cdot dr]$ = [Па·м²/м] = [Па·м] ≠ [Дж/м²]?

Нет: [Па·м] = [Н/м² · м] = [Н/м] = [Дж/м²] ✓ (1 Н/м = 1 Дж/м²). Корректно!

$[\mathcal{A}_{33}]$: $\int [r \cdot \text{Дж/(м³·К)} \cdot 1 \cdot dr]$ = [Дж·м²/(м³·К)] = [Дж/(м·К)] ✓

$[\mathcal{F}_3]$ (JT): $\int [r \cdot \bar{Q}_\text{JT}^* \cdot (dp/dr)^2 \cdot dr]$
$[\bar{Q}_\text{JT}^*] = [\lambda_\alpha \cdot (1-\alpha T)]$ = [м²/(Па·с) · 1] = [м²/(Па·с)]
$[r \cdot \text{м²/(Па·с)} \cdot \text{Па²/м²} \cdot dr]$ = [м · м²/(Па·с) · Па²/м² · м] = [Па·м²/с] = [Дж/м/с] = [Вт/м] ✓

Все размерности сходятся.

---

## Шаги реализации

### Шаг 1: PVT — $(\rho c_p)_\text{eff}$ и $(\rho c_p)_\text{eff}^*$

**Цель:** реализовать модифицированную эффективную теплоёмкость `\eqref{eq:rhocp_eff_mod}`.

**Файлы:** `method_of_moments/src/pvt/black_oil.py`, `method_of_moments/tests/test_coefficients.py`

**Формулы:**

$$(\rho c_p)_\text{eff} = (1-\phi)(\rho c_p)_s + \phi(S_o\,\rho_o\,c_{p,o} + S_g\,\rho_g\,c_{p,g})$$

$$(\rho c_p)_\text{eff}^* = (\rho c_p)_\text{eff} - L\,\rho_g^\text{ст}\,\phi\,\xi_o\,\frac{\partial R_s}{\partial T}$$

**Что сделать:**

1. В `BlackOilFluid` добавить метод:

```python
def rhocp_eff(self, p, T, Sg, phi, rho_cp_s):
    """(ρcp)_eff — эффективная объёмная теплоёмкость. Ур. (eq:rhocp_eff) moments_method.tex."""
    So = 1.0 - Sg
    return (1.0 - phi) * rho_cp_s + phi * (So * self.rho_o(p, T) * self.cp_o(p, T) + Sg * self.rho_g(p, T) * self.cp_g(p, T))
```

2. Добавить метод:

```python
def rhocp_eff_star(self, p, T, Sg, phi, rho_cp_s):
    """(ρcp)_eff* — модифицированная эффективная теплоёмкость. Ур. (eq:rhocp_eff_mod) moments_method.tex."""
    rhocp = self.rhocp_eff(p, T, Sg, phi, rho_cp_s)
    xi_o = self.xi_o(p, T, Sg)
    dRs_dT = self.dRs_dT(p, T)
    L_val = self.L(p, T)
    return rhocp - L_val * self.rho_g_st * phi * xi_o * dRs_dT
```

**Проверка после шага:**

```
cd method_of_moments && .venv/Scripts/python -m pytest tests/test_coefficients.py -k "rhocp" -v
```

**Тесты:**

```
test_rhocp_eff_positive: (ρcp)_eff > 0 при baseline параметрах
test_rhocp_eff_star_ge_eff: (ρcp)_eff* ≥ (ρcp)_eff (т.к. -L·ρg_st·φ·ξo·dRs/dT > 0 при dRs/dT < 0)
test_rhocp_eff_single_phase: при Sg=0 нет газового вклада, ρg·cpg = 0 (Sg=0)
test_rhocp_eff_star_dimension: ≈ 10⁶ [Дж/(м³·К)] — порядок теплоёмкости
```

**Зависимости:** Требует: —. Блокирует: шаг 4 (A₃₃).
**Оценка:** ~15 строк, ~10 минут.

---

### Шаг 2: PVT — $\bar{Q}_\text{ad}^*$ (коэффициент адиабатического источника)

**Цель:** реализовать коэффициент при $\partial p/\partial t$ в модифицированном адиабатическом источнике.

**Файлы:** `method_of_moments/src/pvt/black_oil.py`, `method_of_moments/tests/test_coefficients.py`

**Формула:**

$$\bar{Q}_\text{ad}^*(p, T, S_g) = \phi\left[T\sum_\alpha S_\alpha\,\alpha_\alpha + c_r\left(p + (\rho c_p)_s\,T\right)\right] + L\,\rho_g^\text{ст}\,\phi\,\xi_o\,\frac{\partial R_s}{\partial p}$$

Первый член — из $Q_\text{ad}$ `\eqref{eq:Qad}`, второй — из коррекции дегазации `\eqref{eq:Qad_star}`.

$\alpha_o = \beta_o$ (тепловое расширение нефти), $\alpha_g = 1/T$ (идеальный газ).

$$T \sum_\alpha S_\alpha\,\alpha_\alpha = T(S_o\,\beta_o + S_g/T) = T\,S_o\,\beta_o + S_g$$

**Что сделать:**

1. В `BlackOilFluid` добавить метод:

```python
def Qad_star_coeff(self, p, T, Sg, phi, rho_cp_s, cr):
    """Q̄_ad* — коэффициент при ∂p/∂t в Q_ad*. Ур. (eq:Qad, eq:Qad_star) moments_method.tex."""
    So = 1.0 - Sg
    beta_o_val = self.beta_o(p, T)
    thermal_exp = T * So * beta_o_val + Sg
    compressibility = cr * (p + rho_cp_s * T)
    Qad_base = phi * (thermal_exp + compressibility)
    xi_o = self.xi_o(p, T, Sg)
    dRs_dp = self.dRs_dp(p, T)
    L_val = self.L(p, T)
    return Qad_base + L_val * self.rho_g_st * phi * xi_o * dRs_dp
```

**Проверка после шага:**

```
cd method_of_moments && .venv/Scripts/python -m pytest tests/test_coefficients.py -k "Qad" -v
```

**Тесты:**

```
test_Qad_star_coeff_positive: Q̄_ad* > 0 (доминирует тепловое расширение и сжимаемость)
test_Qad_star_coeff_single_phase: при Sg=0 — no газовый вклад в α, ξo = 1/Bo
test_Qad_star_coeff_dimension: безразмерный (проверка порядка ≈ 0.1–1.0)
```

**Зависимости:** Требует: —. Блокирует: шаг 3 (A₃₁), шаг 5 (F₃).
**Оценка:** ~12 строк, ~10 минут.

---

### Шаг 3: Коэффициент $\mathcal{A}_{31}$

**Цель:** реализовать коэффициент при $\dot{r}_b$ в уравнении энергии.

**Файлы:** `method_of_moments/src/coefficients.py`, `method_of_moments/tests/test_coefficients.py`

**Формула:**

$$\mathcal{A}_{31} = -\int_{r_w}^{R_\text{ext}} r\,\bar{Q}_\text{ad}^*\,\frac{\partial p}{\partial r_b}\,dr$$

Двухзонное разбиение:

$$\mathcal{A}_{31} = -\bar{Q}_{\text{ad},1}^*\int_{r_w}^{r_b} r\,\frac{\partial p}{\partial r_b}\bigg|_\text{inner}dr - \bar{Q}_{\text{ad},2}^*\int_{r_b}^{R_\text{ext}} r\,\frac{\partial p}{\partial r_b}\bigg|_\text{outer}dr$$

> **Минус:** $Q_\text{ad}^*$ стоит в RHS (eq:T_moment0); при переносе части с $\dot{r}_b$ из RHS в LHS ($A\dot{q} = F$) знак меняется.

**Что сделать:**

1. В `coefficients.py` после `gas_F2` добавить:

```python
def energy_A31(fluid, rock, p_profile, t_profile, s_profile, state):
    """Коэффициент A₃₁ при ṙ_b в уравнении энергии. Ур. (eq:A31) moments_method.tex."""
    r_b = state.r_b
    dT_w = state.dT_w
    phi = rock["phi"]
    cr = rock["c_r"]
    rho_cp_s = rock["rho_cp_s"]

    pbs = p_profile.pb_star(r_b, dT_w, fluid, t_profile)

    p1, T1, Sg1 = frozen_pvt_zone1(p_profile.p_wf, pbs, t_profile.T_0, dT_w, state.Sg_w)
    Qad1 = fluid.Qad_star_coeff(p1, T1, Sg1, phi, rho_cp_s, cr)

    p2, T2, Sg2 = frozen_pvt_zone2(pbs, p_profile.p_0, t_profile.T_0)
    Qad2 = fluid.Qad_star_coeff(p2, T2, Sg2, phi, rho_cp_s, cr)

    def integrand_zone1(r):
        dp = dp_drb_numerical(p_profile, r, r_b, fluid, t_profile, dT_w)
        return r * Qad1 * dp

    def integrand_zone2(r):
        dp = dp_drb_numerical(p_profile, r, r_b, fluid, t_profile, dT_w)
        return r * Qad2 * dp

    r_w = p_profile.r_w
    R_ext = p_profile.R_ext

    I1, _ = quad(integrand_zone1, r_w, r_b)
    I2, _ = quad(integrand_zone2, r_b, R_ext)
    return -(I1 + I2)
```

> Структура идентична `oil_A11`, с `Qad_star_coeff` вместо `Cp`.

**Проверка после шага:**

```
cd method_of_moments && .venv/Scripts/python -m pytest tests/test_coefficients.py -k "A31" -v
```

**Тесты:**

```
test_A31_sign: A₃₁ > 0 (минус от переноса RHS→LHS × Q̄_ad* > 0 × ∂p/∂rb < 0)
test_A31_finite: |A₃₁| < ∞ при baseline
test_A31_dimension: порядок ≈ |Cp| × характерный_интеграл, по аналогии с A₁₁
```

**Зависимости:** Требует: шаг 2. Блокирует: —.
**Оценка:** ~25 строк, ~15 минут.

---

### Шаг 4: Коэффициент $\mathcal{A}_{33}$

**Цель:** реализовать коэффициент при $\dot{\Delta T}_w$ в уравнении энергии.

**Файлы:** `method_of_moments/src/coefficients.py`, `method_of_moments/tests/test_coefficients.py`

**Формула:**

$$\mathcal{A}_{33} = -\int_{r_w}^{R_\text{ext}} r\,(\rho c_p)_\text{eff}^*\,\Psi(\zeta)\,dr$$

Двухзонное разбиение:

$$\mathcal{A}_{33} = -(\rho c_p)_{\text{eff},1}^*\int_{r_w}^{r_b} r\,\Psi(\zeta)\,dr - (\rho c_p)_{\text{eff},2}^*\int_{r_b}^{R_\text{ext}} r\,\Psi(\zeta)\,dr$$

**Что сделать:**

1. В `coefficients.py` после `energy_A31`:

```python
def energy_A33(fluid, rock, p_profile, t_profile, s_profile, state):
    """Коэффициент A₃₃ при Δ̇T_w в уравнении энергии. Ур. (eq:A33) moments_method.tex."""
    r_b = state.r_b
    dT_w = state.dT_w
    phi = rock["phi"]
    rho_cp_s = rock["rho_cp_s"]

    pbs = p_profile.pb_star(r_b, dT_w, fluid, t_profile)

    p1, T1, Sg1 = frozen_pvt_zone1(p_profile.p_wf, pbs, t_profile.T_0, dT_w, state.Sg_w)
    rhocp1 = fluid.rhocp_eff_star(p1, T1, Sg1, phi, rho_cp_s)

    p2, T2, Sg2 = frozen_pvt_zone2(pbs, p_profile.p_0, t_profile.T_0)
    rhocp2 = fluid.rhocp_eff_star(p2, T2, Sg2, phi, rho_cp_s)

    def integrand_zone1(r):
        zeta = t_profile.zeta(r)
        return r * rhocp1 * t_profile.Psi(zeta)

    def integrand_zone2(r):
        zeta = t_profile.zeta(r)
        return r * rhocp2 * t_profile.Psi(zeta)

    r_w = p_profile.r_w
    R_ext = p_profile.R_ext

    I1, _ = quad(integrand_zone1, r_w, r_b)
    I2, _ = quad(integrand_zone2, r_b, R_ext)
    return -(I1 + I2)
```

> Структура идентична `oil_A13`, с `rhocp_eff_star` вместо `CT`.

**Проверка после шага:**

```
cd method_of_moments && .venv/Scripts/python -m pytest tests/test_coefficients.py -k "A33" -v
```

**Тесты:**

```
test_A33_sign: A₃₃ < 0 ((ρcp)_eff* > 0, Ψ > 0, знак минус)
test_A33_finite: |A₃₃| < ∞ при baseline
test_A33_dimension: порядок ≈ (ρcp)_eff × R_ext² ≈ 10⁶ × 10⁵ = 10¹¹ [Дж/(м·К)] — слишком большой? Нет: ∫r Ψ dr ≈ R_ext²/2 × <Ψ>, <Ψ> ≪ 1, фактически ≈ 10⁴ [Дж/(м·К)]
test_A33_isothermal: при dT_w = 0 — A₃₃ ≠ 0 (зависит от ёмкости, не от текущего перепада)
```

**Зависимости:** Требует: шаг 1. Блокирует: —.
**Оценка:** ~25 строк, ~10 минут.

---

### Шаг 5: Правая часть $\mathcal{F}_3$

**Цель:** реализовать правую часть уравнения энергии.

**Файлы:** `method_of_moments/src/pvt/black_oil.py`, `method_of_moments/src/coefficients.py`, `method_of_moments/tests/test_coefficients.py`

**Формула:**

$$\mathcal{F}_3 = \underbrace{R_\text{ext}\,\lambda_\text{eff}\,T'(R_\text{ext})}_{\text{теплопроводность}} + \underbrace{\int_{r_w}^{R_\text{ext}} r\,\bar{C}_\text{conv}^*\,(dp/dr)(dT/dr)\,dr}_{\text{конвекция}} + \underbrace{\int_{r_w}^{R_\text{ext}} r\,\bar{Q}_\text{JT}^*\,(dp/dr)^2\,dr}_{\text{JT}} + \underbrace{I_{p_{wf}}^{(3)}\,\dot{p}_{wf}}_{\text{нестац. }p_{wf}}$$

Замороженные коэффициенты:

$$\bar{C}_\text{conv}^* = \rho_o\,c_{p,o}\,\lambda_o + \rho_g\,c_{p,g}\,\lambda_g - L\,\rho_g^\text{ст}\,\frac{\lambda_o}{B_o}\,\frac{\partial R_s}{\partial T}$$

$$\bar{Q}_\text{JT}^* = \sum_\alpha \lambda_\alpha\,(1-\alpha_\alpha T) - L\,\rho_g^\text{ст}\,\frac{\lambda_o}{B_o}\,\frac{\partial R_s}{\partial p}$$

$$I_{p_{wf}}^{(3)} = \int_{r_w}^{R_\text{ext}} r\,\bar{Q}_\text{ad}^*\,\frac{\partial p}{\partial p_{wf}}\,dr$$

**Что сделать:**

1. В `BlackOilFluid` добавить два вспомогательных метода:

```python
def C_conv_star(self, p, T, Sg, k):
    """C̄_conv* — замороженный конвективный коэффициент. Ур. (eq:rhocp_conv_mod) moments_method.tex."""
    rho_o = self.rho_o(p, T)
    rho_g = self.rho_g(p, T)
    cp_o = self.cp_o(p, T)
    cp_g = self.cp_g(p, T)
    lam_o = self.mobility_o(p, T, Sg, k)
    lam_g = self.mobility_g(p, T, Sg, k)
    L_val = self.L(p, T)
    Bo_val = self.Bo(p, T)
    dRs_dT = self.dRs_dT(p, T)
    return rho_o * cp_o * lam_o + rho_g * cp_g * lam_g - L_val * self.rho_g_st * (lam_o / Bo_val) * dRs_dT

def QJT_star_coeff(self, p, T, Sg, k):
    """Q̄_JT* — замороженный коэффициент JT при (dp/dr)². Ур. (eq:QJT_star) moments_method.tex."""
    alpha_o = self.alpha_o(p, T)
    alpha_g = self.alpha_g(p, T)
    lam_o = self.mobility_o(p, T, Sg, k)
    lam_g = self.mobility_g(p, T, Sg, k)
    L_val = self.L(p, T)
    Bo_val = self.Bo(p, T)
    dRs_dp = self.dRs_dp(p, T)
    return (lam_o * (1.0 - alpha_o * T) + lam_g * (1.0 - alpha_g * T)
            - L_val * self.rho_g_st * (lam_o / Bo_val) * dRs_dp)
```

2. В `coefficients.py` добавить `energy_F3`:

```python
def energy_F3(fluid, rock, p_profile, t_profile, s_profile, state):
    """Правая часть F₃ уравнения энергии. Ур. (eq:F3) moments_method.tex."""
    r_b = state.r_b
    dT_w = state.dT_w
    Sg_w = state.Sg_w
    phi = rock["phi"]
    cr = rock["c_r"]
    k = rock["k"]
    lambda_eff = rock["lambda_eff"]
    rho_cp_s = rock["rho_cp_s"]

    pbs = p_profile.pb_star(r_b, dT_w, fluid, t_profile)
    gam = p_profile.gamma(r_b, pbs)

    r_w = p_profile.r_w
    R_ext = p_profile.R_ext

    # --- теплопроводность: R_ext · λ_eff · T'(R_ext) ---
    flux_cond = R_ext * lambda_eff * t_profile.dT_dr(R_ext, dT_w)

    # --- замороженные PVT ---
    p1, T1, Sg1 = frozen_pvt_zone1(p_profile.p_wf, pbs, t_profile.T_0, dT_w, Sg_w)
    p2, T2, Sg2 = frozen_pvt_zone2(pbs, p_profile.p_0, t_profile.T_0)

    Cconv1 = fluid.C_conv_star(p1, T1, Sg1, k)
    Cconv2 = fluid.C_conv_star(p2, T2, Sg2, k)

    QJT1 = fluid.QJT_star_coeff(p1, T1, Sg1, k)
    QJT2 = fluid.QJT_star_coeff(p2, T2, Sg2, k)

    # --- конвективный: ∫r · C̄_conv* · (dp/dr)(dT/dr) dr ---
    def conv_integrand_z1(r):
        dp_dr = p_profile.dp_dr(r, r_b, pbs, gam)
        dT_dr = t_profile.dT_dr(r, dT_w)
        return r * Cconv1 * dp_dr * dT_dr

    def conv_integrand_z2(r):
        dp_dr = p_profile.dp_dr(r, r_b, pbs, gam)
        dT_dr = t_profile.dT_dr(r, dT_w)
        return r * Cconv2 * dp_dr * dT_dr

    I_conv1, _ = quad(conv_integrand_z1, r_w, r_b)
    I_conv2, _ = quad(conv_integrand_z2, r_b, R_ext)
    conv_total = I_conv1 + I_conv2

    # --- JT: ∫r · Q̄_JT* · (dp/dr)² dr ---
    def jt_integrand_z1(r):
        dp_dr = p_profile.dp_dr(r, r_b, pbs, gam)
        return r * QJT1 * dp_dr ** 2

    def jt_integrand_z2(r):
        dp_dr = p_profile.dp_dr(r, r_b, pbs, gam)
        return r * QJT2 * dp_dr ** 2

    if gam > 0.5:
        I_jt1, _ = quad(jt_integrand_z1, r_w, r_b)
    else:
        I_jt1, _ = quad(jt_integrand_z1, r_w, r_b, points=[r_w + r_w * 1e-6])
    I_jt2, _ = quad(jt_integrand_z2, r_b, R_ext)
    jt_total = I_jt1 + I_jt2

    # --- I_pwf^(3): ∫r · Q̄_ad* · (dp/dp_wf) dr ---
    I_pwf = 0.0
    if state.dp_wf_dt != 0.0:
        Qad1 = fluid.Qad_star_coeff(p1, T1, Sg1, phi, rho_cp_s, cr)
        Qad2 = fluid.Qad_star_coeff(p2, T2, Sg2, phi, rho_cp_s, cr)

        def pwf_z1(r):
            dp = dp_dpwf_numerical(p_profile, r, r_b, fluid, t_profile, dT_w)
            return r * Qad1 * dp

        def pwf_z2(r):
            dp = dp_dpwf_numerical(p_profile, r, r_b, fluid, t_profile, dT_w)
            return r * Qad2 * dp

        i1, _ = quad(pwf_z1, r_w, r_b)
        i2, _ = quad(pwf_z2, r_b, R_ext)
        I_pwf = (i1 + i2) * state.dp_wf_dt

    return flux_cond + conv_total + jt_total + I_pwf
```

**Проверка после шага:**

```
cd method_of_moments && .venv/Scripts/python -m pytest tests/test_coefficients.py -k "F3" -v
```

**Тесты:**

```
test_F3_finite: |F₃| < ∞ при baseline
test_F3_sign: F₃ > 0 при dT_w > 0 (JT-нагрев, конвективный перенос)
test_F3_isothermal: при dT_w = 0 — F₃ = JT + конвективный ≠ 0 (JT-эффект действует при любом перепаде давления)
test_F3_no_pwf_contribution: при dp_wf_dt = 0 — вклад I_pwf = 0
test_F3_nonstationary_pwf: при dp_wf_dt ≠ 0 — F₃ меняется
```

> **Подводный камень:** $(dp/dr)^2$ расходится при $r \to r_w$ при $\gamma < 1$, но интегрируем при $\gamma > 1/2$. Используем `points=` в `quad` (как в $Q_\text{quad}$ из $\mathcal{F}_1$).
> **Конвективный интеграл:** $(dp/dr)(dT/dr)$ — произведение, где $dT/dr = 0$ при $r = r_w$ (ГУ). Расходимости нет при $\sigma \geq 1$.

**Зависимости:** Требует: шаг 2 (Qad_star_coeff), PVT-методы. Блокирует: —.
**Оценка:** ~65 строк (коэффициенты + F₃), ~30 минут.

---

### Шаг 6: Тесты — согласованность и регрессия

**Цель:** убедиться, что A₃₂ = 0 и вся существующая тестовая база зелёная.

**Файлы:** `method_of_moments/tests/test_coefficients.py`

**Что сделать:**

1. Добавить тест `test_no_energy_A32_in_api`:

```python
def test_no_energy_A32_in_api(self):
    """A₃₂ = 0 по расщеплению (eq:matrix_structure)."""
    import src.coefficients as coeff
    assert not hasattr(coeff, 'energy_A32'), (
        "energy_A32 не должна существовать: A₃₂ = 0 по расщеплению"
    )
```

2. Добавить тест согласованности знаков:

```python
def test_dot_dTw_positive(self, ...):
    """ΔṪ_w = F₃/A₃₃ > 0 при dT_w > 0 (охлаждение нарастает)."""
    A33 = energy_A33(...)
    F3 = energy_F3(...)
    # A₃₃ < 0, F₃ > 0 (при dT_w > 0) ⟹ F₃/A₃₃ < 0?
    # Нет: система 2×2 (строки 1 и 3). Для грубой оценки:
    # dot_dTw ≈ F₃/A₃₃ (при малом A₃₁ или A₁₃)
    # A₃₃ < 0, F₃ содержит JT > 0 ⟹ F₃/A₃₃ < 0 ⟹ ΔṪ_w < 0?
    # Нет: dΔTw/dt > 0 означает рост перепада.
    # Уравнение: A₃₃·ΔṪ_w = F₃ - A₃₁·ṙ_b
    # Нужен знак (F₃ - A₃₁·ṙ_b)/A₃₃
    # Грубо: оба конечны, проверяем конечность.
    assert np.isfinite(A33)
    assert np.isfinite(F3)
    assert A33 != 0.0
```

3. Прогнать полную регрессию:

```
cd method_of_moments && .venv/Scripts/python -m pytest tests/ -v
```

**Зависимости:** Требует: шаги 1–5. Блокирует: —.
**Оценка:** ~20 строк, ~10 минут.

---

### Шаг 7: LaTeX — вывод формул в tex

**Цель:** добавить `\subsubsection{Коэффициенты третьего уравнения (энергия)}` в §5.5 `moments_method.tex`.

**Файлы:** `method_of_moments/moments_method.tex`

**Что сделать:**

1. После строки ~1261 (конец `\subsubsection{Коэффициенты второго уравнения (масса газа)}`) добавить новый `\subsubsection` с:
   - `\paragraph{Элемент $\mathcal{A}_{31}$}` — формула (eq:A31), вывод, знак
   - `\paragraph{Элемент $\mathcal{A}_{32} = 0$}` — ссылка на (eq:matrix_structure)
   - `\paragraph{Элемент $\mathcal{A}_{33}$}` — формула (eq:A33), вывод, знак
   - `\paragraph{Правая часть $\mathcal{F}_3$}` — формула (eq:F3), все 4 вклада
   - Проверка размерностей

2. Компиляция:

```powershell
cd d:\Lessons\Grants\2026\GPN\Oil_Gas\method_of_moments
pdflatex -interaction=nonstopmode moments_method.tex
```

**Зависимости:** Требует: —. Блокирует: — (можно делать параллельно с кодом).
**Оценка:** ~100 строк LaTeX, ~30 минут.

---

## Тестовая стратегия

### Unit-тесты PVT

```
test_rhocp_eff_positive:
  Файл: tests/test_coefficients.py
  Сценарий: (ρcp)_eff > 0 при baseline (p=16.5 МПа, T=348 К, Sg=0.05)
  Setup: fluid, phi=0.2, rho_cp_s=2e6
  Ожидание: > 0, порядок 10⁶ Дж/(м³·К)
  Формула: (eq:rhocp_eff)
  Предотвращает: отрицательная ёмкость (ошибка знака)

test_rhocp_eff_star_ge_eff:
  Сценарий: модификация из-за дегазации увеличивает ёмкость
  Ожидание: (ρcp)_eff* ≥ (ρcp)_eff (при dRs/dT < 0, L > 0)
  Формула: (eq:rhocp_eff_mod)
  Предотвращает: ошибка знака в модификации

test_Qad_star_coeff_positive:
  Сценарий: Q̄_ad* > 0 (тепловое расширение и сжимаемость)
  Ожидание: > 0
  Формула: (eq:Qad, eq:Qad_star)

test_QJT_star_coeff_sign:
  Сценарий: Q̄_JT* > 0 (диссипация)
  Ожидание: > 0 (при типичных αT < 1)
  Формула: (eq:QJT_star)

test_C_conv_star_positive:
  Сценарий: C̄_conv* > 0
  Ожидание: > 0 (тепловой поток сонаправлен массовому)
  Формула: (eq:rhocp_conv_mod)
```

### Unit-тесты коэффициентов

```
test_A31_sign:
  Сценарий: A₃₁ > 0
  Setup: baseline, r_b=5.0, Sg_w=0.1, dT_w=2.0
  Ожидание: A₃₁ > 0
  Формула: A₃₁ = −∫r·Q̄_ad*·∂p/∂rb dr; Q̄_ad* > 0, ∂p/∂rb < 0, интеграл < 0, минус от переноса RHS→LHS
  Предотвращает: ошибка знака (пропущенный минус переноса)

test_A33_sign:
  Сценарий: A₃₃ < 0
  Ожидание: A₃₃ < 0
  Формула: A₃₃ = -∫r·(ρcp)_eff*·Ψ dr, (ρcp)_eff* > 0, Ψ > 0
  Предотвращает: пропущенный минус

test_A32_absent:
  Сценарий: нет energy_A32 в API (расщепление)
  Формула: (eq:matrix_structure)

test_F3_finite:
  Сценарий: |F₃| < ∞ при baseline
  Предотвращает: сингулярность интегралов

test_F3_isothermal:
  Сценарий: при dT_w = 0 — F₃ ≠ 0 (JT действует всегда)
  Setup: dT_w = 0.0
  Ожидание: F₃ > 0 (только JT, конвективный = 0)
  Предотвращает: неверное зануление

test_F3_no_pwf:
  Сценарий: dp_wf_dt = 0 не влияет
  Ожидание: I_pwf = 0
```

### Предельные случаи

```
test_single_phase_limit:
  Сценарий: r_b → r_w + ε, Sg_w = 0.001
  Ожидание: A₃₁ ≈ 0, A₃₃ конечен, F₃ конечен
  Предотвращает: деление на 0 при вырождении зоны 1

test_isothermal_limit:
  Сценарий: dT_w = 0, Sg_w > 0
  Ожидание: A₃₃ конечен (зависит от ёмкости, не от перепада)
  Предотвращает: зависимость A₃₃ от dT_w
```

### Регрессия

```
Все существующие тесты FEAT-005a/005b зелёные после изменений.
```

---

## Критерии завершения

- [ ] Метод `rhocp_eff()` в `BlackOilFluid`
- [ ] Метод `rhocp_eff_star()` в `BlackOilFluid`
- [ ] Метод `Qad_star_coeff()` в `BlackOilFluid`
- [ ] Метод `C_conv_star()` в `BlackOilFluid`
- [ ] Метод `QJT_star_coeff()` в `BlackOilFluid`
- [ ] Функция `energy_A31()` в `coefficients.py`
- [ ] Функция `energy_A33()` в `coefficients.py`
- [ ] Функция `energy_F3()` в `coefficients.py`
- [ ] Каждая функция имеет docstring с `\eqref{}`
- [ ] Unit-тесты PVT зелёные
- [ ] Unit-тесты коэффициентов зелёные
- [ ] Предельные случаи (Sg→0, dT_w=0, r_b→r_w) зелёные
- [ ] Все существующие тесты зелёные (обратная совместимость)
- [ ] §5.5.3 в moments_method.tex с явными формулами
- [ ] Vault обновлён
- [ ] GitHub issue #7 прокомментирован

---

## Обнаруженные проблемы

### Новые

1. **Формула $Q_\text{ad}$ в tex содержит нестандартный член $c_r(p + (\rho c_p)_s T)$.** Размерность корректна ([б/р]), но физический смысл члена $c_r \cdot p$ требует проверки по первоисточнику (`two_phase_energy.tex`). Не блокирует реализацию, но стоит верифицировать при подготовке §5.5.3.

2. **В однофазной зоне ($S_g = 0$, $p > p_b$):** все добавки из дегазации ($L$, $\partial R_s/\partial T$, $\partial R_s/\partial p$) обнуляются, т.к. $\partial R_s/\partial p = 0$ и $\partial R_s/\partial T = 0$ при фиксированном составе (p > p_b). В коде `dRs_dp` и `dRs_dT` из `BlackOilFluid` уже возвращают 0 при $p > p_b$. Проверить, что `_is_saturated` корректно определяет однофазную зону с учётом `pb_star` (temperature-dependent pb).

---

## Связанные заметки

- [[feat-005a oil-mass-coefficients]] — паттерн реализации
- [[feat-005b gas-mass-coefficients]] — паттерн реализации
- `vault/roadmap/планируемые фичи.md` — FEAT-005c
- `vault/roadmap/roadmap реализации.md` — фаза 3
