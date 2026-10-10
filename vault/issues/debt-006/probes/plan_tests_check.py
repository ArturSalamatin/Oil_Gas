"""Аудит DEBT-006: тесты плана на каждой стадии реализации; правки — в памяти, код не меняется.

Запуск из каталога numerical_solver (журнал фабрики — в stderr, его можно отбросить):

    cd <корень>\\numerical_solver
    .venv\\Scripts\\python <путь к этой пробе> 2>$null

Стадии накопительные, как шаги плана:
  S1 — текущий код (база);
  S2 — шаг 2: свойства TableFullPVT.hydro, PrototypePVTAdapter.proto_pvt,
       PrototypeRPAdapter.proto_rp (property без сеттера);
  S3 — шаг 3: _get_or_create_proto_pvt/_rp по isinstance (код плана дословно);
  S4 — шаг 4: адаптеру — сам FullPVT (обёртка над _create_prototype_hydro
       подставляет adapter._pvt = pvt, что равносильно PrototypeHydroAdapter(model, grid, pvt));
  S5 — шаг 5: _table_nodes (код плана дословно), _pvt_table_nodes — выбор по
       isinstance + публичные свойства перед прежним телом.
Тело каждого теста — из блоков плана (self убран). Для теста шага k печатается
исход на S(k-1), S(k) и S5; ожидание — колонка «До правки» таблицы
«Тестовая стратегия» плана и «все зелёные» на S5.
В конце — отпечаток истории 03/04/05 на S5 против S1 (побитовость шага 4).
"""

import hashlib
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

SOLVER = Path.cwd()
if not (SOLVER / "gpn_multiphase_solver").is_dir():
    sys.exit(f"Запускать из каталога numerical_solver; сейчас {SOLVER}")
sys.path[:0] = [str(SOLVER), str(SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"),
                str(SOLVER / "examples")]

from gpn_multiphase_solver import factory  # noqa: E402
from gpn_multiphase_solver.factory import (  # noqa: E402
    SimulatorFactory, _create_pvt, _create_relperm, _read_relperm_csv,
)
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.hydro.prototype_adapter import PrototypeHydroAdapter  # noqa: E402
from gpn_multiphase_solver.pvt.table_full import TableFullPVT  # noqa: E402
from gpn_multiphase_solver.pvt.prototype_adapter import (  # noqa: E402
    PrototypePVTAdapter, PrototypeRPAdapter,
)
from gpn_multiphase_solver.pvt.hydro_to_blackoil_adapter import HydroPVTtoBlackOilAdapter  # noqa: E402
from gpn_multiphase_solver.pvt.relperm import CoreyRP  # noqa: E402
from radial_blackoil.relperm import TabulatedRelPerm  # noqa: E402
import pvt_plot  # noqa: E402
import relperm_plot  # noqa: E402

print(f"Код: {factory.__file__}")

TABLE_CONFIG = SOLVER / "configs" / "table_pvt" / "config.json"
BASELINE = SOLVER / "configs" / "baseline.json"
EXAMPLES_DIR = SOLVER / "examples"
P0 = 20e6

# ── Правки плана в памяти ────────────────────────────────────

ORIG = {
    "pvt": factory._get_or_create_proto_pvt,
    "rp": factory._get_or_create_proto_rp,
    "cph": factory._create_prototype_hydro,
    "ptn": pvt_plot._pvt_table_nodes,
    "tn": relperm_plot._table_nodes,
}


def new_get_or_create_proto_pvt(pvt, p0):
    """Шаг 3, «После» — дословно."""
    if isinstance(pvt, TableFullPVT):
        return pvt.hydro.proto_pvt
    return HydroPVTtoBlackOilAdapter(pvt, p_max_pa=p0)


def new_get_or_create_proto_rp(relperm):
    """Шаг 3, «После» — дословно (ветка Кори — прежняя)."""
    if isinstance(relperm, PrototypeRPAdapter):
        return relperm.proto_rp
    Sg = np.linspace(0.0, 1.0, 101)
    return TabulatedRelPerm(Sg, relperm.kro(Sg), relperm.krg(Sg))


def new_create_prototype_hydro(config, grid, pvt, relperm):
    """Шаг 4: адаптер держит сам FullPVT."""
    hydro = ORIG["cph"](config, grid, pvt, relperm)
    hydro._pvt = pvt
    return hydro


def new_pvt_table_nodes(pvt, Rs0):
    """Шаг 5: выбор по классу и публичный путь; дальше — прежнее тело."""
    if not isinstance(pvt, TableFullPVT):
        return None
    assert pvt.hydro.proto_pvt is pvt._hydro._pvt
    return ORIG["ptn"](pvt, Rs0)


def new_table_nodes(relperm):
    """Шаг 5, «После» — дословно."""
    from gpn_multiphase_solver.pvt.prototype_adapter import PrototypeRPAdapter as RP
    if not isinstance(relperm, RP):
        return None
    proto = relperm.proto_rp
    return (np.asarray(proto.sg, float),
            np.asarray(proto.kro_tab, float),
            np.asarray(proto.krg_tab, float))


def apply(stage: int) -> None:
    """Привести код в памяти к стадии S<stage> (1…5)."""
    for cls, name in ((PrototypePVTAdapter, "proto_pvt"), (TableFullPVT, "hydro"),
                      (PrototypeRPAdapter, "proto_rp")):
        if name in cls.__dict__:
            delattr(cls, name)
    factory._get_or_create_proto_pvt = ORIG["pvt"]
    factory._get_or_create_proto_rp = ORIG["rp"]
    factory._create_prototype_hydro = ORIG["cph"]
    pvt_plot._pvt_table_nodes = ORIG["ptn"]
    relperm_plot._table_nodes = ORIG["tn"]
    if stage >= 2:
        PrototypePVTAdapter.proto_pvt = property(lambda self: self._pvt)
        TableFullPVT.hydro = property(lambda self: self._hydro)
        PrototypeRPAdapter.proto_rp = property(lambda self: self._rp)
    if stage >= 3:
        factory._get_or_create_proto_pvt = new_get_or_create_proto_pvt
        factory._get_or_create_proto_rp = new_get_or_create_proto_rp
    if stage >= 4:
        factory._create_prototype_hydro = new_create_prototype_hydro
    if stage >= 5:
        pvt_plot._pvt_table_nodes = new_pvt_table_nodes
        relperm_plot._table_nodes = new_table_nodes


# ── Тесты плана (тела — из блоков шагов) ─────────────────────

def _wrappers():
    proto_pvt, proto_rp = object(), object()
    adapter = PrototypePVTAdapter(proto_pvt, rho_o_std=850.0, rho_g_std=0.85)
    table = TableFullPVT(adapter, c_p_oil=2000.0, c_p_gas=2200.0,
                         mu_JT_oil=-4e-7, mu_JT_gas=3e-6, L_degas=0.0)
    rp = PrototypeRPAdapter(proto_rp)
    return proto_pvt, proto_rp, adapter, table, rp


def test_prototype_pvt_adapter_proto_pvt():
    proto_pvt, _, adapter, _, _ = _wrappers()
    assert adapter.proto_pvt is proto_pvt


def test_table_full_pvt_hydro():
    proto_pvt, _, adapter, table, _ = _wrappers()
    assert table.hydro is adapter
    assert table.hydro.proto_pvt is proto_pvt


def test_prototype_rp_adapter_proto_rp():
    _, proto_rp, _, _, rp = _wrappers()
    assert rp.proto_rp is proto_rp


def test_accessors_read_only():
    _, _, adapter, table, rp = _wrappers()
    for obj, name in ((adapter, "proto_pvt"), (table, "hydro"), (rp, "proto_rp")):
        with pytest.raises(AttributeError):
            setattr(obj, name, object())


def test_pvt_branch_ignores_private_field_names():
    pvt = _create_pvt(load_config(BASELINE))
    pvt._hydro = SimpleNamespace(_pvt="посторонний объект")
    proto = factory._get_or_create_proto_pvt(pvt, P0)
    assert isinstance(proto, HydroPVTtoBlackOilAdapter)


def test_rp_branch_ignores_private_field_names():
    corey = CoreyRP(S_or=0.2, S_gc=0.05, n_o=2.0, n_g=2.0)
    corey._rp = "посторонний объект"
    proto = factory._get_or_create_proto_rp(corey)
    assert isinstance(proto, TabulatedRelPerm)
    assert proto.sg.size == 101


def test_proto_pvt_shared_for_table():
    config = load_config(TABLE_CONFIG)
    pvt = _create_pvt(config)
    proto = factory._get_or_create_proto_pvt(pvt, config.initial_conditions.p0)
    assert proto is pvt.hydro.proto_pvt


def test_proto_rp_shared_for_table():
    relperm = _create_relperm(load_config(TABLE_CONFIG))
    assert factory._get_or_create_proto_rp(relperm) is relperm.proto_rp


def test_prototype_relperm_from_csv():
    config = load_config(TABLE_CONFIG)
    assert isinstance(_create_relperm(config), PrototypeRPAdapter)
    simulator, _ = SimulatorFactory.from_config(config)
    model = simulator._hydro._model
    Sg, _, _ = _read_relperm_csv(config.config_dir / config.relperm.file)
    np.testing.assert_array_equal(model.relperm.sg, Sg)
    assert model.sg_activation_cap == 0.6


def test_pvt_objects_are_same():
    config = load_config(TABLE_CONFIG)
    simulator, _ = SimulatorFactory.from_config(config)
    hydro = simulator._hydro
    assert isinstance(hydro, PrototypeHydroAdapter)
    assert hydro._model.pvt is simulator._pvt.hydro.proto_pvt
    assert hydro._pvt is simulator._pvt
    assert simulator._energy._pvt is simulator._pvt


def test_bo_consistency():
    from gpn_multiphase_solver.units import BAR_TO_PA
    config = load_config(TABLE_CONFIG)
    simulator, _ = SimulatorFactory.from_config(config)
    our_pvt = simulator._pvt.hydro
    proto_pvt = our_pvt.proto_pvt
    p_pa, Rs = 15e6, 20.0
    bo_our = our_pvt.Bo(np.array([p_pa]), np.array([Rs]))[0]
    bo_proto = proto_pvt.bo(np.array([p_pa / BAR_TO_PA]), np.array([Rs]))[0]
    assert bo_our == pytest.approx(bo_proto)


def test_standing_pvt_shared():
    simulator, _ = SimulatorFactory.from_config(load_config(BASELINE))
    model_pvt = simulator._hydro._model.pvt
    assert isinstance(model_pvt, HydroPVTtoBlackOilAdapter)
    assert model_pvt._hydro is simulator._pvt
    assert simulator._hydro._pvt is simulator._pvt
    assert simulator._energy._pvt is simulator._pvt


def _pvt_of_config(cfg):
    return _create_pvt(cfg)


def test_relperm_nodes_from_csv():
    cfg = load_config(EXAMPLES_DIR / "04_table_table" / "config.json")
    nodes = relperm_plot._table_nodes(_create_relperm(cfg))
    expected = _read_relperm_csv(cfg.config_dir / cfg.relperm.file)
    assert nodes is not None
    for got, exp in zip(nodes, expected):
        np.testing.assert_array_equal(got, exp)


def test_relperm_nodes_none_for_corey():
    cfg = load_config(EXAMPLES_DIR / "03_standing_corey" / "config.json")
    assert relperm_plot._table_nodes(_create_relperm(cfg)) is None


def test_pvt_nodes_none_for_standing():
    cfg = load_config(EXAMPLES_DIR / "03_standing_corey" / "config.json")
    Rs0 = float(cfg.initial_conditions.Rs0)
    assert pvt_plot._pvt_table_nodes(_pvt_of_config(cfg), Rs0) is None


def test_p_branch_follows_rs0_row():
    """Существующий быстрый тест табличного пути _pvt_table_nodes (test_examples.py:1197)."""
    cfg = load_config(EXAMPLES_DIR / "04_table_table" / "config.json")
    pvt = _pvt_of_config(cfg)
    nodes = pvt_plot._pvt_table_nodes(pvt, 30.0)
    assert np.allclose(nodes["p_branch"], [15e6, 30e6])
    assert np.allclose(nodes["p_oil"], [5e6, 15e6, 30e6])
    assert pvt_plot._pvt_table_nodes(pvt, 20.0)["p_branch"].size == 0


# (тест, шаг плана, ожидание до своей правки: True — зелёный, False — красный)
TESTS = [
    (test_prototype_pvt_adapter_proto_pvt, 2, False),
    (test_table_full_pvt_hydro, 2, False),
    (test_prototype_rp_adapter_proto_rp, 2, False),
    (test_accessors_read_only, 2, False),
    (test_pvt_branch_ignores_private_field_names, 3, False),
    (test_rp_branch_ignores_private_field_names, 3, False),
    (test_proto_pvt_shared_for_table, 3, True),
    (test_proto_rp_shared_for_table, 3, True),
    (test_prototype_relperm_from_csv, 3, True),
    (test_pvt_objects_are_same, 4, False),
    (test_bo_consistency, 4, True),
    (test_standing_pvt_shared, 4, True),
    (test_relperm_nodes_from_csv, 5, True),
    (test_relperm_nodes_none_for_corey, 5, True),
    (test_pvt_nodes_none_for_standing, 5, True),
    (test_p_branch_follows_rs0_row, 5, True),
]


def _run(func, stage):
    """Исход теста на стадии: ('ok', '') или ('FAIL', причина)."""
    apply(stage)
    try:
        func()
        return True, ""
    except BaseException as e:  # noqa: BLE001 — pytest.fail даёт Failed (BaseException)
        return False, f"{type(e).__name__}: {str(e).splitlines()[0][:70] if str(e) else ''}"
    finally:
        apply(1)


def _mark(ok):
    return "✓" if ok else "✗"


def _fingerprint(stage):
    """SHA-256 истории примеров 03/04/05 на стадии (функции пробы history_fingerprint)."""
    spec = importlib.util.spec_from_file_location(
        "hf", Path(__file__).with_name("history_fingerprint.py"))
    hf = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hf)
    apply(stage)
    try:
        out = []
        for name in hf.EXAMPLES:
            config = load_config(EXAMPLES_DIR / name / "config.json")
            config.output.log_level = "WARNING"
            sim, ini = SimulatorFactory.from_config(config)
            h = sim.run(ini)
            d = hashlib.sha256()
            for part in (h.times, h.states, h.hydro_results, h.well_data,
                         h.balance, h.mass_balance):
                hf._feed(d, part)
            out.append((name, d.hexdigest()))
        return out
    finally:
        apply(1)


def main():
    bad = 0
    print(f"{'тест':48s} шаг  до   после  S5   ожидание до")
    for func, step, expect_before in TESTS:
        ok_before, why_before = _run(func, step - 1)
        ok_after, why_after = _run(func, step)
        ok_final, why_final = _run(func, 5)
        good = (ok_before == expect_before) and ok_after and ok_final
        bad += not good
        print(f"{func.__name__:48s} {step:3d}  {_mark(ok_before)}    {_mark(ok_after)}     "
              f"{_mark(ok_final)}    {_mark(expect_before)}  {'' if good else '  <-- РАСХОЖДЕНИЕ'}")
        for why in (why_before if ok_before != expect_before else "",
                    why_after, why_final):
            if why:
                print(f"    {why}")
    print(f"Расхождений с планом: {bad}")

    f1, f5 = _fingerprint(1), _fingerprint(5)
    for (name, a), (_, b) in zip(f1, f5):
        print(f"отпечаток {name}: {'совпал' if a == b else 'РАЗНЫЙ'}  {a[:16]}")


if __name__ == "__main__":
    main()
