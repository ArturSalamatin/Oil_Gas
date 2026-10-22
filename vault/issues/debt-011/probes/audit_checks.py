"""Проверки аудита плана DEBT-011 на текущем дереве (без правки кода проекта).

1. Страж приватного доступа (шаг 3) — что он находит в examples/ сейчас.
2. Страж независимости пакета (шаг 12) — что он находит в пакете сейчас.
3. Числа синтетических тестов шага 4 — на текущих функциях examples/.
4. Разделение рисования (шаги 9, 10): PNG «как сейчас» против «ядро +
   обёртка по тексту плана» — побайтно. История — расчёт примера 03.

Запуск из numerical_solver:
    .venv\\Scripts\\python ..\\vault\\issues\\debt-011\\probes\\audit_checks.py
"""

import ast
import hashlib
import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ["GPN_EXAMPLES_EMF"] = "0"
SOLVER = Path.cwd()
EXAMPLES = SOLVER / "examples"
PACKAGE = SOLVER / "gpn_multiphase_solver"
OUT = Path(__file__).resolve().parent / "out" / "audit"
sys.path.insert(0, str(EXAMPLES))

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

import gpn_multiphase_solver  # noqa: E402
print("пакет:", gpn_multiphase_solver.__file__)

# ── 1. Страж приватного доступа (текст шага 3) ───────────────
CHECKED_PACKAGES = ("gpn_multiphase_solver", "radial_blackoil")
_OWN = {"self", "cls"}


def _private_access(tree):
    found = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Attribute) and node.attr.startswith("_")
                and not node.attr.startswith("__")
                and not (isinstance(node.value, ast.Name)
                         and node.value.id in _OWN)):
            found.append(f"{node.lineno}:.{node.attr}")
        elif (isinstance(node, ast.ImportFrom) and node.module
              and node.module.split(".")[0] in CHECKED_PACKAGES):
            found += [f"{node.lineno}:import {a.name}"
                      for a in node.names if a.name.startswith("_")]
    return found


scripts = sorted(p for p in EXAMPLES.rglob("*.py")
                 if "output" not in p.parts and "__pycache__" not in p.parts)
bad = {}
for p in scripts:
    f = _private_access(ast.parse(p.read_text(encoding="utf-8")))
    if f:
        bad[p.relative_to(EXAMPLES).as_posix()] = f
print(f"\n1. страж приватного доступа: скриптов {len(scripts)}, с находками {len(bad)}")
for k, v in bad.items():
    print(f"   {k}: {v}")

# ── 2. Страж независимости пакета (текст шага 12) ────────────
example_modules = {p.stem for p in EXAMPLES.glob("*.py")}
found = []
for path in sorted(PACKAGE.rglob("*.py")):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            tops = [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            tops = [node.module.split(".")[0]]
        else:
            tops = []
        rel = path.relative_to(PACKAGE).as_posix()
        found += [f"{rel}:{node.lineno} импорт {t}" for t in tops
                  if t in example_modules]
        if (isinstance(node, ast.Attribute) and node.attr == "path"
                and isinstance(node.value, ast.Name) and node.value.id == "sys"):
            found.append(f"{rel}:{node.lineno} sys.path")
print(f"\n2. страж независимости пакета: находок {len(found)} {found}")
# Негативная проверка: подложить импорт модуля examples — страж должен поймать
neg = ast.parse("import closed_form\nfrom figure_io import save_figure\nimport sys\nsys.path.insert(0, 'x')\n")
neg_hits = []
for node in ast.walk(neg):
    if isinstance(node, ast.Import):
        neg_hits += [a.name for a in node.names if a.name.split(".")[0] in example_modules]
    elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
        if node.module.split(".")[0] in example_modules:
            neg_hits.append(node.module)
    if (isinstance(node, ast.Attribute) and node.attr == "path"
            and isinstance(node.value, ast.Name) and node.value.id == "sys"):
        neg_hits.append("sys.path")
print(f"   негатив: {neg_hits} (ожидание: closed_form, figure_io, sys.path)")

# ── 3. Числа синтетических тестов шага 4 ─────────────────────
from gpn_multiphase_solver.energy.balance import CUMULATIVE_KEYS  # noqa: E402
from gpn_multiphase_solver.state import SimulationHistory  # noqa: E402
import energy_balance as eb  # noqa: E402
import mass_balance as mb  # noqa: E402

zero = dict.fromkeys(CUMULATIVE_KEYS, 0.0)
last = dict(delta_E=5.0, cum_adiab=1.0, cum_conv=2.0, cum_jt=-1.0,
            cum_deg=0.5, cum_cond=2.0)
h = SimulationHistory(times=[0.0, 10.0], balance=[zero, last])
bal = eb.compute_balance(h, None, None)
print("\n3. энергия: total", bal["total"][1], "residual", bal["residual"][1],
      "rel", bal["rel_residual"][1], "= 0.5/11.5:", bal["rel_residual"][1] == 0.5 / 11.5,
      "rel[0]", bal["rel_residual"][0], "ключи", sorted(bal))
print("   CUMULATIVE_KEYS == _CUMULATIVE:", tuple(CUMULATIVE_KEYS) == tuple(eb._CUMULATIVE))
print("   масса пустая:", mb.compute_mass_balance(SimulationHistory()),
      mb.compute_mass_balance(SimulationHistory(mass_balance=[None])))
snaps = [dict(M_o=100.0, M_g=0.0, cum_o_well=0.0, cum_o_ext=0.0, cum_g_well=0.0, cum_g_ext=0.0),
         dict(M_o=90.0, M_g=0.0, cum_o_well=-12.0, cum_o_ext=-2.0, cum_g_well=0.0, cum_g_ext=0.0)]
mbal = mb.compute_mass_balance(SimulationHistory(times=[0.0, 1.0], mass_balance=snaps))
print("   масса: residual_o", mbal["residual_o"][1], "rel_o", mbal["rel_residual_o"][1],
      "prod_o", mbal["prod_o"][1], "inflow_o", mbal["inflow_o"][1],
      "rel_g", mbal["rel_residual_g"][1])

# ── 4. Разделение рисования: побайтно ────────────────────────
from figure_io import save_figure  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory, _create_relperm  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.units import S_TO_DAY  # noqa: E402
import relperm_plot as rp  # noqa: E402

cfg = load_config(EXAMPLES / "03_standing_corey" / "config.json")
cfg.output.log_level = "ERROR"
sim, init = SimulatorFactory.from_config(cfg)
hist = sim.run(init)
A, B = OUT / "a", OUT / "b"


# --- ядро по тексту плана, шаг 9 ---
def plot_energy_balance_series(bal, axes=None, title="Баланс энергии"):
    if axes is None:
        _, axes = plt.subplots(2, 1, figsize=(9, 8), sharex=True,
                               gridspec_kw={"height_ratios": [3, 1]})
    ax1, ax2 = axes
    t_days = bal["t"] * S_TO_DAY
    ax1.plot(t_days, bal["delta_E"], 'k-', linewidth=2, label=r"$\Delta E$ (накопление)")
    ax1.plot(t_days, bal["cum_adiab"], 'b--', linewidth=1.5, label="адиабатика (кумул.)")
    ax1.plot(t_days, bal["cum_conv"], 'r--', linewidth=1.5, label="чистая конвекция (кумул.)")
    ax1.plot(t_days, bal["cum_jt"], 'm--', linewidth=1.5, label="Джоуль–Томсон (кумул.)")
    ax1.plot(t_days, bal["cum_deg"], 'c--', linewidth=1.5, label="скрытая теплота (кумул.)")
    ax1.plot(t_days, bal["cum_cond"], color='olive', linestyle='--',
             linewidth=1.5, label="теплопроводность (кумул.)")
    ax1.plot(t_days, bal["total"], 'g:', linewidth=1.5, label="сумма источников")
    ax1.set_ylabel("Энергия, Дж")
    ax1.legend(fontsize=9)
    ax1.set_title(title)
    ax1.grid(True, alpha=0.3)
    ax1.ticklabel_format(axis='y', style='scientific', scilimits=(0, 0))
    ax2.plot(t_days, bal["rel_residual"], 'k-', linewidth=1)
    ax2.set_xlabel("Время, сут")
    ax2.set_ylabel(r"|невязка| / $\Sigma$|членов|")
    ax2.set_title("Относительная невязка баланса")
    ax2.grid(True, alpha=0.3)
    ax2.ticklabel_format(axis='y', style='scientific', scilimits=(0, 0))
    return axes


def plot_mass_balance_series(bal, axes=None):
    if axes is None:
        _, axes = plt.subplots(2, 2, figsize=(13, 8), sharex=True,
                               gridspec_kw={"height_ratios": [3, 1]})
    axes = np.asarray(axes)
    t_days = bal["t"] * S_TO_DAY
    for col, (a, name) in enumerate((("o", "Нефтяной компонент"),
                                     ("g", "Газовый компонент"))):
        ax1, ax2 = axes[0, col], axes[1, col]
        ax1.plot(t_days, bal[f"dM_{a}"], 'k-', linewidth=2, label=r"$\Delta M$ (изменение запаса)")
        ax1.plot(t_days, bal[f"prod_{a}"], 'r-', linewidth=3, alpha=0.5,
                 label="добыча через забой (кумул.)")
        ax1.plot(t_days, bal[f"inflow_{a}"], 'b--', linewidth=1.5,
                 label="приток через контур (кумул.)")
        ax1.plot(t_days, bal[f"inflow_{a}"] - bal[f"prod_{a}"], 'g:',
                 linewidth=1.5, label="приток − добыча")
        ax1.set_ylabel("Объём, м³ст")
        ax1.set_title(name)
        ax1.legend(fontsize=9)
        ax1.grid(True, alpha=0.3)
        ax1.ticklabel_format(axis='y', style='scientific', scilimits=(0, 0))
        ax2.plot(t_days, bal[f"rel_residual_{a}"], 'k-', linewidth=1)
        ax2.set_xlabel("Время, сут")
        ax2.set_ylabel(r"|невязка| / $\Sigma$|членов|")
        ax2.grid(True, alpha=0.3)
        ax2.ticklabel_format(axis='y', style='scientific', scilimits=(0, 0))
    return axes


# --- ядро по тексту плана, шаг 10: тело панелей — из текущего модуля ---
# Код панелей берётся текстом из examples/relperm_plot.py (строки
# «# ── Панель 1» … перед fig.tight_layout()) — ровно то, что план велит
# перенести дословно; правка одна — заголовок первой панели.
_src = (EXAMPLES / "relperm_plot.py").read_text(encoding="utf-8").splitlines()
_i0 = next(i for i, s in enumerate(_src) if "── Панель 1" in s)
_i1 = next(i for i, s in enumerate(_src) if s.strip() == "fig.tight_layout()" and i > _i0)
_panels = "\n".join(s[4:] for s in _src[_i0:_i1])
_panels = _panels.replace('ax1.set_title(f"{title}\\nОФП — {_describe(config)}", fontsize=9)',
                          'ax1.set_title(title, fontsize=9)')
assert 'ax1.set_title(title, fontsize=9)' in _panels, "заголовок не заменён"


def plot_relperm_curves(relperm, sg_range, axes=None, title=""):
    Sg_lo, Sg_hi = float(sg_range[0]), float(sg_range[1])
    two_phase = Sg_hi > 1e-12
    nodes = rp._table_nodes(relperm)
    S = np.linspace(0.0, 1.0, 1000)
    kro, krg = relperm.kro(S), relperm.krg(S)
    n_panels = 2 if two_phase else 1
    if axes is None:
        _, axes = plt.subplots(1, n_panels, figsize=(6.5 * n_panels, 5), squeeze=False)
    axes = np.asarray(axes)
    ax1 = axes[0, 0]
    ns = dict(np=np, plt=plt, relperm=relperm, Sg_lo=Sg_lo, Sg_hi=Sg_hi,
              two_phase=two_phase, nodes=nodes, S=S, kro=kro, krg=krg,
              axes=axes, ax1=ax1, title=title)
    exec(_panels, ns)
    return axes


# --- «как сейчас» ---
eb.plot_energy_balance(hist, sim._grid, cfg, A)
mb.plot_mass_balance(cfg, hist, A)
rp.plot_relperm(cfg, hist, A, "T")
one_phase = SimpleNamespace(states=[SimpleNamespace(Sg=np.zeros(5))])
rp.plot_relperm(cfg, one_phase, A / "one", "T")

# --- «по плану»: ядро + обёртка ---
B.mkdir(parents=True, exist_ok=True)
axes = plot_energy_balance_series(eb.compute_balance(hist, None, None),
                                  title=f"Баланс энергии — {Path(cfg.config_dir).name}")
fig = axes[0].figure
fig.tight_layout()
save_figure(fig, B / "energy_balance.png", dpi=130)
plt.close(fig)

axes = plot_mass_balance_series(mb.compute_mass_balance(hist))
fig = axes[0, 0].figure
fig.suptitle(f"Баланс массы компонентов — {Path(cfg.config_dir).name}")
fig.tight_layout()
save_figure(fig, B / "mass_balance.png", dpi=130)
plt.close(fig)

relperm = _create_relperm(cfg)
for sub, h_ in (("", hist), ("one", one_phase)):
    axes = plot_relperm_curves(relperm, rp._sg_range(h_),
                               title=f"T\nОФП — {rp._describe(cfg)}")
    fig = axes[0, 0].figure
    fig.tight_layout()
    (B / sub).mkdir(parents=True, exist_ok=True)
    save_figure(fig, B / sub / "relperm.png", dpi=120)
    plt.close(fig)

print("\n4. PNG «как сейчас» против «ядро + обёртка»:")
for name in ("energy_balance.png", "mass_balance.png", "relperm.png", "one/relperm.png"):
    ha = hashlib.sha256((A / name).read_bytes()).hexdigest()
    hb = hashlib.sha256((B / name).read_bytes()).hexdigest()
    print(f"   {name}: {'побайтно' if ha == hb else 'РАЗЛИЧАЮТСЯ'}")

# Синтетические тесты шагов 9–10 на «ядре по плану»
axes = plot_energy_balance_series(bal, title="T")
print("\n   энергия: кривых", len(axes[0].get_lines()), "+", len(axes[1].get_lines()),
      "заголовок", repr(axes[0].get_title()))
plt.close(axes[0].figure)
for sg_max in (0.05, 0.0):
    axes = plot_relperm_curves(relperm, (0.0, sg_max), title="T")
    print(f"   ОФП sg_max={sg_max}: форма {axes.shape}, заголовок {axes[0, 0].get_title()!r}")
    plt.close(axes[0, 0].figure)
