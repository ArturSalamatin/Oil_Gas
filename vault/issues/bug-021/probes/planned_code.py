"""BUG-021, проба при планировании: код вариантов исправления _newton_fixed_active_set.

NEW_V2 — вариант 2 (проверка сходимости после каждого обновления по невязке ft
принятого приближения линейного поиска; нулевое число обновлений — по f_initial
до цикла). NEW_V1 — вариант 1 (проверка невязки после цикла, одна строка).
Тексты — те же, что в блоках «После» плана vault/plans/bug-021 *.md.

apply(variant) — подменяет метод в памяти (для проб в одном процессе);
patch_text(src, variant) — заменяет текст метода в исходнике blackoil.py (для копии
прототипа, на которой идёт регрессия: run_regression.py запускает каждый кейс
отдельным процессом, подмена в памяти туда не доходит).
"""
import re

# Вариант 2 — рекомендуемый
NEW_V2 = '''    def _newton_fixed_active_set(self,z0,state_old,dt_s,gas_active,max_iter=15,rtol=1e-8,atol_sm3s=1e-11):
        z=np.asarray(z0,float).copy(); f=self.residual(z,state_old,dt_s,gas_active); nrm=np.linalg.norm(f,np.inf)
        scale=max(nrm,1e-9); tol=atol_sm3s+rtol*scale
        # BUG-016: norm of the line search; the convergence test stays on ||F||_inf.
        # With defaults the comparison is norm(ft,inf)<nrm, bitwise as before.
        merit=(lambda v: np.linalg.norm(v)) if self._line_search_l2 else (lambda v: np.linalg.norm(v,np.inf))
        # BUG-021: convergence is tested on every new iterate, the last one included.
        # It used to be tested at the top of the next iteration only, so a solve that
        # converged on update max_iter was reported as failed.  f is residual(z),
        # bitwise the f0 that the Jacobian call returns at the same z: wherever the
        # solve converged before, iterates and reports are unchanged, and the
        # Jacobian that was built only to detect convergence is no longer built.
        if nrm<=tol: return z,BlackOilNewtonReport(True,0,float(nrm))
        for it in range(1,max_iter+1):
            J,f=self.finite_difference_jacobian(z,state_old,dt_s,gas_active)
            try: dz=self._linear_solve(J,-f)
            except Exception: return z,BlackOilNewtonReport(False,it,float(nrm))
            if self._sg_step_max is not None:
                # BUG-016: scale the whole update (p and Sg together, the Newton
                # direction is kept) so that |dSg| of two-phase cells <= limit
                dsg=np.abs(dz[self.grid.n:][gas_active])
                if dsg.size and dsg.max()>self._sg_step_max: dz=dz*(self._sg_step_max/dsg.max())
            mf=merit(f); alpha=1.0; accepted=False
            for _ in range(12):
                trial=z+alpha*dz
                if self._trial_is_reasonable(trial,gas_active):
                    ft=self.residual(trial,state_old,dt_s,gas_active)
                    if merit(ft)<mf: z=trial; f=ft; accepted=True; break
                alpha*=0.5
            if not accepted: return z,BlackOilNewtonReport(False,it,float(nrm))
            nrm=np.linalg.norm(f,np.inf)
            if nrm<=tol: return z,BlackOilNewtonReport(True,it,float(nrm))
        return z,BlackOilNewtonReport(False,max_iter,float(nrm))
'''

# Вариант 1 — для сверки «решения варианта 2 = решения варианта 1» (замена строки после цикла)
OLD_TAIL = ("        f=self.residual(z,state_old,dt_s,gas_active); "
            "return z,BlackOilNewtonReport(False,max_iter,float(np.linalg.norm(f,np.inf)))\n")
NEW_TAIL_V1 = ("        f=self.residual(z,state_old,dt_s,gas_active); nrm=np.linalg.norm(f,np.inf)\n"
               "        return z,BlackOilNewtonReport(bool(nrm<=atol_sm3s+rtol*scale),max_iter,float(nrm))\n")

METHOD_RE = re.compile(r"    def _newton_fixed_active_set\(.*?(?=    def advance\()", re.S)


def patch_text(src, variant):
    """Исходник blackoil.py с методом варианта variant (1 или 2)."""
    m = METHOD_RE.findall(src)
    assert len(m) == 1, f"метод найден {len(m)} раз"
    old = m[0]
    assert old.count(OLD_TAIL) == 1, "хвост метода не тот, что ожидался (код изменился?)"
    new = NEW_V2 if variant == 2 else old.replace(OLD_TAIL, NEW_TAIL_V1)
    return src.replace(old, new)


def apply(variant):
    """Подменить метод в загруженном модуле radial_blackoil.blackoil."""
    import inspect
    import radial_blackoil.blackoil as bo
    src = inspect.getsource(bo.RadialBlackOilModel._newton_fixed_active_set)
    if variant == 2:
        code = NEW_V2
    else:
        assert src.count(OLD_TAIL) == 1, "хвост метода не тот, что ожидался"
        code = src.replace(OLD_TAIL, NEW_TAIL_V1)
    ns = {}
    exec("class _X:\n" + code, bo.__dict__, ns)
    bo.RadialBlackOilModel._newton_fixed_active_set = ns["_X"].__dict__["_newton_fixed_active_set"]
    return bo
