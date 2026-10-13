"""DEBT-055, аудит 1: правки плана (шаги 3, 4) применяются к исходникам в памяти.

Исходники проекта не меняются: текст radial_blackoil/blackoil.py и
gpn_multiphase_solver/hydro/prototype_adapter.py читается с диска, к нему применяются
подстановки «До -> После» плана (каждая должна найтись ровно один раз — так проверяется,
что цитаты «До» плана верны), результат исполняется как модуль под прежним именем и
кладётся в sys.modules до сбора тестов. Фабрика импортирует RadialBlackOilModel внутри
функции, адаптер — при импорте фабрики, поэтому подмена действует на модели фабрики.

DEBT055_PATCH: all (по умолчанию) — шаги 3 и 4; proto — только шаг 3 (прототип);
none — без подмены (красное состояние шага 2).

Запуск из numerical_solver/ (основного каталога или worktree):
    .venv\\Scripts\\python -m pytest ..\\vault\\issues\\debt-055\\probes\\audit1 -q -p no:cacheprovider
"""
import os
import sys
import types
from pathlib import Path

SOLVER = Path.cwd()
assert (SOLVER / "gpn_multiphase_solver").is_dir(), "запускать из numerical_solver/"
# numerical_solver — первым: у прототипа тоже есть пакет tests (pythonpath pyproject кладёт
# каталог прототипа в начало sys.path), и «tests.test_prototype_…» иначе ищется там
for _p in (str(SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"), str(SOLVER)):
    while _p in sys.path:
        sys.path.remove(_p)
    sys.path.insert(0, _p)

MODE = os.environ.get("DEBT055_PATCH", "all")

# ── Шаг 3: blackoil.py ──
PROTO_EDITS = [
    # 1. docstring модуля — после абзаца BUG-025
    ("~0.05 s after production with a developed gas zone failed every stage of advance.\n",
     "~0.05 s after production with a developed gas zone failed every stage of advance.\n"
     "DEBT-055: a failed Newton report also carries the rounding limit of the per-cell measure\n"
     "(cell_floor): the measure of |J| @ ulp(z), the change of the residual when every unknown\n"
     "moves by one ulp; the Newton does not get far below it, and it grows as dt.\n"),
    # 2. поле отчёта
    ("    exit_reason: str = ''\n",
     "    exit_reason: str = ''\n"
     "    # DEBT-055: rounding limit of cell_measure on the same iterate -- the per-cell measure of\n"
     "    # |J| @ ulp(z): the unknowns are representable to ulp(z) only, and the Newton stops at\n"
     "    # 0.1-0.4 of it (GPN probes).  J is the last Jacobian of the solve; for the 'max_iter' exit\n"
     "    # of _newton_fixed_active_set it is the Jacobian of the iterate before the last update.\n"
     "    # Only on a failed solve with the per-cell test on; None otherwise ('active_set': no Newton\n"
     "    # failed; 'branch': the Newton converged).\n"
     "    cell_floor: float | None = None\n"),
    # 3. комментарий конструктора
    ("        # the Rs error of a step is estimated by cell_tol*Bo*(gas_residual_scale + Rs).  Far\n"
     "        # below ~eps_mach*PV_max/PV_min the test is not met and steps are split (GPN example\n"
     "        # 17 at cell_tol = 1e-10: 214 rejected steps against 47; the mechanism is not\n"
     "        # established -- both the line search and the stage-4 Newton stall).\n",
     "        # the Rs error of a step is estimated by cell_tol*Bo*(gas_residual_scale + Rs).\n"
     "        # DEBT-055: below a rounding limit the test is not met.  The unknowns are representable\n"
     "        # to ulp(z) only, and the measure does not get far below that of |J| @ ulp(z)\n"
     "        # (cell_floor of a failed report; the Newton stops at 0.1-0.4 of it).  It is the\n"
     "        # pressure term of the face fluxes, ~eps_mach*p*T*lambda*dt/PV_i: it grows as dt and,\n"
     "        # near the well of the log grid, as N^2/ln^2(r_e/r_w) -- not as PV_max/PV_min, as\n"
     "        # BUG-022 assumed.  A step below it fails and is split until the limit drops (GPN\n"
     "        # example 17 at cell_tol = 1e-10: 214 rejected steps against 47; at 1e-8 only N = 350\n"
     "        # with daily steps meets it).\n"),
    # 4. новый метод — после _cell_measure, перед _cells_converged
    ("    def _cells_converged(self,f,w):\n",
     "    def _cell_floor(self,J,z,w):\n"
     "        \"\"\"DEBT-055: rounding limit of the per-cell measure -- _cell_measure of |J| @ ulp(z); None when the test is off or there is no Jacobian.\"\"\"\n"
     "        if w is None or J is None: return None\n"
     "        return self._cell_measure(abs(J)@np.spacing(np.abs(z)),w)\n"
     "    def _cells_converged(self,f,w):\n"),
    # 5. _newton_report
    ("    def _newton_report(self,converged,iterations,nrm,tol,f,w,reason,**fields):\n"
     "        \"\"\"DEBT-054: report of a Newton solve -- ||F||_inf, its absolute tolerance, the per-cell measure of the same f, the exit reason.\"\"\"\n"
     "        return BlackOilNewtonReport(converged,iterations,float(nrm),\n"
     "                                    residual_tol=None if tol is None else float(tol),\n"
     "                                    cell_measure=self._cell_measure(f,w),exit_reason=reason,**fields)\n",
     "    def _newton_report(self,converged,iterations,nrm,tol,f,w,reason,J=None,z=None,**fields):\n"
     "        \"\"\"DEBT-054: report of a Newton solve -- ||F||_inf, its absolute tolerance, the per-cell measure of the same f, the exit reason; DEBT-055: on a failure the rounding limit of the measure at (J, z).\"\"\"\n"
     "        return BlackOilNewtonReport(converged,iterations,float(nrm),\n"
     "                                    residual_tol=None if tol is None else float(tol),\n"
     "                                    cell_measure=self._cell_measure(f,w),exit_reason=reason,\n"
     "                                    cell_floor=None if converged else self._cell_floor(J,z,w),**fields)\n"),
    # 6. _newton_fixed_active_set
    ("        if nrm<=tol and self._cells_converged(f,w): return z,self._newton_report(True,0,nrm,tol,f,w,'converged')\n",
     "        if nrm<=tol and self._cells_converged(f,w): return z,self._newton_report(True,0,nrm,tol,f,w,'converged')\n"
     "        # DEBT-055: the last Jacobian goes into a failure report (rounding limit of the measure)\n"
     "        J=None\n"),
    ("except Exception: return z,self._newton_report(False,it,nrm,tol,f,w,'linear_solver')",
     "except Exception: return z,self._newton_report(False,it,nrm,tol,f,w,'linear_solver',J=J,z=z)"),
    ("if not accepted: return z,self._newton_report(False,it,nrm,tol,f,w,'line_search')",
     "if not accepted: return z,self._newton_report(False,it,nrm,tol,f,w,'line_search',J=J,z=z)"),
    ("return z,self._newton_report(False,max_iter,nrm,tol,f,w,'max_iter')",
     "return z,self._newton_report(False,max_iter,nrm,tol,f,w,'max_iter',J=J,z=z)"),
    # 7. _newton_switching
    ("'converged' if ok else 'sg_bound',\n",
     "'converged' if ok else 'sg_bound',J=J,z=z,\n"),
    ("self._newton_report(False,it-1,np.linalg.norm(f,np.inf),tol,f,w,reason,\n",
     "self._newton_report(False,it-1,np.linalg.norm(f,np.inf),tol,f,w,reason,J=J,z=z,\n"),
    ("            # the per-cell measure are of the scheme the Newton was solving (DEBT-054)\n",
     "            # the per-cell measure are of the scheme the Newton was solving (DEBT-054); the rounding\n"
     "            # limit -- with the Jacobian of the last pass, built at the same z (DEBT-055)\n"),
    # 8. advance, подмена DEBT-030
    ("            # Newton fields too -- the original algorithm's, consistent with its residual.\n",
     "            # Newton fields too -- the original algorithm's, consistent with its residual; and the\n"
     "            # rounding limit of the measure (DEBT-055).\n"),
    ("exit_reason=orig.exit_reason)",
     "exit_reason=orig.exit_reason,cell_floor=orig.cell_floor)"),
]

# ── Шаг 4: prototype_adapter.py, _failure_details ──
ADAPTER_EDITS = [
    ("    measure = getattr(report, \"cell_measure\", None)\n",
     "    measure = getattr(report, \"cell_measure\", None)\n"
     "    floor = getattr(report, \"cell_floor\", None)\n"),
    ("            text += f\" (порог numerics.newton_cell_tol = {cell_tol:g})\"\n",
     "            text += f\" (порог numerics.newton_cell_tol = {cell_tol:g})\"\n"
     "        # DEBT-055: предел округления меры на том же приближении — мера вектора |J|·ulp(z)\n"
     "        # (eq:newton_cell_floor); есть только у отказа Ньютона с условием по ячейке\n"
     "        if floor is not None:\n"
     "            text += f\", предел округления {floor:.2e}\"\n"),
    ("            }[(abs_ok, measure <= cell_tol)]\n",
     "            }[(abs_ok, measure <= cell_tol)]\n"
     "            # DEBT-055: только условие ячейки, и мера не выше предела округления — точнее\n"
     "            # на этом шаге не решить; предел пропорционален шагу, дробление его снимает.\n"
     "            # Сравнение — факт, как и классы выше\n"
     "            if abs_ok and measure > cell_tol and floor is not None and measure <= floor:\n"
     "                text += \", мера не выше предела округления (он пропорционален шагу)\"\n"),
]


def _load(name, package, path, edits):
    """Исполнить исходник path с подстановками edits как модуль name; каждая — ровно один раз."""
    src = path.read_text(encoding="utf-8")
    for old, new in edits:
        n = src.count(old)
        assert n == 1, f"{path.name}: цитата «До» найдена {n} раз: {old[:80]!r}"
        src = src.replace(old, new)
    mod = types.ModuleType(name)
    mod.__file__ = str(path)
    mod.__package__ = package
    sys.modules[name] = mod
    exec(compile(src, str(path), "exec"), mod.__dict__)
    return mod


if MODE in ("all", "proto"):
    import radial_blackoil
    bo = _load("radial_blackoil.blackoil", "radial_blackoil",
               SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3" / "radial_blackoil" / "blackoil.py",
               PROTO_EDITS)
    radial_blackoil.blackoil = bo
if MODE == "all":
    import gpn_multiphase_solver.hydro as hydro_pkg
    ad = _load("gpn_multiphase_solver.hydro.prototype_adapter", "gpn_multiphase_solver.hydro",
               SOLVER / "gpn_multiphase_solver" / "hydro" / "prototype_adapter.py", ADAPTER_EDITS)
    hydro_pkg.prototype_adapter = ad
print(f"\nDEBT-055 audit1: режим подмены {MODE}; SOLVER = {SOLVER}")
