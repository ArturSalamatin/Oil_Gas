r"""Проба DEBT-057: код и правки тестов шагов 2–3 плана — к копии пакета; тесты и отпечаток T на ней.

Запуск из numerical_solver/ (копия — vault/issues/debt-057/probes/check/, удаляется следующим запуском,
не коммитится):
    <python> ..\vault\issues\debt-057\probes\apply_code.py                   # проверка на копии
    <python> ..\vault\issues\debt-057\probes\apply_code.py --inplace newtest # шаг 2: новый файл тестов в tests/
    <python> ..\vault\issues\debt-057\probes\apply_code.py --inplace code    # шаг 3: правки CODE и TESTS в дереве
Пары (было, стало, сколько раз) — блоки шагов 2–3 плана. Копия пакета —
check/pkg, тесты — check/tests; pytest запускается из check/ с PYTHONPATH=check/pkg
(cwd в sys.path первым — из numerical_solver/ взялся бы пакет основного каталога).
Ожидание: новые тесты и тесты test_energy.py зелёные, сверка матрицы 18 и 03 зелёная,
отпечаток T примера 18 = fd040715fc926897 (вариант B пробы phi_energy.py).
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

SOLVER = Path.cwd()
HERE = Path(__file__).parent
CHECK = HERE / "check"
PKG = CHECK / "pkg"

CODE = {
    "gpn_multiphase_solver/energy/tridiag.py": [
        # E1 — p_ref в конструкторе
        ("""    def __init__(self, grid: Grid, pvt: FullPVT, rock: RockConfig):
        self._grid = grid
        self._pvt = pvt
        self._rock = rock
""",
         """    def __init__(self, grid: Grid, pvt: FullPVT, rock: RockConfig,
                 p_ref: float | None = None):
        self._grid = grid
        self._pvt = pvt
        self._rock = rock
        # Опорное давление закона пористости φ(p) = φ0·exp(c_r·(p − p_ref))
        # (eq:porosity): rock.porosity задана при p_ref. Фабрика передаёт
        # начальное p0 — то же, что получает порода прототипа (factory.py,
        # CompressibleRock): энергия и гидродинамика считают один поровый
        # объём (DEBT-057). При c_r = 0 пористость от p_ref не зависит.
        # rock = None допустим: тесты сверки матрицы создают решатель только
        # ради методов, которым порода не нужна.
        if rock is not None and rock.compressibility != 0.0 and p_ref is None:
            raise ValueError(
                f"TridiagEnergySolver: rock.compressibility = {rock.compressibility} "
                "≠ 0 — нужно p_ref, давление, при котором задана rock.porosity "
                "(фабрика передаёт initial_conditions.p0)")
        self._p_ref = p_ref
""", 1),
        # E6 — solve передаёт p в compute_degassing
        ("""        Q_deg = self.compute_degassing(
            So, Sg, Rs, Rs_old, props['Bo'], G_o, props['L'], dt, N, Rs_ext)
""",
         """        Q_deg = self.compute_degassing(
            So, Sg, Rs, Rs_old, props['Bo'], G_o, props['L'], dt, N, Rs_ext,
            p=p)
""", 1),
        # E2 — метод porosity и φ в compute_cell_properties
        ("""    # ──────────────────────────────────────────────────────
    # Подшаг 1–2: PVT + эффективные свойства в ячейках
    # ──────────────────────────────────────────────────────

    def compute_cell_properties(self, p, Sg, Rs, So, T_old):
        \"\"\"Тепловые PVT и вспомогательные величины в ячейках.

        Ур. (eq:main_rhocpeff), (eq:lambda_eff).
        \"\"\"
        pvt = self._pvt
        rock = self._rock
        phi = rock.porosity
""",
         """    # ──────────────────────────────────────────────────────
    # Пористость φ(p) — поровый объём гидродинамики (DEBT-057)
    # ──────────────────────────────────────────────────────

    def porosity(self, p):
        \"\"\"Пористость φ(p) = φ0·exp(c_r·(p − p_ref)) в ячейках. Ур. (eq:porosity).\"\"\"
        rock = self._rock
        # c_r = 0: скаляр rock.porosity — те же операции, что до DEBT-057,
        # поэтому расчёты с c_r = 0 побитово прежние; p не нужно.
        if rock.compressibility == 0.0:
            return rock.porosity
        if p is None:
            raise ValueError(
                "TridiagEnergySolver.porosity: при rock.compressibility ≠ 0 "
                "нужно давление p в ячейках")
        # Та же формула, что у CompressibleRock прототипа (там в барах):
        # запасы компонентов гидродинамики — V·φ(p)·S_α/B_α
        return rock.porosity * np.exp(rock.compressibility * (p - self._p_ref))

    # ──────────────────────────────────────────────────────
    # Подшаг 1–2: PVT + эффективные свойства в ячейках
    # ──────────────────────────────────────────────────────

    def compute_cell_properties(self, p, Sg, Rs, So, T_old):
        \"\"\"Тепловые PVT и вспомогательные величины в ячейках.

        Ур. (eq:main_rhocpeff), (eq:lambda_eff).
        \"\"\"
        pvt = self._pvt
        rock = self._rock
        # Флюид — поровый объём φ(p^{n+1}), как в запасах гидродинамики;
        # скелет — (1 − φ0)(ρc_p)_s: его масса в ячейке постоянна, и от p
        # теплоёмкость скелета не зависит (DEBT-057, eq:rock_dt).
        # λ_eff — эмпирическое замыкание при φ0 (eq:lambda_eff).
        phi0 = rock.porosity
        phi = self.porosity(p)
""", 1),
        # E3 — (ρc_p)_eff и λ_eff
        ("""        rho_cp_eff = ((1 - phi) * rock.rho_cp_solid
                      + phi * (So * rho_o * c_p_o + Sg * rho_g * c_p_g))

        # Эффективная теплопроводность (eq:lambda_eff), Вт/(м·К)
        lambda_eff = ((1 - phi) * rock.lambda_solid
                      + phi * (So * rock.lambda_oil + Sg * rock.lambda_gas))
""",
         """        rho_cp_eff = ((1 - phi0) * rock.rho_cp_solid
                      + phi * (So * rho_o * c_p_o + Sg * rho_g * c_p_g))

        # Эффективная теплопроводность (eq:lambda_eff), Вт/(м·К)
        lambda_eff = ((1 - phi0) * rock.lambda_solid
                      + phi0 * (So * rock.lambda_oil + Sg * rock.lambda_gas))
""", 1),
        # E4 — Q_ad
        ("""    # Подшаг 5b: адиабатический эффект (eq:Qad_disc — форма при c_r = 0, DEBT-057)
    # ──────────────────────────────────────────────────────

    def compute_adiabatic(self, So, Sg, rho_o, rho_g, c_p_o, c_p_g,
                            mu_JT_o, mu_JT_g, p, p_old, dt):
        \"\"\"Q_ad[j] = φ · Σ_α S_α · (1 + ρ_α·cp_α·μ_JT_α) · dp/dt, Вт/м³.\"\"\"
        phi = self._rock.porosity
""",
         """    # Подшаг 5b: адиабатический эффект (eq:Qad_disc; φ = φ(p^{n+1}), DEBT-057)
    # ──────────────────────────────────────────────────────

    def compute_adiabatic(self, So, Sg, rho_o, rho_g, c_p_o, c_p_g,
                            mu_JT_o, mu_JT_g, p, p_old, dt):
        \"\"\"Q_ad[j] = φ(p)·Σ_α S_α·(1 + ρ_α·cp_α·μ_JT_α)·dp/dt, Вт/м³. Ур. (eq:Qad_disc).\"\"\"
        # Сжимаемость породы — только через φ(p): членов c_r·(p + (ρc_p)_s·T)
        # в Q_ad нет (eq:rock_dt, DEBT-057)
        phi = self.porosity(p)
""", 1),
        # E5 — ṁ: сигнатура и φ(p)
        ("""    def compute_degassing(self, So, Sg, Rs, Rs_old, Bo, G_o, L, dt, N, Rs_ext):
""",
         """    def compute_degassing(self, So, Sg, Rs, Rs_old, Bo, G_o, L, dt, N, Rs_ext,
                          p=None):
""", 1),
        ("""        Rs_ext — состав притока с контура (eq:bc_Sg_ext): R_s|_ext = R_s^0.
        \"\"\"
        phi = self._rock.porosity
""",
         """        Rs_ext — состав притока с контура (eq:bc_Sg_ext): R_s|_ext = R_s^0.
        \"\"\"
        # Запас нефти во временной части — с пористостью φ(p^{n+1}) (eq:porosity),
        # как в запасах гидродинамики (DEBT-057); при c_r = 0 p не нужно.
        phi = self.porosity(p)
""", 1),
    ],
    "gpn_multiphase_solver/factory.py": [
        # E7
        ("""        energy = TridiagEnergySolver(grid, pvt, config.rock)
""",
         """        # p_ref = p0: пористость конфига задана при начальном давлении — так же
        # фабрика строит породу прототипа (_create_prototype_hydro): поровый
        # объём энергии и гидродинамики один (DEBT-057)
        energy = TridiagEnergySolver(grid, pvt, config.rock,
                                     p_ref=config.initial_conditions.p0)
""", 1),
    ],
    "gpn_multiphase_solver/io/config.py": [
        # E8
        ("""    # Энергия берёт постоянную porosity (energy/tridiag.py) — при c_r ≠ 0 см. DEBT-057.
""",
         """    # Энергия (energy/tridiag.py, DEBT-057): флюид — φ(p) по тому же закону,
    # скелет и λ_eff — porosity при p0 (масса скелета в ячейке постоянна).
""", 1),
    ],
    "gpn_multiphase_solver/energy/balance.py": [
        # E9
        ("""        # Q_ad = φ Σ_α S_α (1 + ρ_α cp_α μ_JT,α) dp/dt, Вт/м³ (eq:Qad_disc, c_r = 0).
""",
         """        # Q_ad = φ(p) Σ_α S_α (1 + ρ_α cp_α μ_JT,α) dp/dt, Вт/м³ (eq:Qad_disc, DEBT-057).
""", 1),
    ],
    "examples/verify_balance_vs_solver.py": [
        # E10 — инструмент повторяет solve: p в compute_degassing так же
        ("""        Q_deg = self.compute_degassing(
            So, Sg, Rs, Rs_old, props['Bo'], G_o, props['L'], dt, N, Rs_ext)
""",
         """        # p — как в solve: пористость временной части ṁ φ(p) (DEBT-057)
        Q_deg = self.compute_degassing(
            So, Sg, Rs, Rs_old, props['Bo'], G_o, props['L'], dt, N, Rs_ext,
            p=p)
""", 1),
    ],
}

TESTS = {
    "tests/test_energy_matrix_examples.py": [
        # R3 + R1 — _ref_porosity и φ в _ref_cell_properties
        ('''def _ref_cell_properties(pvt, rock, p, Sg, Rs, T_old):
    """Эффективные свойства в ячейках. eq:main_rhocpeff, eq:lambda_eff.

    (ρcp)_eff = (1-φ)·(ρcp)_s + φ·Σ_α S_α·ρ_α·c_pα   [Дж/(м³·К)]
    λ_eff     = (1-φ)·λ_s     + φ·Σ_α S_α·λ_α        [Вт/(м·К)]

    So берётся как 1 - Sg, как в ядре: тождество So + Sg = 1 обязано
    выполняться точно.
    """
    So = 1.0 - Sg
    phi = rock.porosity
''',
         '''def _ref_porosity(rock, p, p_ref):
    """Пористость в ячейках. eq:porosity.

    φ(p) = φ0·exp(c_r·(p − p0)), φ0 = rock.porosity задана при начальном
    давлении p0 = p_ref — так же фабрика строит породу прототипа (DEBT-057).
    При c_r = 0 — φ0 в каждой ячейке, p_ref не нужен.
    """
    if rock.compressibility == 0.0:
        return np.full(np.shape(p), rock.porosity)
    return rock.porosity * np.exp(rock.compressibility * (p - p_ref))


def _ref_cell_properties(pvt, rock, phi, p, Sg, Rs, T_old):
    """Эффективные свойства в ячейках. eq:main_rhocpeff, eq:lambda_eff.

    (ρcp)_eff = (1-φ0)·(ρcp)_s + φ(p)·Σ_α S_α·ρ_α·c_pα   [Дж/(м³·К)]
    λ_eff     = (1-φ0)·λ_s     + φ0·Σ_α S_α·λ_α          [Вт/(м·К)]

    φ0 = rock.porosity — скелет (масса в ячейке постоянна) и замыкание λ_eff;
    φ = φ(p^{n+1}) (_ref_porosity) — флюид (DEBT-057).

    So берётся как 1 - Sg, как в ядре: тождество So + Sg = 1 обязано
    выполняться точно.
    """
    So = 1.0 - Sg
    phi0 = rock.porosity
''', 1),
        # R2
        ("""    props['rho_cp_eff'] = ((1.0 - phi) * rock.rho_cp_solid
                           + phi * (So * props['rho_o'] * props['c_p_o']
                                    + Sg * props['rho_g'] * props['c_p_g']))
    props['lambda_eff'] = ((1.0 - phi) * rock.lambda_solid
                           + phi * (So * rock.lambda_oil
                                    + Sg * rock.lambda_gas))
""",
         """    props['rho_cp_eff'] = ((1.0 - phi0) * rock.rho_cp_solid
                           + phi * (So * props['rho_o'] * props['c_p_o']
                                    + Sg * props['rho_g'] * props['c_p_g']))
    props['lambda_eff'] = ((1.0 - phi0) * rock.lambda_solid
                           + phi0 * (So * rock.lambda_oil
                                     + Sg * rock.lambda_gas))
""", 1),
        # R4 — _ref_adiabatic
        ('''def _ref_adiabatic(rock, So, Sg, rho_o, rho_g, c_p_o, c_p_g,
                   mu_JT_o, mu_JT_g, p, p_old, dt):
    """Адиабатический эффект. eq:Qad_disc (при c_r = 0).

    ФОРМА ДОКУМЕНТА — единица ВНЕ суммы:
''',
         '''def _ref_adiabatic(phi, So, Sg, rho_o, rho_g, c_p_o, c_p_g,
                   mu_JT_o, mu_JT_g, p, p_old, dt):
    """Адиабатический эффект. eq:Qad_disc.

    ФОРМА ДОКУМЕНТА — единица ВНЕ суммы, φ = φ(p^{n+1}) (DEBT-057):
''', 1),
        ("""    dp_dt = (p - p_old) / dt
    return rock.porosity * (1.0
                            + So * rho_o * c_p_o * mu_JT_o
                            + Sg * rho_g * c_p_g * mu_JT_g) * dp_dt
""",
         """    dp_dt = (p - p_old) / dt
    return phi * (1.0
                  + So * rho_o * c_p_o * mu_JT_o
                  + Sg * rho_g * c_p_g * mu_JT_g) * dp_dt
""", 1),
        # R5 — _ref_degassing
        ("""def _ref_degassing(grid, pvt, rock, So, Sg, Rs, Rs_old, Bo, G_o, L,
""",
         """def _ref_degassing(grid, pvt, phi, So, Sg, Rs, Rs_old, Bo, G_o, L,
""", 1),
        ("""    phi = rock.porosity
    V = grid.volumes
    rho_g_std = pvt.rho_g_std
""",
         """    # phi — φ(p^{n+1}) (_ref_porosity): запас нефти временной части — с тем же
    # поровым объёмом, что у гидродинамики (DEBT-057)
    V = grid.volumes
    rho_g_std = pvt.rho_g_std
""", 1),
        # R6 — build_reference
        ("""def build_reference(grid, pvt, rock, hydro_result, state_prev, dt, bc,
                    T_ref=0.0, with_scale=False):
""",
         """def build_reference(grid, pvt, rock, hydro_result, state_prev, dt, bc,
                    T_ref=0.0, with_scale=False, p_ref=None):
""", 1),
        ("""    with_scale=True — пятым элементом масштаб слагаемых d (_ref_d_scale),
    для допуска сверки d.
    \"\"\"
    N = grid.N
    st = hydro_result.state

    props = _ref_cell_properties(pvt, rock, st.p, st.Sg, st.Rs, state_prev.T)
""",
         """    with_scale=True — пятым элементом масштаб слагаемых d (_ref_d_scale),
    для допуска сверки d.

    p_ref — давление, при котором задана rock.porosity (начальное p0);
    нужно при c_r ≠ 0 (DEBT-057).
    \"\"\"
    N = grid.N
    st = hydro_result.state

    # Пористость φ(p^{n+1}): флюид в (ρc_p)_eff, Q_ad и временной части ṁ
    phi = _ref_porosity(rock, st.p, p_ref)
    props = _ref_cell_properties(pvt, rock, phi, st.p, st.Sg, st.Rs, state_prev.T)
""", 1),
        # R7
        ("""    Q_ad = _ref_adiabatic(rock, props['So'], st.Sg,
""",
         """    Q_ad = _ref_adiabatic(phi, props['So'], st.Sg,
""", 1),
        ("""    Q_deg = _ref_degassing(grid, pvt, rock, props['So'], st.Sg,
""",
         """    Q_deg = _ref_degassing(grid, pvt, phi, props['So'], st.Sg,
""", 1),
        # R8
        ("""            hydro_result, state_prev, dt, bc, T_ref=T_ref, with_scale=True)
""",
         """            hydro_result, state_prev, dt, bc, T_ref=T_ref, with_scale=True,
            p_ref=cfg.initial_conditions.p0)
""", 1),
    ],
}


def apply(path: Path, pairs, write=True):
    """Применить пары к файлу; окончания строк — как в файле (рабочая копия Windows: CRLF)."""
    raw = path.read_bytes()
    crlf = b"\r\n" in raw
    text = raw.decode("utf-8").replace("\r\n", "\n")
    for k, (old, new, n) in enumerate(pairs, 1):
        found = text.count(old)
        assert found == n, f"{path.name}, пара {k}: «было» найдено {found} раз, ожидалось {n}"
        text = text.replace(old, new)
    if write:
        path.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))
    print(f"{path.name}: пар {len(pairs)} {'применено' if write else 'найдено'}")


def inplace(part):
    """Правки в дереве numerical_solver/: newtest — шаг 2, code — шаг 3."""
    if part == "newtest":
        dst = SOLVER / "tests" / "test_energy_porosity.py"
        assert not dst.exists(), f"{dst} уже есть"
        text = (HERE / "test_energy_porosity_draft.py").read_text(encoding="utf-8")
        dst.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
        print(f"записан {dst}")
    elif part == "code":
        for rel, pairs in {**CODE, **TESTS}.items():
            apply(SOLVER / rel, pairs)
    else:
        sys.exit(f"неизвестная часть: {part}")


def main():
    if "--inplace" in sys.argv:
        inplace(sys.argv[sys.argv.index("--inplace") + 1])
        return
    if CHECK.exists():
        shutil.rmtree(CHECK)
    shutil.copytree(SOLVER / "gpn_multiphase_solver", PKG / "gpn_multiphase_solver",
                    ignore=shutil.ignore_patterns("__pycache__"))
    for rel, pairs in CODE.items():
        if rel.startswith("gpn_multiphase_solver/"):
            apply(PKG / rel, pairs)
        else:
            apply(SOLVER / rel, pairs, write=False)   # вне пакета — только сверка «было»
    tests = CHECK / "tests"
    tests.mkdir()
    for rel, pairs in TESTS.items():
        dst = tests / Path(rel).name
        shutil.copy(SOLVER / rel, dst)
        apply(dst, pairs)
    shutil.copy(SOLVER / "tests" / "test_energy.py", tests / "test_energy.py")
    shutil.copy(HERE / "test_energy_porosity_draft.py", tests / "test_energy_porosity.py")
    # Пути к примерам — от numerical_solver, а не от копии
    for name in ("test_energy_matrix_examples.py", "test_energy_porosity.py"):
        p = tests / name
        t = p.read_text(encoding="utf-8").replace(
            'Path(__file__).parent.parent / "examples"', f'Path(r"{SOLVER}") / "examples"')
        p.write_text(t, encoding="utf-8")
    (CHECK / "pytest.ini").write_text("[pytest]\nmarkers =\n    slow: тяжёлые\n", encoding="utf-8")

    env = dict(os.environ, PYTHONPATH=str(PKG))
    out = subprocess.run([sys.executable, "-c", "import gpn_multiphase_solver as g; print(g.__file__)"],
                         cwd=CHECK, env=env, capture_output=True, text=True)
    print("пакет pytest:", out.stdout.strip())
    cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
           "tests/test_energy_porosity.py", "tests/test_energy.py",
           "tests/test_energy_matrix_examples.py::test_matrix_matches_reference[18_prototype_input]",
           "tests/test_energy_matrix_examples.py::test_matrix_matches_reference[03_standing_corey]"]
    r = subprocess.run(cmd, cwd=CHECK, env=env, capture_output=True, text=True)
    print("\n".join(r.stdout.strip().splitlines()[-15:]))
    r = subprocess.run([sys.executable, str(HERE / "t_fingerprint.py"), "код плана"],
                       cwd=SOLVER, env=env, capture_output=True, text=True)
    print(r.stdout.strip(), r.stderr.strip()[-2000:])


if __name__ == "__main__":
    main()
