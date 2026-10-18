"""Аудит плана FEAT-031, шаг 1: запасной вариант — фикстура уровня модуля над классом.

Та же модель, что audit_classmethod_fixture.py; проверяется на pytest 7.4 и 9.1.
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

    def test_values(self, model_solutions):
        assert model_solutions == {1: 10, 2: 20}

    def test_once(self, model_solutions):
        assert CALLS == [1, 2]


@pytest.fixture(scope="module")
def model_solutions():
    return {n: TestModel._run(n) for n in TestModel.N_LIST}
