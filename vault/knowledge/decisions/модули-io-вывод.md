---
name: модули-io-вывод
description: Модуль I/O — config.py (чтение JSON, dataclasses), output.py (NPZ/CSV, визуализация matplotlib)
metadata:
  type: project
---

# I/O — ввод и вывод

## config.py — чтение JSON

### Структура

```python
import json
from dataclasses import dataclass

@dataclass
class GeometryConfig:
    r_well: float   # м
    R_ext: float     # м
    h: float         # м

    def __post_init__(self):
        if self.r_well <= 0:
            raise ValueError("r_well must be > 0")
        if self.R_ext <= self.r_well:
            raise ValueError("R_ext must be > r_well")
        if self.h <= 0:
            raise ValueError("h must be > 0")

@dataclass
class GridConfig:
    N: int
    type: str = "log_radial"

    def __post_init__(self):
        if self.N < 3:
            raise ValueError("N must be >= 3")

@dataclass
class RockConfig:
    porosity: float
    permeability: float    # м²
    rho_cp_solid: float    # Дж/(м³·К)
    lambda_solid: float    # Вт/(м·К)
    lambda_oil: float      # Вт/(м·К)
    lambda_gas: float      # Вт/(м·К)

    def __post_init__(self):
        if not (0 < self.porosity < 1):
            raise ValueError("porosity must be in (0, 1)")
        if self.permeability <= 0:
            raise ValueError("permeability must be > 0")

# Аналогично: PVTConfig, RelPermConfig, ThermalConfig,
# ICConfig, BCConfig, NumericsConfig, OutputConfig

@dataclass
class SimulationConfig:
    geometry: GeometryConfig
    grid: GridConfig
    rock: RockConfig
    pvt: PVTConfig
    relperm: RelPermConfig
    thermal: ThermalConfig
    initial_conditions: ICConfig
    boundary_conditions: BCConfig
    numerics: NumericsConfig
    output: OutputConfig
```

### Загрузка

```python
def load_config(path: str) -> SimulationConfig:
    with open(path, 'r') as f:
        data = json.load(f)

    return SimulationConfig(
        geometry=GeometryConfig(**data["geometry"]),
        grid=GridConfig(**data["grid"]),
        rock=RockConfig(**data["rock"]),
        pvt=PVTConfig(**data["pvt"]),
        relperm=RelPermConfig(**data["relperm"]),
        thermal=ThermalConfig(**data["thermal"]),
        initial_conditions=ICConfig(**data["initial_conditions"]),
        boundary_conditions=BCConfig(**data["boundary_conditions"]),
        numerics=NumericsConfig(**data["numerics"]),
        output=OutputConfig(**data.get("output", {})),
    )
```

`**data["section"]` — распаковка dict в аргументы dataclass. Если ключ в JSON не совпадает с полем dataclass — TypeError с понятным сообщением.

### Единицы

Всё в SI в JSON. Если пользователь работает с другими единицами — конвертация в утилите или в отдельном пре-процессоре, не внутри библиотеки.

## output.py — сохранение результатов

### NPZ (по умолчанию)

```python
def save_npz(history: SimulationHistory, path: str, r_centers: np.ndarray):
    arrays = history.to_arrays()
    np.savez(path,
             times=arrays['times'],
             r=r_centers,
             p=arrays['p'],
             T=arrays['T'],
             Sg=arrays['Sg'],
             Rs=arrays['Rs'])
```

Загрузка: `data = np.load("result.npz"); p = data['p']` — матрица (n_steps, N).

### CSV

```python
def save_csv(history: SimulationHistory, path: str, r_centers: np.ndarray):
    arrays = history.to_arrays()
    n_steps, N = arrays['p'].shape

    with open(path, 'w') as f:
        f.write("time_step,time_s,r_m,p_Pa,T_K,Sg,Rs\n")
        for i in range(n_steps):
            for j in range(N):
                f.write(f"{i},{arrays['times'][i]:.6e},{r_centers[j]:.6e},"
                        f"{arrays['p'][i,j]:.6e},{arrays['T'][i,j]:.6e},"
                        f"{arrays['Sg'][i,j]:.6e},{arrays['Rs'][i,j]:.6e}\n")
```

Длинная таблица (tidy format) — удобна для pandas, Excel, Matplotlib.

## Визуализация (matplotlib)

### 1. Профили p(r), T(r), Sg(r) на выбранных моментах

```python
def plot_profiles(history, r, times_to_plot, field='p', ax=None):
    """Профиль выбранного поля на нескольких моментах времени."""
    arrays = history.to_arrays()
    for t_target in times_to_plot:
        idx = np.argmin(np.abs(arrays['times'] - t_target))
        ax.semilogx(r, arrays[field][idx, :],
                    label=f"t = {arrays['times'][idx]:.1f} s")
    ax.set_xlabel('r, м')
    ax.legend()
```

semilogx — логарифмическая шкала по r (ячейки у скважины мелкие, сетка логарифмическая).

### 2. Динамика на забое

```python
def plot_wellbore_dynamics(history):
    arrays = history.to_arrays()
    fig, axes = plt.subplots(3, 1, sharex=True)
    axes[0].plot(arrays['times'], arrays['p'][:, 0])
    axes[0].set_ylabel('p(r_w), Па')
    axes[1].plot(arrays['times'], arrays['T'][:, 0])
    axes[1].set_ylabel('T(r_w), К')
    axes[2].plot(arrays['times'], arrays['Sg'][:, 0])
    axes[2].set_ylabel('Sg(r_w)')
    axes[2].set_xlabel('t, с')
```

### 3. Дебит скважины

```python
def plot_well_rate(history, grid):
    """Дебит при стандартных условиях через левую грань."""
    # q_o_std = G_o_well (поток нефтяного компонента = м³ст/с)
    # G_o нужно хранить в history или пересчитывать
```

Вопрос: хранить ли потоки через грани в SimulationHistory? Они нужны для дебита, для проверки баланса масс, для визуализации потоков. Рекомендую хранить G_o_well и G_g_well (скаляры на каждом шаге) — это дебит нефти и газа.

### 4. 2D карта r-t

```python
def plot_2d_map(history, r, field='T'):
    arrays = history.to_arrays()
    fig, ax = plt.subplots()
    c = ax.pcolormesh(r, arrays['times'], arrays[field],
                      shading='auto', cmap='coolwarm')
    ax.set_xlabel('r, м')
    ax.set_ylabel('t, с')
    ax.set_xscale('log')
    fig.colorbar(c, label=field)
```

## Связанные заметки

- [[json-config-schema]] — структура JSON
- [[модули-simulator-оркестратор]] — SimulationHistory
- [[architecture-numerical-solver]] — общая архитектура
