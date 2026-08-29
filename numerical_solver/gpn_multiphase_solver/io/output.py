"""Сохранение результатов и визуализация.

Сериализация:
  save_npz — SimulationHistory → .npz (numpy)
  save_csv — SimulationHistory → .csv (tidy format)

Визуализация (matplotlib):
  plot_profiles        — p(r), T(r), Sg(r) на выбранных моментах (semilogx)
  plot_wellbore_dynamics — p(rw,t), T(rw,t), Sg(rw,t)
  plot_well_rate       — q_o(t), q_g(t) из WellData
  plot_2d_map          — pcolormesh(r, t, field)
"""

from pathlib import Path

import numpy as np

from ..state import SimulationHistory
from ..grid.base import Grid


# ═══════════════════════════════════════════════════════════
# Вспомогательная функция: история → словарь массивов
# ═══════════════════════════════════════════════════════════

def history_to_arrays(history: SimulationHistory) -> dict[str, np.ndarray]:
    """Упаковать SimulationHistory в словарь numpy-массивов.

    Возвращает:
      times  — [K]
      p      — [K, N]
      T      — [K, N]
      Sg     — [K, N]
      Rs     — [K, N]
      q_o_std — [K]
      q_g_std — [K]
      p_wf   — [K]
      T_wf   — [K]
    """
    return {
        'times': np.array(history.times),
        'p': np.array([s.p for s in history.states]),
        'T': np.array([s.T for s in history.states]),
        'Sg': np.array([s.Sg for s in history.states]),
        'Rs': np.array([s.Rs for s in history.states]),
        'q_o_std': np.array([w.q_o_std for w in history.well_data]),
        'q_g_std': np.array([w.q_g_std for w in history.well_data]),
        'p_wf': np.array([w.p_wf for w in history.well_data]),
        'T_wf': np.array([w.T_wf for w in history.well_data]),
    }


# ═══════════════════════════════════════════════════════════
# Сохранение: NPZ
# ═══════════════════════════════════════════════════════════

def save_npz(history: SimulationHistory, grid: Grid,
             path: str | Path) -> None:
    """Сохранить SimulationHistory в .npz файл.

    Содержимое:
      r[N], times[K], p[K,N], T[K,N], Sg[K,N], Rs[K,N],
      q_o_std[K], q_g_std[K], p_wf[K], T_wf[K].
    """
    arrays = history_to_arrays(history)
    np.savez(
        path,
        r=grid.r_centers,
        **arrays,
    )


# ═══════════════════════════════════════════════════════════
# Сохранение: CSV (tidy format)
# ═══════════════════════════════════════════════════════════

def save_csv(history: SimulationHistory, grid: Grid,
             path: str | Path) -> None:
    """Сохранить SimulationHistory в CSV (длинная таблица, tidy format).

    Столбцы: step, time_s, r_m, p_Pa, T_K, Sg, Rs.
    Одна строка = одна ячейка на одном сохранённом шаге.
    """
    r = grid.r_centers
    path = Path(path)

    with open(path, 'w', encoding='utf-8') as f:
        f.write("step,time_s,r_m,p_Pa,T_K,Sg,Rs\n")
        for i, state in enumerate(history.states):
            t = history.times[i]
            for j in range(len(r)):
                f.write(
                    f"{i},{t:.6e},{r[j]:.6e},"
                    f"{state.p[j]:.6e},{state.T[j]:.6e},"
                    f"{state.Sg[j]:.6e},{state.Rs[j]:.6e}\n"
                )


# ═══════════════════════════════════════════════════════════
# Визуализация
# ═══════════════════════════════════════════════════════════

def plot_profiles(history: SimulationHistory, grid: Grid,
                  times_to_plot: list[float], field: str = 'T',
                  ax=None):
    """Профиль поля (p, T, Sg, Rs) на выбранных моментах времени.

    semilogx — логарифмическая шкала по r (ячейки у скважины мелкие).
    """
    import matplotlib.pyplot as plt

    if ax is None:
        _, ax = plt.subplots()

    arrays = history_to_arrays(history)
    r = grid.r_centers
    times = arrays['times']

    labels = {'p': 'p, Па', 'T': 'T, К', 'Sg': 'Sg', 'Rs': 'Rs, м³ст/м³ст'}

    for t_target in times_to_plot:
        idx = int(np.argmin(np.abs(times - t_target)))
        ax.semilogx(r, arrays[field][idx, :],
                     label=f"t = {times[idx]:.0f} с")

    ax.set_xlabel('r, м')
    ax.set_ylabel(labels.get(field, field))
    ax.legend()
    ax.grid(True, alpha=0.3)
    return ax


def plot_wellbore_dynamics(history: SimulationHistory, axes=None):
    """Динамика на забое: p(rw,t), T(rw,t), Sg(rw,t).

    Три графика с общей осью t.
    """
    import matplotlib.pyplot as plt

    if axes is None:
        _, axes = plt.subplots(3, 1, sharex=True, figsize=(8, 8))

    arrays = history_to_arrays(history)
    t = arrays['times']

    axes[0].plot(t, arrays['p'][:, 0])
    axes[0].set_ylabel('p(rw), Па')
    axes[0].grid(True, alpha=0.3)

    axes[1].plot(t, arrays['T'][:, 0])
    axes[1].set_ylabel('T(rw), К')
    axes[1].grid(True, alpha=0.3)

    axes[2].plot(t, arrays['Sg'][:, 0])
    axes[2].set_ylabel('Sg(rw)')
    axes[2].set_xlabel('t, с')
    axes[2].grid(True, alpha=0.3)

    return axes


def plot_well_rate(history: SimulationHistory, ax=None):
    """Дебит скважины: q_o(t) и q_g(t) из WellData."""
    import matplotlib.pyplot as plt

    if ax is None:
        _, ax = plt.subplots()

    arrays = history_to_arrays(history)
    t = arrays['times']

    ax.plot(t, arrays['q_o_std'], label='q_o, м³ст/с')
    ax.plot(t, arrays['q_g_std'], label='q_g, м³ст/с')
    ax.set_xlabel('t, с')
    ax.set_ylabel('Дебит, м³ст/с')
    ax.legend()
    ax.grid(True, alpha=0.3)
    return ax


def plot_2d_map(history: SimulationHistory, grid: Grid,
                field: str = 'T', ax=None):
    """2D карта r-t: pcolormesh(r, t, field).

    Логарифмическая шкала по r.
    """
    import matplotlib.pyplot as plt

    if ax is None:
        _, ax = plt.subplots()

    arrays = history_to_arrays(history)
    r = grid.r_centers
    t = arrays['times']

    labels = {'p': 'p, Па', 'T': 'T, К', 'Sg': 'Sg', 'Rs': 'Rs'}

    c = ax.pcolormesh(r, t, arrays[field], shading='auto', cmap='coolwarm')
    ax.set_xlabel('r, м')
    ax.set_ylabel('t, с')
    ax.set_xscale('log')
    plt.colorbar(c, ax=ax, label=labels.get(field, field))
    return ax
