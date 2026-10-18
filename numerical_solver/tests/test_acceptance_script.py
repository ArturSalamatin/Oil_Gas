"""Скрипт приёмки tools/acceptance.py (FEAT-031): его чистые функции и списки.

Целиком приёмка идёт на собранной копии (tools/handover.py в корне
репозитория — около 15 мин и доступ к PyPI). Здесь — разбор итога pytest,
допустимые причины пропуска (не разошлись ли с текстами в тестах), набор
файлов результатов (описан ли в README), чтение versions.txt.
"""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]                  # numerical_solver/


def _load():
    """Модуль tools/acceptance.py (каталог tools — не пакет)."""
    spec = importlib.util.spec_from_file_location("acceptance", ROOT / "tools" / "acceptance.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


acc = _load()

# Итог pytest -rs в копии без vault и без черновика руководителя (замер плана
# FEAT-031 на срезе v1.0.0)
PYTEST_TAIL = """\
=========================== short test summary info ===========================
SKIPPED [2] tests\\test_eq_references.py:80: нет vault/knowledge/ — копия без vault (поставка, FEAT-031)
SKIPPED [1] tests\\test_xlsx_reader.py:476: черновик руководителя вне git (решение 11)
2458 passed, 3 skipped, 1 warning in 693.78s (0:11:33)
"""


def test_parse_skips_counts_and_reasons():
    """Число и причина каждого пропуска — из строк SKIPPED итога."""
    assert acc.parse_skips(PYTEST_TAIL) == [
        (2, "нет vault/knowledge/ — копия без vault (поставка, FEAT-031)"),
        (1, "черновик руководителя вне git (решение 11)"),
    ]


def test_known_skips_allowed_unknown_flagged():
    """Пропуски копии — допустимы; незнакомая причина — нарушение."""
    skips = acc.parse_skips(PYTEST_TAIL)
    assert acc.disallowed_skips(skips) == []
    assert acc.disallowed_skips(skips + [(1, "нет Inkscape")]) == ["нет Inkscape"]


def test_allowed_skips_match_test_sources():
    """Каждая допустимая причина — подстрока текста пропуска в тестах.

    Иначе правка текста pytest.skip в тесте молча сделала бы пропуск
    «незнакомым» и уронила приёмку у заказчика. Причина tomllib — сообщение
    самого pytest.importorskip, в исходниках — вызов importorskip("tomllib").
    """
    sources = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "tests").glob("test_*.py")
                        if p.name != Path(__file__).name)
    for reason in acc.ALLOWED_SKIPS:
        if "tomllib" in reason:
            assert 'importorskip("tomllib")' in sources
        else:
            assert reason in sources, reason


def test_required_output_described_in_readme():
    """Каждый файл, который приёмка требует в каталоге результатов, описан в README (§3.5)."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert [n for n in acc.REQUIRED_OUTPUT if n not in readme] == []


def test_missing_outputs(tmp_path):
    """Отсутствующие файлы — по относительным путям, в порядке списка."""
    (tmp_path / "input").mkdir()
    (tmp_path / "a.csv").write_text("", encoding="utf-8")
    (tmp_path / "input" / "config.json").write_text("{}", encoding="utf-8")
    assert acc.missing_outputs(tmp_path, ("a.csv", "b.png", "input/config.json")) == ["b.png"]


def test_read_versions(tmp_path):
    """versions.txt — по строке «имя номер», как пишет run_case."""
    f = tmp_path / "versions.txt"
    f.write_text("gpn-multiphase-solver 1.0.1\nradial-blackoil 1.0.3+gpn.2\nPython 3.13.3\n",
                 encoding="utf-8")
    assert acc.read_versions(f) == {"gpn-multiphase-solver": "1.0.1",
                                    "radial-blackoil": "1.0.3+gpn.2", "Python": "3.13.3"}


def test_source_versions_match_package():
    """Номера из исходников копии — те же, что у пакетов этого дерева."""
    import gpn_multiphase_solver
    import radial_blackoil
    assert acc.source_versions(ROOT) == (gpn_multiphase_solver.__version__,
                                         radial_blackoil.__version__)
