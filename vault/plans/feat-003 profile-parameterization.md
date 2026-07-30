---
tags:
  - план
  - физика
date: 2026-07-30
issue: FEAT-003
github: 3
branch: feat/feat-003/profile-parameterization
model_level: М.6
status: в процессе
audit:
  date: 2026-07-30
  found: 7
  auto-fixed: 7
  manual-required: 0
  round2:
    date: 2026-07-30
    found: 6
    auto-fixed: 6
    manual-required: 0
  round3:
    date: 2026-07-30
    found: 0
    auto-fixed: 0
    manual-required: 0
---

# FEAT-003: Параметризация профилей p(r), Sg(r), T(r)

## Как начать работу по этому плану

1. Прочитай этот файл целиком
2. Прочитай `method_of_moments/moments_method.tex` §4 (строки 464–616)
3. Создай ветку: `git checkout -b feat/feat-003/profile-parameterization`
4. Прогони тесты (baseline): `cd method_of_moments && .venv/Scripts/python -m pytest tests/ -v`
5. Начни с шага 1. После каждого шага: pytest

## Подтип

**Физика** — параметризация радиальных профилей давления, насыщенности и температуры. Формулы из moments_method.tex §4.

## Связь формула → код

| Формула | Уравнение в tex | Python-функция | Модуль | Тест |
|---|---|---|---|---|
| $\Phi(\eta) = \eta^\gamma$ | `\eqref{eq:Phi}` | внутри `PressureProfile.__call__` | `src/profiles/pressure.py` | `test_p_inner_at_rw`, `test_p_inner_at_rb` |
| $p(r)$ внутренняя зона | `\eqref{eq:p_inner}` | `PressureProfile.__call__` | `src/profiles/pressure.py` | `test_p_inner_at_rw`, `test_p_inner_at_rb` |
| $p(r)$ внешняя зона | `\eqref{eq:p_outer}` | `PressureProfile.__call__` | `src/profiles/pressure.py` | `test_p_outer_at_rb`, `test_p_outer_at_Rext` |
| $\gamma = \Delta p_2 L_b / (\Delta p_1 L_e)$ | `\eqref{eq:gamma_constraint}` | `PressureProfile.gamma` | `src/profiles/pressure.py` | `test_gamma_flux_continuity` |
| $p_b^* = p_b(T(r_b))$ | `\eqref{eq:pb_star}` | `PressureProfile.pb_star` | `src/profiles/pressure.py` | `test_pb_star_isothermal` |
| $dp/dr$ внутренняя | `\eqref{eq:dp_inner}` | `PressureProfile.dp_dr` | `src/profiles/pressure.py` | `test_dp_dr_vs_fd` |
| $dp/dr$ внешняя | `\eqref{eq:dp_outer}` | `PressureProfile.dp_dr` | `src/profiles/pressure.py` | `test_dp_dr_vs_fd` |
| $S_g(r) = S_{g,w}(1 - \eta^\beta)$ | `\eqref{eq:Sg_profile}` | `SaturationProfile.__call__` | `src/profiles/saturation.py` | `test_Sg_boundary` |
| $\Psi(\zeta) = \zeta^\sigma(2 - \zeta^\sigma)$ | `\eqref{eq:Psi}` | `TemperatureProfile.Psi` | `src/profiles/temperature.py` | `test_Psi_boundary` |
| $T(r) = T_0 - \Delta T_w \Psi(\zeta)$ | `\eqref{eq:T_profile}` | `TemperatureProfile.__call__` | `src/profiles/temperature.py` | `test_T_boundary` |
| $dT/dr$ | `\eqref{eq:dT_dr}` | `TemperatureProfile.dT_dr` | `src/profiles/temperature.py` | `test_dT_dr_adiabatic_wall` |
| $J^{(m)} = 2/(m+1) - 1/(m+\sigma+1)$ | `\eqref{eq:IPsi}` | `TemperatureProfile.J` | `src/profiles/temperature.py` | `test_J_vs_quad` |

## Обратная совместимость

- [x] Существующие тесты (57: 31 PVT + 26 relperm) не затрагиваются — создаются новые файлы
- [x] Существующие конфиги (`baseline.json`) уже содержат секцию `profiles` с `beta` и `sigma`
- [x] API `BlackOilFluid` не меняется — используется только метод `pb(T)` (строка 91)
- [x] Новые модули — аддитивные, не модифицируют существующий код

## Вариант решения

Единственный разумный вариант: три класса (по одному на профиль), каждый инкапсулирует геометрию и формулы из §4. Классы — stateful (хранят геометрию $r_w$, $R_\text{ext}$), методы принимают текущие параметры ($r_b$, $S_{g,w}$, $\Delta T_w$).

Альтернатива (чистые функции без классов) — хуже, потому что геометрические параметры ($r_w$, $R_\text{ext}$, $L_0 = \ln(R_\text{ext}/r_w)$) постоянны и их пришлось бы протаскивать в каждый вызов.

## Подводные камни

- ✅ **Размерности:** $r$ [м], $p$ [Па], $T$ [К], $S_g$ [безразм.] — единицы SI, как в PVT
- ⚠️ **Граничный случай $r_b \to r_w$:** $L_b = \ln(r_b/r_w) \to 0$, деление в $\gamma$, $\eta$, $dp/dr$. Адресован: проверка `L_b > 0` при вычислении; при $r_b = r_w$ профили вырождаются (начальная асимптотика — FEAT-006)
- ⚠️ **$\gamma$ при $\Delta p_1 \to 0$:** если $p_{wf} \to p_b^*$, то $\Delta p_1 \to 0$ и $\gamma \to \infty$. Физически не возникает при $p_{wf} < p_b$
- ⚠️ **Сингулярность $dp/dr$ на забое при $\gamma < 1$:** при baseline параметрах ($r_w=0.1$, $r_b=10$, $\Delta p_1=3$ МПа, $\Delta p_2=2$ МПа) $\gamma \approx 0.785 < 1$. Тогда $dp/dr \sim \eta^{\gamma-1}$ при $\eta \to 0$ расходится — `dp_dr(r_w, ...)` выбросит `ZeroDivisionError`. Это физически корректная интегрируемая сингулярность (аналог $1/r$ при логарифмическом профиле). Интегралы $I_\Phi^{(n)} = 1/(n\gamma+1)$ сходятся при $\gamma > 0$. **Решение:** `dp_dr` должен обрабатывать $\eta = 0$: возвращать `math.inf` (со знаком $\Delta p_1 > 0$). FEAT-004/005 будут использовать интегралы, не поточечные значения на забое
- ✅ **$\eta$ вне [0,1]:** если $r < r_w$ или $r > r_b$ — вне определения, `__call__` разветвляет на зоны
- ✅ **Import-цепочки:** `profiles/pressure.py` импортирует `pvt.black_oil.BlackOilFluid` — линейная зависимость, без циклов
- ✅ **Производительность:** вычисления — элементарные (log, pow), горячий цикл — в FEAT-004/005 через предвычисленные интегралы
- ⚠️ **Сингулярность $dS_g/dr$ на забое при $\beta < 1$:** аналогично $dp/dr$, формула $dS_g/dr \sim \eta^{\beta-1}$ расходится при $\eta = 0$. Baseline $\beta = 2$ — безопасно. При $\beta < 1$ — `dSg_dr(r_w, ...)` вернёт `inf`/`ZeroDivisionError`. Решение: аналогичная обработка $\eta = 0$
- ⚠️ **Сингулярность $\Psi'(0)$ при $\sigma < 1$:** $\Psi'(\zeta) = 2\sigma\zeta^{\sigma-1}(1-\zeta^\sigma)$. При $\zeta = 0$: $\zeta^{\sigma-1} \to \infty$ если $\sigma < 1$. Означает бесконечный градиент $dT/dr$ на контуре питания. Физически допустимо (конвективный фронт), но `dT_dr(R_ext, dT_w)` вернёт `inf`. Адресован: baseline `sigma ≥ 1`; при $\sigma < 1$ предупредить в docstring. Тест: проверить поведение при $\sigma = 0.5$
- ⚠️ **Интегралы $I_\Phi^{(n)}$, $I_S^{(n)}$ — граница ответственности FEAT-003 vs FEAT-004:** эти интегралы зависят от $\gamma$ и $\beta$ (параметры профилей), но не от формы профиля как объекта. Решение: оставить $I_\Phi$, $I_S$ на FEAT-004 (`src/integrals.py`), в FEAT-003 реализовать только $J^{(m)}$ — он специфичен для профиля температуры

---

## Шаги реализации

### Шаг 1: `src/profiles/pressure.py` — профиль давления

**Цель:** реализовать $p(r)$, $dp/dr$, $\gamma$, $p_b^*$ по формулам §4.2 moments_method.tex.

**Файлы:** `method_of_moments/src/profiles/pressure.py` (создать)

**Контекст:**
Область делится на две зоны границей $r_b$. Во внешней зоне ($r_b \leqslant r \leqslant R_\text{ext}$) — логарифмический профиль. Во внутренней ($r_w \leqslant r \leqslant r_b$) — степенной с показателем $\gamma$. Непрерывность потока $r \Lambda \partial p/\partial r$ на $r = r_b$ определяет $\gamma$.

**Формулы:**

Внешняя зона:
$$p(r) = p_b^* + (p_0 - p_b^*) \frac{\ln(r/r_b)}{\ln(R_\text{ext}/r_b)}, \quad r_b \leqslant r \leqslant R_\text{ext} \quad \eqref{eq:p\_outer}$$

Внутренняя зона:
$$p(r) = p_{wf} + (p_b^* - p_{wf}) \cdot \Phi(\eta), \quad \Phi(\eta) = \eta^\gamma, \quad \eta = \frac{\ln(r/r_w)}{\ln(r_b/r_w)} \quad \eqref{eq:p\_inner}, \eqref{eq:Phi}$$

Непрерывность потока:
$$\gamma = \frac{\Delta p_2 \cdot L_b}{\Delta p_1 \cdot L_e} \quad \eqref{eq:gamma\_constraint}$$
где $L_b = \ln(r_b/r_w)$, $L_e = \ln(R_\text{ext}/r_b)$, $\Delta p_1 = p_b^* - p_{wf}$, $\Delta p_2 = p_0 - p_b^*$.

Давление насыщения на фронте:
$$p_b^* = p_b(T_0 - \Delta T_w \cdot \Psi(\zeta_b)), \quad \zeta_b = L_e / L_0 \quad \eqref{eq:pb\_star}$$

Производные:
$$\frac{\partial p}{\partial r}\bigg|_\text{inner} = \frac{\Delta p_1 \cdot \gamma}{r \cdot L_b} \eta^{\gamma - 1} \quad \eqref{eq:dp\_inner}$$
$$\frac{\partial p}{\partial r}\bigg|_\text{outer} = \frac{\Delta p_2}{r \cdot L_e} \quad \eqref{eq:dp\_outer}$$

**Что сделать:**

1. Создать класс `PressureProfile`:
   - `__init__(self, r_w, R_ext, p_wf, p_0)` — геометрия и ГУ давления
   - `L_b(self, r_b)` — $\ln(r_b / r_w)$
   - `L_e(self, r_b)` — $\ln(R_\text{ext} / r_b)$
   - `eta(self, r, r_b)` — безразмерная координата $\eta \in [0, 1]$ внутренней зоны
   - `gamma(self, r_b, pb_star)` — параметр $\gamma$ из непрерывности потока
   - `pb_star(self, r_b, dT_w, fluid, temp_profile)` — давление насыщения на фронте; принимает `fluid.pb(T)` и `temp_profile` для вычисления $T(r_b)$
   - `__call__(self, r, r_b, pb_star, gamma)` — $p(r)$ в обеих зонах
   - `dp_dr(self, r, r_b, pb_star, gamma)` — $dp/dr$ в обеих зонах

2. Docstring каждого метода: одна строка + `\eqref{}`

**Проектное решение — `pb_star`:**
Метод `pb_star` принимает `fluid` (для `fluid.pb(T)`) и `temp_profile` (для `temp_profile(r_b, dT_w)`). Это связывает профили давления и температуры, как и в физике. Альтернатива — передавать готовое число $p_b^*$ извне — чище для тестирования, поэтому `__call__` и `dp_dr` принимают `pb_star` как число, а метод `pb_star()` — отдельная утилита для вычисления этого числа.

**Проверка после шага:**
- Импорт: `cd method_of_moments && .venv/Scripts/python -c "from src.profiles.pressure import PressureProfile; print('OK')"`
- Регрессия: `.venv/Scripts/python -m pytest tests/ -v` (57 тестов, все зелёные)

**Зависимости:** Требует: —. Метод `pb_star()` принимает `temp_profile` как аргумент (duck typing), но для реализации и тестирования `__call__`/`dp_dr` он не нужен. Блокирует: шаг 4 (тесты давления).
**Оценка:** ~80 строк, ~20 мин

---

### Шаг 2: `src/profiles/saturation.py` — профиль насыщенности

**Цель:** реализовать $S_g(r)$ и $dS_g/dr$ по формуле §4.3.

**Файлы:** `method_of_moments/src/profiles/saturation.py` (создать)

**Контекст:**
Газонасыщенность определена только в зоне разгазирования $[r_w, r_b]$. Профиль — степенная функция с компактным носителем. Во внешней зоне $S_g \equiv 0$.

**Формулы:**

$$S_g(r) = S_{g,w} \left(1 - \eta^\beta\right), \quad r_w \leqslant r \leqslant r_b \quad \eqref{eq:Sg\_profile}$$
$$\eta = \frac{\ln(r/r_w)}{\ln(r_b/r_w)}$$

$S_g(r_w) = S_{g,w}$ (максимум на забое), $S_g(r_b) = 0$ (граница разгазирования).

Производная:
$$\frac{dS_g}{dr} = -\frac{S_{g,w} \cdot \beta}{r \cdot L_b} \eta^{\beta - 1}$$

**Что сделать:**

1. Создать класс `SaturationProfile`:
   - `__init__(self, r_w, beta=2.0)` — $r_w$ и показатель формы $\beta$
   - `eta(self, r, r_b)` — $\eta$ (та же формула, что в давлении; дублирование ОК — профили независимы)
   - `__call__(self, r, r_b, Sg_w)` — $S_g(r)$; вне $[r_w, r_b]$ возвращает 0
   - `dSg_dr(self, r, r_b, Sg_w)` — $dS_g/dr$; вне $[r_w, r_b]$ возвращает 0

**Проверка после шага:**
- Импорт: `cd method_of_moments && .venv/Scripts/python -c "from src.profiles.saturation import SaturationProfile; print('OK')"`
- Регрессия: `.venv/Scripts/python -m pytest tests/ -v`

**Зависимости:** Требует: —. Блокирует: шаг 5 (тесты насыщенности).
**Оценка:** ~40 строк, ~10 мин

---

### Шаг 3: `src/profiles/temperature.py` — профиль температуры

**Цель:** реализовать $T(r)$, $dT/dr$, $\Psi(\zeta)$, $J^{(m)}$ по формулам §4.4.

**Файлы:** `method_of_moments/src/profiles/temperature.py` (создать)

**Контекст:**
Температурный профиль определён на всей области $[r_w, R_\text{ext}]$, в отличие от насыщенности. Функция формы $\Psi(\zeta)$ удовлетворяет ГУ по построению: $T(R_\text{ext}) = T_0$ и $T'(r_w) = 0$ (адиабатическая стенка). Интеграл $J^{(m)}$ нужен для FEAT-004.

**Формулы:**

Координата:
$$\zeta = \frac{\ln(R_\text{ext}/r)}{L_0}, \quad L_0 = \ln(R_\text{ext}/r_w)$$

Профиль:
$$T(r) = T_0 - \Delta T_w \cdot \Psi(\zeta) \quad \eqref{eq:T\_profile}$$

Функция формы:
$$\Psi(\zeta) = \zeta^\sigma (2 - \zeta^\sigma) \quad \eqref{eq:Psi}$$

Свойства: $\Psi(0) = 0$, $\Psi(1) = 1$, $\Psi'(1) = 0$.

Производная:
$$\frac{\partial T}{\partial r} = \frac{\Delta T_w}{r \cdot L_0} \Psi'(\zeta) = \frac{2\sigma \Delta T_w}{r \cdot L_0} \zeta^{\sigma-1}(1 - \zeta^\sigma) \quad \eqref{eq:dT\_dr}$$

Знак: $\Psi'(\zeta) \geqslant 0$ при $\zeta \in [0,1]$, поэтому $\partial T/\partial r \geqslant 0$ при $\Delta T_w \geqslant 0$ (температура растёт от забоя к контуру — корректно, т.к. забой охлаждается).

Интеграл:
$$J^{(m)} = \int_0^1 \zeta^m (2 - \zeta^\sigma) d\zeta = \frac{2}{m+1} - \frac{1}{m+\sigma+1} \quad \eqref{eq:IPsi}$$

**Что сделать:**

1. Создать класс `TemperatureProfile`:
   - `__init__(self, r_w, R_ext, T_0, sigma=1.0)` — геометрия, $T_0$, показатель формы
   - `self.L_0 = math.log(R_ext / r_w)` — предвычислить (проект использует `math`, не `numpy`, для скалярных вычислений)
   - `zeta(self, r)` — безразмерная координата $\zeta \in [0, 1]$
   - `Psi(self, zeta)` — функция формы $\Psi(\zeta)$
   - `dPsi_dzeta(self, zeta)` — $\Psi'(\zeta) = 2\sigma\zeta^{\sigma-1}(1 - \zeta^\sigma)$
   - `__call__(self, r, dT_w)` — $T(r)$
   - `dT_dr(self, r, dT_w)` — $\partial T/\partial r$
   - `J(self, m)` — аналитический интеграл $J^{(m)}$

2. Метод `zeta_b(self, r_b)` — $\zeta_b = L_e / L_0$ — нужен для `PressureProfile.pb_star`

**Проверка после шага:**
- Импорт: `cd method_of_moments && .venv/Scripts/python -c "from src.profiles.temperature import TemperatureProfile; print('OK')"`
- Регрессия: `.venv/Scripts/python -m pytest tests/ -v`

**Зависимости:** Требует: —. Блокирует: шаг 6 (тесты температуры), шаг 8 (интеграционный — pb_star использует temp_profile).
**Оценка:** ~60 строк, ~15 мин

---

### Шаг 4: Тесты профиля давления

**Цель:** unit-тесты для `PressureProfile`.

**Файлы:** `method_of_moments/tests/test_profiles.py` (создать)

**Параметры тестов (из baseline.json):**
- $r_w = 0.1$ м, $R_\text{ext} = 500$ м
- $p_{wf} = 15 \times 10^6$ Па, $p_0 = 20 \times 10^6$ Па, $p_b = 18 \times 10^6$ Па
- $T_0 = 350$ К

Выбор $r_b$: при $\Delta T_w = 0$ имеем $p_b^* = p_b(T_0)$. Типичное значение $r_b = 10$ м (зона разгазирования — первые десятки метров).

**Тесты:**

```
Тест: test_p_inner_at_rw
Сценарий: p(r_w) = p_wf (ГУ на забое)
Setup: r_w=0.1, R_ext=500, p_wf=15e6, p_0=20e6, r_b=10, pb_star=18e6
Ожидание: p(0.1) == 15e6 (точно)
Формула: \eqref{eq:p_inner} при η=0: p = p_wf + Δp₁·Φ(0) = p_wf
Предотвращает: ошибка в смещении профиля

Тест: test_p_inner_at_rb
Сценарий: p(r_b) = pb_star (непрерывность на фронте)
Setup: то же
Ожидание: p(10) == 18e6 (точно)
Формула: \eqref{eq:p_inner} при η=1: p = p_wf + Δp₁·Φ(1) = p_wf + Δp₁ = pb_star
Предотвращает: ошибка в амплитуде

Тест: test_p_outer_at_rb
Сценарий: p(r_b) из внешнего профиля = pb_star
Setup: то же
Ожидание: p(10) == 18e6
Формула: \eqref{eq:p_outer} при r=r_b: ln(r_b/r_b)=0
Предотвращает: разрыв профиля на границе

Тест: test_p_outer_at_Rext
Сценарий: p(R_ext) = p_0
Setup: то же
Ожидание: p(500) == 20e6
Формула: \eqref{eq:p_outer} при r=R_ext
Предотвращает: ошибка во внешнем профиле

Тест: test_gamma_flux_continuity
Сценарий: dp/dr непрерывен на r=r_b
Setup: то же
Ожидание: dp_dr(r_b⁻) == dp_dr(r_b⁺) с точностью 1e-6 Па/м
Формула: \eqref{eq:gamma_constraint} — γ выбран именно для этого
Предотвращает: ошибка в формуле γ или в dp/dr

Тест: test_dp_dr_inner_vs_fd
Сценарий: аналитическая dp/dr совпадает с конечной разностью
Setup: r=1.0 (внутри зоны), ε=1e-6
Ожидание: |dp_dr_analytic - (p(r+ε)-p(r-ε))/(2ε)| / |dp_dr_analytic| < 1e-4
Предотвращает: ошибка в формуле производной

Тест: test_dp_dr_outer_vs_fd
Сценарий: то же для внешней зоны
Setup: r=100.0

Тест: test_p_monotone_increasing
Сценарий: p(r) монотонно растёт от r_w до R_ext
Setup: 50 точек от r_w до R_ext
Ожидание: p(r_{i+1}) > p(r_i) для всех i
Предотвращает: немонотонный профиль (физический абсурд)

Тест: test_pb_star_isothermal
Сценарий: при ΔTw=0 давление насыщения = pb(T_0)
Setup: dT_w=0, fluid с T_0=350
Ожидание: pb_star == fluid.pb(350.0)
Предотвращает: ошибка в связи p–T

Тест: test_dp_dr_at_rw_gamma_lt_1
Сценарий: dp/dr на забое при γ < 1 — интегрируемая сингулярность
Setup: baseline параметры, r_b=10 → γ≈0.785 < 1, r=r_w
Ожидание: dp_dr(r_w) возвращает math.inf (не ZeroDivisionError)
Формула: dp/dr ~ η^{γ-1}, η=0, γ-1<0 → 0^{neg} → inf
Предотвращает: необработанное исключение при вычислении потока
```

**Проверка после шага:**
- `cd method_of_moments && .venv/Scripts/python -m pytest tests/test_profiles.py -k "Pressure" -v`

**Зависимости:** Требует: шаг 1, шаг 3 (для test_pb_star). Блокирует: —.
**Оценка:** ~100 строк, ~20 мин

---

### Шаг 5: Тесты профиля насыщенности

**Цель:** unit-тесты для `SaturationProfile`.

**Файлы:** `method_of_moments/tests/test_profiles.py` (добавить)

**Тесты:**

```
Тест: test_Sg_at_rw
Сценарий: Sg(r_w) = Sg_w
Setup: r_w=0.1, r_b=10, Sg_w=0.15, beta=2
Ожидание: Sg(0.1) == 0.15
Формула: \eqref{eq:Sg_profile} при η=0: Sg = Sg_w·(1-0) = Sg_w
Предотвращает: ошибка в амплитуде

Тест: test_Sg_at_rb
Сценарий: Sg(r_b) = 0
Setup: то же
Ожидание: Sg(10) == 0 (точно)
Формула: \eqref{eq:Sg_profile} при η=1: Sg = Sg_w·(1-1) = 0
Предотвращает: ненулевая насыщенность на фронте

Тест: test_Sg_outside_zone
Сценарий: Sg(r) = 0 при r > r_b
Setup: r=100
Ожидание: Sg(100) == 0
Предотвращает: некорректное поведение вне зоны разгазирования

Тест: test_Sg_monotone_decreasing
Сценарий: Sg(r) убывает от r_w до r_b
Setup: 20 точек от r_w до r_b
Ожидание: Sg(r_{i+1}) <= Sg(r_i)
Предотвращает: немонотонный профиль

Тест: test_Sg_in_range
Сценарий: 0 ≤ Sg(r) ≤ Sg_w для всех r
Setup: 20 точек
Ожидание: 0 ≤ Sg ≤ 0.15
Предотвращает: отрицательная насыщенность

Тест: test_dSg_dr_vs_fd
Сценарий: аналитическая dSg/dr совпадает с конечной разностью
Setup: r=1.0, ε=1e-6
Ожидание: относительная ошибка < 1e-4
Предотвращает: ошибка в формуле производной

Тест: test_Sg_different_beta
Сценарий: при разных β форма профиля меняется, но ГУ сохраняются
Setup: beta=1, 2, 5
Ожидание: Sg(r_w)=Sg_w, Sg(r_b)=0 для всех β
Предотвращает: зависимость ГУ от параметра формы
```

**Проверка после шага:**
- `cd method_of_moments && .venv/Scripts/python -m pytest tests/test_profiles.py -k "Saturation" -v`

**Зависимости:** Требует: шаг 2, шаг 4 (файл `test_profiles.py` создаётся в шаге 4). Блокирует: —.
**Оценка:** ~70 строк, ~15 мин

---

### Шаг 6: Тесты профиля температуры

**Цель:** unit-тесты для `TemperatureProfile`.

**Файлы:** `method_of_moments/tests/test_profiles.py` (добавить)

**Тесты:**

```
Тест: test_Psi_at_zero
Сценарий: Ψ(0) = 0 (контур питания)
Ожидание: Psi(0) == 0
Формула: \eqref{eq:Psi}
Предотвращает: ошибка ГУ на контуре

Тест: test_Psi_at_one
Сценарий: Ψ(1) = 1 (забой)
Ожидание: Psi(1) == 1
Предотвращает: ошибка ГУ на забое

Тест: test_dPsi_at_one
Сценарий: Ψ'(1) = 0 (адиабатическая стенка)
Ожидание: dPsi_dzeta(1) == 0
Формула: Ψ'(ζ) = 2σζ^{σ-1}(1-ζ^σ), при ζ=1: 2σ·1·0 = 0
Предотвращает: нарушение адиабатического ГУ

Тест: test_T_at_Rext
Сценарий: T(R_ext) = T_0
Setup: R_ext=500, T_0=350, dT_w=5
Ожидание: T(500) == 350 К
Предотвращает: ошибка ГУ на контуре питания

Тест: test_T_at_rw
Сценарий: T(r_w) = T_0 - ΔTw
Setup: r_w=0.1, dT_w=5
Ожидание: T(0.1) == 345 К
Предотвращает: ошибка амплитуды

Тест: test_dT_dr_adiabatic_wall
Сценарий: dT/dr|_{r_w} = 0
Setup: r=r_w=0.1, dT_w=5
Ожидание: dT_dr(0.1, 5) == 0
Формула: \eqref{eq:dT_dr} при ζ=1: (1-ζ^σ) = 0
Предотвращает: нарушение адиабатического ГУ

Тест: test_dT_dr_vs_fd
Сценарий: аналитическая dT/dr совпадает с конечной разностью
Setup: r=10.0, ε=1e-6, dT_w=5
Ожидание: относительная ошибка < 1e-4
Предотвращает: ошибка в формуле производной

Тест: test_T_isothermal
Сценарий: при ΔTw=0 температура постоянна
Setup: dT_w=0
Ожидание: T(r) == T_0 для всех r
Предотвращает: ненулевое возмущение при нулевой амплитуде

Тест: test_J_vs_quad
Сценарий: аналитический J^(m) совпадает с численным интегрированием
Setup: sigma=1, m=0,1,2,3
Ожидание: |J_analytic - quad(ζ^m·(2-ζ^σ), 0, 1)| < 1e-12
Формула: \eqref{eq:IPsi}
Предотвращает: ошибка в замкнутой формуле интеграла

Тест: test_J_vs_quad_sigma2
Сценарий: то же при sigma=2 (baseline.json)
Setup: sigma=2, m=0,1,2
Ожидание: |J_analytic - quad| < 1e-12
Предотвращает: ошибка при нестандартном σ

Тест: test_Psi_different_sigma
Сценарий: при разных σ ГУ сохраняются
Setup: sigma=0.5, 1, 2, 5
Ожидание: Psi(0)=0, Psi(1)=1, dPsi(1)=0
Предотвращает: зависимость ГУ от параметра формы

Тест: test_dT_dr_at_Rext_sigma_lt_1
Сценарий: dT/dr на контуре питания при σ < 1 — сингулярность
Setup: sigma=0.5, r=R_ext, dT_w=5
Ожидание: dT_dr → ∞ (math.isinf) или очень большое значение
Формула: Ψ'(0) = 2σ·0^{σ-1}·1 → ∞ при σ < 1
Предотвращает: молчаливый NaN вместо inf
```

**Проверка после шага:**
- `cd method_of_moments && .venv/Scripts/python -m pytest tests/test_profiles.py -k "Temperature" -v`

**Зависимости:** Требует: шаг 3, шаг 4 (файл `test_profiles.py` создаётся в шаге 4). Блокирует: —.
**Оценка:** ~120 строк, ~20 мин

---

### Шаг 7: `src/profiles/__init__.py` — экспорт

**Цель:** обновить `__init__.py` для удобного импорта.

**Файлы:** `method_of_moments/src/profiles/__init__.py` (обновить)

**Что сделать:**

```python
from .pressure import PressureProfile
from .saturation import SaturationProfile
from .temperature import TemperatureProfile
```

**Проверка после шага:**
- `cd method_of_moments && .venv/Scripts/python -c "from src.profiles import PressureProfile, SaturationProfile, TemperatureProfile; print('OK')"`
- Регрессия: `.venv/Scripts/python -m pytest tests/ -v`

**Зависимости:** Требует: шаги 1–3. Блокирует: —.
**Оценка:** ~3 строки, ~2 мин

---

### Шаг 8: Интеграционный тест — согласованность профилей

**Цель:** проверить совместную работу трёх профилей с `BlackOilFluid`.

**Файлы:** `method_of_moments/tests/test_profiles.py` (добавить)

**Тесты:**

```
Тест: test_pb_star_with_temperature
Сценарий: pb_star вычисляется корректно при ненулевом ΔTw
Setup: dT_w=5 К, r_b=10 м, fluid (baseline PVT)
Ожидание: pb_star < pb(T_0) (охлаждение снижает давление насыщения)
Формула: \eqref{eq:pb_star}, pb(T) убывает с T для Standing
Предотвращает: неверный знак коррекции pb

Тест: test_profiles_consistency_at_rb
Сценарий: все профили согласованы на границе r_b
Setup: baseline параметры, r_b=10
Ожидание:
  - p_inner(r_b) == p_outer(r_b) == pb_star
  - Sg(r_b) == 0
  - T — непрерывна (единый профиль на всей области)
Предотвращает: рассогласование профилей

Тест: test_gamma_positive
Сценарий: γ > 0 при типичных параметрах
Setup: p_wf=15e6, p_0=20e6, pb_star=18e6, r_b=10
Ожидание: gamma > 0
Формула: \eqref{eq:gamma_constraint}, все множители положительны
Предотвращает: отрицательный показатель степени
```

**Проверка после шага:**
- `cd method_of_moments && .venv/Scripts/python -m pytest tests/test_profiles.py -v`
- Полная регрессия: `.venv/Scripts/python -m pytest tests/ -v`

**Зависимости:** Требует: шаги 1–3, шаг 7. Блокирует: —.
**Оценка:** ~50 строк, ~10 мин

---

## Критерии завершения

- [ ] Все 12 формул из §4 moments_method.tex реализованы (таблица «Связь формула → код»)
- [ ] Каждый метод имеет docstring с `\eqref{}`
- [ ] Unit-тесты зелёные (~25 тестов)
- [ ] Интеграционные тесты зелёные (3 теста)
- [ ] Все существующие тесты зелёные (57: 31 PVT + 26 relperm)
- [ ] Предельные случаи: $\Delta T_w = 0$, разные $\beta$, разные $\sigma$
- [ ] `__init__.py` обновлён
- [ ] GitHub issue #3 прокомментирован

## Оценка

- **Файлов:** 4 новых (`pressure.py`, `saturation.py`, `temperature.py`, `test_profiles.py`) + 1 обновлённый (`__init__.py`)
- **Строк кода:** ~180 (профили) + ~340 (тесты) ≈ 520
- **Тестов:** ~28
- **Время:** ~2 часа

## Связи

- **Зависит от:** FEAT-001 ✅ (PVT), FEAT-002 ✅ (ОФП — косвенно)
- **Блокирует:** FEAT-004 (интегралы $I_\Phi$, $I_S$, $J$), FEAT-005 (коэффициенты ODE), FEAT-006 (начальная асимптотика использует профили)
- **Vault:** [[feat-001 standing-pvt]], [[feat-002 corey-relperm]], [[интегральная нормировка нелинейных коэффициентов]]
- **Литература:** moments_method.tex §4
