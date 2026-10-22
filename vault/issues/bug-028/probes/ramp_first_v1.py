"""BUG-028 (/plan-fix): нарастающий шаг FEAT-032 на первом интервале при варианте 1.

FEAT-032 первый интервал сменой управления не считает (решение пользователя
2026-10-11, из-за BUG-028). Проба: с вариантом 1 (variant1.py) подменить
first_substep_depth так, чтобы и интервал 0 начинался с подшага dt/2**m <= h0, и
сравнить забойную ячейку со штатным прогоном (тоже с вариантом 1 — он побитово штатный).
Пакет не правится. Только данные для решения пользователя — не правка плана.

Запуск из numerical_solver/ (P — путь к скрипту):
    .venv\\Scripts\\python P <пример> <h0, с>
"""

import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER_ROOT = Path.cwd()
sys.path.insert(0, str(SOLVER_ROOT))
sys.path.insert(0, str(HERE))
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

import gpn_multiphase_solver  # noqa: E402
import variant1  # noqa: E402
from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

DAY, BAR = 86400.0, 1e5


def run(name, h0):
    cfg = load_config(SOLVER_ROOT / "examples" / name / "config.json")
    cfg.output.log_level = "ERROR"
    sim, s0 = SimulatorFactory.from_config(cfg)
    if h0 is not None:
        sched = sim._schedule

        def depth(k):
            # как TimeSchedule.first_substep_depth, но интервал 0 — тоже смена
            if k > 0:
                return type(sched).first_substep_depth(sched, k)
            _, dt = sched.substeps(k)
            m = 0
            while dt / 2 ** m > h0:
                m += 1
            return m

        sched.first_substep_depth = depth
    variant1.EVENTS.clear()
    t0 = time.perf_counter()
    hist = sim.run(s0)
    return hist, time.perf_counter() - t0, list(variant1.EVENTS)


def main():
    print(f"код: {Path(gpn_multiphase_solver.__file__).parent}", flush=True)
    name, h0 = sys.argv[1], float(sys.argv[2])
    variant1.install()
    base, t_b, _ = run(name, None)
    ramp, t_r, ev = run(name, h0)
    most = max((e["passes"] for e in ev), default=0)
    print(f"{name}: штатный {t_b:.1f} с; нарастание с первого интервала h0 = {h0:g} с — {t_r:.1f} с, "
          f"вызовов варианта 1 сверх 12 проходов {len(ev)} (наибольший — {most} проходов)", flush=True)
    t = np.array(base.times) / DAY
    for f, scale, unit in (("T", 1.0, "К"), ("Rs", 1.0, "м³/м³"), ("p", 1 / BAR, "бар")):
        a = np.array([getattr(s, f)[0] for s in base.states]) * scale
        b = np.array([getattr(s, f)[0] for s in ramp.states]) * scale
        i = int(np.argmax(np.abs(b - a)))
        print(f"  {f}(r_w): max|Δ| = {abs(b[i] - a[i]):.4f} {unit} при t = {t[i]:.4f} сут "
              f"({a[i]:.4f} → {b[i]:.4f}); первая запись t = {t[1]:.4f} сут: {a[1]:.4f} → {b[1]:.4f}; "
              f"конец: Δ = {b[-1] - a[-1]:+.4f}", flush=True)


if __name__ == "__main__":
    main()
