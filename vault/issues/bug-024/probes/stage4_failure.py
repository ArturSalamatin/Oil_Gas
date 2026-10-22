"""BUG-024: почему ступень 4 (_newton_switching) отказывает на суточном останове при условии по ячейке.

Код решателя не меняется: проба оборачивает методы экземпляра модели прототипа.
  _newton_switching           — запись решения: исход, причина отказа;
  finite_difference_jacobian  — итерация ступени 4: ||F||_inf против tol, условие по ячейке
                                max_c |F_c,i| dt/PV_i против cell_tol (ячейка, строка), переключения
                                фаз прошлой итерации, согласованность зафиксированных граней;
  _switch_phases              — какие ячейки сменили набор фаз;
  _linear_solve               — исключения линейного решателя.
Причина отказа (_newton_switching пишет iterations = max_iter при любом отказе, blackoil.py:578):
  лимит        — построено max_iter+1 якобианов (цикл дошёл до конца);
  S_g>0.98     — все условия выполнены, но решение отвергнуто проверкой S_g > 0.98;
  лин.решатель — исключение _linear_solve;
  нечисловое   — цикл прерван раньше лимита без исключения (pn/xn не конечны).

Сценарий — как vault/issues/debt-048/probes/stage_memory.py, режим e2e:
  <конфиг 19|20|21> <n_prod> <n_shut> <A|B> <dt_integration>
  n_prod суточных интервалов добычи при p_wf примера, затем n_shut суток останова
  (A: p_wf = p_ext; B: q_oil = 0, min_bhp = 1 атм).
Окружение:
  BUG024_SOLVER      — numerical_solver проверяемого дерева (по умолчанию основной каталог);
  BUG024_CELL_TOL    — numerics.newton_cell_tol: число или none (условие выключено);
  BUG024_MAX_RETRIES — numerics.max_retries;
  BUG024_MAX_ITER4   — лимит итераций ступени 4 (опыт, подмена умолчания _newton_switching);
  BUG024_ATOL        — atol_sm3s обоих Ньютонов (опыт: возмущение траектории без условия по ячейке);
  BUG024_VARIANT     — вариант обновления R_s в ступени 4 (stage4_variants.py: base, satrel, half, rel);
  BUG024_DR          — параметр варианта;
  BUG024_T_STOP      — остановить расчёт, когда подшаг начинается позже T_STOP сут;
  BUG024_DETAIL      — сколько отказавших решений печатать по итерациям (по умолчанию 6);
  BUG024_TAG         — суффикс имени файла вывода.
Вывод — в stdout и в файл рядом со скриптом (diag_<конфиг><режим>_<dt>_<TAG>.out.txt, UTF-8).

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\bug-024\\probes\\stage4_failure.py 20 10 3 B 86400
"""

import copy
import os
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER = Path(os.environ.get("BUG024_SOLVER", Path.cwd())).resolve()
for p in (SOLVER, SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"):
    sys.path.insert(0, str(p))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

DAY = 86400.0
BAR = 1e5
BASES = {"20": "20_rs300_cooling", "19": "19_rs150_cooling", "21": "21_rs100_cooling"}
TAG = os.environ.get("BUG024_TAG", "")
T_STOP = float(os.environ["BUG024_T_STOP"]) if os.environ.get("BUG024_T_STOP") else None
DETAIL = int(os.environ.get("BUG024_DETAIL", "6"))


class StopProbe(Exception):
    """Остановка по BUG024_T_STOP; не HydroConvergenceError — Simulator её не ловит."""


class Tee:
    def __init__(self, path):
        self.f = open(path, "w", encoding="utf-8")

    def __call__(self, *a):
        line = " ".join(str(x) for x in a)
        print(line, flush=True)
        self.f.write(line + "\n")
        self.f.flush()


class Trace:
    """Журнал решений ступени 4."""

    def __init__(self, model, max_iter):
        self.m = model
        self.max_iter = max_iter
        self.solves = []      # словари по решению
        self.cur = None       # текущее решение
        self.t = self.h = None
        m = model
        base_ns = m._newton_switching
        base_jac = m.finite_difference_jacobian
        base_sw = m._switch_phases
        base_ls = m._linear_solve
        base_cc = m._cells_converged

        def newton_switching(state_old, dt_s, *a, **kw):
            n = m.grid.n
            mask = state_old.gas_active.copy()
            # tol — как в _newton_switching (blackoil.py:538) при умолчаниях rtol, atol
            f0 = m.residual(m.pack(state_old, mask), state_old, dt_s, mask)
            tol = 1e-11 + 1e-8 * max(np.linalg.norm(f0, np.inf), 1e-9)
            w = m._cell_weights(state_old, dt_s)
            self.cur = {"t": self.t, "h": dt_s, "n": n, "tol": tol, "w": w, "its": [],
                        "switched": 0, "lin_exc": False, "cc_true": False,
                        "n2_old": int(np.count_nonzero(mask))}
            new, rep = base_ns(state_old, dt_s, *a, **kw)
            c = self.cur
            c["conv"] = bool(rep.converged)
            nj = len(c["its"])
            if c["conv"]:
                c["why"] = "сошлось"
            elif c["cc_true"]:
                c["why"] = "S_g>0.98"
            elif c["lin_exc"]:
                c["why"] = "лин.решатель"
            elif nj >= self.max_iter + 1:
                c["why"] = "лимит"
            else:
                c["why"] = "нечисловое"
            c["n_jac"] = nj
            del c["w"]
            self.solves.append(c)
            self.cur = None
            return new, rep

        def jac(z, state_old, dt_s, mask, *a, **kw):
            J, f = base_jac(z, state_old, dt_s, mask, *a, **kw)
            c = self.cur
            if c is not None and m._phase_switching:
                n = c["n"]
                nrm = float(np.linalg.norm(f, np.inf))
                rec = {"nrm": nrm, "sw": c["switched"], "n2": int(np.count_nonzero(mask))}
                # недонасыщенные ячейки с R_s = 0: отсечка np.maximum(x + dz, 0) обновления
                # (blackoil.py:573) или отсечка формулы выхода из двухфазных (_switch_phases)
                rec["rs0"] = int(np.count_nonzero(~mask & (z[n:] == 0.0)))
                p = z[:n]
                left = (p[:-1] - p[1:]) >= 0
                fz = m._upwind_frozen
                rec["polish"] = fz is None
                rec["nfz"] = 0 if fz is None else int(np.count_nonzero(fz))
                rec["fz_ok"] = fz is None or bool(np.array_equal(m._upwind_left[fz], left[fz]))
                if c["w"] is not None:
                    w = c["w"]
                    eo, eg = np.abs(f[:n]) * w, np.abs(f[n:]) * w
                    io, ig = int(np.argmax(eo)), int(np.argmax(eg))
                    if eo[io] >= eg[ig]:
                        rec["cell"], rec["row"], rec["ce"] = io, "o", float(eo[io])
                    else:
                        rec["cell"], rec["row"], rec["ce"] = ig, "g", float(eg[ig])
                    i = rec["cell"]
                    rec["cell_2ph"] = bool(mask[i])
                    rec["cell_x"] = float(z[n + i])
                    rec["cell_p"] = float(p[i])
                    # вторая по величине ячейка (по max из двух строк) — один ли нарушитель
                    e = np.maximum(eo, eg)
                    rec["n_bad"] = None   # заполняется ниже, когда известен cell_tol
                    rec["e_all"] = e
                c["switched"] = 0
                c["its"].append(rec)
                c["z"], c["mask"], c["state_old"] = z, mask, state_old
            return J, f

        def switch_phases(p, x, mask):
            x2, m2, k = base_sw(p, x, mask)
            c = self.cur
            if c is not None:
                c["switched"] = k
                # выход из двухфазных с отсечкой R_s до 0 формулой закрытого флэша
                c["deact_rs0"] = c.get("deact_rs0", 0) + int(np.count_nonzero(mask & ~m2 & (x2 == 0.0)))
                # R_s = 0 у недонасыщенных до переключения — от отсечки обновления
                c["upd_rs0"] = c.get("upd_rs0", 0) + int(np.count_nonzero(~mask & (x == 0.0)))
                if k and c["its"]:
                    ch = np.flatnonzero(m2 != mask)
                    c["its"][-1]["sw_cells"] = ch[:8].tolist()
                    c["its"][-1]["sw_on"] = int(np.count_nonzero(m2 & ~mask))
                    c["its"][-1]["sw_off"] = int(np.count_nonzero(mask & ~m2))
            return x2, m2, k

        def linear_solve(J, b):
            try:
                dz = base_ls(J, b)
            except Exception:
                if self.cur is not None:
                    self.cur["lin_exc"] = True
                raise
            c = self.cur
            if c is not None and m._phase_switching and "z" in c and c["its"]:
                # недонасыщенные ячейки с R_s = 0: куда тянет их R_s направление Ньютона
                n = c["n"]
                z, mask, so = c["z"], c["mask"], c["state_old"]
                idx = np.flatnonzero(~mask & (z[n:] == 0.0))
                if idx.size:
                    p = z[:n][idx]
                    c["its"][-1]["rs0_info"] = [
                        (int(i), float(dz[n + i]), float(p[k]), float(m.pvt.rs_sat(np.array([p[k]]))[0]),
                         bool(so.gas_active[i]), float(so.sg[i]), float(so.rs_sm3_sm3[i]))
                        for k, i in enumerate(idx[:3])]
            return dz

        def cells_converged(f, w):
            r = base_cc(f, w)
            if self.cur is not None and m._phase_switching and r:
                self.cur["cc_true"] = True
            return r

        m._newton_switching = newton_switching
        m.finite_difference_jacobian = jac
        m._switch_phases = switch_phases
        m._linear_solve = linear_solve
        m._cells_converged = cells_converged


def describe(c, cell_tol, out, detail):
    """Сводка решения и, при detail, трасса итераций."""
    its = c["its"]
    tol = c["tol"]
    g = [k for k, r in enumerate(its) if r["nrm"] <= tol]
    # итерации, где выполнено глобальное условие: что мешало принять
    blk = Counter()
    for k in g:
        r = its[k]
        if r["sw"] > 0:
            blk["перекл."] += 1
        elif not r["fz_ok"]:
            blk["грани"] += 1
        elif cell_tol is not None and r.get("ce", 0.0) > cell_tol:
            blk["ячейка"] += 1
    ce_g = [its[k]["ce"] for k in g if "ce" in its[k] and its[k]["sw"] == 0 and its[k]["fz_ok"]]
    t = c["t"] / DAY if c["t"] is not None else float("nan")
    why = c["why"]
    if why == "лимит" and len(its) >= 6:
        # застой: ||F|| последних 6 итераций в пределах 25 %, без переключений фаз
        last = its[-6:]
        nr = [r["nrm"] for r in last]
        if max(nr) <= 1.25 * min(nr) and all(r["sw"] == 0 for r in last[1:]):
            why = f"лимит:застой R_s0={last[-1]['rs0']}"
        else:
            why = "лимит:хаос"
    c["why2"] = why
    tail = f" | min усл.ячейки при ||F||<=tol и без перекл.: {min(ce_g):.2e}" if ce_g else ""
    out(f"  t = {t:.5f} сут, h = {c['h']:8.2f} с | {why:<12} | якобианов {c['n_jac']:>3} | "
        f"R_s=0: из обновления {c.get('upd_rs0', 0)}, из выхода {c.get('deact_rs0', 0)} | "
        f"двухфазных {c['n2_old']} | tol {tol:.2e} | ||F||<=tol с итерации "
        f"{g[0] if g else '—'} ({len(g)} раз) | мешало: {dict(blk) if blk else '—'}{tail}")
    if not detail:
        return
    out("     ит | ||F||/tol | усл.ячейки | ячейка стр. 2ф   p, бар       x | >cell_tol | двухф. | перекл. (вкл/выкл) | заф.граней | согл. | R_s=0")
    for k, r in enumerate(its):
        e = r.get("e_all")
        nb = int(np.count_nonzero(e > cell_tol)) if (e is not None and cell_tol is not None) else -1
        sw = ""
        if "sw_cells" in r:
            sw = f"{r['sw_on']}/{r['sw_off']} {r['sw_cells']}"
        cell = (f"{r['cell']:>6} {r['row']:>3} {'да' if r['cell_2ph'] else 'нет':>3} "
                f"{r['cell_p']:8.3f} {r['cell_x']:9.3e}") if "cell" in r else " " * 33
        out(f"    {k:>3} | {r['nrm'] / tol:9.2e} | {r.get('ce', float('nan')):10.2e} | {cell} | "
            f"{nb:>9} | {r['n2']:>6} | {sw:<18} | {'полир.' if r['polish'] else r['nfz']:>10} | "
            f"{'да' if r['fz_ok'] else 'НЕТ':>5} | {r['rs0']}")
        if "rs0_info" in r and k >= len(its) - 2:
            # ячейка, dR_s Ньютона, p, R_s^sat(p), старое состояние: двухфазная, S_g, R_s
            out("           R_s=0: " + "; ".join(
                f"яч.{i} dR_s={d:+.3e} p={pp:.3f} R_s^sat={rsat:.2f} старое: {'2ф' if a else '1ф'} "
                f"S_g={sg:.4f} R_s={rs:.2f}" for i, d, pp, rsat, a, sg, rs in r["rs0_info"]))


def main(args):
    from gpn_multiphase_solver.factory import SimulatorFactory
    from gpn_multiphase_solver.io.config import load_config
    base_key, n_prod, n_shut, mode, dt_int = args
    n_prod, n_shut, dt_int = int(n_prod), int(n_shut), float(dt_int)
    out = Tee(HERE / f"diag_{base_key}{mode}_{dt_int:.0f}{TAG}.out.txt")
    cfg = load_config(SOLVER / "examples" / BASES[base_key] / "config.json")
    cfg.output.log_level = "ERROR"
    iv = cfg.time.history[0]
    p_ext = cfg.initial_conditions.p0
    hist = []
    for _ in range(n_prod):
        x = copy.deepcopy(iv); x.dt = DAY; hist.append(x)
    for _ in range(n_shut):
        x = copy.deepcopy(iv); x.dt = DAY
        if mode == "A":
            x.control, x.p_wf = "pressure", p_ext
        else:
            x.control, x.p_wf, x.q_oil, x.min_bhp = "rate", None, 0.0, 101325.0
        hist.append(x)
    cfg.time.history = hist
    cfg.time.dt_integration = dt_int
    if os.environ.get("BUG024_MAX_RETRIES"):
        cfg.numerics.max_retries = int(os.environ["BUG024_MAX_RETRIES"])
    if os.environ.get("BUG024_CELL_TOL"):
        v = os.environ["BUG024_CELL_TOL"]
        cfg.numerics.newton_cell_tol = None if v == "none" else float(v)
    sim, init = SimulatorFactory.from_config(cfg)
    model = sim._hydro._model
    assert model.phase_switching_stage is True
    max_iter = 40
    if os.environ.get("BUG024_MAX_ITER4"):
        # max_iter — первый параметр по умолчанию _newton_switching (blackoil.py:520)
        max_iter = int(os.environ["BUG024_MAX_ITER4"])
        f = type(model)._newton_switching
        d = list(f.__defaults__); d[0] = max_iter; f.__defaults__ = tuple(d)
    if os.environ.get("BUG024_ATOL"):
        # atol_sm3s — третий параметр по умолчанию обоих Ньютонов (как DEBT048_ATOL в
        # debt-048/probes/stage_memory.py): малое возмущение траектории без условия по ячейке
        for name in ("_newton_fixed_active_set", "_newton_switching"):
            f = getattr(type(model), name)
            d = list(f.__defaults__); d[2] = float(os.environ["BUG024_ATOL"]); f.__defaults__ = tuple(d)
    variant = os.environ.get("BUG024_VARIANT", "")
    if variant:
        # копия _newton_switching с правкой обновления R_s (stage4_variants.py)
        sys.path.insert(0, str(HERE))
        import stage4_variants
        stage4_variants.install(model, variant)
    tr = Trace(model, max_iter)
    base_solve = sim._hydro.solve

    def solve(state, h, bc):
        if T_STOP is not None and state.t / DAY > T_STOP:
            raise StopProbe()
        tr.t, tr.h = state.t, h
        return base_solve(state, h, bc)

    sim._hydro.solve = solve
    import gpn_multiphase_solver, radial_blackoil
    out(f"    код: {Path(gpn_multiphase_solver.__file__).parent}, {Path(radial_blackoil.__file__).parent}")
    cell_tol = cfg.numerics.newton_cell_tol
    out(f"=== {BASES[base_key]}: {n_prod} сут добычи + {n_shut} сут останова ({mode}); "
        f"dt_integration = {dt_int:.0f} с, max_retries = {cfg.numerics.max_retries}, "
        f"newton_cell_tol = {cell_tol}, лимит ступени 4 = {max_iter}, "
        f"atol = {os.environ.get('BUG024_ATOL', '1e-11')}, вариант ступени 4 = {variant or 'код'}"
        f"{', DR = ' + os.environ['BUG024_DR'] if os.environ.get('BUG024_DR') else ''}"
        f"{', останов расчёта после ' + str(T_STOP) + ' сут' if T_STOP else ''} ===")
    t0 = time.perf_counter()
    try:
        h = sim.run(init)
        # отпечаток истории — как fingerprint в debt-048/probes/stage_memory.py
        import hashlib
        hs = hashlib.sha256()
        for s in h.states:
            for a in (s.p, s.T, s.Sg, s.Rs):
                hs.update(np.ascontiguousarray(a, dtype=float).tobytes())
        hs.update(np.asarray(h.times, float).tobytes())
        hs.update(np.asarray([w.q_o_std for w in h.well_data], float).tobytes())
        status = (f"✓ отпечаток {hs.hexdigest()[:16]}; p(r_w) = {h.states[-1].p[0] / BAR:.4f} бар, "
                  f"T(r_w) = {h.states[-1].T[0]:.5f} К")
    except StopProbe:
        status = f"остановлен на T_STOP = {T_STOP} сут"
    except RuntimeError as e:
        status = f"✗ {str(e)[:170]}"
    out(f"итог: {status}; счёт {time.perf_counter() - t0:.0f} с")
    why = Counter(c["why"] for c in tr.solves)
    out(f"решений ступени 4: {len(tr.solves)}; исходы: {dict(why)}; якобианов ступени 4: "
        f"{sum(c['n_jac'] for c in tr.solves)}")
    shown = 0
    for c in tr.solves:
        det = (c["why"] != "сошлось") and shown < DETAIL
        if os.environ.get("BUG024_DETAIL_ALL"):
            det = True
        shown += det
        describe(c, cell_tol, out, det)
    why2 = Counter(c["why2"].split(" R_s0")[0] for c in tr.solves)
    out(f"исходы с видом отказа: {dict(why2)}")


if __name__ == "__main__":
    main(sys.argv[1:])
