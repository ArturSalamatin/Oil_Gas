"""Состав уровней тестов DEBT-032: правило плана против фактических меток slow.

Запуск из numerical_solver/:
    .venv\\Scripts\\python ..\\vault\\issues\\debt-032\\probes\\tier_composition.py        # состав, ~3 с
    .venv\\Scripts\\python ..\\vault\\issues\\debt-032\\probes\\tier_composition.py --run  # + прогон быстрого уровня по правилу

Правило (вариант 1 плана): тест тяжёлый, если использует фикстуру results
(tests/test_examples.py), если это test_matrix_matches_reference или если
он в KNOWN_SLOW (метка slow стояла до DEBT-032).
До шага 2 плана метку несёт только KNOWN_SLOW; после шага 2 множество
«по правилу» обязано совпасть с множеством «помечены slow».
"""

import argparse
import time

import pytest

HEAVY_BY_NAME = ("test_matrix_matches_reference",)
# Метка slow, поставленная вручную до DEBT-032 (BUG-011).
KNOWN_SLOW = (
    "tests/test_examples.py::TestHighGasSaturation::test_dense_grid_converges_at_default_retries",
)


class Composition:
    def __init__(self, deselect_heavy: bool):
        self.deselect_heavy = deselect_heavy

    # trylast: метки из хука tests/conftest.py должны быть уже поставлены.
    @pytest.hookimpl(trylast=True)
    def pytest_collection_modifyitems(self, config, items):
        by_results = {i.nodeid for i in items if "results" in i.fixturenames}
        by_name = {i.nodeid for i in items if i.originalname in HEAVY_BY_NAME}
        known = {i.nodeid for i in items if i.nodeid in KNOWN_SLOW}
        rule = by_results | by_name | known
        marked = {i.nodeid for i in items if i.get_closest_marker("slow") is not None}

        print(f"\nвсего: {len(items)}")
        print(f"по правилу тяжёлых: {len(rule)} "
              f"(фикстура results: {len(by_results)}, по имени: {len(by_name)}, "
              f"KNOWN_SLOW: {len(known)})")
        print(f"быстрый уровень по правилу: {len(items) - len(rule)}")
        print(f"помечены slow: {len(marked)}")
        print(f"по правилу, но без метки: {len(rule - marked)} {sorted(rule - marked)[:5]}")
        print(f"с меткой, но не по правилу: {len(marked - rule)} {sorted(marked - rule)[:5]}")

        if self.deselect_heavy:
            drop = [i for i in items if i.nodeid in rule]
            config.hook.pytest_deselected(items=drop)
            items[:] = [i for i in items if i.nodeid not in rule]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true",
                        help="прогнать быстрый уровень по правилу (без тяжёлых)")
    args = parser.parse_args()

    pytest_args = ["tests", "-q", "-p", "no:cacheprovider"]
    if not args.run:
        pytest_args.append("--collect-only")

    t0 = time.perf_counter()
    rc = pytest.main(pytest_args, plugins=[Composition(deselect_heavy=args.run)])
    print(f"код возврата pytest: {int(rc)}, время: {time.perf_counter() - t0:.1f} с")
    return int(rc)


if __name__ == "__main__":
    raise SystemExit(main())
