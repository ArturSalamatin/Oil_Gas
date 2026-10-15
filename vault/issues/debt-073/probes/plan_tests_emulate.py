"""DEBT-073: эмуляция кода шага 1 плана и сценариев его тестов на коде базы.

Код плана (_check_relperm_table с kro, вызов в create_relperm) подставлен в модуль
factory в памяти; файлы пакета не меняются. Сценарии — тесты плана §7 и прежние
тесты порядка проверок.

Запуск из numerical_solver/:
    .venv\\Scripts\\python ..\\vault\\issues\\debt-073\\probes\\plan_tests_emulate.py
"""
import re
import shutil
from pathlib import Path

import gpn_multiphase_solver
import gpn_multiphase_solver.factory as factory
from gpn_multiphase_solver.factory import SimulatorFactory, _read_relperm_csv
from gpn_multiphase_solver.io.config import load_config
from gpn_multiphase_solver.pvt.prototype_adapter import PrototypeRPAdapter

SOLVER = Path.cwd()
HERE = Path(__file__).resolve().parent
WORK = HERE / "emulate_work"
print(f"код: {Path(gpn_multiphase_solver.__file__).parent}", flush=True)

_orig_check = factory._check_relperm_table


# ── Код плана, шаг 1 ──
def _check_relperm_table(Sg, kro, relperm_file):
    _orig_check(Sg, relperm_file)
    if kro[-1] > 0:
        raise ValueError(
            f"{relperm_file}: k_ro в последней строке (S_g = {Sg[-1]:g}) = {kro[-1]:g}, "
            f"нужно 0. Выше последней строки k_ro и k_rg берутся из неё: при k_ro > 0 "
            f"нефть подвижна при любой S_o, и у забоя S_o ничто не удерживает от "
            f"ухода ниже нуля. Таблица кончается строкой с k_ro = 0 — при "
            f"S_g = 1 - S_or (S_or — остаточная нефтенасыщенность) или выше.")


_orig_create = factory.create_relperm


def create_relperm(config):
    rc = config.relperm
    if rc.model != "table":
        return _orig_create(config)
    Sg, kro, krg = _read_relperm_csv(config.config_dir / rc.file)
    _check_relperm_table(Sg, kro, rc.file)
    from radial_blackoil.relperm import TabulatedRelPerm
    return PrototypeRPAdapter(TabulatedRelPerm(Sg, kro, krg))


factory._check_relperm_table = _check_relperm_table
factory.create_relperm = create_relperm

# ── Помощники тестов (копии test_factory_prototype.py) ──
TABLE_CONFIG = SOLVER / "configs" / "table_pvt" / "config.json"
RP_HEADER = "Sg,kro,krg\n"
TABLE_RP_ROWS = ["0.0,1.0,0.0\n", "0.1,0.8,0.01\n", "0.2,0.6,0.05\n",
                 "0.4,0.3,0.2\n", "0.6,0.1,0.5\n", "0.8,0.0,0.8\n"]


def _with_row(header, rows, index, line):
    rows = list(rows)
    rows[index] = line
    return header + "".join(rows)


def _table_config_with_csv(case, name, text):
    d = WORK / case
    d.mkdir(parents=True, exist_ok=True)
    for fname in ("oil_pvt.csv", "gas_pvt.csv", "relperm.csv"):
        shutil.copy(TABLE_CONFIG.parent / fname, d / fname)
    (d / name).write_text(text, encoding="utf-8")
    config = load_config(TABLE_CONFIG)
    config.config_dir = d
    return config


def expect_raises(label, config, pattern):
    try:
        SimulatorFactory.from_config(config)
    except ValueError as exc:
        ok = re.search(pattern, str(exc)) is not None
        print(f"{'PASS' if ok else 'FAIL'} {label}: {str(exc)[:200]}")
        return
    print(f"FAIL {label}: исключения нет")


expect_raises("mobile_oil_at_edge",
              _table_config_with_csv("edge", "relperm.csv",
                                     _with_row(RP_HEADER, TABLE_RP_ROWS, 5, "0.8,0.05,0.8\n")),
              r"relperm\.csv: k_ro в последней строке \(S_g = 0\.8\) = 0\.05, нужно 0")
expect_raises("rounding_noise_at_edge",
              _table_config_with_csv("noise", "relperm.csv",
                                     _with_row(RP_HEADER, TABLE_RP_ROWS, 5, "0.8,1e-30,0.8\n")),
              r"= 1e-30, нужно 0")
# Порядок проверок: прежние тексты
expect_raises("one_row (прежний текст)",
              _table_config_with_csv("one", "relperm.csv", RP_HEADER + TABLE_RP_ROWS[0]),
              r"relperm\.csv: строк данных 1, нужно не меньше двух")
expect_raises("header_only (прежний текст)",
              _table_config_with_csv("hdr", "relperm.csv", RP_HEADER),
              r"relperm\.csv: строк данных 0, нужно не меньше двух")
swapped = TABLE_RP_ROWS[:2] + [TABLE_RP_ROWS[3], TABLE_RP_ROWS[2]] + TABLE_RP_ROWS[4:]
expect_raises("sg_not_increasing (прежний текст)",
              _table_config_with_csv("swap", "relperm.csv", RP_HEADER + "".join(swapped)),
              r"relperm\.csv: S_g не растёт строго: 0\.2 после 0\.4")

# Тест DEBT-071, переделанный: пример 05, таблица до 0.01, абсолютный путь в relperm.file
cfg = load_config(SOLVER / "examples" / "05_standing_table_rp" / "config.json")
cfg.time.history = cfg.time.history[:1]
d = WORK / "standing"
d.mkdir(parents=True, exist_ok=True)
csv = d / "relperm.csv"
csv.write_text("Sg,kro,krg\n0.0,1.0,0.0\n0.01,0.98,0.001\n", encoding="utf-8")
cfg.relperm.file = str(csv)
expect_raises("mobile_oil_edge_rejected_before_run (05, Стендинг)", cfg,
              r"relperm\.csv: k_ro в последней строке \(S_g = 0\.01\) = 0\.98, нужно 0")

# Все таблицы проекта
files = [p for folder in ("configs", "examples", "tests/data")
         for p in sorted((SOLVER / folder).glob("*/relperm.csv"))]
bad = []
for p in files:
    Sg, kro, _ = _read_relperm_csv(p)
    try:
        _check_relperm_table(Sg, kro, p.name)
    except ValueError as exc:
        bad.append((p, str(exc)[:100]))
print(f"{'PASS' if len(files) >= 16 and not bad else 'FAIL'} project_relperm_tables_accepted: "
      f"файлов {len(files)}, отвергнуто {len(bad)}")
for p, m in bad:
    print(f"    {p}: {m}")

# Принятая таблица проекта строит решатель как прежде
sim, _ = SimulatorFactory.from_config(load_config(TABLE_CONFIG))
print(f"PASS configs/table_pvt: from_config прошёл ({type(sim).__name__})")
shutil.rmtree(WORK)
