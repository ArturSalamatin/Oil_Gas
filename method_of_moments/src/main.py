"""CLI-точка входа метода моментов — FEAT-008."""

import json
import sys
from pathlib import Path

import numpy as np

from .pvt.black_oil import BlackOilFluid
from .profiles.pressure import PressureProfile
from .profiles.temperature import TemperatureProfile
from .profiles.saturation import SaturationProfile
from .solver import solve_moments, reconstruct_profiles

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def load_config(path):
    """JSON-конфиг → dict."""
    with open(path) as f:
        return json.load(f)


def build_objects(cfg):
    """Конфиг → (fluid, rock, p_profile, t_profile, s_profile, solver_opts)."""
    fluid = BlackOilFluid(
        pvt_config=cfg["pvt"],
        p_b=cfg["initial_conditions"]["p_b"],
        T_0=cfg["initial_conditions"]["T_0"],
        relperm_config=cfg["relative_permeability"],
    )
    rock = cfg["rock"]

    geo = cfg["geometry"]
    ic = cfg["initial_conditions"]
    bc = cfg["boundary_conditions"]
    prof = cfg["profiles"]

    p_profile = PressureProfile(geo["r_w"], geo["R_ext"],
                                bc["p_wf"], ic["p_0"])
    t_profile = TemperatureProfile(geo["r_w"], geo["R_ext"],
                                   ic["T_0"], prof["sigma"])
    s_profile = SaturationProfile(geo["r_w"], prof["beta"])

    solver_opts = cfg["solver"]

    return fluid, rock, p_profile, t_profile, s_profile, solver_opts


def save_csv(sol, path):
    """OdeResult → CSV с колонками t, r_b, Sg_w, dT_w."""
    data = np.column_stack([sol.t, sol.y.T])
    np.savetxt(path, data, delimiter=",",
               header="t,r_b,Sg_w,dT_w", comments="")


def plot_dynamics(sol, path):
    """r_b(t) → PNG."""
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(sol.t, sol.y[0])
    ax.set_xlabel("$t$, с")
    ax.set_ylabel("$r_b$, м")
    ax.set_title("Динамика радиуса двухфазной зоны")
    ax.grid(True, alpha=0.3)
    fig.savefig(path, bbox_inches="tight", dpi=150)
    plt.close(fig)


def plot_profiles(sol, p_profile, t_profile, s_profile, fluid,
                  r_w, r_e, path):
    """p(r), Sg(r), T(r) на последний момент → PNG."""
    r_b, Sg_w, dT_w = sol.y[:, -1]
    r_grid = np.geomspace(r_w, r_e, 500)
    p_arr, Sg_arr, T_arr = reconstruct_profiles(
        r_b, Sg_w, dT_w, p_profile, t_profile, s_profile,
        fluid, r_grid)

    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(8, 12),
                                         sharex=True)
    ax1.semilogx(r_grid, p_arr / 1e6)
    ax1.axvline(r_b, color="k", ls="--", lw=0.8,
                label=f"$r_b$ = {r_b:.1f} м")
    ax1.set_ylabel("$p$, МПа")
    ax1.set_title("Профили на последний момент времени")
    ax1.legend()

    ax2.semilogx(r_grid, Sg_arr)
    ax2.axvline(r_b, color="k", ls="--", lw=0.8)
    ax2.set_ylabel("$S_g$")

    ax3.semilogx(r_grid, T_arr)
    ax3.axvline(r_b, color="k", ls="--", lw=0.8)
    ax3.set_xlabel("$r$, м")
    ax3.set_ylabel("$T$, К")

    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight", dpi=150)
    plt.close(fig)


def run(config_path, output_dir="results"):
    """JSON-конфиг → решение → CSV + графики."""
    cfg = load_config(config_path)
    fluid, rock, p_profile, t_profile, s_profile, solver_opts = build_objects(cfg)

    geo = cfg["geometry"]
    bc = cfg["boundary_conditions"]
    p_wf = bc["p_wf"]
    r_w = geo["r_w"]
    r_e = geo["R_ext"]

    sol = solve_moments(
        fluid, rock, p_profile, t_profile, s_profile,
        p_wf, r_e, solver_opts["t_end"],
        t_eps=solver_opts["t_epsilon"],
        method=solver_opts.get("method", "Radau"),
        rtol=solver_opts.get("rtol", 1e-6),
        atol=solver_opts.get("atol", 1e-9),
    )

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    if not sol.success:
        print(f"Предупреждение: solver не сошёлся — {sol.message}",
              file=sys.stderr)

    if sol.t.size == 0:
        print("Предупреждение: solver не вернул ни одной точки.",
              file=sys.stderr)
        return sol

    save_csv(sol, out / "solution.csv")
    plot_dynamics(sol, out / "rb_vs_t.png")
    plot_profiles(sol, p_profile, t_profile, s_profile, fluid,
                  r_w, r_e, out / "profiles.png")

    print(f"Результаты: {out}/")
    print(f"  solution.csv  ({sol.t.shape[0]} точек,"
          f" t ∈ [{sol.t[0]:.2e}, {sol.t[-1]:.2e}] с)")
    print(f"  rb_vs_t.png")
    print(f"  profiles.png")
    return sol


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="Метод моментов — решатель двухфазной фильтрации Black Oil")
    parser.add_argument("config", help="путь к JSON-конфигу")
    parser.add_argument("--output-dir", default="results",
                        help="директория для результатов (по умолчанию: results/)")
    args = parser.parse_args()
    run(args.config, args.output_dir)
