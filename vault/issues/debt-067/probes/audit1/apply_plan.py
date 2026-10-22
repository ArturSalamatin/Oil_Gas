"""DEBT-067, аудит 1: правки плана — на копии отслеживаемого дерева numerical_solver.

Копия — `git archive HEAD numerical_solver` в audit1/tree (удаляется после аудита). Правки
шагов 1–4 плана применяются подстановками «До -> После»: каждая цитата «До» должна найтись
ровно один раз (так проверяется, что цитаты плана верны). Правки, которые план описывает
словами (monkeypatch в 8 тестах, докстринги), — по описанию.

Режим: 2 — шаги 1–2 (красное состояние), 4 — шаги 1–4 (целевое).
Запуск из корня проекта:
    numerical_solver\\.venv\\Scripts\\python vault\\issues\\debt-067\\probes\\audit1\\apply_plan.py 2|4
"""
import io
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
STAGE = int(sys.argv[1])
# своя копия на режим: каталог, где стоит сессия оболочки, Windows удалить не даёт
TREE = HERE / f"tree{STAGE}"
NS = TREE / "numerical_solver"

if TREE.exists():
    shutil.rmtree(TREE)
TREE.mkdir()
tar = subprocess.run(["git", "-C", str(ROOT), "archive", "--format=tar", "HEAD", "numerical_solver"],
                     check=True, capture_output=True).stdout
tarfile.open(fileobj=io.BytesIO(tar)).extractall(TREE)
head = subprocess.run(["git", "-C", str(ROOT), "log", "--oneline", "-1"], capture_output=True,
                      text=True).stdout.strip()
print(f"копия HEAD: {head}")


def edit(rel, old, new):
    p = NS / rel
    src = p.read_text(encoding="utf-8")
    n = src.count(old)
    assert n == 1, f"{rel}: цитата «До» найдена {n} раз: {old[:90]!r}"
    p.write_text(src.replace(old, new), encoding="utf-8")


def add_kappa0(rel, name, comment):
    """monkeypatch CELL_FLOOR_KAPPA = 0 первой строкой тела теста name (шаг 2 плана)."""
    p = NS / rel
    src = p.read_text(encoding="utf-8")
    assert src.count(f"def {name}(") == 1, f"{rel}: тест {name} не единственный"
    i = src.index(f"def {name}(")
    j = src.index("):", i)
    if "monkeypatch" not in src[i:j]:
        # пустой список параметров — без запятой
        src = src[:j] + (", monkeypatch" if src[j - 1] != "(" else "monkeypatch") + src[j:]
    line_start = src.rindex("\n", 0, i) + 1
    indent = " " * (i - line_start + 4)
    k = src.index('"""', i)
    k2 = src.index('"""', k + 3) + 3
    k2 = src.index("\n", k2) + 1
    ins = "".join(f"{indent}# {c}\n" for c in comment)
    ins += f'{indent}monkeypatch.setattr(blackoil, "CELL_FLOOR_KAPPA", 0.0)\n'
    p.write_text(src[:k2] + ins + src[k2:], encoding="utf-8")


BO = "HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/blackoil.py"

# ═══ Шаг 1: постановка ═══
edit("doc/problem_statement.tex",
     "предел убывает как $\\ln^{-2}(R_{\\text{ext}}/r_w)$. В~отличие от~предела абсолютного\n"
     "условия~\\eqref{eq:newton_abs_tol}, который растёт с~уменьшением шага, этот растёт\n"
     "с~его увеличением. Шаг, на~котором порог ниже предела, отвергается и~дробится, пока\n"
     "предел не~опустится ниже порога; в~расчётах проекта с~порогом по~умолчанию так было\n"
     "лишь при $N = 350$ и~суточном шаге.\n",
     (HERE / "tex_after.txt").read_text(encoding="utf-8"))

# ═══ Шаг 2: константа и тесты ═══
edit(BO, "ROUNDOFF_KAPPA=4.0\n",
     "ROUNDOFF_KAPPA=4.0\n"
     "# DEBT-067: factor of the rounding limit in the per-cell test (_cells_converged): a row above\n"
     "# cell_tol passes when |F_r| <= CELL_FLOOR_KAPPA*(|J| @ ulp(z))_r; 0 -- the strict test of BUG-022\n"
     "CELL_FLOOR_KAPPA=1.0\n")
shutil.copy(HERE / "test_prototype_cell_floor.py", NS / "tests" / "test_prototype_cell_floor.py")

FD = "tests/test_prototype_failure_diagnostics.py"
C_FAIL = ["DEBT-067: отказ на пределе округления — предел в условии выключен (строгое условие",
          "BUG-022); тест проверяет отчёт и текст отказа, а не сходимость"]
C_1E30 = ["DEBT-067: предел выключен — с ним отказ при 1e-30 тоже есть (8 строк у контура",
          "на округлении накопления, tiny_tol.out.txt), но случайно"]
for name, c in (("test_limit_only_cell_test", C_1E30), ("test_real_total_failure_only_cell_test", C_FAIL),
                ("test_bug018_failure_at_floor", C_FAIL), ("test_floor_proportional_to_dt", C_FAIL),
                ("test_switching_limit_stops_at_floor", C_1E30), ("test_adapter_message_cell_test_only", C_FAIL),
                ("test_simulator_message_ends_with_adapter_text", C_FAIL)):
    add_kappa0(FD, name, c)
edit(FD, "vault/issues/debt-055/probes/.\n\"\"\"\n",
     "vault/issues/debt-055/probes/.\n\n"
     "DEBT-067: строка выше порога проходит, если её невязка не выше её предела\n"
     "(eq:newton_cell_tol_floor, CELL_FLOOR_KAPPA = 1): сутки BUG-018 при N = 350 сходятся.\n"
     "Тесты отказа на пределе выключают предел (monkeypatch CELL_FLOOR_KAPPA = 0) — проверяют\n"
     "отчёт и текст отказа, а не сходимость. План: vault/plans/debt-067 accept-at-cell-floor.md.\n"
     "\"\"\"\n")

CT = "tests/test_prototype_cell_tolerance.py"
edit(CT, "from radial_blackoil.blackoil import RadialBlackOilModel\n",
     "from radial_blackoil import blackoil\nfrom radial_blackoil.blackoil import RadialBlackOilModel\n")
add_kappa0(CT, "test_switching_meets_cell_tol", C_1E30)

AC = "tests/test_prototype_activation_cap.py"
edit(AC,
     "        assert calls == [(86400.0, False), (43200.0, False), (21600.0, True),\n"
     "                         (21600.0, True), (43200.0, True)]\n"
     "        st = h.states[-1]\n"
     "        assert st.Sg[0] == pytest.approx(0.419040, abs=1e-5)\n"
     "        assert st.p[0] == pytest.approx(5.141098e6, abs=100.0)\n",
     "        assert calls == [(86400.0, True)]\n"
     "        st = h.states[-1]\n"
     "        assert st.Sg[0] == pytest.approx(0.417217, abs=1e-5)\n"
     "        assert st.p[0] == pytest.approx(5.140841e6, abs=100.0)\n")

PS = "tests/test_prototype_phase_switching.py"
edit(PS,
     "        assert len(ok) == 10 and len(failed) == 7\n"
     "        assert sum(ok) == pytest.approx(3 * DAY, rel=1e-12)   # трое суток пройдены ровно один раз\n"
     "        assert min(ok) == 5400.0\n"
     "        assert st.p[0] / BAR == pytest.approx(327.2428, abs=1e-3)\n"
     "        assert st.T[0] == pytest.approx(375.3667, abs=1e-3)\n",
     "        assert len(ok) == 6 and len(failed) == 3\n"
     "        assert sum(ok) == pytest.approx(3 * DAY, rel=1e-12)   # трое суток пройдены ровно один раз\n"
     "        assert min(ok) == 21600.0\n"
     "        assert st.p[0] / BAR == pytest.approx(326.7378, abs=1e-3)\n"
     "        assert st.T[0] == pytest.approx(375.3124, abs=1e-3)\n")
edit(PS, "max_retries = 9 (~6 с).", "max_retries = 9 (~4 с).")
edit(PS, "        Давление ниже, чем при шаге 1 ч (328.10 бар), — погрешность суточного шага.\n",
     "        Давление ниже, чем при шаге 1 ч (328.10 бар), — погрешность суточного шага.\n"
     "        DEBT-067 (решение на пределе округления принимается): 9 вызовов, 3 отказа, принято 6\n"
     "        подшагов, наименьший 21600 с; p(r_w) = 326.7378 бар, T(r_w) = 375.3124 К (замер плана,\n"
     "        variants.py, daily_shutin). Ушли 4 отказа второго дня: суточный шаг, отвергнутый\n"
     "        ступенью 4 по памяти на пределе (мера 1.29e-8, предел 4.67e-8), и три его дробления.\n"
     "        Давление дальше от шага 1 ч: дробление от отказа уменьшало погрешность суточного шага,\n"
     "        теперь шаг — тот, что задан конфигом.\n")

# Проверка путей: код и прототип — из копии (временный тест, только в копии)
(NS / "tests" / "test_zz_audit_paths.py").write_text(
    "from pathlib import Path\n"
    "import gpn_multiphase_solver, radial_blackoil\n\n\n"
    "def test_paths_are_copy():\n"
    f"    root = Path(r'{TREE}')\n"
    "    for m in (gpn_multiphase_solver, radial_blackoil):\n"
    "        assert root in Path(m.__file__).resolve().parents, m.__file__\n", encoding="utf-8")

if STAGE >= 4:
    # ═══ Шаг 3: прототип ═══
    edit(BO, "moves by one ulp; the Newton does not get far below it, and it grows as dt.\n\"\"\"\n",
         "moves by one ulp; the Newton does not get far below it, and it grows as dt.\n"
         "DEBT-067: a row of the per-cell test above cell_tol passes at its rounding limit,\n"
         "|F_r| <= CELL_FLOOR_KAPPA*(|J| @ ulp(z))_r (J -- the last Jacobian of the solve): a solve the\n"
         "round-off does not let below cell_tol is accepted, not split.\n\"\"\"\n")
    edit(BO,
         "    # DEBT-055: rounding limit of cell_measure on the same iterate -- the per-cell measure of\n"
         "    # |J| @ ulp(z): the unknowns are representable to ulp(z) only, and the Newton stops at\n"
         "    # 0.1-0.4 of it (GPN probes).  J is the last Jacobian of the solve; for the 'max_iter' exit\n"
         "    # of _newton_fixed_active_set it is the Jacobian of the iterate before the last update.\n"
         "    # Only on a failed solve with the per-cell test on; None otherwise ('active_set': no Newton\n"
         "    # failed; 'branch': the Newton converged).\n",
         "    # DEBT-055: rounding limit of cell_measure on the same iterate -- the per-cell measure of\n"
         "    # |J| @ ulp(z): the unknowns are representable to ulp(z) only, and the Newton stops at\n"
         "    # 0.1-0.46 of it (GPN probes).  J is the last Jacobian of the solve; for the 'max_iter' exit\n"
         "    # of _newton_fixed_active_set and for its solve accepted after an update it is the Jacobian\n"
         "    # of the iterate before the last update.  Only with the per-cell test on, on a failed solve\n"
         "    # or (DEBT-067) on a solve accepted at the limit (converged with cell_measure > cell_tol);\n"
         "    # None otherwise ('active_set': no Newton failed; 'branch': the Newton converged).\n")
    edit(BO,
         "        # near the well of the log grid, as N^2/ln^2(r_e/r_w) -- not as PV_max/PV_min, as\n"
         "        # BUG-022 assumed.  A step below it fails and is split until the limit drops (GPN\n"
         "        # example 17 at cell_tol = 1e-10: 214 rejected steps against 47; at 1e-8 only N = 350\n"
         "        # with daily steps meets it).\n",
         "        # near the well of the log grid, as N^2/ln^2(r_e/r_w) -- not as PV_max/PV_min, as\n"
         "        # BUG-022 assumed.  DEBT-067: a row above cell_tol passes when |F_r| is not above its\n"
         "        # own limit (_cells_converged, CELL_FLOOR_KAPPA), so such a step is accepted, not split\n"
         "        # until the limit drops: GPN example 17 at cell_tol = 1e-10 -- 7 rejected steps against\n"
         "        # 205, Jacobians /3.1; at 1e-8 the limit is above cell_tol only at N = 350 with daily\n"
         "        # steps.  The storage round-off ~eps*M/dt is not in the limit: cell_tol below ~1e-15\n"
         "        # stays unreachable.\n")
    edit(BO,
         "    def _cells_converged(self,f,w):\n"
         "        \"\"\"BUG-022: max_c |f_c,i|*dt/PV_i <= cell_tol over the oil and gas rows of f = residual(); True when the test is off.\"\"\"\n"
         "        # the same operations as before DEBT-054, so the test is bitwise unchanged\n"
         "        m=self._cell_measure(f,w)\n"
         "        return m is None or m<=self.cell_tol\n",
         "    def _cells_converged(self,f,w,J=None,z=None):\n"
         "        \"\"\"BUG-022: max_c |f_c,i|*dt/PV_i <= cell_tol over the oil and gas rows of f = residual(); True when the test is off; DEBT-067: a row above cell_tol passes when |f_r| <= CELL_FLOOR_KAPPA*(|J| @ ulp(z))_r.\"\"\"\n"
         "        # the same operations as before DEBT-054, so the test is bitwise unchanged\n"
         "        m=self._cell_measure(f,w)\n"
         "        if m is None or m<=self.cell_tol: return True\n"
         "        # DEBT-067: every row above cell_tol against its own rounding limit -- the Newton does\n"
         "        # not get below 0.28-0.46 of it (GPN probes).  Row by row: with maxima over the grid a\n"
         "        # row would pass at the limit of another cell (BUG-018: measure in o16, limit in g13).\n"
         "        # No Jacobian (the test before the first iteration) or CELL_FLOOR_KAPPA = 0: strict.\n"
         "        if J is None or z is None or not CELL_FLOOR_KAPPA>0.0: return False\n"
         "        # ~(<=): a NaN row counts as above cell_tol and fails below (np.all of an empty selection is True)\n"
         "        a=np.abs(f); bad=~(a*np.concatenate([w,w])<=self.cell_tol)\n"
         "        return bool(np.all(a[bad]<=CELL_FLOOR_KAPPA*(abs(J)@np.spacing(np.abs(z)))[bad]))\n")
    edit(BO,
         "        \"\"\"DEBT-054: report of a Newton solve -- ||F||_inf, its absolute tolerance, the per-cell measure of the same f, the exit reason; DEBT-055: on a failure the rounding limit of the measure at (J, z).\"\"\"\n"
         "        return BlackOilNewtonReport(converged,iterations,float(nrm),\n"
         "                                    residual_tol=None if tol is None else float(tol),\n"
         "                                    cell_measure=self._cell_measure(f,w),exit_reason=reason,\n"
         "                                    cell_floor=None if converged else self._cell_floor(J,z,w),**fields)\n",
         "        \"\"\"DEBT-054: report of a Newton solve -- ||F||_inf, its absolute tolerance, the per-cell measure of the same f, the exit reason; DEBT-055: on a failure the rounding limit of the measure at (J, z); DEBT-067: also on a solve accepted at the limit.\"\"\"\n"
         "        m=self._cell_measure(f,w)\n"
         "        # DEBT-067: converged with the measure above cell_tol -- accepted at the rounding limit\n"
         "        at_limit=converged and m is not None and m>self.cell_tol\n"
         "        return BlackOilNewtonReport(converged,iterations,float(nrm),\n"
         "                                    residual_tol=None if tol is None else float(tol),\n"
         "                                    cell_measure=m,exit_reason=reason,\n"
         "                                    cell_floor=self._cell_floor(J,z,w) if (not converged or at_limit) else None,**fields)\n")
    edit(BO,
         "        if nrm<=tol and self._cells_converged(f,w): return z,self._newton_report(True,0,nrm,tol,f,w,'converged')\n",
         "        # DEBT-067: no Jacobian before the first iteration -- the strict per-cell test\n"
         "        if nrm<=tol and self._cells_converged(f,w): return z,self._newton_report(True,0,nrm,tol,f,w,'converged')\n")
    edit(BO,
         "        # DEBT-055: the last Jacobian goes into a failure report (rounding limit of the measure)\n",
         "        # DEBT-055: the last Jacobian goes into a failure report (rounding limit of the measure)\n"
         "        # and (DEBT-067) into the per-cell test after an update: the Jacobian of the iterate\n"
         "        # before it; its limit and that of the Jacobian at the new iterate agreed within 0.1 %\n"
         "        # in 325 GPN acceptances\n")
    edit(BO,
         "            if nrm<=tol and self._cells_converged(f,w): return z,self._newton_report(True,it,nrm,tol,f,w,'converged')\n",
         "            if nrm<=tol and self._cells_converged(f,w,J,z): return z,self._newton_report(True,it,nrm,tol,f,w,'converged',J=J,z=z)\n")
    edit(BO,
         "                        # BUG-022: and the per-cell test; not met -- iterate on (up to max_iter)\n"
         "                        if self._cells_converged(f,w):\n",
         "                        # BUG-022: and the per-cell test; not met -- iterate on (up to max_iter);\n"
         "                        # DEBT-067: a row above cell_tol at its rounding limit passes (J built at z)\n"
         "                        if self._cells_converged(f,w,J,z):\n")

    # ═══ Шаг 4: документы и комментарии ═══
    edit("gpn_multiphase_solver/io/config.py",
         "    # Предел округления (DEBT-055, eq:newton_cell_floor): неизвестные представимы с шагом\n"
         "    # ulp, и меру нельзя сделать меньше доли меры вектора |J|·ulp(z) — Ньютон встаёт на\n"
         "    # 0.1–0.4 её. Это давление в потоках через грани, ~2.2e-16·p·T·λ·Δt/V_p: предел растёт\n"
         "    # как Δt и у забоя логарифмической сетки как N²/ln²(R_ext/r_w) (с ростом R_ext при том\n"
         "    # же N — убывает). Шаг ниже предела отвергается и дробится, пока предел не опустится:\n"
         "    # у 17 при 1e-10 отказов шагов 214 против 47, якобианов ×2.9; при 1e-8 — лишь у N = 350\n"
         "    # с шагом 1 сут (пример 14, BUG-018). Предел шага — в тексте отказа. null — выкл.\n",
         "    # Предел округления (DEBT-055, eq:newton_cell_floor): неизвестные представимы с шагом\n"
         "    # ulp, и меру нельзя сделать меньше доли меры вектора |J|·ulp(z) — Ньютон встаёт на\n"
         "    # 0.1–0.46 её. Это давление в потоках через грани, ~2.2e-16·p·T·λ·Δt/V_p: предел растёт\n"
         "    # как Δt и у забоя логарифмической сетки как N²/ln²(R_ext/r_w) (с ростом R_ext при том\n"
         "    # же N — убывает). Строка выше порога проходит, если её невязка не выше её предела\n"
         "    # (DEBT-067, eq:newton_cell_tol_floor): такой шаг принимается, а не дробится. У 17 при\n"
         "    # 1e-10 отклонённых шагов 7 против 205, якобианов в 3.1 раза меньше; при 1e-8 предел\n"
         "    # выше порога лишь у N = 350 с шагом 1 сут (пример 14). Порог ниже ~1e-15 недостижим\n"
         "    # и с пределом (округление накопления). Предел шага — в тексте отказа. null — выкл.\n")
    edit("gpn_multiphase_solver/hydro/prototype_adapter.py",
         "            # DEBT-055: только условие ячейки, и мера не выше предела округления — точнее\n"
         "            # на этом шаге не решить; предел пропорционален шагу, дробление его снимает.\n"
         "            # Сравнение — факт, как и классы выше (максимумы по сетке; в отказах на\n"
         "            # пределе, замеренных планом, оно верно и поячеечно)\n",
         "            # DEBT-055: только условие ячейки, и мера не выше предела округления; предел\n"
         "            # пропорционален шагу, дробление его снимает. Сравнение — факт, как и классы\n"
         "            # выше (максимумы по сетке). С DEBT-067 решение, у которого каждая строка выше\n"
         "            # порога не выше своего предела, принимается (eq:newton_cell_tol_floor): такой\n"
         "            # отказ значит, что какая-то строка выше своего предела (или проверка шла без\n"
         "            # якобиана — до первой итерации)\n")
    edit("tests/test_energy_matrix_examples.py",
         "# 14_high_gor_cooling после BUG-022 дробит один шаг, но в список не входит:\n"
         "# тест без метки slow добавил бы расчёт 14 (~12 с) в быстрый уровень, а\n"
         "# инвариант от примера не зависит.\n",
         "# 14_high_gor_cooling после BUG-022 дробил первые сутки (отказ на пределе\n"
         "# округления условия по ячейке), с DEBT-067 решает их целиком — не дробится.\n")
    edit("examples/14_high_gor_cooling/README.md",
         "Баланс энергии замыкается с относительной невязкой $2.9\\cdot10^{-16}$.",
         "Баланс энергии замыкается с относительной невязкой $9.8\\cdot10^{-17}$.")
    ch = NS / "HydroSolverPrototype/Prototype_1.0.3/CHANGELOG_1.0.3.md"
    ch.write_text(ch.read_text(encoding="utf-8") + "\n## Local changes — GPN project (DEBT-067)\n- (текст плана)\n",
                  encoding="utf-8")
print(f"правки шагов 1–{STAGE} применены: {NS}")
