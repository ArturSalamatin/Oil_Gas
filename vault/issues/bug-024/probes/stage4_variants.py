"""BUG-024: варианты обновления R_s недонасыщенных ячеек в ступени 4 (_newton_switching).

Копия _newton_switching (blackoil.py:520-580 на a26706a) с одной правкой — строка обновления
x недонасыщенных ячеек (R_s). В коде базы:
    xn = np.where(mask, x + clip(dz[n:], -ds_max, ds_max), np.maximum(x + dz[n:], 0.0))
шаг по R_s не ограничен, отрицательный R_s обрезается до 0 (замер BUG-024: десятки и сотни
обрезаний на решение, у двух отказов — застой Ньютона с R_s = 0 в ячейке у забоя).
Варианты (install(model, name)):
  base   — копия кода базы без правок (проверка копии: побитово как код);
  satrel — |dR_s| <= DR * R_s^sat(p) (как ds_max = 0.2 для S_g: доля полного размаха R_s), R_s >= 0;
  half   — отрицательный R_s не обрезается до 0, а заменяется половиной текущего: R_s >= R_s/2;
  rel    — |dR_s| <= DR * max(R_s, 1) (относительное ограничение, как drMaxRel OPM Flow), R_s >= 0.
DR — из окружения BUG024_DR (по умолчанию 0.2 для satrel, 0.5 для rel).
"""

import os
import types

import numpy as np

from radial_blackoil.blackoil import BlackOilNewtonReport


def _rs_update(self, name, p, x, dzx, mask):
    """Новое x недонасыщенных ячеек (R_s) по варианту; двухфазные — как в коде базы."""
    if name == "base":
        return np.maximum(x + dzx, 0.0)
    if name == "satrel":
        dr = float(os.environ.get("BUG024_DR", "0.2"))
        lim = dr * np.maximum(self.pvt.rs_sat(p), 1.0)
        return np.maximum(x + np.clip(dzx, -lim, lim), 0.0)
    if name == "half":
        return np.maximum(x + dzx, 0.5 * x)
    if name == "rel":
        dr = float(os.environ.get("BUG024_DR", "0.5"))
        lim = dr * np.maximum(x, 1.0)
        return np.maximum(x + np.clip(dzx, -lim, lim), 0.0)
    if name == "mix":
        # масштаб — большее из R_s^sat(p) и текущего R_s (у забоя при низком p R_s^sat мало,
        # а R_s недонасыщенной ячейки велико)
        dr = float(os.environ.get("BUG024_DR", "0.2"))
        lim = dr * np.maximum(np.maximum(self.pvt.rs_sat(p), x), 1.0)
        return np.maximum(x + np.clip(dzx, -lim, lim), 0.0)
    raise ValueError(name)


def make(name):
    def _newton_switching(self, state_old, dt_s, max_iter=40, rtol=1e-8, atol_sm3s=1e-11, dp_rel=0.3,
                          ds_max=0.2, flips_to_freeze=2):
        state_old = state_old.copy(); n = self.grid.n; nf = max(n - 1, 0)
        mask = state_old.gas_active.copy(); z = self.pack(state_old, mask)
        scale = max(np.linalg.norm(self.residual(z, state_old, dt_s, mask), np.inf), 1e-9); tol = atol_sm3s + rtol * scale
        w = self._cell_weights(state_old, dt_s)
        switched = total = 0; flips = np.zeros(nf, int); prev = None; polish = False
        self._upwind_frozen = np.zeros(nf, bool); self._upwind_left = np.zeros(nf, bool)
        try:
            for it in range(1, max_iter + 2):
                p = z[:n]; left = (p[:-1] - p[1:]) >= 0
                if not polish:
                    if prev is not None: flips += (left != prev) & ~self._upwind_frozen
                    fr = (~self._upwind_frozen) & (flips >= flips_to_freeze)
                    self._upwind_left = np.where(fr, left, self._upwind_left); self._upwind_frozen = self._upwind_frozen | fr
                prev = left
                J, f = self.finite_difference_jacobian(z, state_old, dt_s, mask); nrm = np.linalg.norm(f, np.inf)
                if nrm <= tol and switched == 0:
                    fz = self._upwind_frozen
                    if fz is None or np.array_equal(self._upwind_left[fz], left[fz]):
                        if self._cells_converged(f, w):
                            new = self.unpack(z, mask); new.sg[mask & (new.sg < 0)] = 0.0
                            ok = not np.any(new.sg[mask] > 0.98)
                            return new, BlackOilNewtonReport(ok, it - 1, float(nrm), 1, total)
                    else:
                        self._upwind_frozen = None; polish = True; continue
                if it > max_iter: break
                try: dz = self._linear_solve(J, -f)
                except Exception: break
                x = z[n:]; lim = dp_rel * np.maximum(p, 1.0)
                pn = np.maximum(p + np.clip(dz[:n], -lim, lim), 1.0 + 1e-6)
                # ── правка варианта: обновление R_s недонасыщенных ячеек ──
                xn = np.where(mask, x + np.clip(dz[n:], -ds_max, ds_max), _rs_update(self, name, p, x, dz[n:], mask))
                if not (np.all(np.isfinite(pn)) and np.all(np.isfinite(xn))): break
                xn, mask, switched = self._switch_phases(pn, xn, mask); total += switched
                z = np.concatenate([pn, xn])
            f = self.residual(z, state_old, dt_s, mask)
            return self.unpack(z, mask), BlackOilNewtonReport(False, max_iter, float(np.linalg.norm(f, np.inf)), 1, total)
        finally:
            self._upwind_frozen = None; self._upwind_left = None
    return _newton_switching


def install(model, name):
    """Подменяет _newton_switching экземпляра; лимит итераций — умолчание класса (BUG024_MAX_ITER4)."""
    fn = make(name)
    cls_default = type(model)._newton_switching.__defaults__
    fn.__defaults__ = cls_default
    model._newton_switching = types.MethodType(fn, model)
