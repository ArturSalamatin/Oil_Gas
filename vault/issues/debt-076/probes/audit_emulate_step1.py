"""DEBT-076, аудит 1: эмуляция шага 1 плана в памяти — блок «После:» как обёртка _validate.

Запуск из numerical_solver/ (в worktree — с PYTHONPATH на numerical_solver/ worktree):
    set PYTHONIOENCODING=utf-8
    .venv\\Scripts\\python ..\\vault\\issues\\debt-076\\probes\\audit_emulate_step1.py

Что проверяется, без правки файлов пакета и тестов:
  1. тесты TestValidationPVT из плана (код дословно) — до правки: 10 отказов нет
     (красные), 3 приёма; с проверкой плана: 10 отказов с ожидаемым текстом, 3 приёма;
  2. множество stricter теста FEAT-033 test_excel_not_stricter_than_program —
     без проверки {pvt.rho_g_std, pvt.rho_o_std}, с проверкой пустое.
Временные JSON — в подкаталоге _tmp_audit рядом со скриптом, удаляется в конце.
"""
import importlib.util
import inspect
import json
import logging
import shutil
from pathlib import Path

import pytest

SOLVER = Path.cwd()
print(f"каталог решателя: {SOLVER}")
TMP = Path(__file__).resolve().parent / "_tmp_audit"

logging.disable(logging.CRITICAL)
import gpn_multiphase_solver.io.config as c  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402

ORIG_VALIDATE = c._validate


def planned_check(cfg):
    """Блок «После:» шага 1 плана, дословно (без комментария)."""
    pc = cfg.pvt
    for name, value, phase in (("pvt.rho_o_std", pc.rho_o_std, "нефти"),
                               ("pvt.rho_g_std", pc.rho_g_std, "газа")):
        if value <= 0:
            raise ValueError(
                f"{name} = {value} кг/м³: плотность {phase} при стандартных "
                f"условиях (не пластовая) должна быть > 0")


def patched_validate(cfg):
    # Порча одного поля: порядок относительно остальных проверок не важен
    ORIG_VALIDATE(cfg)
    planned_check(cfg)


# ── Тесты плана (шаг 1, п. 1), без классов и декораторов ─────
def _write_json(tmp_path, data):
    p = tmp_path / "test.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def _minimal_raw():
    return {
        "geometry": {"r_well": 0.1, "R_ext": 50.0, "h": 10.0},
        "grid": {"N": 10},
        "rock": {"porosity": 0.2, "permeability": 1e-13},
        "pvt": {"model": "standing", "rho_o_std": 850.0, "rho_g_std": 0.85},
        "relperm": {"model": "corey"},
        "thermal": {},
        "initial_conditions": {"p0": 20e6, "T0": 350.0, "Rs0": 50.0},
        "time": {
            "dt_integration": 3600,
            "history": [{"dt": 86400, "control": "pressure", "p_wf": 10e6}],
        },
    }


REJECT = [("rho_o_std", -850.0), ("rho_o_std", 0.0), ("rho_g_std", -0.85),
          ("rho_g_std", 0.0), ("rho_g_std", -5e-324)]
ACCEPT = [(850.0, 0.85), (800.0, 0.727), (800.0, 1.014)]


def test_nonpositive_density_rejected(tmp_path, key, value, model):
    raw = _minimal_raw()
    raw["pvt"]["model"] = model
    if model == "table":
        raw["pvt"].update(oil_pvt_file="oil_pvt.csv", gas_pvt_file="gas_pvt.csv")
    raw["pvt"][key] = value
    with pytest.raises(ValueError, match=f"pvt.{key}") as exc:
        load_config(_write_json(tmp_path, raw))
    assert f"= {value} кг/м³" in str(exc.value)
    assert "при стандартных условиях" in str(exc.value)
    return str(exc.value)


def test_project_densities_accepted(tmp_path, rho_o, rho_g):
    raw = _minimal_raw()
    raw["pvt"].update(rho_o_std=rho_o, rho_g_std=rho_g)
    cfg = load_config(_write_json(tmp_path, raw))
    assert (cfg.pvt.rho_o_std, cfg.pvt.rho_g_std) == (rho_o, rho_g)


def run_plan_tests(label):
    failed = passed = 0
    for model in ("standing", "table"):
        for key, value in REJECT:
            try:
                msg = test_nonpositive_density_rejected(TMP, key, value, model)
                passed += 1
                if model == "table":
                    print(f"  {key} = {value}: {msg}")
            except BaseException as e:  # pytest.raises без исключения — Failed (BaseException)
                failed += 1
    for rho_o, rho_g in ACCEPT:
        try:
            test_project_densities_accepted(TMP, rho_o, rho_g)
            passed += 1
        except BaseException:
            failed += 1
    print(f"{label}: TestValidationPVT — {passed} passed, {failed} failed")


# ── Тест FEAT-033: множество stricter ─────────────────────────
def feat033_stricter():
    path = SOLVER / "tests" / "test_workbook_format.py"
    spec = importlib.util.spec_from_file_location("twf_probe", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    src = inspect.getsource(mod.test_excel_not_stricter_than_program)
    old = 'assert stricter == {"pvt.rho_o_std", "pvt.rho_g_std"}'
    assert old in src, "якорь теста FEAT-033 не найден"
    exec(src.replace(old, "return stricter"), mod.__dict__)
    return sorted(mod.test_excel_not_stricter_than_program(TMP))


TMP.mkdir(exist_ok=True)
try:
    run_plan_tests("без проверки (база)")
    print(f"без проверки (база): stricter FEAT-033 = {feat033_stricter()}")
    c._validate = patched_validate
    run_plan_tests("с проверкой плана")
    print(f"с проверкой плана: stricter FEAT-033 = {feat033_stricter()}")
finally:
    c._validate = ORIG_VALIDATE
    shutil.rmtree(TMP, ignore_errors=True)
