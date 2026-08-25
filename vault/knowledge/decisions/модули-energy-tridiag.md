---
name: модули-energy-tridiag
description: Тепловой модуль — прогонка Томаса, коэффициенты уравнения энергии, JT, дегазация, ГУ
metadata:
  type: project
---

# EnergySolver — прогонка Томаса

## ABC

```python
class EnergySolver(ABC):

    @abstractmethod
    def solve(self, hydro_result: HydroResult,
              state_prev: SimulationState,
              dt: float, T_ext: float) -> np.ndarray:
        """Один шаг теплопереноса: T^n → T^{n+1}.

        Вход:
        - hydro_result: p^{n+1}, Sg^{n+1}, Rs^{n+1}, G_o, G_g, Q_o, Q_g
        - state_prev: состояние на предыдущем шаге (T^n, p^n, Sg^n, Rs^n)
        - dt: шаг по времени, с
        - T_ext: температура на контуре питания (Дирихле), К

        Выход: T^{n+1} — массив [N]
        """
        ...
```

## Порядок вычислений

1. Вычислить тепловые PVT при (p^{n+1}, T^n)
2. Вычислить эффективные коэффициенты в ячейках
3. Вычислить потоки через грани (конвективные, кондуктивные, JT)
4. Вычислить источники (адиабатический, дегазация)
5. Собрать трёхдиагональную СЛАУ
6. Применить ГУ
7. Решить прогонкой

## Коэффициенты в ячейках (problem_statement.tex eq. 5-7)

```python
# Эффективная теплоёмкость (eq. 5)
rho_cp_eff[j] = (1-phi)*rho_cp_s + phi*(So[j]*rho_o[j]*cp_o[j] + Sg[j]*rho_g[j]*cp_g[j])

# Эффективная теплопроводность (eq. 7)
lambda_eff[j] = (1-phi)*lambda_s + phi*(So[j]*lambda_o + Sg[j]*lambda_g)
```

Все величины при p^{n+1}, T^n. So = 1 - Sg.

## Потоки через грани

### Расход фазы через грань (eq. 24)

```python
Q_alpha[j+1/2] = T_geom[j] * (kr_alpha/mu_alpha)_up * (p[j+1] - p[j])
```

Это расход при пластовых условиях [м³/с], не компонентный поток G.

### Конвективный коэффициент фазы

```python
Phi_alpha[j+1/2] = rho_alpha_up * cp_alpha_up * Q_alpha[j+1/2]
```

Upstream определяется **раздельно по каждой фазе** — фазы могут течь в разные стороны (нефть к скважине, газ от скважины при определённых условиях).

### Upstream-оператор для скаляра (eq. 22)

```python
<G·ψ>_{j+1/2} = G^+_{j+1/2} · ψ_j + G^-_{j+1/2} · ψ_{j+1}
```

G⁺ = max(G, 0), G⁻ = min(G, 0). Для T: ψ = T.

### Конвективный поток энергии через грань (eq. 23)

```python
F[j+1/2] = sum_alpha( <Phi_alpha · T>_{j+1/2} )
         = sum_alpha( Phi_alpha_plus * T_j + Phi_alpha_minus * T_{j+1} )
```

где Phi_alpha_plus/minus — разделение по знаку расхода **каждой фазы**.

### Кондуктивный поток через грань (eq. 25)

```python
Q_lambda[j+1/2] = (2*pi*h / ln(r_{j+1}/r_j)) * lambda_eff_face * (T_{j+1} - T_j)
```

lambda_eff_face — гармоническое среднее с логарифмическими весами (eq. 21):
```python
lambda_eff_face = 1.0 / (w_left/lambda_eff[j] + w_right/lambda_eff[j+1])
```

Обозначим кондуктивную проводимость:
```python
Q_T[j+1/2] = (2*pi*h / ln(r_{j+1}/r_j)) * lambda_eff_face
```

## Источниковые члены

### Эффект Джоуля-Томсона (пространственный, eq. 28-29)

JT-поток через грань:
```python
J[j+1/2] = sum_alpha( mu_JT_alpha_up * <Phi_alpha · p>_{j+1/2} )
```

Вклад JT в ячейку j:
```python
J_cell[j] = J[j+1/2] - J[j-1/2]
```

Это **известная** величина (p^{n+1} определено).

### Адиабатический эффект (временной, eq. 29)

```python
Q_ad[j] = V[j] * phi * sum_alpha(
    S_alpha[j] * (1 + rho_alpha[j]*cp_alpha[j]*mu_JT_alpha[j])
) * (p[j]^{n+1} - p[j]^n) / dt
```

При c_r = 0 (наша модель) член с c_r выпадает. Это **известная** величина.

### Теплота дегазации (eq. 30-31)

Массовый темп дегазации ṁ (eq. 31):
```python
# Временная часть
mdot_time[j] = -rho_g_std * V[j] * phi * (1-Sg[j])/Bo[j] * (Rs[j]^{n+1} - Rs[j]^n) / dt

# Конвективная часть (через потоки G^o и upstream Rs)
R_face[j+1/2] = <G^o · Rs>_{j+1/2}   # upstream-оператор
mdot_conv[j] = -rho_g_std * (R_face[j+1/2] - R_face[j-1/2])

# Полный темп
mdot[j] = (mdot_time[j] + mdot_conv[j]) / V[j]

# Теплота дегазации
Q_deg[j] = -L * mdot[j]
```

В режиме 2 (однофазная зона): Rs = Rs^0 = const, ∂Rs/∂t = 0, ∂Rs/∂r = 0 → ṁ = 0 → Q_deg = 0.

## Трёхдиагональная СЛАУ (eq. 33-36)

```
a_j · T_{j-1}^{n+1} + b_j · T_j^{n+1} + c_j · T_{j+1}^{n+1} = d_j
```

Коэффициенты:
```python
a[j] = -Q_T[j-1/2] - Phi_plus[j-1/2]     # ≤ 0
c[j] = -Q_T[j+1/2] + Phi_minus[j+1/2]     # ≤ 0
b[j] = V[j]*rho_cp_eff[j]/dt + Q_T[j-1/2] + Q_T[j+1/2] + Phi_plus[j+1/2] - Phi_minus[j-1/2]  # > 0
d[j] = V[j]*rho_cp_eff[j]/dt * T_n[j] + J_cell[j] + V[j]*(Q_ad[j] + Q_deg[j])
```

Phi_plus = sum_alpha(max(Phi_alpha, 0))  — суммарный положительный конвективный коэффициент
Phi_minus = sum_alpha(min(Phi_alpha, 0)) — суммарный отрицательный

Диагональное преобладание обеспечено: b > |a| + |c|.

## Граничные условия

### Контур питания (r = R_ext): T = T_пл (Дирихле)

Правая грань ячейки j=N-1:
- Кондуктивный поток: `Q_T_ext * (T_ext - T_{N-1})` → вклад `-Q_T_ext` в c[N-1] (но c[N-1] отсутствует, слагаемое переносится в d)
- Конвективный поток: upstream берёт T = T_ext (приток с контура)

Реализация: c[N-1] = 0 (нет T_{N}). Вместо этого:
```python
b[N-1] += Q_T_ext           # кондуктивная часть
d[N-1] += Q_T_ext * T_ext   # кондуктивная часть

# Конвективная часть: Phi_ext_minus * T_ext → в d[N-1]
d[N-1] += (-Phi_ext_minus) * T_ext   # Phi_minus < 0, -Phi_minus > 0
b[N-1] += Phi_ext_plus                # если поток из ячейки N-1 наружу
```

### Забой (r = r_w): ∂T/∂r = 0 (Нейман)

Левая грань ячейки j=0:
- Кондуктивный поток = 0: `Q_T_well = 0`
- Конвективный поток: upstream берёт T = T_0 (из ячейки j=0, флюид уходит в скважину)

Реализация: a[0] = 0 (нет T_{-1}). Конвективный вклад:
```python
# Phi_well_plus * T_0 → в b[0]
b[0] += Phi_well_plus
# Phi_well_minus = 0 (нет притока из скважины)
```

## Решение СЛАУ

`scipy.linalg.solve_banded` — LAPACK dgbsv. Banded-формат для трёхдиагональной:
```python
ab = np.zeros((3, N))
ab[0, 1:] = c[:-1]    # верхняя диагональ
ab[1, :] = b           # главная диагональ
ab[2, :-1] = a[1:]     # нижняя диагональ
T_new = scipy.linalg.solve_banded((1, 1), ab, d)
```

Сложность O(N), компилированный Fortran — быстрее ручной прогонки на Python.

## Связанные заметки

- [[architecture-numerical-solver]]
- [[модули-pvt-контракт]] — ThermalPVT: c_p, mu_JT, L
- [[модули-grid-сетка]] — проводимости, веса
- [[модули-hydro-newton]] — u_o, u_g, G_o для конвекции и ṁ
