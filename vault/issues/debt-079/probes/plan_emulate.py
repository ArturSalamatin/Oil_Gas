"""DEBT-079, планирование: правка шага 1 плана (factory.py) в памяти + сценарии тестов плана.

Блоки «До/После» ниже — те же, что в плане vault/plans/debt-079 relperm-immobile-gas-first-row.md
(шаг 1, пп. 1–3). Каждый «До» обязан найтись в factory.py ровно один раз. Исправленный
исходник исполняется в копии пространства имён модуля; _check_relperm_table и create_relperm
ставятся в настоящий модуль (from_config ищет create_relperm по имени при вызове).

Запуск из numerical_solver/ (код базы):
    .venv\\Scripts\\python ..\\vault\\issues\\debt-079\\probes\\plan_emulate.py
Быстрый уровень с правкой — plan_patch_plugin.py (-p), см. его докстринг.
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOLVER = HERE.parents[3] / "numerical_solver"     # probes → debt-079 → issues → vault → корень

# ── п. 1: сигнатура и докстринг ──
SIG_OLD = '''def _check_relperm_table(Sg: list, kro: list, relperm_file: str) -> None:
    """Таблица ОФП: ≥ 2 строк, S_g строго растёт, k_ro последней строки = 0, иначе ValueError (DEBT-044, DEBT-073)."""
'''
SIG_NEW = '''def _check_relperm_table(Sg: list, kro: list, krg: list, relperm_file: str) -> None:
    """Таблица ОФП: ≥ 2 строк, S_g строго растёт, k_rg первой строки = 0, k_ro последней = 0, иначе ValueError (DEBT-044, DEBT-079, DEBT-073)."""
'''

# ── п. 2: новая проверка — перед проверкой DEBT-073 ──
ANCHOR = "    # DEBT-073: выше последней строки TabulatedRelPerm берёт k_ro, k_rg из неё\n"
CHECK_NEW = '''    # DEBT-079: ниже первой строки TabulatedRelPerm берёт k_ro, k_rg из неё
    # (np.interp), то есть k_rg(S_g = 0) = k_rg[0]. Подвижность газа прототип по
    # признаку «газ есть» не обнуляет: при k_rg[0] > 0 свободный газ течёт из
    # недонасыщенных ячеек (S_g = 0) в скважину и в соседние ячейки и приходит
    # с контура питания вместе с недонасыщенной нефтью. Газовый фактор у забоя
    # завышен на λ_g/λ_o при S_g = 0 — на PVT configs/table_pvt это 1.6e4-1.8e4
    # м³ст/м³ст на единицу k_rg[0]. Замер (vault/issues/debt-079/probes/
    # krg0_scan.out.txt): configs/table_pvt, k_rg[0] = 1e-4 — за 24 ч свободный
    # газ в 19 ячейках из 20, хотя p всюду выше p_b; ГФ 31.7 вместо 30; пример
    # 05 с первой строкой 0.05,0.9,0.005 — ГФ 97 вместо 50 за 6 ч, без записей
    # журнала. k_rg = 0 при S_g = 0 — следствие определения скорости фильтрации
    # (поток фазы пропорционален её количеству), а не эмпирика; для нефти то же
    # условие — k_ro = 0 в последней строке (ниже). Первая строка с S_g > 0 и
    # k_rg = 0 допустима: ниже неё газ неподвижен (критическая газонасыщенность).
    # Сравнение строгое — решение пользователя 2026-10-15: уже k_rg[0] = 1e-4
    # переводит недонасыщенные ячейки в двухфазные. Проверка — после числа строк
    # (на пустой таблице krg[0] нет), первая строка — раньше последней.
    if krg[0] > 0:
        raise ValueError(
            f"{relperm_file}: k_rg в первой строке (S_g = {Sg[0]:g}) = {krg[0]:g}, "
            f"нужно 0. Ниже первой строки k_ro и k_rg берутся из неё: при k_rg > 0 "
            f"свободный газ подвижен при S_g = 0 — течёт из ячеек, где его нет, и "
            f"приходит с контура питания вместе с недонасыщенной нефтью. Таблица "
            f"начинается строкой с k_rg = 0 — при S_g = 0 или при критической "
            f"газонасыщенности.")

'''

# ── п. 3: вызов в create_relperm ──
CALL_OLD = '''        # DEBT-044: число строк и рост S_g проверяет и TabulatedRelPerm, но без
        # имени файла; k_ro = 0 в последней строке (DEBT-073) — только здесь
        _check_relperm_table(Sg, kro, rc.file)
'''
CALL_NEW = '''        # DEBT-044: число строк и рост S_g проверяет и TabulatedRelPerm, но без
        # имени файла; k_rg = 0 в первой строке (DEBT-079) и k_ro = 0 в последней
        # (DEBT-073) — только здесь
        _check_relperm_table(Sg, kro, krg, rc.file)
'''

# ── п. 4: перечень правил в комментарии _read_numeric_csv ──
LIST_OLD = '''    # Правила таблицы целиком (число строк, рост давления и S_g, ветви R_s)
    # проверяют _check_pvto_branches, _check_gas_pvt_table, _check_relperm_table.
'''
LIST_NEW = '''    # Правила таблицы целиком (число строк, рост давления и S_g, ветви R_s,
    # крайние строки ОФП) проверяют _check_pvto_branches, _check_gas_pvt_table,
    # _check_relperm_table.
'''


def _replace_once(src, old, new, what):
    n = src.count(old)
    assert n == 1, f"{what}: блок «До» найден {n} раз"
    return src.replace(old, new)


def patched_source() -> str:
    src = (SOLVER / "gpn_multiphase_solver" / "factory.py").read_text(encoding="utf-8")
    src = _replace_once(src, SIG_OLD, SIG_NEW, "п. 1 сигнатура")
    src = _replace_once(src, ANCHOR, CHECK_NEW + ANCHOR, "п. 2 якорь DEBT-073")
    src = _replace_once(src, CALL_OLD, CALL_NEW, "п. 3 вызов")
    src = _replace_once(src, LIST_OLD, LIST_NEW, "п. 4 перечень правил")
    compile(src, "factory.py", "exec")
    return src


def patch_in_memory() -> None:
    import gpn_multiphase_solver.factory as mod
    ns = dict(mod.__dict__)
    exec(compile(patched_source(), mod.__file__ + " [план DEBT-079]", "exec"), ns)
    mod._check_relperm_table = ns["_check_relperm_table"]
    mod.create_relperm = ns["create_relperm"]


# ═══ Сценарии тестов плана ═══

RP_HEADER = "Sg,kro,krg\n"
TABLE_RP_ROWS = ["0.0,1.0,0.0\n", "0.1,0.8,0.01\n", "0.2,0.6,0.05\n",
                 "0.4,0.3,0.2\n", "0.6,0.1,0.5\n", "0.8,0.0,0.8\n"]


def _with_row(header, rows, index, line):
    rows = list(rows)
    rows[index] = line
    return header + "".join(rows)


def _table_config(work, text):
    """configs/table_pvt с relperm.csv = text (как _table_config_with_csv теста)."""
    import shutil
    from gpn_multiphase_solver.io.config import load_config
    cfg_path = SOLVER / "configs" / "table_pvt" / "config.json"
    for fname in ("oil_pvt.csv", "gas_pvt.csv"):
        shutil.copy(cfg_path.parent / fname, work / fname)
    (work / "relperm.csv").write_text(text, encoding="utf-8")
    config = load_config(cfg_path)
    config.config_dir = work
    return config


def _standing_config(work, rows, hours):
    from gpn_multiphase_solver.io.config import load_config
    config = load_config(SOLVER / "examples" / "05_standing_table_rp" / "config.json")
    config.time.history = config.time.history[:hours]
    csv = work / "relperm.csv"
    csv.write_text("Sg,kro,krg\n" + "\n".join(rows) + "\n", encoding="utf-8")
    config.relperm.file = str(csv)
    return config


def expect_raises(name, config, pattern):
    from gpn_multiphase_solver.factory import SimulatorFactory
    try:
        SimulatorFactory.from_config(config)
    except ValueError as exc:
        ok = re.search(pattern, str(exc)) is not None
        print(f"{'PASS' if ok else 'FAIL'} {name}: {str(exc)[:150]}")
        return ok
    print(f"FAIL {name}: отказа нет")
    return False


def main():
    patch_in_memory()
    import logging
    from gpn_multiphase_solver.factory import (
        SimulatorFactory, _read_relperm_csv, _check_relperm_table)
    work = HERE / "work"
    work.mkdir(exist_ok=True)
    res = []

    # ── новые тесты TestCSVValueChecks ──
    res.append(expect_raises(
        "test_relperm_mobile_gas_at_zero_raises",
        _table_config(work, _with_row(RP_HEADER, TABLE_RP_ROWS, 0, "0.0,1.0,0.005\n")),
        r"relperm\.csv: k_rg в первой строке \(S_g = 0\) = 0\.005, нужно 0"))
    res.append(expect_raises(
        "test_relperm_rounding_noise_at_zero_raises",
        _table_config(work, _with_row(RP_HEADER, TABLE_RP_ROWS, 0, "0.0,1.0,1e-30\n")),
        r"k_rg в первой строке \(S_g = 0\) = 1e-30, нужно 0"))
    try:
        SimulatorFactory.from_config(
            _table_config(work, _with_row(RP_HEADER, TABLE_RP_ROWS, 0, "0.05,1.0,0.0\n")))
        print("PASS test_relperm_critical_gas_saturation_accepted: from_config прошёл")
        res.append(True)
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL test_relperm_critical_gas_saturation_accepted: {exc}")
        res.append(False)

    # ── прежние тексты: порядок проверок ──
    res.append(expect_raises("test_relperm_header_only_raises", _table_config(work, RP_HEADER),
                             r"relperm.csv: строк данных 0, нужно не меньше двух"))
    res.append(expect_raises("test_relperm_one_row_raises",
                             _table_config(work, RP_HEADER + TABLE_RP_ROWS[0]),
                             r"relperm.csv: строк данных 1, нужно не меньше двух"))
    swapped = TABLE_RP_ROWS[:2] + [TABLE_RP_ROWS[3], TABLE_RP_ROWS[2]] + TABLE_RP_ROWS[4:]
    res.append(expect_raises("test_relperm_sg_not_increasing_raises",
                             _table_config(work, RP_HEADER + "".join(swapped)),
                             r"relperm.csv: S_g не растёт строго: 0.2 после 0.4"))
    res.append(expect_raises(
        "test_relperm_mobile_oil_at_edge_raises",
        _table_config(work, _with_row(RP_HEADER, TABLE_RP_ROWS, 5, "0.8,0.05,0.8\n")),
        r"relperm\.csv: k_ro в последней строке \(S_g = 0\.8\) = 0\.05, нужно 0"))
    res.append(expect_raises(
        "test_relperm_rounding_noise_at_edge_raises",
        _table_config(work, _with_row(RP_HEADER, TABLE_RP_ROWS, 5, "0.8,1e-30,0.8\n")),
        r"= 1e-30, нужно 0"))
    res.append(expect_raises(
        "test_mobile_oil_edge_rejected_before_run",
        _standing_config(work, ["0.0,1.0,0.0", "0.01,0.98,0.001"], hours=1),
        r"relperm\.csv: k_ro в последней строке \(S_g = 0\.01\) = 0\.98, нужно 0"))
    # обе ошибки сразу — какая названа (порядок: первая строка раньше последней)
    both = _with_row(RP_HEADER, TABLE_RP_ROWS[:5] + ["0.8,0.05,0.8\n"], 0, "0.0,1.0,0.005\n")
    print("  (справка) обе ошибки:", end=" ")
    expect_raises("первая строка раньше последней", _table_config(work, both),
                  r"k_rg в первой строке")

    # ── таблицы проекта ──
    files = [p for folder in ("configs", "examples", "tests/data")
             for p in sorted((SOLVER / folder).glob("*/relperm.csv"))]
    extra = sorted((SOLVER / "deliverables").glob("*/relperm.csv"))
    for p in files + extra:
        Sg, kro, krg = _read_relperm_csv(p)
        _check_relperm_table(Sg, kro, krg, p.name)
    print(f"PASS test_project_relperm_tables_accepted: {len(files)} файлов в configs/examples/"
          f"tests/data (нужно ≥ 16) + {len(extra)} в deliverables — приняты")
    res.append(len(files) >= 16)

    # ── test_initial_below_table_not_repeated (DEBT-071): прежняя таблица и правка ──
    old = ["0.05,0.9,0.005", "0.1,0.8,0.01", "0.2,0.6,0.05", "0.4,0.3,0.2", "0.6,0.1,0.5", "0.8,0.0,0.8"]
    res.append(expect_raises("прежняя таблица теста DEBT-071 отвергается",
                             _standing_config(work, old, hours=6),
                             r"relperm\.csv: k_rg в первой строке \(S_g = 0\.05\) = 0\.005, нужно 0"))
    new = ["0.05,0.9,0.0"] + old[1:]

    class Collect(logging.Handler):
        def __init__(self):
            super().__init__(level=logging.WARNING)
            self.records = []

        def emit(self, record):
            self.records.append(record.getMessage())

    logger = logging.getLogger("gpn_multiphase_solver")
    h = Collect()
    logger.addHandler(h)
    logger.setLevel(logging.WARNING)
    try:
        sim, s0 = SimulatorFactory.from_config(_standing_config(work, new, hours=6))
        history = sim.run(s0)
    finally:
        logger.removeHandler(h)
    ok = (history.states[-1].Sg.min() == 0.0 and h.records == [
        "Начальное состояние вне таблиц: RELPERM Sg below table: min Sg=0, "
        "table min=0.05. Endpoint value used; no extrapolation."])
    print(f"{'PASS' if ok else 'FAIL'} test_initial_below_table_not_repeated (0.05,0.9,0.0): "
          f"Sg.min = {history.states[-1].Sg.min()}, записи {h.records}")
    res.append(ok)

    print(f"\nитого: {sum(res)} PASS из {len(res)}")


if __name__ == "__main__":
    main()
