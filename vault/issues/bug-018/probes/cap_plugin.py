"""BUG-018: pytest-плагин — правка patch_cap.py на уровне класса прототипа.

Подменяет RadialBlackOilModel._advance_phases для ВСЕХ моделей, созданных в
прогоне (тесты numerical_solver и тесты самого прототипа). cap — по таблице
ОФП модели (patch_cap.cap_of, правило из $env:BUG018_RULE, по умолчанию node).
Каждое срабатывание ограничения пишется в cap_plugin_hits.txt (тест, cap,
max S_g активации). Исходники не меняются.

Запуск (из numerical_solver, PowerShell):
    $env:PYTHONPATH = "..\\vault\\issues\\bug-018\\probes"
    .venv\\Scripts\\python -m pytest tests/ -q -p cap_plugin
    .venv\\Scripts\\python -m pytest HydroSolverPrototype/Prototype_1.0.3/tests -q -p cap_plugin
"""

import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
HITS = HERE / "cap_plugin_hits.txt"
_current = {"test": "?"}


def pytest_configure(config):
    import patch_cap as pc                      # пути решателя подключает patch_cap
    from radial_blackoil.blackoil import RadialBlackOilModel
    rule = os.environ.get("BUG018_RULE", "node")
    HITS.write_text(f"правило {rule}\n", encoding="utf-8")

    def _advance_phases(self, *a, **kw):
        if not hasattr(self, "_bug018_stats"):
            self._bug018_stats = {"cap": pc.cap_of(self.relperm, rule), "max_guess": 0.0, "hits": 0}
            self._bug018_impl = pc.patched_advance_phases(self._bug018_stats)
        st = self._bug018_stats
        before = st["hits"]
        out = self._bug018_impl(self, *a, **kw)
        if st["hits"] > before:
            with HITS.open("a", encoding="utf-8") as f:
                f.write(f"{_current['test']}: cap = {st['cap']}, срабатываний +{st['hits'] - before}, "
                        f"max S_g активации {st['max_guess']:.4f}\n")
        return out

    RadialBlackOilModel._advance_phases = _advance_phases


def pytest_runtest_setup(item):
    _current["test"] = item.nodeid
