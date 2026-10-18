"""Аудит плана FEAT-031, шаг 1: фикстура класса классовым методом — без PytestRemovedIn10Warning.

Модель TestCaseC_MeshConvergence (tests/test_val002.py:455,474): вспомогательный
метод читает только константы класса; фикстура scope="class" собирает словарь.
Запуск (из корня репозитория):

    numerical_solver\\.venv\\Scripts\\python -m pytest vault\\issues\\feat-031\\probes\\audit_classmethod_fixture.py ^
        -q -p no:cacheprovider -W error::pytest.PytestRemovedIn10Warning
"""

import pytest

CALLS = []


class TestModel:
    N_LIST = [1, 2]
    FACTOR = 10

    @classmethod
    def _run(cls, n):
        CALLS.append(n)
        return n * cls.FACTOR

    @pytest.fixture(scope="class")
    @classmethod
    def solutions(cls):
        return {n: cls._run(n) for n in cls.N_LIST}

    def test_values(self, solutions):
        assert solutions == {1: 10, 2: 20}

    def test_once_per_class(self, solutions):
        # Фикстура класса считается один раз на класс, не на тест
        assert CALLS == [1, 2]
