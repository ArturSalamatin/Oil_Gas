---
tags: [inbox, обнаружено-при-реализации]
date: 2026-07-31
source: FEAT-008
---
# Solver расходится при t_end=86400

Обнаружено при реализации [[feat-008 cli-visualization]].

При запуске `solve_moments` с `baseline.json` (`t_end=86400 с`) Radau получает NaN/Inf в якобиане:
```
ValueError: array must not contain infs or NaNs
```
Ошибка в `lu_factor` при LU-разложении якобиана Radau. Причина: ODE-система порождает NaN в правой части (матрица A или вектор F из `assemble_ode_system`).

При `t_end=0.1` — работает корректно (27 точек, все конечные).

Требует диагностики: на каком шаге по времени и при каких значениях `r_b, Sg_w, dT_w` возникает NaN.
