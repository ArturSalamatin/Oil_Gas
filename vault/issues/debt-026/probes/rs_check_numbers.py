"""DEBT-026: числа проверки R_s на всех примерах с газом (до и после правки).

Для каждого примера с Rs0 > 0 — расчёт штатного конфига; на последней записи:
  прежняя проверка: max|Rs - min(Rs_eq(p), Rs0)| по всем ячейкам;
    ячеек p < pb, Sg > 1e-12 (порог прежнего report_rs) и regime == 1;
  новая — считается здесь прямыми формулами, независимо от rs_analytics:
    ячеек с газом (Sg > 1e-8) и max|Rs - Rs_eq(p)| в них; ячеек без газа,
    пересыщенных из них (Rs > Rs_eq(p) + 1e-5) и наибольшее Rs - Rs_eq(p);
    ячеек без газа с p < pb; ячеек Rs > Rs0 + 1e-5;
  предпосылки плана:
    mask(p < pb) == mask(газ)      — подпись линии «фронт» или «изобара»;
    газ только в regime == 1       — в ячейках с газом Rs задан решателем
                                     как Rs_eq(p);
    ячейки p < pb образуют префикс — front_radius (searchsorted) корректен;
  затем вывод rs_analytics.report_rs — как его печатает пример.

Пороги 1e-8 и 1e-5 — те же, что SG_GAS и RS_TOL в rs_analytics после
DEBT-026; здесь они продублированы, чтобы замер до правки модуля считал
новую проверку теми же числами.

Запуск, все примеры ~4 мин:
    python rs_check_numbers.py [--solver каталог] [--out файл] [папка ...]
--solver — каталог numerical_solver, чей код мерить (пакет, examples/,
прототип); по умолчанию — numerical_solver рядом с этим vault. Нужен при
реализации в git worktree: vault/issues в .gitignore, скрипт лежит только
в основном каталоге и без ключа мерил бы его код, а не код worktree.
--out — копия вывода в файл UTF-8. Перенаправление «| Out-File» в
PowerShell 5.1 не годится: оно перекодирует вывод через кодировку консоли
и портит кириллицу.
"""

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ARGS = sys.argv[1:]
SOLVER = HERE.parents[3] / "numerical_solver"
if ARGS[:1] == ["--solver"]:
    SOLVER = Path(ARGS[1]).resolve()
    ARGS = ARGS[2:]
for p in (SOLVER, SOLVER / "examples",
          SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"):
    sys.path.insert(0, str(p))

# Консоль Windows (cp1251) не печатает «≤», «…», «³» — BUG-009.
for _stream in (sys.stdout, sys.stderr):
    _stream.reconfigure(encoding="utf-8")

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
import rs_analytics  # noqa: E402

EXAMPLES = SOLVER / "examples"
SG = 1e-8            # порог свободного газа (SG_GAS в rs_analytics)
TOL = 1e-5           # допуск пересыщения = rs_switch_tol решателя (RS_TOL)


def _is_prefix(mask: np.ndarray) -> bool:
    """True, если True-ячейки маски идут подряд от забоя (или их нет)."""
    k = int(np.count_nonzero(mask))
    return bool(np.all(mask[:k]) and not np.any(mask[k:]))


def probe(name: str) -> None:
    cfg = load_config(EXAMPLES / name / "config.json")
    Rs0 = cfg.initial_conditions.Rs0
    if Rs0 <= 0.0:
        return
    sim, init = SimulatorFactory.from_config(cfg)
    hist = sim.run(init)
    pvt = sim._energy._pvt          # тот PVT, что передаёт report_rs пример
    st = hist.states[-1]
    pb = float(pvt.pb(np.array([Rs0]))[0])

    below = st.p < pb
    gas = st.Sg > SG
    one = ~gas
    rs_eq = pvt.Rs_eq(st.p)

    old = float(np.abs(np.minimum(rs_eq, Rs0) - st.Rs).max())
    n_old_gas = int(np.count_nonzero(st.Sg > 1e-12))
    n_regime = int(np.count_nonzero(st.regime == 1))
    err2 = float(np.abs(rs_eq[gas] - st.Rs[gas]).max()) if gas.any() else 0.0
    exc = (st.Rs - rs_eq)[one]
    n_bad = int(np.count_nonzero(exc > TOL))
    exc_max = float(exc.max()) if exc.size else float("nan")
    n_under = int(np.count_nonzero(one & below))
    n_above = int(np.count_nonzero(st.Rs > Rs0 + TOL))

    print(f"\n=== {name}  (t = {st.t / 86400:.3f} сут, N = {st.p.size}) ===")
    # Какой rs_analytics мерится — при --solver на worktree должен быть его.
    # В файл не пишется: путь различается между основным каталогом и
    # worktree, а сверка «до/после» побитовая.
    print(f"  [rs_analytics: {Path(rs_analytics.__file__).parent.parent.name}"
          f"/{Path(rs_analytics.__file__).parent.name}]", file=sys.stderr)
    print(f"  прежняя: max|Rs - min(Rs_eq, Rs0)| = {old:.3e}; "
          f"p<pb: {int(below.sum())}, Sg>1e-12: {n_old_gas}, regime 1: {n_regime}")
    print(f"  новая: с газом {int(gas.sum())}, max|Rs - Rs_eq(p)| = {err2:.3e}; "
          f"без газа {int(one.sum())}, пересыщенных {n_bad} "
          f"(max Rs - Rs_eq = {exc_max:.3e}), ниже pb {n_under}; Rs > Rs0: {n_above}")
    print(f"  предпосылки: (p<pb)==(газ): {np.array_equal(below, gas)}; "
          f"газ только в regime 1: {bool(np.all(st.regime[gas] == 1))}; "
          f"префикс p<pb: {_is_prefix(below)}")
    print("  --- report_rs ---")
    rs_analytics.report_rs(cfg, hist, pvt)


class _Tee:
    """Печать одновременно в консоль и в файл UTF-8."""

    def __init__(self, path):
        self._console = sys.stdout
        self._file = open(path, "w", encoding="utf-8")

    def write(self, s):
        self._console.write(s)
        self._file.write(s)

    def flush(self):
        self._console.flush()
        self._file.flush()


if __name__ == "__main__":
    args = ARGS                     # --solver уже снят при подключении путей
    if args[:1] == ["--out"]:
        sys.stdout = _Tee(args[1])
        args = args[2:]
    names = args or sorted(
        d.name for d in EXAMPLES.iterdir() if (d / "config.json").is_file())
    for n in names:
        probe(n)
    sys.stdout.flush()
