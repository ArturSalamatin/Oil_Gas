"""Скрипт установки setup.bat (FEAT-031): статические проверки.

Сам скрипт здесь не исполняется: он создаёт .venv и ставит пакеты из
PyPI — в тестах это слишком долго и требует сети. Здесь — то, что ломается правкой текста: кодировка, команда
установки, граница версии Python, концы строк.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]                  # numerical_solver/
SETUP = ROOT / "setup.bat"
# Команда установки обоих пакетов для разработки — та же, что в README §1
# и в комментарии pyproject.toml
INSTALL = r'-m pip install -e HydroSolverPrototype\Prototype_1.0.3 -e ".[dev]"'


def test_setup_bat_ascii_only():
    """Только ASCII: консоль cmd в кодировке 866 вывела бы кириллицу из UTF-8 мусором."""
    data = SETUP.read_bytes()
    bad = sorted({b for b in data if b > 127})
    assert not bad, f"не-ASCII байты в setup.bat: {bad[:10]}"


def test_setup_bat_installs_both_packages():
    """Прототип и решатель с группой [dev] — одной командой; каталог прототипа существует."""
    text = SETUP.read_text(encoding="ascii")
    assert INSTALL in text
    assert (ROOT / "HydroSolverPrototype" / "Prototype_1.0.3" / "pyproject.toml").is_file()
    # Проверка установки — справка команды расчёта (решение пользователя FEAT-031:
    # без прогона тестов)
    assert "-m gpn_multiphase_solver run --help" in text


def test_setup_bat_command_matches_readme():
    """Ручная установка README §1 — та же команда, что выполняет setup.bat."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert rf".venv\Scripts\python {INSTALL}" in readme
    assert "setup.bat" in readme


def test_setup_bat_python_floor_matches_pyproject():
    """Граница версии Python в setup.bat — та же, что requires-python в pyproject.toml."""
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    major, minor = re.search(r'requires-python\s*=\s*">=(\d+)\.(\d+)"', pyproject).groups()
    text = SETUP.read_text(encoding="ascii")
    # Обе попытки — py -3 и python — проверяют одну и ту же границу
    assert text.count(f"sys.version_info < ({major}, {minor})") == 2


def test_gitattributes_bat_crlf():
    """.bat — с CRLF и в рабочем каталоге, и в срезе git archive (переходы goto в cmd)."""
    attrs = (ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert re.search(r"^\*\.bat\s+text\s+eol=crlf\s*$", attrs, re.M)
