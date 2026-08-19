---
tags:
  - план
  - физика
date: 2026-07-29
issue: FEAT-001
github: 1
branch: feat/feat-001/standing-pvt
model_level: null
status: реализован
audit:
  date: 2026-07-29
  round: 6
  found: 0
  auto-fixed: 0
  manual-required: 0
---

# План: FEAT-001 — PVT-корреляции Black Oil (Standing)

## Как начать работу по этому плану

1. Прочитай этот файл целиком
2. Прочитай `method_of_moments/moments_method.tex` §2 (строки 50–270) — уравнения давления, насыщенности, энергии и какие PVT-функции в них входят
3. Прочитай `method_of_moments/two_phase_energy.tex` §2 (строки 74–200) — обозначения PVT, и §4.1 (строки 306–430) — раскрытие балансов масс (co_sat, beta_o_sat)
4. Создай ветку: `git checkout -b feat/feat-001/standing-pvt`
5. Создай venv и установи пакет: `cd method_of_moments && python -m venv .venv && .venv/Scripts/pip install -e ".[dev]"`
6. Прогони тесты (baseline — 0 тестов): `.venv/Scripts/python -m pytest tests/ -v`
7. Начни с шага 1. После каждого шага — pytest

## Подтип

**Физика** — PVT-корреляции, фундамент решателя.

## Обратная совместимость

Код создаётся с нуля (модули пустые), обратная совместимость не актуальна.

## Формулы → код

| Формула | Уравнение в tex | Python-функция | Модуль | Тест |
|---|---|---|---|---|
| Rs(p,T) | moments_method §2 | `Rs()` | `correlations.py` | `test_Rs_*` |
| pb(T) | обратная Rs | `pb()` | `correlations.py` | `test_pb_*` |
| Bo(p,T,Rs) | moments_method §2 | `Bo()` | `correlations.py` | `test_Bo_*` |
| Bg(p,T) | moments_method §2 | `Bg()` | `correlations.py` | `test_Bg_*` |
| μo(p,T,Rs) | \eqref{eq:mobility} | `mu_o()` | `correlations.py` | `test_mu_o_*` |
| μg(p,T) | \eqref{eq:mobility} | `mu_g()` | `correlations.py` | `test_mu_g_*` |
| ρo(p,T) | через Bo, Rs | `rho_o()` | `black_oil.py` | `test_rho_o` |
| ρg(p,T) | через Bg | `rho_g()` | `black_oil.py` | `test_rho_g` |
| co | \eqref{eq:co_cg} | `co()` | `black_oil.py` | `test_co` |
| cg | \eqref{eq:co_cg} | `cg()` | `black_oil.py` | `test_cg` |
| βo | \eqref{eq:beta_o_g} | `beta_o()` | `black_oil.py` | `test_beta_o` |
| βg | \eqref{eq:beta_o_g} | `beta_g()` | `black_oil.py` | `test_beta_g` |
| dRs/dp | аналитическая | `dRs_dp()` | `correlations.py` | `test_dRs_dp` |
| dRs/dT | аналитическая | `dRs_dT()` | `correlations.py` | `test_dRs_dT` |
| co_sat | \eqref{eq:co_sat} | `co_sat()` | `black_oil.py` | `test_co_sat` |
| βo_sat | \eqref{eq:beta_o_sat} | `beta_o_sat()` | `black_oil.py` | `test_beta_o_sat` |
| αo, αg | \eqref{eq:thermal_expansion} | `alpha_o()`, `alpha_g()` | `black_oil.py` | `test_alpha` |
| cp_o, cp_g | const (начальное приближение) | `cp_o()`, `cp_g()` | `black_oil.py` | `test_cp` |
| L(p,T) | \eqref{eq:L_def} | `L_degas()` | `black_oil.py` | `test_L_degas` |
| ξo | \eqref{eq:xi_o} | `xi_o()` | `black_oil.py` | `test_xi_o` |

## Подводные камни

1. ✅ **Размерности:** все формулы Стендинга в исходных публикациях используют полевые единицы (psi, °F, scf/bbl). Код работает в СИ (Па, К, м³/м³). Пересчёт внутри функций.
2. ⚠️ **dBo/dT при фикс. Rs vs полная производная:** уравнение энергии использует ∂Bo/∂T|_{Rs} (βo), балансы масс — полную производную вдоль кривой насыщения (βo_sat). API должен предоставлять оба. Адресовано: отдельные методы `beta_o()` и `beta_o_sat()`.
3. ⚠️ **dBo/dRs:** нужна для co_sat и βo_sat (\eqref{eq:co_sat}, \eqref{eq:beta_o_sat}). Стендинг даёт Bo как функцию Rs — производная аналитическая.
4. ⚠️ **p > pb:** при p ≥ pb(T) нефть недонасыщена, Rs = Rs(pb,T) = const, Sg = 0. Функции должны корректно обрабатывать оба режима.
5. ⚠️ **z-фактор газа:** для Bg нужен z(p,T). Начальное приближение — идеальный газ (z=1) или корреляция Hall–Yarborough. Решение: начать с z=1, оставить точку расширения.
6. ✅ **Circular imports:** correlations.py — чистые функции без импорта из проекта; black_oil.py импортирует только correlations.
7. ⚠️ **Теплота дегазации L:** строго определена как L = hg − h̄go (\eqref{eq:L_def}), но для корреляций Стендинга нет стандартной формулы для L. Решение: параметрическая оценка L ≈ const (типично 200–400 кДж/кг) или через приближение Клаузиуса. Оставить как параметр в конфиге с default.
8. ⚠️ **Знак dRs/dT:** для типичных нефтей dRs/dT < 0 (при росте T растворимость газа падает). Формула даёт отрицательный множитель через −ln10·0.00091/0.83·(9/5). Тест должен проверить знак.
9. ⚠️ **Член −1.4 в Standing:** стандартная формула pb = 18.2·[(Rs/γg)^0.83 · 10^a − 1.4]. Без −1.4 обратная задача Rs(p) даёт ошибку до 20% при малых Rs. В плане исправлено (аудит).
10. ⚠️ **Инициализация BlackOilFluid:** класс должен получать p_b и T_0 (из initial_conditions), т.к. Rs_total = Rs(p_b, T_0). В секции pvt конфига pb отсутствует. В плане исправлено (аудит).
11. ⚠️ **Пересчёт Rs в scf/STB:** 1 м³/м³ = 5.6146 scf/STB. Этот коэффициент входит в Bo (через F) и в dBo/dRs. Ошибка пересчёта — мультипликативная ошибка во всех производных Bo.
12. ℹ️ **Разрыв dRs/dp при p = pb:** dRs/dp имеет скачок в точке насыщения (>0 при p<pb, =0 при p≥pb). Аналогично co_sat, beta_o_sat. Это не проблема PVT-модуля (реализация корректна), но downstream ODE-решатель (FEAT-007) должен обрабатывать эту негладкость — event detection или регуляризация.

---

## Шаг 1: Корреляции газосодержания Rs(p,T) и давления насыщения pb(T)

**Цель:** реализовать Rs(p,T) по Стендингу и обратную задачу pb(T).

**Файлы:** `method_of_moments/src/pvt/correlations.py` (создать)

**Контекст:**
Газосодержание Rs(p,T) — объём растворённого газа (при ст. условиях) на единицу объёма нефти (при ст. условиях). При p ≥ pb нефть насыщена: Rs = Rs_max = const. При p < pb газ выделяется и Rs(p,T) < Rs_max.

**Формулы (Standing, 1947; Craft & Hawkins):**

Корреляция Стендинга для давления насыщения:
$$
p_b = 18.2 \left[\left(\frac{R_s}{\gamma_g}\right)^{0.83} \times 10^{a(T)} - 1.4\right], \quad a(T) = 0.00091\,T_F - 0.0125\,\gamma_{\text{API}}
$$
где T_F — температура в °F, γ_API = (141.5/γ_o) − 131.5, γ_o = ρ_o_st / ρ_w_st (ρ_w_st = 999.0 кг/м³), γ_g = ρ_g_st / ρ_air_st (ρ_air_st = 1.225 кг/м³). Давление pb в psia → перевод в Па: pb [Па] = pb [psia] × 6894.757.

Обратная задача — Rs(p,T): из формулы Стендинга выразить Rs:
$$
R_s(p,T) = \gamma_g \left[\frac{p\,[\text{psia}]}{18.2} + 1.4\right]^{1/0.83} \times 10^{-a(T)/0.83}
$$
При p ≥ pb(T): Rs = Rs_total = const.

**Внимание:** член +1.4 в обратной задаче (−1.4 в прямой) критически важен для корректного roundtrip Rs↔pb и для производных. Без него ошибка при малых Rs достигает десятков процентов.

Аналитические производные (при p < pb):

Обозначим Y = p_psia/18.2 + 1.4, тогда Rs = γg · Y^(1/0.83) · 10^(−a/0.83).
$$
\frac{\partial R_s}{\partial p} = \frac{R_s}{0.83 \cdot Y} \cdot \frac{1}{18.2} \cdot \frac{1}{6894.757} = \frac{R_s}{0.83 \cdot (p_{\text{psia}}/18.2 + 1.4)} \cdot \frac{1}{18.2 \cdot 6894.757}
$$
Упрощение: если ввести Y = p_psia/18.2 + 1.4:
$$
\frac{\partial R_s}{\partial p} = \frac{1}{0.83} \cdot \frac{R_s}{Y} \cdot \frac{1}{18.2 \cdot 6894.757}
$$

$$
\frac{\partial R_s}{\partial T} = -\frac{R_s}{0.83} \cdot \ln 10 \cdot \frac{\partial a}{\partial T_F} \cdot \frac{dT_F}{dT_K} = -\frac{R_s}{0.83} \cdot \ln 10 \cdot 0.00091 \cdot \frac{9}{5}
$$
Знак минус: при увеличении T → a растёт → Rs снижается (газ менее растворим при высокой T).

При p ≥ pb: обе производные = 0.

**Что сделать:**

1. Создать файл `method_of_moments/src/pvt/correlations.py`
2. Вспомогательные функции пересчёта единиц:
   - `_pa_to_psia(p)`, `_psia_to_pa(p)`
   - `_K_to_F(T)`, `_K_to_R(T)`
   - `_api_gravity(rho_o_st)` — γ_API из плотности нефти при ст.условиях [кг/м³]
   - `_gas_specific_gravity(rho_g_st)` — γ_g из плотности газа при ст.условиях [кг/м³]
3. `Rs(p, T, rho_o_st, rho_g_st) -> float` — газосодержание [м³ст/м³ст]
4. `dRs_dp(p, T, rho_o_st, rho_g_st) -> float` — ∂Rs/∂p [м³ст/(м³ст·Па)]
5. `dRs_dT(p, T, rho_o_st, rho_g_st) -> float` — ∂Rs/∂T [м³ст/(м³ст·К)]
6. `pb(Rs_total, T, rho_o_st, rho_g_st) -> float` — давление насыщения [Па]

**Проверка после шага:**
```
cd method_of_moments && .venv/Scripts/python -m pytest tests/test_pvt.py -k "Rs or pb" -v
```

**Примечание:** тесты (test_pvt.py) создаются в шаге 5. После шагов 1–3 код можно проверить только вручную (import, вызов функции в REPL). Полный pytest — только после шага 5.

**Зависимости:** нет. Блокирует: шаги 2, 3, 4, 5.
**Оценка:** ~80 строк, ~30 мин

---

## Шаг 2: Объёмные коэффициенты Bo(p,T,Rs) и Bg(p,T)

**Цель:** реализовать Bo и Bg по Стендингу.

**Файлы:** `method_of_moments/src/pvt/correlations.py` (дополнить)

**Контекст:**
Bo — отношение объёма нефтяной фазы при пластовых условиях к объёму нефтяного компонента при стандартных. Bo > 1, т.к. нефть содержит растворённый газ и расширена. Bg — аналогично для газа.

**Формулы:**

Стендинг для Bo (Standing, 1947; Craft & Hawkins):
$$
B_o = 0.9759 + 1.2 \times 10^{-4} \, F^{1.2}, \quad F = R_{s,\text{scf/STB}} \left(\frac{\gamma_g}{\gamma_o}\right)^{0.5} + 1.25\,T_F
$$
Здесь Rs в scf/STB (1 м³/м³ = 5.6146 scf/STB). Результат Bo безразмерный (м³пл/м³ст).

Bg (z-фактор = 1 как начальное приближение):
$$
B_g = \frac{p_{\text{ст}}\,T}{T_{\text{ст}}\,p} = \frac{101325 \cdot T}{288.71 \cdot p}
$$
Единицы: м³пл/м³ст. При z ≠ 1: домножить на z(p,T).

Производные Bo при фикс. Rs (для уравнения энергии):

Обозначим dBo/dF = 1.2 × 10^{-4} · 1.2 · F^{0.2} = 1.44 × 10^{-4} · F^{0.2}.

$$
\frac{\partial B_o}{\partial p}\bigg|_{T,R_s} = 0 \quad \text{(корреляция Стендинга: Bo зависит от p только через Rs)}
$$
Сжимаемость co = 0 в этом приближении. На практике нефть сжимается и при фиксированном составе (co ∼ 1e-9 Па⁻¹), но для консистентности со Стендингом — co = 0. Для FEAT-005 это может потребовать коррекции (отдельная задача).

Полная сжимаемость co_sat ≠ 0 — определяется через dBo/dRs · dRs/dp (шаг 4).

$$
\frac{\partial B_o}{\partial T}\bigg|_{p,R_s} = \frac{dB_o}{dF} \cdot \frac{\partial F}{\partial T}\bigg|_{R_s} = 1.44 \times 10^{-4} \cdot F^{0.2} \cdot 1.25 \cdot \frac{9}{5}
$$

Производная dBo/dRs (нужна для co_sat, βo_sat):
$$
\frac{\partial B_o}{\partial R_s}\bigg|_{p,T} = \frac{dB_o}{dF} \cdot \frac{\partial F}{\partial R_s} = 1.44 \times 10^{-4} \cdot F^{0.2} \cdot \left(\frac{\gamma_g}{\gamma_o}\right)^{0.5} \cdot 5.6146
$$
(множитель 5.6146 — пересчёт Rs из м³/м³ в scf/STB).

Производные Bg:
$$
\frac{\partial B_g}{\partial p} = -\frac{p_{\text{ст}}\,T}{T_{\text{ст}}\,p^2} = -\frac{B_g}{p}, \qquad
\frac{\partial B_g}{\partial T} = \frac{p_{\text{ст}}}{T_{\text{ст}}\,p} = \frac{B_g}{T}
$$

**Что сделать:**

1. `Bo(p, T, Rs, rho_o_st, rho_g_st) -> float` — объёмный к-т нефти (безразм.)
2. `dBo_dRs(p, T, Rs, rho_o_st, rho_g_st) -> float` — ∂Bo/∂Rs|_{p,T}
3. `dBo_dT_fixed_Rs(p, T, Rs, rho_o_st, rho_g_st) -> float` — ∂Bo/∂T|_{p,Rs} (= 1.44e-4·F^0.2·2.25; связь: βo = dBo_dT/Bo)
4. `Bg(p, T) -> float` — объёмный к-т газа
5. `dBg_dp(p, T) -> float` — ∂Bg/∂p
6. `dBg_dT(p, T) -> float` — ∂Bg/∂T

**Проверка после шага:**
```
cd method_of_moments && .venv/Scripts/python -m pytest tests/test_pvt.py -k "Bo or Bg" -v
```

**Зависимости:** Требует: шаг 1 (Rs для вычисления F). Блокирует: шаги 3, 4, 5.
**Оценка:** ~70 строк, ~30 мин

---

## Шаг 3: Вязкости μo(p,T,Rs) и μg(p,T)

**Цель:** реализовать вязкость нефти (Beggs–Robinson) и газа (Lee–Gonzalez–Eakin).

**Файлы:** `method_of_moments/src/pvt/correlations.py` (дополнить)

**Контекст:**
Вязкости входят в подвижности λα = k·krα/μα (\eqref{eq:mobility}), суммарную подвижность Λ (\eqref{eq:Lambda}), конвективный перенос тепла (\eqref{eq:rhocp_conv}).

**Формулы:**

**Вязкость мёртвой нефти (Beggs–Robinson, 1975; McCain 1990):**
$$
A = 10^{3.0324 - 0.02023\,\gamma_{\text{API}}}, \quad \mu_{od} = 10^{A \cdot T_F^{-1.163}} - 1 \quad [\text{cP}]
$$
**Внимание:** показатель степени = A·T_F^{−1.163}, где A = 10^Y — это число, НЕ показатель. Нельзя записывать как 10^{10^{Y/T_F^{1.163}}} — это другое выражение (степень степени ≠ произведение).

**Вязкость живой нефти (Beggs et al., 1975):**
$$
\mu_o = A \cdot \mu_{od}^B, \quad A = \frac{10.715}{(R_{s,\text{scf/bbl}} + 100)^{0.515}}, \quad B = \frac{5.44}{(R_{s,\text{scf/bbl}} + 150)^{0.338}}
$$
Результат в cP → перевод в Па·с: μo_Pa_s = μo_cP × 1e-3.

**Вязкость газа (Lee–Gonzalez–Eakin, 1966):**
$$
\mu_g = 10^{-4}\,K\,\exp(X\,\rho_g^Y), \quad K = \frac{(9.4 + 0.02\,M_g)\,T_R^{1.5}}{209 + 19\,M_g + T_R}
$$
$$
X = 3.5 + \frac{986}{T_R} + 0.01\,M_g, \quad Y = 2.4 - 0.2\,X
$$
где T_R — температура в Ранкинах, M_g — молярная масса газа [г/моль] (≈ 28.97·γ_g), ρ_g в г/см³.
Результат в cP → Па·с.

**Что сделать:**

1. `mu_dead_oil(T, rho_o_st) -> float` — μ_od [Па·с]
2. `mu_o(T, Rs, rho_o_st) -> float` — μ_o живой нефти [Па·с]
3. `mu_g(p, T, rho_g_st) -> float` — μ_g [Па·с]; ρ_g вычислять внутри через Bg

**Проверка после шага:**
```
cd method_of_moments && .venv/Scripts/python -m pytest tests/test_pvt.py -k "mu" -v
```

**Зависимости:** Требует: шаг 1 (Rs), шаг 2 (Bg для ρ_g). Блокирует: шаг 5.
**Оценка:** ~50 строк, ~20 мин

---

## Шаг 4: Класс BlackOilFluid — ядро

**Цель:** создать класс-обёртку, инициализируемый из JSON-конфига, предоставляющий все PVT-свойства и их производные.

**Файлы:** `method_of_moments/src/pvt/black_oil.py` (создать)

**Контекст:**
Все downstream-модули (профили, интегралы, коэффициенты ODE) вызывают PVT через единый интерфейс BlackOilFluid. Класс хранит параметры флюида (rho_o_st, rho_g_st) и делегирует вычисления в correlations.py.

**Что сделать:**

1. Класс `BlackOilFluid`:
   - `__init__(self, pvt_config: dict, p_b: float, T_0: float)` — требует:
     - `pvt_config` — секция `pvt` из baseline.json: `rho_o_st`, `rho_g_st`
     - `p_b` — давление насыщения [Па] (из `initial_conditions.p_b`)
     - `T_0` — начальная температура [К] (из `initial_conditions.T_0`)
     - Вычисляет при инициализации: `Rs_total = Rs(p_b, T_0, rho_o_st, rho_g_st)`
     - Опциональные из pvt_config (с default): `cp_o` (2000), `cp_g` (1000) [Дж/(кг·К)], `L_degas` (300e3) [Дж/кг]
   - Базовые PVT (делегация в correlations):
     - `Rs(p, T)`, `Bo(p, T)`, `Bg(p, T)`, `mu_o(p, T)`, `mu_g(p, T)`, `pb(T)`
   - Производные Rs:
     - `dRs_dp(p, T)`, `dRs_dT(p, T)`
   - Плотности:
     - `rho_o(p, T)` = (rho_o_st + Rs·rho_g_st) / Bo
     - `rho_g(p, T)` = rho_g_st / Bg
   - Сжимаемости при фикс. составе (\eqref{eq:co_cg}):
     - `co(p, T)` = −(1/Bo)·∂Bo/∂p|_{T,Rs}  (= 0 для Стендинга)
     - `cg(p, T)` = −(1/Bg)·∂Bg/∂p|_T = 1/p
   - Температурные коэфф. расширения (\eqref{eq:beta_o_g}):
     - `beta_o(p, T)` = (1/Bo)·∂Bo/∂T|_{p,Rs}
     - `beta_g(p, T)` = (1/Bg)·∂Bg/∂T|_p = 1/T
   - Полные коэфф. вдоль кривой насыщения (\eqref{eq:co_sat}, \eqref{eq:beta_o_sat}):
     - `co_sat(p, T)` = co − (1/Bo)·∂Bo/∂Rs · ∂Rs/∂p
     - `beta_o_sat(p, T)` = beta_o + (1/Bo)·∂Bo/∂Rs · ∂Rs/∂T
   - Коэфф. теплового расширения (\eqref{eq:thermal_expansion}):
     - `alpha_o(p, T)` = −(1/ρo)·∂ρo/∂T|_{p,Rs}
     - `alpha_g(p, T)` = −(1/ρg)·∂ρg/∂T|_p = 1/T (идеальный газ)
   - Вспомогательные:
     - `xi_o(p, T, Sg)` = (1 − Sg) / Bo (\eqref{eq:xi_o})
     - `cp_o(p, T)` → const
     - `cp_g(p, T)` → const
     - `L(p, T)` → const (теплота дегазации)

**Формулы для alpha_o:**
$$
\rho_o = \frac{\rho_o^{\text{ст}} + R_s \cdot \rho_g^{\text{ст}}}{B_o}
$$
$$
\alpha_o = -\frac{1}{\rho_o}\frac{\partial \rho_o}{\partial T}\bigg|_{p,R_s} = \frac{1}{B_o}\frac{\partial B_o}{\partial T}\bigg|_{p,R_s} = \beta_o
$$
(при фикс. Rs числитель ρo не зависит от T, поэтому ∂ρo/∂T = −ρo/Bo · ∂Bo/∂T = −ρo·βo).
Следовательно, α_o = β_o.

**Проверка после шага:**
```
cd method_of_moments && .venv/Scripts/python -m pytest tests/test_pvt.py -k "BlackOil" -v
```

**Зависимости:** Требует: шаги 1–3. Блокирует: шаг 5, шаг 6.
**Оценка:** ~150 строк, ~45 мин

---

## Шаг 5: Тесты — unit

**Цель:** полный набор unit-тестов для correlations.py и black_oil.py.

**Файлы:** `method_of_moments/tests/test_pvt.py` (создать)

**Контекст:**
Тесты должны покрывать все функции, граничные случаи и производные. Параметры из baseline.json: p0=20 МПа, pb=18 МПа, T0=350 К, ρ_o_st=850 кг/м³, ρ_g_st=0.85 кг/м³.

**Тесты:**

```
test_Rs_at_pb:
  Сценарий: Rs(pb, T0) = Rs_total, roundtrip: pb(Rs_total, T0) ≈ pb
  Setup: p_b=18e6, T=350, rho_o_st=850, rho_g_st=0.85
  Ожидание: pb(Rs(p_b, T0), T0) ≈ p_b, tolerance < 100 Па
  Формула: обратимость Rs ↔ pb (Standing ±1.4)
  Предотвращает: ошибки пересчёта единиц, пропущенный член −1.4

test_Rs_above_pb:
  Сценарий: при p > pb газосодержание не растёт
  Setup: p=25e6
  Ожидание: Rs(p, T0) == Rs(pb, T0)

test_Rs_positive:
  Сценарий: Rs > 0 при p > 0
  Ожидание: Rs(1e6, 350) > 0

test_dRs_dp_vs_finite_diff:
  Сценарий: аналитическая производная vs конечные разности
  Setup: p=15e6, T=350, dp=100 Па
  Ожидание: |dRs_dp_analytic − (Rs(p+dp)−Rs(p−dp))/(2dp)| / |dRs_dp_analytic| < 1e-6
  Предотвращает: ошибки в аналитических производных

test_dRs_dT_vs_finite_diff:
  Аналогично, dT=0.01 К

test_dRs_dT_negative:
  Сценарий: dRs/dT < 0 (растворимость падает с ростом T)
  Setup: p=15e6, T=350
  Ожидание: dRs_dT(p, T) < 0
  Предотвращает: ошибку знака в формуле (пропущенный минус)

test_dRs_dp_zero_above_pb:
  Setup: p=25e6 (> pb)
  Ожидание: dRs_dp == 0

test_pb_roundtrip:
  Сценарий: pb(Rs(p, T), T) ≈ p при p < pb
  Setup: p=15e6, T=350
  Ожидание: |pb(Rs(p,T), T) − p| < 1 Па

test_Bo_greater_than_one:
  Setup: p=15e6, T=350
  Ожидание: Bo > 1.0

test_Bo_increases_with_Rs:
  Сценарий: Bo растёт с Rs (набухание от растворённого газа)
  Setup: Bo(p, T, Rs1) < Bo(p, T, Rs2) при Rs1 < Rs2

test_dBo_dRs_vs_finite_diff:
  Аналогично dRs_dp, dRs=0.01

test_Bg_positive:
  Setup: p=15e6, T=350
  Ожидание: Bg > 0

test_Bg_decreases_with_p:
  Ожидание: Bg(p1) > Bg(p2) при p1 < p2

test_dBg_dp_vs_finite_diff:
  Аналогично

test_mu_o_positive:
  Setup: p=15e6, T=350
  Ожидание: mu_o > 0, порядок 1e-4...1e-1 Па·с (для лёгкой нефти γ_API≈35 с высоким Rs ~2700 scf/STB вязкость живой нефти может быть ~2.5e-4 Па·с)

test_mu_g_positive:
  Setup: p=15e6, T=350
  Ожидание: mu_g > 0, порядок 1e-5...1e-4 Па·с

test_mu_o_less_than_dead:
  Ожидание: mu_o(T, Rs) < mu_dead_oil(T) при Rs > 0

test_rho_o_formula:
  Setup: p=15e6, T=350
  Ожидание: rho_o == (rho_o_st + Rs·rho_g_st) / Bo (точное равенство)

test_rho_g_formula:
  Ожидание: rho_g == rho_g_st / Bg

test_co_sat_negative:
  Сценарий: co_sat < co (при p < pb, \eqref{eq:co_sat})
  Ожидание: co_sat < co  (co = 0 для Стендинга → co_sat < 0)

test_xi_o_range:
  Сценарий: ξo ∈ (0, 1/Bo)
  Setup: Sg=0.1
  Ожидание: 0 < xi_o < 1/Bo

test_alpha_o_equals_beta_o:
  Сценарий: для Стендинга αo = βo (см. вывод в шаге 4)
  Ожидание: alpha_o(p,T) == beta_o(p,T)

test_cg_equals_1_over_p:
  Сценарий: для идеального газа cg = 1/p
  Ожидание: cg(p,T) ≈ 1/p, tolerance < 1e-12

test_baseline_config_loads:
  Сценарий: BlackOilFluid(config["pvt"], p_b, T_0) создаётся без ошибок
  Setup: загрузить baseline.json, p_b=config["initial_conditions"]["p_b"], T_0=config["initial_conditions"]["T_0"]
  Ожидание: объект создан, все методы вызываются, Rs_total > 0

test_dBo_dT_vs_finite_diff:
  Сценарий: аналитическая dBo/dT|_{Rs} vs конечные разности
  Setup: p=15e6, T=350, dT=0.01 К, Rs=Rs(p,T)
  Ожидание: |(analytic − FD) / analytic| < 1e-5
  Предотвращает: ошибки в коэффициенте 9/5 (K→F) и показателе 0.2

test_beta_o_vs_finite_diff:
  Сценарий: beta_o = (1/Bo)·dBo/dT|_{Rs} vs конечные разности (1/Bo)·(Bo(T+dT)−Bo(T−dT))/(2dT) при фикс. Rs
  Предотвращает: путаница полной vs частной производной

test_dBg_dT_vs_finite_diff:
  Сценарий: dBg/dT = Bg/T vs конечные разности
  Setup: p=15e6, T=350, dT=0.01
  Ожидание: |(Bg/T − FD)/(Bg/T)| < 1e-6
  Предотвращает: ошибки в аналитике dBg/dT

test_co_zero_standing:
  Сценарий: co = 0 для корреляции Стендинга (Bo не зависит от p при фикс. Rs)
  Setup: p=15e6, T=350
  Ожидание: co(p, T) == 0.0
  Предотвращает: случайное добавление ненулевой сжимаемости

test_beta_o_sat_sign:
  Сценарий: beta_o_sat < beta_o (второй член отрицательный: dBo/dRs > 0, dRs/dT < 0)
  Setup: p=15e6, T=350
  Ожидание: beta_o_sat(p, T) < beta_o(p, T)
  Предотвращает: ошибку знака в формуле beta_o_sat

test_mu_od_beggs_robinson:
  Сценарий: проверка значения mu_od при известных условиях
  Setup: T=350 К (170°F), γ_API=35 (ρ_o_st=850)
  Ожидание: μ_od порядка 1–10 cP (1e-3...1e-2 Па·с)
  Предотвращает: ошибку в группировке показателей степени (10^Y·T^{-1.163} vs 10^{Y·T^{-1.163}})
```

**Проверка после шага:**
```
cd method_of_moments && .venv/Scripts/python -m pytest tests/test_pvt.py -v
```

**Зависимости:** Требует: шаги 1–4. Блокирует: шаг 6.
**Оценка:** ~250 строк (31 тест), ~50 мин

---

## Шаг 6: Экспорт и интеграция

**Цель:** настроить `__init__.py`, убедиться что BlackOilFluid доступен из `src.pvt`.

**Файлы:** `method_of_moments/src/pvt/__init__.py`

**Что сделать:**

1. В `__init__.py`:
```python
from .black_oil import BlackOilFluid
from . import correlations
```

2. Smoke-тест в test_pvt.py:
```python
def test_import():
    from src.pvt import BlackOilFluid, correlations
    assert callable(getattr(correlations, 'Rs', None))
    assert callable(BlackOilFluid)
```

**Проверка после шага:**
```
cd method_of_moments && .venv/Scripts/python -m pytest tests/test_pvt.py -v
```

**Зависимости:** Требует: шаги 4–5.
**Оценка:** ~5 строк, ~5 мин

---

## Критерии завершения

- [x] Все формулы из таблицы «Формулы → код» реализованы
- [x] Каждая функция имеет docstring с ссылкой на уравнение
- [x] Unit-тесты зелёные (шаг 5)
- [x] Все производные проверены vs конечные разности
- [x] Граничные случаи: p=pb, p>pb, Sg=0
- [x] BlackOilFluid загружается из baseline.json
- [x] Экспорт через __init__.py
- [x] Vault обновлён
- [x] GitHub issue прокомментирован

## Связанные vault-заметки

- [[roadmap реализации]] — граф зависимостей, фаза 1
- [[планируемые фичи]] — запись FEAT-001
