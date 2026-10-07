"""Контракт _LazyResults из шага 3 плана DEBT-032 — на заглушке вместо расчёта примера.

Запуск из numerical_solver/:
    .venv\\Scripts\\python ..\\vault\\issues\\debt-032\\probes\\lazy_results_contract.py
Класс скопирован из блока «После:» шага 3 дословно; _run подменён счётчиком.
Проверяет: (1) пример считается один раз; (2) упавший расчёт не повторяется,
следующие обращения получают RuntimeError с исходной ошибкой в __cause__;
(3) .get() и in расчёт не запускают.
"""

calls: dict[str, int] = {}


def _run(name: str) -> dict:
    calls[name] = calls.get(name, 0) + 1
    if name == "bad":
        raise ValueError("Ньютон не сошёлся")
    return {"name": name}


# ── Блок «После:» шага 3 (без изменений) ─────────────────────
class _LazyResults(dict):
    """Срезы результатов примеров по имени: расчёт при первом обращении (DEBT-032)."""

    # dict вызывает __missing__, когда ключа нет: results["03_standing_corey"]
    # считает пример, кладёт в словарь, следующие обращения берут готовое.
    # Расчёт запускает только results[name]; .get(), in и items() — нет.
    # Тесты обращаются к results только как results[name].
    def __init__(self) -> None:
        super().__init__()
        # Упавший расчёт запоминается: иначе каждый тест примера (до ~12)
        # пересчитывал бы его заново до той же ошибки. Прежняя фикстура
        # падала один раз — pytest кеширует исключение фикстуры с областью
        # «сессия».
        self._failed: dict[str, Exception] = {}

    def __missing__(self, name: str) -> dict:
        if name in self._failed:
            raise RuntimeError(
                f"{name}: расчёт примера уже упал в этой сессии") from self._failed[name]
        try:
            self[name] = _run(name)
        except Exception as exc:
            self._failed[name] = exc
            raise
        return self[name]
# ─────────────────────────────────────────────────────────────


r = _LazyResults()

# (1) один расчёт на пример
assert r["a"] == {"name": "a"} and r["a"] is r["a"]
assert calls == {"a": 1}, calls

# (3) .get() и in не считают
assert r.get("b") is None and "b" not in r
assert "b" not in calls, calls

# (2) упавший расчёт: первое обращение — исходная ошибка, дальше — RuntimeError без пересчёта
try:
    r["bad"]
except ValueError as e:
    first = e
else:
    raise AssertionError("ожидалась ValueError")
for _ in range(3):
    try:
        r["bad"]
    except RuntimeError as e:
        assert e.__cause__ is first
    else:
        raise AssertionError("ожидалась RuntimeError")
assert calls["bad"] == 1, calls
assert "bad" not in r

print("контракт _LazyResults: OK", calls)
