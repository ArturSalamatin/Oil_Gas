"""Команда расчёта по конфигу: python -m gpn_multiphase_solver run (FEAT-030).

Инженер заказчика считает свой сценарий командой из установленного пакета,
из любого каталога, без репозитория. Проверяется:
  - команда в отдельном процессе из постороннего каталога: код 0, штатный
    набор файлов, печать заголовка и сводки;
  - коды возврата: 2 — ошибка конфига или аргументов (расчёт не начат),
    1 — отказ решателя (без трассировки), 0 — успех;
  - флаги --output, --title, --profiles доходят до run_case;
  - точка входа gpn-solver объявлена в pyproject.toml;
  - модули пакета не трогают режим matplotlib и кодировку консоли при
    импорте — это делает только configure_batch_run.

Подпроцессы получают PYTHONPATH на пакет и прототип этого дерева: иначе в
worktree они взяли бы установленный пакет основного каталога (правило 3
/implement). GPN_EXAMPLES_EMF = "0" наследуется из tests/conftest.py.
"""

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import gpn_multiphase_solver.report.pipeline as pipeline
from gpn_multiphase_solver import cli
from gpn_multiphase_solver.simulator import Simulator

SOLVER = Path(__file__).resolve().parents[1]                 # numerical_solver/
PROTO = SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"  # дистрибутив radial-blackoil
EXAMPLES_DIR = SOLVER / "examples"

# Штатный набор файлов двухфазного расчёта (R_s0 > 0: есть rs_profiles.png)
STANDARD_FILES = sorted([
    "well_history.csv", "profiles.csv",
    "pressure_profiles.png", "temperature_profiles.png", "saturation_profiles.png",
    "rs_profiles.png", "well_rates.png", "wellbore_dynamics.png",
    "relperm.png", "pvt.png", "energy_balance.png", "mass_balance.png",
])


def _env(**extra) -> dict:
    """Окружение подпроцесса: пакет и прототип этого дерева, вывод в UTF-8."""
    env = dict(os.environ, PYTHONIOENCODING="utf-8",
               PYTHONPATH=os.pathsep.join([str(SOLVER), str(PROTO)]))
    env.update(extra)
    return env


def _run(args, cwd: Path, **extra) -> subprocess.CompletedProcess:
    """python <args> в отдельном процессе из каталога cwd."""
    return subprocess.run([sys.executable, *args], cwd=cwd, env=_env(**extra),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace")


def _small_case(dst: Path, **output) -> Path:
    """Конфиг примера 03 на сетке N = 20, одни сутки (запись раз в 12 ч) — в dst/case.

    Standing + Corey: CSV не нужны. Расчёт ~1 с, с рисунками и запуском
    процесса — ~8 с (проба аудита FEAT-030 audit_key_scenario.py). output
    заменяется целиком: стационарная аналитика — по умолчанию (выключена).
    """
    raw = json.loads((EXAMPLES_DIR / "03_standing_corey" / "config.json")
                     .read_text(encoding="utf-8"))
    raw["grid"]["N"] = 20
    h0 = raw["time"]["history"][0]
    raw["time"]["history"] = [dict(h0, duration=86400.0, dt_out=43200.0)]
    raw["output"] = {"log_level": "INFO", "title": "тест команды", **output}
    case = dst / "case"
    case.mkdir(parents=True)
    cfg = case / "config.json"
    cfg.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    return cfg


# ── Команда в отдельном процессе ─────────────────────────────

def test_help_via_module(tmp_path):
    """python -m gpn_multiphase_solver run --help: код 0, флаги и коды возврата в справке."""
    r = _run(["-m", "gpn_multiphase_solver", "run", "--help"], cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    for text in ("--output", "--title", "--profiles", "Коды возврата"):
        assert text in r.stdout, f"нет «{text}» в справке"


def test_run_from_foreign_directory(tmp_path):
    """Команда из постороннего каталога: код 0, 12 файлов штатного набора, заголовок из конфига.

    Путь к конфигу относительный — команда печатает абсолютный (так же,
    как печатали main.py примеров). Ловит: зависимость команды от
    каталога запуска или от examples/ в sys.path.
    """
    cfg = _small_case(tmp_path)
    r = _run(["-m", "gpn_multiphase_solver", "run", "case/config.json"], cwd=tmp_path)
    assert r.returncode == 0, r.stderr[-2000:]

    out = cfg.parent / "output"
    assert sorted(f.name for f in out.iterdir()) == STANDARD_FILES
    lines = r.stdout.splitlines()
    assert lines[0] == "=== тест команды ==="
    assert lines[1] == f"Конфиг: {cfg.resolve()}"
    assert any(s.startswith("Шагов сохранено") for s in lines)

    # Пакет — из этого дерева, а не установленный в общий venv
    p = _run(["-c", "import gpn_multiphase_solver as g; print(g.__file__)"], cwd=tmp_path)
    assert Path(p.stdout.strip()).resolve().parent == (SOLVER / "gpn_multiphase_solver").resolve()


# ── Коды возврата (в процессе тестов) ────────────────────────

def test_missing_config_returns_2(tmp_path, capsys):
    """Нет файла конфига → код 2, сообщение называет файл."""
    assert cli.main(["run", str(tmp_path / "нет.json")]) == 2
    err = capsys.readouterr().err
    assert "Ошибка конфига" in err and "нет.json" in err


def test_invalid_field_returns_2(tmp_path, capsys):
    """Недопустимое поле конфига → код 2, имя поля в сообщении (проверка load_config)."""
    cfg = _small_case(tmp_path, n_profiles=1)
    assert cli.main(["run", str(cfg)]) == 2
    assert "output.n_profiles" in capsys.readouterr().err


def test_unknown_key_returns_2(tmp_path, capsys):
    """Лишний ключ секции (опечатка в имени поля) → код 2, а не трассировка TypeError."""
    cfg = _small_case(tmp_path)
    raw = json.loads(cfg.read_text(encoding="utf-8"))
    raw["geometry"]["foo"] = 1.0
    cfg.write_text(json.dumps(raw), encoding="utf-8")
    assert cli.main(["run", str(cfg)]) == 2
    assert "Ошибка конфига" in capsys.readouterr().err


def test_run_failure_returns_1(tmp_path, capsys, monkeypatch):
    """Отказ решателя → код 1, его текст в stderr, без трассировки."""
    def fail(self, *args, **kwargs):
        raise RuntimeError("шаг не сошёлся")
    monkeypatch.setattr(Simulator, "run", fail)

    cfg = _small_case(tmp_path)
    assert cli.main(["run", str(cfg)]) == 1
    err = capsys.readouterr().err
    assert "Расчёт не завершён" in err and "шаг не сошёлся" in err
    assert "Traceback" not in err


def test_output_with_config_refused(tmp_path, capsys, monkeypatch):
    """--output = папка конфига → код 2 до расчёта, конфиг на месте (решение пользователя 2026-10-13)."""
    def must_not_run(self, *args, **kwargs):
        raise AssertionError("расчёт начат при каталоге вывода с конфигом")
    monkeypatch.setattr(Simulator, "run", must_not_run)

    cfg = _small_case(tmp_path)
    assert cli.main(["run", str(cfg), "--output", str(cfg.parent)]) == 2
    assert cfg.is_file()
    assert "содержит входной файл" in capsys.readouterr().err


# ── Аргументы ────────────────────────────────────────────────

def test_flags_passed_to_run_case(tmp_path, monkeypatch):
    """--output, --title, --profiles доходят до run_case; пути — абсолютные; без флагов — None."""
    calls = []
    monkeypatch.setattr(pipeline, "run_case",
                        lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.chdir(tmp_path)

    assert cli.main(["run", "cfg.json", "--title", "T", "--profiles", "5",
                     "--output", "o"]) == 0
    assert calls[0] == (((tmp_path / "cfg.json").resolve(), (tmp_path / "o").resolve()),
                        {"title": "T", "n_profiles": 5})

    # Без флагов — None: run_case возьмёт значения из output конфига, вывод — рядом с ним
    assert cli.main(["run", "cfg.json"]) == 0
    assert calls[1] == (((tmp_path / "cfg.json").resolve(), None),
                        {"title": None, "n_profiles": None})


def test_profiles_below_two_rejected():
    """--profiles 1 → ошибка аргументов, код 2: один момент эволюции не показывает."""
    with pytest.raises(SystemExit) as e:
        cli.main(["run", "c.json", "--profiles", "1"])
    assert e.value.code == 2


def test_command_required():
    """Без подкоманды → ошибка аргументов, код 2."""
    with pytest.raises(SystemExit) as e:
        cli.main([])
    assert e.value.code == 2


def test_console_script_declared():
    """gpn-solver в [project.scripts] указывает на cli.main — ту же функцию, что и python -m."""
    tomllib = pytest.importorskip("tomllib")
    with open(SOLVER / "pyproject.toml", "rb") as f:
        scripts = tomllib.load(f)["project"]["scripts"]
    assert scripts["gpn-solver"] == "gpn_multiphase_solver.cli:main"
    module, func = scripts["gpn-solver"].split(":")
    assert getattr(importlib.import_module(module), func) is cli.main


# ── Побочные эффекты импорта ─────────────────────────────────

def test_report_import_has_no_side_effects(tmp_path):
    """Импорт конвейера и команды не меняет режим matplotlib и кодировку консоли.

    Пользователь пакета в Jupyter не должен получить Agg и перенастроенный
    поток от одного import. Режим svg задан до импорта — после него должен
    остаться svg; поток в cp1251 — остаться cp1251. Ловит: возврат
    matplotlib.use("Agg") или reconfigure на уровень модуля пакета.
    """
    code = ("import matplotlib; matplotlib.use('svg'); "
            "import gpn_multiphase_solver.report.pipeline, gpn_multiphase_solver.cli; "
            "import sys; print(matplotlib.get_backend(), sys.stdout.encoding)")
    r = _run(["-c", code], cwd=tmp_path, PYTHONIOENCODING="cp1251")
    assert r.returncode == 0, r.stderr[-2000:]
    assert r.stdout.split() == ["svg", "cp1251"]


def test_configure_batch_run(tmp_path):
    """configure_batch_run: консоль UTF-8 и режим Agg (имя — в регистре, переданном use)."""
    code = ("from gpn_multiphase_solver.cli import configure_batch_run; "
            "configure_batch_run(); import matplotlib, sys; "
            "print(matplotlib.get_backend().lower(), sys.stdout.encoding)")
    r = _run(["-c", code], cwd=tmp_path, PYTHONIOENCODING="cp1251")
    assert r.returncode == 0, r.stderr[-2000:]
    assert r.stdout.split() == ["agg", "utf-8"]
