---
name: модули-hydro-newton
description: Гидродинамический модуль — блочный Ньютон 3×3, невязки, якобиан, прогонка, переключение режимов, upstream
metadata:
  type: project
---

# HydroSolver — блочный Ньютон

## ABC

```python
class HydroSolver(ABC):

    @abstractmethod
    def solve(self, state: SimulationState, dt: float,
              bc: BoundaryConditions) -> HydroResult:
        """Один шаг гидродинамики: state^n → state^{n+1}.

        dt определяется Simulator (из TimeSchedule). HydroSolver
        не адаптирует dt — это фиксированный шаг.

        bc содержит: well (WellControl → p_wf), p_ext, Rs_ext, Sg_ext.

        Возвращает HydroResult (определён в state.py).
        """
        ...
```

HydroResult определён в `state.py` (не в `hydro/base.py`) — это контейнер данных, а не часть ABC гидро-модуля. Избегает циклических зависимостей: SimulationHistory импортирует HydroResult, а hydro/base.py импортирует SimulationState.

```python
@dataclass
class HydroResult:
    state: SimulationState
    # Потоки компонентов (при ст. условиях) через грани
    G_o: np.ndarray        # [N+1] — нефтяной компонент, м³ст/с, >0 = от скважины
    G_g: np.ndarray        # [N+1] — ПОЛНЫЙ газовый компонент (растворённый+свободный), м³ст/с
    G_free_gas: np.ndarray # [N+1] — СВОБОДНЫЙ газовый компонент, м³ст/с
    # Объёмные расходы фаз (при пл. условиях) через грани
    Q_o: np.ndarray        # [N+1] — нефтяная фаза, м³пл/с, >0 = от скважины
    Q_g: np.ndarray        # [N+1] — газовая фаза, м³пл/с
    # Скорости фильтрации на гранях
    u_o: np.ndarray        # [N+1] — м/с, >0 = от скважины
    u_g: np.ndarray        # [N+1] — м/с
    # Фазовые массовые расходы через грани
    m_o: np.ndarray        # [N+1] — кг/с, = ρ_o_up · Q_o
    m_g: np.ndarray        # [N+1] — кг/с, = ρ_g_up · Q_g
    # Покомпонентные массовые расходы через грани
    Gm_o: np.ndarray       # [N+1] — кг/с, = ρ_o_ст · G_o
    Gm_g: np.ndarray       # [N+1] — кг/с, = ρ_g_ст · G_g
```

Связи: `Q_o = G_o · Bo_up`, `Q_g = G_free_gas · Bg_up`, `G_g = Rs_up · G_o + G_free_gas`.

Все величины с единой конвенцией: **>0 = от скважины (рост r)**.
При типичном потоке к скважине все величины **< 0**.

Связи:
```
u_α[f] = Q_α[f] / (2π·h·r_faces[f])
m_α[f] = ρ_α_up · Q_α[f]
G_o[f] = Q_o[f] / Bo_up
G_g[f] = Rs_up · Q_o[f] / Bo_up + Q_g[f] / Bg_up
```

См. [[конвенции-знаков]].

## Аналитическая заглушка (AnalyticalHydroSolver → LogProfileHydroStub)

Для тестирования EnergySolver и Simulator до получения модуля коллеги.

> **DEBT-005 (2026-09-10):** класс удалён из пакета и вынесен в тестовую
> оснастку — `numerical_solver/tests/_doubles.py`, имя `LogProfileHydroStub`.
> Причина: заглушка не решает уравнение фильтрации (не учитывает
> разгазирование и сжимаемость, не зависит от `dt`), но удовлетворяла ABC
> `HydroSolver` и потому могла быть незаметно подставлена в production-расчёт.
> Арифметика перенесена без изменений; листинг ниже актуален по существу,
> изменились только имя класса и его местоположение.

```python
class LogProfileHydroStub(HydroSolver):   # было AnalyticalHydroSolver
    """Аналитические поля для тестирования."""

    def solve(self, state, dt, bc):
        p_wf = bc.well.boundary_pressure(state, self._grid, self._pvt, self._relperm)
        p_ext = bc.p_ext
        Rs_ext = bc.Rs_ext

        # Логарифмический профиль давления (стационарный однофазный)
        p = p_wf + (p_ext - p_wf) * np.log(r / r_w) / np.log(R_ext / r_w)

        # Однофазная зона
        Sg = np.zeros(N)
        Rs = np.full(N, Rs_ext)
        regime = np.full(N, 2, dtype=int)

        # Скорость Дарси, потоки, массовые расходы
        ...

        return HydroResult(state=..., G_o=..., G_g=..., G_free_gas=...,
                           Q_o=..., Q_g=..., u_o=..., u_g=...,
                           m_o=..., m_g=..., Gm_o=..., Gm_g=...)
```

Достаточно для: тестирования T(r), проверки JT-эффекта, VAL-001.

## Вектор неизвестных

Размер 3N. Хранение: `np.ndarray shape (N, 3)`.
- `U[j, 0]` = p_j
- `U[j, 1]` = Sg_j
- `U[j, 2]` = Rs_j

Для СЛАУ — reshape в `(3N,)` (numpy view, без копирования).

## Алгоритм одного шага

```
Вход: state^n, dt, p_wf, p_ext, Rs0
1. U^(0) = U^n (начальное приближение)
2. Цикл k = 0, 1, ..., newton_max_iter:
   a) PVT(p^(k)): Bo, Bg, mu_o, mu_g, Rs_eq и все производные
   b) ОФП(Sg^(k)): kro, krg, dkro_dSg, dkrg_dSg
   c) Потоки через грани: G^o, G^g (с upstream)
   d) Невязки F^oil, F^gas, F^eq для каждой ячейки
   e) Якобиан: блоки 3×3 (D_j, L_j, U_j)
   f) Граничные условия: модификация блоков для j=0 и j=N-1
   g) Блочная прогонка: J·δU = -F → δU
   h) Обновление: U^(k+1) = U^(k) + δU
   i) Переключение режимов
   j) Контроль физичности
   k) Проверка сходимости → выход если выполнена
3. Если не сошлось: dt *= cut_factor, goto 1
4. Вычислить u_o, u_g на гранях из p^{n+1}
Выход: HydroResult
```

## Невязки (problem_statement.tex eq. 14, 15, 16-17)

### Потоки через внутреннюю грань f (между ячейками f-1 и f)

Конвенция: **G > 0 = от скважины (рост r).**

```python
# Upstream: ячейка с бо́льшим давлением
if p[f-1] > p[f]:    # G > 0, поток от скважины (нетипично)
    up = f - 1
else:                 # G < 0, поток к скважине (типично)
    up = f

mob_o = kro[up] / (mu_o[up] * Bo[up])
mob_g = krg[up] / (mu_g[up] * Bg[up])
Rs_up = Rs[up]

G_o[f] = T[f] * mob_o * (p[f-1] - p[f])
G_g[f] = T[f] * (mob_o * Rs_up + mob_g) * (p[f-1] - p[f])
```

При типичном потоке: p[f-1] < p[f] → G < 0.

### Потоки через граничные грани

Забой (грань f=0, между забоем и ячейкой 0):
```python
G_o[0] = T_well * (kro[0]/(mu_o[0]*Bo[0])) * (p_wf - p[0])
G_g[0] = T_well * (Rs[0]*kro[0]/(mu_o[0]*Bo[0]) + krg[0]/(mu_g[0]*Bg[0])) * (p_wf - p[0])
# p_wf < p[0] → G_o[0] < 0 → поток к скважине ✓
```

Контур (грань f=N, между ячейкой N-1 и контуром):
```python
G_o[N] = T_ext * (kro[N-1]/(mu_o[N-1]*Bo[N-1])) * (p[N-1] - p_ext)
G_g[N] = T_ext * (Rs0*kro[N-1]/(mu_o[N-1]*Bo[N-1])) * (p[N-1] - p_ext)
# krg=0 на контуре (однофазная зона, Sg=0)
# p[N-1] < p_ext → G_o[N] < 0, G_g[N] < 0 → приток из контура ✓
```

### Невязки

Конвенция: G > 0 = от скважины. Невязка: accum + G[j+1] − G[j].

```python
# Баланс нефтяного компонента (eq. 14)
F_oil[j] = V[j] * phi * ((1-Sg[j])/Bo[j] - (1-Sg_n[j])/Bo_n[j]) / dt
           + G_o[j+1] - G_o[j]

# Баланс газового компонента (eq. 15)
F_gas[j] = V[j] * phi * ((Rs[j]*(1-Sg[j])/Bo[j] + Sg[j]/Bg[j])
                        - (Rs_n[j]*(1-Sg_n[j])/Bo_n[j] + Sg_n[j]/Bg_n[j])) / dt
           + G_g[j+1] - G_g[j]

# Замыкающее уравнение (eq. 16-17)
if regime[j] == 1:  # двухфазная
    F_eq[j] = Rs[j] - Rs_eq(p[j])
else:               # однофазная
    F_eq[j] = Sg[j]
```

## Якобиан — блоки 3×3

### Диагональный блок D_j

Первые две строки — производные F_oil, F_gas по (p_j, Sg_j, Rs_j).
Содержат:
- производные членов накопления (eq. 22-27)
- производные потоков через обе грани ячейки j

Третья строка зависит от режима:
- Режим 1 (eq. 28): [-dRs_eq/dp, 0, 1]
- Режим 2 (eq. 29): [0, 1, 0]

### Внедиагональные блоки L_j, U_j

Только производные потоков через грани по неизвестным соседних ячеек.
Третья строка — нулевая (замыкающее уравнение локально).

Зависят от upstream-направления:
- Если upstream = j (текущая ячейка): производные подвижностей входят в D_j, не в L/U
- Если upstream = j±1 (сосед): производные подвижностей входят в L/U

## Блочная прогонка (Block Thomas)

Обобщение скалярной прогонки на блоки 3×3.

```python
# Прямой ход
alpha = np.zeros((N, 3, 3))
d_mod = np.zeros((N, 3))

alpha[0] = np.linalg.inv(D[0])
d_mod[0] = alpha[0] @ rhs[0]

for j in range(1, N):
    temp = D[j] - L[j] @ alpha[j-1] @ U_block[j-1]
    alpha[j] = np.linalg.inv(temp)
    d_mod[j] = alpha[j] @ (rhs[j] - L[j] @ d_mod[j-1])

# Обратный ход
x = np.zeros((N, 3))
x[N-1] = d_mod[N-1]

for j in range(N-2, -1, -1):
    x[j] = d_mod[j] - alpha[j] @ U_block[j] @ x[j+1]
```

Сложность O(N) — по одному обращению матрицы 3×3 на ячейку.

Для N=100..500 — цикл Python приемлем. Для N>1000 — numba/Cython.

## Переключение режимов (problem_statement.tex §4.2.4)

После каждой итерации Ньютона:
```python
for j in range(N):
    if regime[j] == 1 and Sg[j] < 0:
        regime[j] = 2
        Sg[j] = 0.0
    elif regime[j] == 2 and Rs[j] > Rs_eq(p[j]):
        regime[j] = 1
        Rs[j] = Rs_eq(p[j])
        Sg[j] = 1e-6  # малое положительное
```

Размерность системы не меняется (3N). Меняется только третья строка диагонального блока.

## Контроль физичности и адаптация dt

Проверки после каждой итерации:
- `0 ≤ Sg ≤ 1 - S_or`
- `0 ≤ Rs ≤ Rs_eq(p)`
- `p > 0`

Нарушение → dt *= cut_factor, рестарт итераций с U^n. Если dt < dt_min → ошибка.

Критерий сходимости — покомпонентный (§5.2):
```python
converged = all(
    (abs(F_oil[j]) < tol_abs and abs(F_gas[j]) < tol_abs)
    or
    (abs(F_oil[j])/abs(F_oil_0[j]) < tol_rel and 
     abs(F_gas[j])/abs(F_gas_0[j]) < tol_rel)
    for j in range(N)
)
```

## Скорости Дарси на гранях

После сходимости Ньютона:
```python
u_o[j+1/2] = -Lambda_o * dp/dr  (через потоки)
u_g[j+1/2] = -Lambda_g * dp/dr
```

Или проще: из уже вычисленных потоков:
```python
Q_o[j] = T[j] * (kro/mu_o)_up * (p[j+1] - p[j])   # расход фазы (пл. усл.)
u_o[j] = Q_o[j] / (2*pi*h*r_face[j])                # скорость = расход / площадь
```

Нужны для уравнения энергии.

## Связанные заметки

- [[архитектура библиотеки numerical_solver]]
- [[модули-pvt-контракт]] — PVT-интерфейс
- [[модули-grid-сетка]] — проводимости, объёмы
- [[модули-energy-tridiag]] — использование HydroResult: Q_o, Q_g, G_o, p_wf
