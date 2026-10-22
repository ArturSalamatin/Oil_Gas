"""BUG-024, аудит 2: правки шагов плана на копии numerical_solver (probes/impl) заменой «До» -> «После».

Каждая замена обязана найти «До» ровно один раз — иначе отказ с именем файла и правки.
Второй аргумент — каталог numerical_solver, к которому применять (по умолчанию копия аудита
probes/impl/numerical_solver; копия создаётся robocopy и после аудита удаляется). Шаг 4 правит
только числа README; абзац о шаге интегрирования README 17 переписывается вручную (план, шаг 4).
Запуск:
    & $PY vault\\issues\\bug-024\\probes\\apply_plan.py 1                       # копия аудита
    & $PY ..\\vault\\issues\\bug-024\\probes\\apply_plan.py 1 (Get-Location).Path   # из numerical_solver worktree
    ... 2 / 3 / 4 / 5 — следующие шаги (по одному, по порядку)
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
NS = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else HERE / "impl" / "numerical_solver"
BO = "HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/blackoil.py"
PS = "tests/test_prototype_phase_switching.py"
CT = "tests/test_prototype_cell_tolerance.py"
AC = "tests/test_prototype_activation_cap.py"
EX = "tests/test_examples.py"
EM = "tests/test_energy_matrix_examples.py"
R17 = "examples/17_shut_in_strong_cooling/README.md"
RS = "examples/README.md"


def rep(rel, old, new):
    p = NS / rel
    t = p.read_text(encoding="utf-8")
    n = t.count(old)
    if n != 1:
        raise SystemExit(f"✗ {rel}: «До» найдено {n} раз:\n{old[:300]}")
    p.write_text(t.replace(old, new), encoding="utf-8")
    print(f"  ✓ {rel}: {old.strip().splitlines()[0][:70]}")


def append(rel, text):
    p = NS / rel
    t = p.read_text(encoding="utf-8")
    p.write_text(t.rstrip("\n") + "\n" + text, encoding="utf-8")
    print(f"  ✓ {rel}: дописано в конец ({len(text.splitlines())} строк)")


# ═══ шаг 1 ═══
def step1():
    rep(BO, """cell i (PV_i: pore volume of state_old), besides the absolute test.
\"\"\"
""", """cell i (PV_i: pore volume of state_old), besides the absolute test.
BUG-024: the fourth stage limits the Rs update of undersaturated cells,
|dRs| <= dr_rel*Rs_sat(p) (dr_rel = 0.2, as ds_max for Sg).
\"\"\"
""")
    rep(BO, """    def _newton_switching(self,state_old,dt_s,max_iter=40,rtol=1e-8,atol_sm3s=1e-11,dp_rel=0.3,ds_max=0.2,flips_to_freeze=2):
        \"\"\"BUG-020 fourth stage: Newton with phase switches after every iteration, per-cell update limits, no line search.\"\"\"
""", """    def _newton_switching(self,state_old,dt_s,max_iter=40,rtol=1e-8,atol_sm3s=1e-11,dp_rel=0.3,ds_max=0.2,flips_to_freeze=2,dr_rel=0.2):
        \"\"\"BUG-020 fourth stage: Newton with phase switches after every iteration, per-cell update limits (p, Sg; Rs -- BUG-024), no line search.\"\"\"
""")
    rep(BO, """        # an iterate takes its Sg below 0, and the limits act per cell (dpMaxRel, dsMax of OPM
        # Flow).  No line search: after the per-cell limit the update is not a descent
        # direction of ||F||, and the search stopped at the first iteration (plan BUG-020, 1.4).
""", """        # an iterate takes its Sg below 0, and the limits act per cell (dpMaxRel, dsMax of OPM
        # Flow; the Rs of undersaturated cells since BUG-024, see the update below).  No line
        # search: after the per-cell limit the update is not a descent direction of ||F||, and
        # the search stopped at the first iteration (plan BUG-020, 1.4).
""")
    rep(BO, """                # per-cell limits; Rs of undersaturated cells >= 0, pressure >= 1 bar
                x=z[n:]; lim=dp_rel*np.maximum(p,1.0)
                pn=np.maximum(p+np.clip(dz[:n],-lim,lim),1.0+1e-6)
                xn=np.where(mask,x+np.clip(dz[n:],-ds_max,ds_max),np.maximum(x+dz[n:],0.0))
""", """                # per-cell limits; Rs of undersaturated cells >= 0, pressure >= 1 bar
                x=z[n:]; lim=dp_rel*np.maximum(p,1.0)
                pn=np.maximum(p+np.clip(dz[:n],-lim,lim),1.0+1e-6)
                # BUG-024: |dRs| of undersaturated cells <= dr_rel*Rs_sat(p) -- the analogue of
                # ds_max: a share of the admissible range 0 <= Rs <= Rs_sat(p).  Unlimited, the
                # first shut-in hours after production with a developed gas zone (GPN config 20,
                # q_oil = 0) gave |dRs| up to 1.7e4 per iteration; the cut at Rs = 0 then either
                # stalled the Newton (a cell near the well held at Rs = 0, ||F|| constant for 30
                # iterations) or sent it into chaos (p up to 433 bar, mass phase switches), and
                # whether a daily step passed at dt/512 depended on round-off of earlier steps.
                # dr_rel 0.1-0.5 passes, 1.0 fails (plan BUG-024, 1.3-1.5).  Steps below the
                # limit are bitwise the former ones (np.clip returns them unchanged).
                lim_rs=dr_rel*np.maximum(self.pvt.rs_sat(p),1.0)
                xn=np.where(mask,x+np.clip(dz[n:],-ds_max,ds_max),np.maximum(x+np.clip(dz[n:],-lim_rs,lim_rs),0.0))
""")
    rep(PS, """сохранением отношения газ/нефть, поячеечное ограничение |dp| <= 0.3 p,
|dSg| <= 0.2, без линейного поиска, замораживание ячейки выше по потоку на
гранях после 2 смен направления, доводка без замораживания.
""", """сохранением отношения газ/нефть, поячеечное ограничение |dp| <= 0.3 p,
|dSg| <= 0.2, у недонасыщенных |dR_s| <= 0.2 R_s^sat(p) (BUG-024), без
линейного поиска, замораживание ячейки выше по потоку на гранях после 2 смен
направления, доводка без замораживания.
""")
    rep(PS, """        первой итерации). Замер плана: 20 итераций, 127 переключений фаз,
        p(r_w) = 174.4349 бар, двухфазных 250, max S_g = 0.3084.
""", """        первой итерации). Замер плана: p(r_w) = 174.4349 бар, двухфазных 250,
        max S_g = 0.3084; 21 итерация и 127 переключений фаз, после BUG-024
        (ограничение шага R_s) — 16 и 91, корень тот же.
""")
    append(PS, '''

# ═══════════════════════════════════════════════════════════
# E. BUG-024: шаг R_s недонасыщенных ячеек в ступени 4 ограничен
# ═══════════════════════════════════════════════════════════

def _first_update(model, ps, drs, monkeypatch):
    """z до и после одного обновления _newton_switching при подменённом направлении Ньютона.

    Направление: dp = 0, dS_g = 0, dR_s = drs у недонасыщенных ячеек (подмена
    _linear_solve). Второй вызов якобиана получает обновлённое z; на нём расчёт
    обрывается исключением _Stop. Двухфазные ячейки не меняются, давление тоже —
    переключений фаз при dR_s < 0 нет (активация требует R_s > R_s^sat).
    """
    n = model.grid.n
    mask = ps.gas_active.copy()
    zs = []
    orig_jac = model.finite_difference_jacobian

    def jac(z, *a, **kw):
        zs.append(z.copy())
        if len(zs) == 2:
            raise _Stop
        return orig_jac(z, *a, **kw)

    def lin(J, b):
        dz = np.zeros(2 * n)
        dz[n:][~mask] = drs
        return dz

    monkeypatch.setattr(model, "finite_difference_jacobian", jac)
    monkeypatch.setattr(model, "_linear_solve", lin)
    with pytest.raises(_Stop):
        model._newton_switching(ps, DT_STAGE4)
    return zs[0], zs[1], mask


class TestRsStepLimit:
    def test_large_rs_step_is_limited(self, shutin_start, monkeypatch):
        """dR_s = -1e4 (замер BUG-024: до 1.7e4 за итерацию) обрезается до 0.2 R_s^sat(p).

        Состояние после 10 сут добычи rs300: 61 недонасыщенная ячейка у контура,
        R_s = 300 при R_s^sat ~ 300-330 — шаг -60...-66, R_s ~ 234-240 > 0.
        До исправления R_s всех этих ячеек становился 0 (отсечка снизу) — так ступень 4
        застревала на останове (ячейка у забоя на R_s = 0, ||F|| стоит 30 итераций).
        Ловит: снятие ограничения шага R_s в _newton_switching.
        """
        model, ps, _ = shutin_start
        model.set_oil_rate_control(0.0, ATM_BAR)
        z0, z1, mask = _first_update(model, ps, -1e4, monkeypatch)
        n = model.grid.n
        und = ~mask
        assert np.count_nonzero(und) > 0
        rs0, rs1 = z0[n:][und], z1[n:][und]
        lim = 0.2 * np.maximum(model.pvt.rs_sat(z0[:n][und]), 1.0)
        assert np.array_equal(rs1, np.maximum(rs0 - lim, 0.0))
        assert np.all(rs1 > 0.0)
        _assert_restored(model)

    def test_small_rs_step_unchanged(self, shutin_start, monkeypatch):
        """dR_s = +1e-3 — ограничение не действует: R_s + 1e-3 побитово, как до BUG-024.

        Берутся ячейки, далёкие от насыщения (R_s + 1 < R_s^sat): шаг не переводит их
        в двухфазный набор. Ловит: ограничение, задевающее малые шаги (смену корня
        или сходимости там, где ступень 4 сходилась и раньше).
        """
        model, ps, _ = shutin_start
        model.set_oil_rate_control(0.0, ATM_BAR)
        z0, z1, mask = _first_update(model, ps, 1e-3, monkeypatch)
        n = model.grid.n
        keep = ~mask & (z0[n:] + 1.0 < model.pvt.rs_sat(z0[:n]))
        assert np.count_nonzero(keep) > 0
        assert np.array_equal(z1[n:][keep], z0[n:][keep] + 1e-3)
''')
    rep(CT, '''        """Шаг останова 168.75 с ступенью 4: без условия забой недорешён, с условием — нет.

        Замер плана: без условия — 20 итераций, мера 2.24e-8 > 1e-8; с условием — 21
        итерация, мера 1.15e-11, |dp| 2.14e-9 бар. Модель фабрики: cell_tol выключается
        на экземпляре и возвращается в finally (фикстура общая).
        Ловит: условие не стоит в _newton_switching.
        """
        model, ps = shutin
        assert model.cell_tol == CELL_TOL               # фабрика включила (шаг 3)
        try:
            model.cell_tol = None
            a, ra = model._newton_switching(ps, DT_STAGE4)
            assert ra.converged and _measure(model, ps, a, DT_STAGE4) > CELL_TOL
            model.cell_tol = CELL_TOL
            b, rb = model._newton_switching(ps, DT_STAGE4)
        finally:
            model.cell_tol = CELL_TOL
        assert rb.converged and rb.iterations > ra.iterations
        assert _measure(model, ps, b, DT_STAGE4) <= CELL_TOL
        assert np.max(np.abs(b.pressure_bar - a.pressure_bar)) < 1e-7
''', '''        """Шаг останова 168.75 с ступенью 4: условие по ячейке стоит в _newton_switching.

        Недостижимый порог 1e-30 — отказ (40 итераций), без условия — сходится; с порогом
        1e-8 мера решения <= 1e-8. До BUG-024 тест сравнивал решения без условия и с ним
        (без условия мера 2.24e-8 > 1e-8, 20 итераций против 21). С ограничением шага R_s
        (BUG-024) Ньютон и без условия сходится за 16 итераций с мерой 1.2e-11 —
        сравнение перестало различать, недостижимый порог различает всегда. Замер плана
        BUG-024: без условия и с 1e-8 — 16 итераций, мера 1.21e-11, |dp| = 0.
        Модель фабрики: cell_tol меняется на экземпляре и возвращается в finally.
        Ловит: условие не стоит в _newton_switching.
        """
        model, ps = shutin
        assert model.cell_tol == CELL_TOL               # фабрика включила (шаг 3)
        try:
            model.cell_tol = None
            a, ra = model._newton_switching(ps, DT_STAGE4)
            model.cell_tol = 1e-30
            _, rc = model._newton_switching(ps, DT_STAGE4)
            model.cell_tol = CELL_TOL
            b, rb = model._newton_switching(ps, DT_STAGE4)
        finally:
            model.cell_tol = CELL_TOL
        assert ra.converged and not rc.converged
        assert rb.converged and _measure(model, ps, b, DT_STAGE4) <= CELL_TOL
        assert np.max(np.abs(b.pressure_bar - a.pressure_bar)) < 1e-7
''')
    rep(AC, '''        """N = 350 с условием по ячейке (BUG-022): первые сутки — двумя подшагами Simulator.

        Замер плана BUG-022 (vault/issues/bug-022/probes/failing_tests.out.txt): шаг 86400 с
        ступени 1–4 не решают (ступени 1–3 — отказ линейного поиска при выполненном
        абсолютном критерии, невязка 6.5e-15), Simulator делит его пополам: 2 × 43200 с.
        На 1 сут S_g(r_w) = 0.418464, p(r_w) = 5.142747 МПа — против 0.417217 и
        5.140841 одним шагом: погрешность шага по времени, а не решателя.
        Ловит: срыв дробления при условии по ячейке (больше подшагов — разобрать, не подгонять).
        """''', '''        """N = 350 с условием по ячейке (BUG-022): первые сутки — подшагами Simulator.

        Замер плана BUG-022 (vault/issues/bug-022/probes/failing_tests.out.txt): шаг 86400 с
        ступени 1–4 не решают (ступени 1–3 — отказ линейного поиска при выполненном
        абсолютном критерии, невязка 6.5e-15). До BUG-024 Simulator проходил сутки
        2 × 43200 с: первый подшаг 43200 с ступень 4 решала «через» отсечку R_s = 0
        недонасыщенных ячеек. С ограничением шага R_s (BUG-024) он отказывает — так ведут
        себя все проверенные формы правки строки обновления R_s, даже меняющая только
        отсечку (план BUG-024, 1.7): 21600 + 21600 + 43200 с (рост после удачи, DEBT-015).
        На 1 сут S_g(r_w) = 0.419040, p(r_w) = 5.141098 МПа — против 0.417217 и
        5.140841 одним шагом: погрешность шага по времени, а не решателя.
        Ловит: срыв дробления при условии по ячейке (больше подшагов — разобрать, не подгонять).
        """''')
    rep(AC, '''        assert calls == [(86400.0, False), (43200.0, True), (43200.0, True)]
        st = h.states[-1]
        assert st.Sg[0] == pytest.approx(0.418464, abs=1e-5)
        assert st.p[0] == pytest.approx(5.142747e6, abs=100.0)
''', '''        assert calls == [(86400.0, False), (43200.0, False), (21600.0, True),
                         (21600.0, True), (43200.0, True)]
        st = h.states[-1]
        assert st.Sg[0] == pytest.approx(0.419040, abs=1e-5)
        assert st.p[0] == pytest.approx(5.141098e6, abs=100.0)
''')
    rep(AC, "        # и Simulator проходит сутки двумя подшагами — test_first_day_with_cell_tol.\n",
        "        # и Simulator проходит сутки дроблением — test_first_day_with_cell_tol.\n")


# ═══ шаг 2 ═══
def step2():
    rep(PS, "\nfrom pathlib import Path\n\nimport numpy as np\n", "\nimport copy\nfrom pathlib import Path\n\nimport numpy as np\n")
    append(PS, '''

class TestDailyShutin:
    def test_daily_shutin_passes_default_retries(self):
        """10 сут добычи + 3 сут останова (q_oil = 0) при dt_integration = 1 сут и max_retries = 9 (~6 с).

        До BUG-024: отказ «не сошёлся при дроблении шага до dt/512» на подшаге
        t = 10.0781 сут — ступень 4 не сходилась ни на одном подшаге от 1 сут до 169 с
        (застой при R_s = 0 у забоя или хаос; проходил ли расчёт, зависело от
        округлений предыдущих шагов: с условием по ячейке 1e-7 — да, 1e-8 — нет).
        Замер плана BUG-024: на останове 17 вызовов гидро, 7 отказов, принято 10
        подшагов, наименьший 5400 с; p(r_w) = 327.2428 бар, T(r_w) = 375.3667 К.
        Давление ниже, чем при шаге 1 ч (328.10 бар), — погрешность суточного шага.
        Ловит: возврат к неограниченному шагу R_s в ступени 4 (BUG-024).
        """
        cfg = load_config(RS300)
        cfg.output.log_level = "ERROR"
        hist = list(cfg.time.history)
        for _ in range(3):
            x = copy.deepcopy(hist[0])
            x.control, x.p_wf, x.q_oil, x.min_bhp = "rate", None, 0.0, 101325.0
            hist.append(x)
        cfg.time.history = hist
        # штатные значения замороженного конфига: шаг 1 сут, глубина дробления 9 (dt/512)
        assert cfg.time.dt_integration == DAY and cfg.numerics.max_retries == 9
        sim, init = SimulatorFactory.from_config(cfg)
        calls = []
        orig = sim._hydro.solve

        def solve(state, dt, bc):
            shut = state.t >= 10 * DAY - 1e-6
            try:
                r = orig(state, dt, bc)
            except HydroConvergenceError:
                if shut:
                    calls.append((dt, False))
                raise
            if shut:
                calls.append((dt, True))
            return r

        sim._hydro.solve = solve
        st = sim.run(init).states[-1]
        ok = [dt for dt, conv in calls if conv]
        failed = [dt for dt, conv in calls if not conv]
        assert len(ok) == 10 and len(failed) == 7
        assert sum(ok) == pytest.approx(3 * DAY, rel=1e-12)   # трое суток пройдены ровно один раз
        assert min(ok) == 5400.0
        assert st.p[0] / BAR == pytest.approx(327.2428, abs=1e-3)
        assert st.T[0] == pytest.approx(375.3667, abs=1e-3)
''')


# ═══ шаг 3 ═══
def step3():
    rep(EX, """        Замер: 5.1545 МПа (15 сут) -> 24.5554 (1 ч) -> 30.4537 (запись 27,
        15.5 сут — первая выше p_b = 30.2921 МПа) -> 31.6425 (16 сут) ->
        33.0000 (27 сут); наименьшее приращение между записями 3.7 Па;
        финал max|p - p0| = 2.3 Па. Допуск ±1 запись: на записи 26 до p_b
        не хватает 2.2 кПа — граница хрупкая.
""", """        Замер: 5.1545 МПа (15 сут) -> 24.5554 (1 ч) -> 30.4199 (запись 27,
        15.5 сут — первая выше p_b = 30.2921 МПа) -> 31.6335 (16 сут) ->
        33.0000 (27 сут); наименьшее приращение между записями 3.7 Па;
        финал max|p - p0| = 2.4 Па. Допуск ±1 запись: граница хрупкая — на
        записи 26 до p_b не хватает 37.6 кПа, а до BUG-024 (часы останова
        дробились) запись 26 была уже выше p_b на 3.8 кПа.
""")
    rep(EX, """        (1 ч) -> 373.6456 (16 сут) -> 377.3093 К (30 сут); наименьшее
        приращение между записями 0.0646 К.
""", """        (1 ч) -> 373.6369 (16 сут) -> 377.3078 К (30 сут); наименьшее
        приращение между записями 0.0653 К. С BUG-024 часы останова не
        дробятся: T на 16 сут ниже на 8.9 мК — погрешность шага 1 ч.
""")
    rep(EX, """        assert T[39] == pytest.approx(373.6456, abs=2e-3)
        assert T[-1] == pytest.approx(377.3093, abs=2e-3)
""", """        assert T[39] == pytest.approx(373.6369, abs=2e-3)
        assert T[-1] == pytest.approx(377.3078, abs=2e-3)
""")
    rep(EX, "        +0.001 К. Замер: max ΔT = +0.2216 К.\n", "        +0.001 К. Замер: max ΔT = +0.2212 К.\n")
    rep(EX, "        assert dT[k] == pytest.approx(0.2216, abs=2e-3)\n",
        "        assert dT[k] == pytest.approx(0.2212, abs=2e-3)\n")
    rep(EX, """        30 сут (energy_balance.compute_balance), Дж: ΔE = +1.776e11,
""", """        30 сут (energy_balance.compute_balance), Дж: ΔE = +1.775e11,
""")
    rep(EX, """        +3.960e10, Джоуль–Томсон +6.8e8, конвекция +2.0e8. За добычу член
""", """        +3.962e10, Джоуль–Томсон +6.7e8, конвекция +2.0e8. За добычу член
""")
    rep(EX, '        assert d["delta_E"] == pytest.approx(1.776e11, rel=2e-3)\n',
        '        assert d["delta_E"] == pytest.approx(1.775e11, rel=2e-3)\n')
    rep(EX, '        assert d["cum_deg"] == pytest.approx(3.960e10, rel=2e-3)\n',
        '        assert d["cum_deg"] == pytest.approx(3.962e10, rel=2e-3)\n')
    rep(EM, """# 17_shut_in_strong_cooling дробится массово (локальное дробление DEBT-015:
# 34 шага останова, 768 вызовов энергии на 720 шагов, подшаги до 450 с;
# до DEBT-015 — 36 шагов, 770 вызовов), но в список не входит: тест без
# метки slow втащил бы расчёт 17 (~100 с) в быстрый уровень, а инвариант
# от примера не зависит.
# На остальных конфигах дробления нет и проверять нечего.
""", """# 17_shut_in_strong_cooling после BUG-024 (ограничение шага R_s в ступени 4)
# не дробится: часы останова, которые дробились на 2–3 подшага (41 отказ
# гидродинамики), решаются целиком.
# 14_high_gor_cooling после BUG-022 дробит один шаг, но в список не входит:
# тест без метки slow добавил бы расчёт 14 (~12 с) в быстрый уровень, а
# инвариант от примера не зависит.
# На остальных конфигах дробления нет и проверять нечего.
""")


# ═══ шаг 4 ═══
def step4():
    for old, new in [
        ("| 27 | 15.5 | 0 | **30.4520** | 372.5830 | 0 | 82 |", "| 27 | 15.5 | 0 | **30.4199** | 372.5595 | 0 | 82 |"),
        ("| 39 | 16 | 0 | 31.6425 | 373.6453 | 0 | 66 |", "| 39 | 16 | 0 | 31.6335 | 373.6369 | 0 | 66 |"),
        ("| 43 | 20 | 0 | 32.9708 | 375.9562 | 0 | 51 |", "| 43 | 20 | 0 | 32.9704 | 375.9546 | 0 | 51 |"),
        ("| 53 | 30 | 0 | 33.0000 | 377.3089 | 0 | 51 |", "| 53 | 30 | 0 | 33.0000 | 377.3078 | 0 | 51 |"),
        ("к концу первых суток — 31.64 МПа", "к концу первых суток — 31.63 МПа"),
        ("с точностью 2.3 Па", "с точностью 2.4 Па"),
        ("$S_g$ до 0.062 на 12 м", "$S_g$ до 0.063 на 12 м"),
        ("к концу первых суток 373.65 К", "к концу первых суток 373.64 К"),
        ("| адиабатический | $+6.67\\cdot10^{10}$ |", "| адиабатический | $+6.65\\cdot10^{10}$ |"),
        ("| Джоуль–Томсон | $+5.9\\cdot10^{8}$ | $+6.8\\cdot10^{8}$ |", "| Джоуль–Томсон | $+5.8\\cdot10^{8}$ | $+6.7\\cdot10^{8}$ |"),
        ("| $+5.8\\cdot10^{5}$ |", "| $+5.7\\cdot10^{5}$ |"),
        ("  Rs: 79.5367 … 332.4101", "  Rs: 79.5369 … 332.4101"),
    ]:
        rep(R17, old, new)
    rep(RS, "| 1 сут; первые сутки останова — 1 ч | 377.309 |", "| 1 сут; первые сутки останова — 1 ч | 377.308 |")
    rep(RS, "| **16** | **1.5 / 0.14 / 0.04** | $9.3\\cdot10^{-16}$ |", "| **16** | **1.5 / 0.14 / 0.04** | $1.8\\cdot10^{-15}$ |")
    rep(RS, "| **17** | **2.5 / 0.13 / 0.05** | $3.8\\cdot10^{-15}$ |", "| **17** | **2.5 / 0.13 / 0.05** | $3.4\\cdot10^{-15}$ |")


# ═══ шаг 5 (docstring тестов; CHANGELOG и vault — вне копии) ═══
def step5():
    rep(EX, """        30 сут отличается на 0.04 К). После DEBT-015 (локальное дробление)
        суточный шаг на останове сходится, 3600 с — выбор, а не требование.
""", """        30 сут отличается на 0.04 К). После DEBT-015 (локальное дробление)
        суточный шаг на останове сходится, 3600 с — выбор, а не требование;
        после BUG-024 — без единого отказа (~12 с против ~70 с при 3600 с).
""")
    rep(AC, """    при смене режима» снята: при локальном дроблении останов проходит и при
    1 сут. Оба рычага — max_retries и dt_integration — названы.
""", """    при смене режима» снята: при локальном дроблении останов проходит и при
    1 сут (между BUG-022 и BUG-024 — нет: на конфигах 19 и 20 нужен был
    max_retries = 11). Оба рычага — max_retries и dt_integration — названы.
""")


if __name__ == "__main__":
    print(f"дерево: {NS}")
    {"1": step1, "2": step2, "3": step3, "4": step4, "5": step5}[sys.argv[1]]()
