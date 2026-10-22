"""DEBT-054, проба планирования: код _failure_details из плана (шаг 4) даёт строки теста F2 (раздел 4.1).

Код функции и параметры теста скопированы из плана; отчёты с полями DEBT-054 эмулируются
SimpleNamespace (у текущего BlackOilNewtonReport этих полей ещё нет).
Запуск: python vault\\issues\\debt-054\\probes\\check_failure_details.py
"""
from types import SimpleNamespace

_EXIT_REASONS = {
    "line_search": "линейный поиск не принял ни одной точки",
    "linear_solver": "отказ линейного решателя",
    "max_iter": "исчерпан лимит итераций",
    "nonfinite": "нечисловое приближение",
    "active_set": "набор фаз не установился",
    "sg_bound": "корень с S_g > 0.98",
    "branch": "ветвь скважины несогласована",
}


def _failure_details(report, cell_tol, stage):
    tol = getattr(report, "residual_tol", None)
    measure = getattr(report, "cell_measure", None)
    reason = getattr(report, "exit_reason", "")
    if tol is None and measure is None and not reason:
        return ""
    text = ""
    if tol is not None:
        text += f" (допуск {tol:.2e})"
    if measure is not None:
        text += f", мера ячеек {measure:.2e}"
        if cell_tol is not None:
            text += f" (порог numerics.newton_cell_tol = {cell_tol:g})"
    if reason:
        text += f", выход: {_EXIT_REASONS.get(reason, reason)}"
    if tol is not None:
        abs_ok = report.residual_inf <= tol
        if measure is None or cell_tol is None:
            text += " — абсолютное условие " + ("выполнено" if abs_ok else "не выполнено")
        else:
            text += " — " + {
                (True, False): "не выполнено только условие по ячейке",
                (False, True): "не выполнено только абсолютное условие",
                (False, False): "не выполнены оба условия сходимости",
                (True, True): "оба условия сходимости выполнены",
            }[(abs_ok, measure <= cell_tol)]
    return text + f"; числа — Ньютона ступени {stage}"


def _rep(res, tol=None, meas=None, reason=""):
    return SimpleNamespace(converged=False, iterations=3, residual_inf=res, residual_tol=tol,
                           cell_measure=meas, exit_reason=reason)


_THRESHOLD = " (порог numerics.newton_cell_tol = 1e-08)"
CASES = [
    (_rep(1e-15, 1e-9, 3e-8, "line_search"), 1e-8, 1,
     " (допуск 1.00e-09), мера ячеек 3.00e-08" + _THRESHOLD + ", выход: линейный поиск не принял "
     "ни одной точки — не выполнено только условие по ячейке; числа — Ньютона ступени 1"),
    (_rep(1e-3, 1e-9, 1e-9, "max_iter"), 1e-8, 1,
     " (допуск 1.00e-09), мера ячеек 1.00e-09" + _THRESHOLD + ", выход: исчерпан лимит итераций"
     " — не выполнено только абсолютное условие; числа — Ньютона ступени 1"),
    (_rep(1e-3, 1e-9, 1.0, "max_iter"), 1e-8, 4,
     " (допуск 1.00e-09), мера ячеек 1.00e+00" + _THRESHOLD + ", выход: исчерпан лимит итераций"
     " — не выполнены оба условия сходимости; числа — Ньютона ступени 4"),
    (_rep(0.0, 1e-11, 0.0, "branch"), 1e-8, 1,
     " (допуск 1.00e-11), мера ячеек 0.00e+00" + _THRESHOLD + ", выход: ветвь скважины несогласована"
     " — оба условия сходимости выполнены; числа — Ньютона ступени 1"),
    (_rep(1e-3, 1e-9, None, "linear_solver"), None, 1,
     " (допуск 1.00e-09), выход: отказ линейного решателя — абсолютное условие не выполнено;"
     " числа — Ньютона ступени 1"),
    (_rep(2.7e-4, None, 5e-3, "active_set"), 1e-8, 1,
     ", мера ячеек 5.00e-03" + _THRESHOLD + ", выход: набор фаз не установился; числа — Ньютона ступени 1"),
    (_rep(1e-3, None, None, "new_code"), None, 1, ", выход: new_code; числа — Ньютона ступени 1"),
    # аудит 1: перевод двух кодов, которых нет в других случаях
    (_rep(1e-15, 1e-11, 1e-12, "sg_bound"), 1e-8, 4,
     " (допуск 1.00e-11), мера ячеек 1.00e-12" + _THRESHOLD + ", выход: корень с S_g > 0.98"
     " — оба условия сходимости выполнены; числа — Ньютона ступени 4"),
    (_rep(9.2e-3, 4.4e-11, 2.0, "nonfinite"), 1e-8, 4,
     " (допуск 4.40e-11), мера ячеек 2.00e+00" + _THRESHOLD + ", выход: нечисловое приближение"
     " — не выполнены оба условия сходимости; числа — Ньютона ступени 4"),
    (SimpleNamespace(converged=False, iterations=0, residual_inf=1.0), 1e-8, 1, ""),
    # BlackOilNewtonReport(False, 0, 1.0) после правки: поля по умолчанию None, None, ''
    (_rep(1.0), 1e-8, 1, ""),
]

bad = 0
for i, (rep, ct, st, exp) in enumerate(CASES, 1):
    got = _failure_details(rep, ct, st)
    ok = got == exp
    bad += not ok
    print(f"{i}: {'OK' if ok else 'РАЗЛИЧИЕ'}\n   {got!r}" + ("" if ok else f"\n   ждали {exp!r}"))

# Полные тексты для сценариев 1.2 плана (числа — из failure_census*.out.txt)
print("\nBUG-018:", "advance не сошёлся: dt = 8.640e+04 с, t = 0.0000 сут, итераций 4, невязка 6.51e-15"
      + _failure_details(_rep(6.509e-15, 5.355e-07, 2.596e-08, "line_search"), 1e-8, 1))
print("по памяти:", "advance не сошёлся (ступень 4 по памяти): dt = 8.640e+04 с, t = 11.0000 сут, "
      "итераций 40, невязка 7.57e-16"
      + _failure_details(_rep(7.573e-16, 1.034e-11, 1.290e-08, "max_iter"), 1e-8, 4))
print("ИТОГ:", "OK" if not bad else f"{bad} РАЗЛИЧИЙ")
