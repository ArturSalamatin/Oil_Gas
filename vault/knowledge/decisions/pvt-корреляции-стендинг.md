---
name: pvt-корреляции-стендинг
description: Набор PVT-корреляций для StandingPVT — Standing, Beggs-Robinson, LGE, производные, ветвление p≷pb, векторизация
metadata:
  type: project
---

# PVT-корреляции для StandingPVT

## Источник

Базовый код: `method_of_moments/src/pvt/correlations.py`. Нужно:
1. Векторизовать (math → numpy)
2. Добавить ветвление p ≷ pb (под/над давлением насыщения)
3. Добавить недостающие производные (dBo/dp, dμ_o/dp, dμ_g/dp)

## Газосодержание Rs_eq(p) — Standing 1947

```
Rs_eq = γ_g · (p_psia/18.2 + 1.4)^{1/0.83} · 10^{-a/0.83}
a = 0.00091·T_F - 0.0125·γ_API
```

Производная (аналитическая):
```
dRs/dp = Rs / (0.83 · Y · 18.2 · Pa_per_psi),   Y = p_psia/18.2 + 1.4
```

Уже реализовано в correlations.py. Нужна векторизация: `math.log(10)` → `np.log(10)`.

## Давление насыщения pb — Standing 1947 (обратная)

```
pb_psia = 18.2 · ((Rs_scf/γ_g)^0.83 · 10^a - 1.4)
```

В numerical_solver pb — скаляр (T = T0 = const, Rs = Rs0). Вычисляется один раз в конструкторе StandingPVT.

## Объёмный коэффициент нефти Bo

### p < pb (двухфазная зона, режим 1)

Standing 1947:
```
F = Rs_scf · (γ_g/γ_o)^0.5 + 1.25·T_F
Bo = 0.9759 + 1.2e-4 · F^1.2
```

Bo = f(Rs, T). При фиксированном Rs: **dBo/dp|_{Rs} = 0**.

dBo/dRs — уже реализовано:
```
dBo/dRs = 1.44e-4 · F^0.2 · dF/dRs
dF/dRs = (γ_g/γ_o)^0.5 · SCF_PER_M3
```

### p ≥ pb (однофазная зона, режим 2)

Vasquez-Beggs (упрощённый) — экспоненциальная сжимаемость:
```
Bo(p) = Bo_at_pb · exp(-co_under · (p - pb))
```

co_under — сжимаемость нефти выше pb. Задаётся в JSON как скаляр (порядок 1e-9..1e-10 1/Па).

Bo_at_pb = Bo(pb, Rs0) — вычисляется Standing при Rs = Rs0.

Производные:
```
dBo/dp|_{Rs} = -co_under · Bo(p)     (при p ≥ pb)
dBo/dRs = 0                           (при p ≥ pb, Rs = Rs0 = const)
```

### Реализация ветвления

```python
def Bo(self, p, Rs):
    mask = p < self._pb
    result = np.empty_like(p)

    # p < pb: Standing
    F = self._F_standing(Rs[mask])
    result[mask] = 0.9759 + 1.2e-4 * F**1.2

    # p >= pb: exp-сжимаемость
    result[~mask] = self._Bo_at_pb * np.exp(-self._co_under * (p[~mask] - self._pb))
    return result
```

## Объёмный коэффициент газа Bg — идеальный газ

```
Bg = P_ст · T / (T_ст · p)     (z-фактор = 1)
dBg/dp = -Bg / p
```

Векторизация тривиальна. Для более точной модели — добавить z-фактор (Standing-Katz, Dranchuk-Abou-Kassem). Пока z=1 достаточно.

## Вязкость нефти μ_o

### p < pb: Beggs-Robinson 1975

```
μ_dead = (10^(A·T_F^{-1.163}) - 1) · 1e-3     [Па·с]
A = 10^(3.0324 - 0.02023·γ_API)

μ_o = a · μ_dead^b     [Па·с]
a = 10.715 / (Rs_scf + 100)^0.515
b = 5.44 / (Rs_scf + 150)^0.338
```

μ_o = f(Rs, T). При фиксированном Rs: **dμ_o/dp|_{Rs} = 0**.

### p ≥ pb: Vasquez-Beggs 1980

```
μ_o(p) = μ_o(pb) · (p/pb)^m
m = 2.6 · p_psia^{1.187} · exp(-11.513 - 8.98e-5 · p_psia)
```

Упрощённый вариант (аналог Bo): линейное приближение
```
μ_o(p) = μ_o(pb) · (1 + cμ · (p - pb))
dμ_o/dp = μ_o(pb) · cμ
```

cμ — коэффициент роста вязкости с давлением выше pb. Порядок: 1e-9..1e-8 1/Па.

Или задать как скаляр в JSON: `"c_mu_o_undersaturated"`.

### Производные по p

- p < pb: dμ_o/dp|_{Rs} = 0
- p ≥ pb: dμ_o/dp = μ_o(pb) · cμ (линейная модель) или аналитически из Vasquez-Beggs

## Вязкость газа μ_g — Lee-Gonzalez-Eakin 1966

```
K = (9.4 + 0.02·M_g) · T_R^1.5 / (209 + 19·M_g + T_R)
X = 3.5 + 986/T_R + 0.01·M_g
Y = 2.4 - 0.2·X
μ_g = 1e-4 · K · exp(X · ρ_g_gcc^Y)     [Па·с]
```

ρ_g = ρ_g_ст / Bg(p). При z=1: ρ_g = ρ_g_ст · T_ст · p / (P_ст · T).

### Производная dμ_g/dp

Цепное правило:
```
dμ_g/dp = μ_g · X · Y · ρ_g_gcc^{Y-1} · dρ_g_gcc/dp
dρ_g/dp = ρ_g / p     (для идеального газа)
dρ_g_gcc/dp = dρ_g/dp / 1000 = ρ_g / (1000·p)
```

Итого:
```
dμ_g/dp = μ_g · X · Y · ρ_g_gcc^{Y-1} · ρ_g_gcc / p
        = μ_g · X · Y · ρ_g_gcc^Y / p
```

## Параметры в JSON — секция pvt

```json
"pvt": {
    "model": "standing",
    "rho_o_std": 850.0,
    "rho_g_std": 1.2,
    "Rs0": 50.0,
    "co_undersaturated": 1.5e-9,
    "c_mu_o_undersaturated": 5e-9
}
```

Минимальный набор для Standing: rho_o_std, rho_g_std, Rs0. gamma_o и gamma_g вычисляются из плотностей. Температура T0 берётся из initial_conditions.

co_undersaturated и c_mu_o_undersaturated — опциональные; если не заданы, используются нулевые (Bo, μ_o постоянны при p > pb).

## Связанные заметки

- [[модули-pvt-контракт]] — ABC HydroPVT, ThermalPVT
- [[architecture-numerical-solver]] — общая архитектура
- [[открытые-вопросы-проектирования]] — Q5
