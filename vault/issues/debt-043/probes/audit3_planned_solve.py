"""DEBT-043, аудит плана (вариант Б): код шага 1 — из ФАЙЛА ПЛАНА, применённый к исходнику solve.

Блоки «До:» / «После:» шага 1 (п. 1) извлекаются из плана и подставляются
str.replace в исходник TridiagEnergySolver.solve (inspect.getsource). Если «До:»
не совпадает с кодом дословно — исключение (значит, Edit при реализации не найдёт
old_string). Получившийся метод ставится на класс подменой — рабочие файлы не меняются.

install() — подменить solve; используется плагином pytest audit3_plugin.py и пробой
audit3_planned_tests.py.
"""

import inspect
import re
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLAN = HERE.parents[2] / "plans" / "debt-043 energy-temperature-deviation-solve.md"


def _blocks():
    """Пары (До, После) из шага 1, п. 1 плана — python-блоки, отступ списка (3 пробела) снят."""
    text = PLAN.read_text(encoding="utf-8")
    step1 = text.split("### Шаг 1:", 1)[1].split("2. `tridiag.py`, шапка модуля", 1)[0]
    code = re.findall(r"```python\n(.*?)```", step1, flags=re.S)
    # Блоки вложены в нумерованный список плана — сняли его отступ (3 пробела)
    # rstrip(" "): отступ закрывающей ``` не должен стать лишней пустой строкой
    code = ["\n".join(line[3:] if line.startswith("   ") else line
                      for line in c.rstrip(" ").splitlines()) + "\n"
            for c in code]
    assert len(code) == 4, f"ожидалось 4 блока (2 × До/После), найдено {len(code)}"
    return [(code[0], code[1]), (code[2], code[3])]


def planned_source():
    from gpn_multiphase_solver.energy.tridiag import TridiagEnergySolver
    src = textwrap.dedent(inspect.getsource(TridiagEnergySolver.solve))
    for before, after in _blocks():
        b = textwrap.dedent(before)
        a = textwrap.dedent(after)
        # тело метода в dedent-исходнике — с отступом 4
        b4 = textwrap.indent(b, "    ")
        a4 = textwrap.indent(a, "    ")
        n = src.count(b4)
        assert n == 1, f"блок «До:» найден {n} раз — не совпадает с кодом:\n{b4[:200]}"
        src = src.replace(b4, a4)
    return src


def install():
    import gpn_multiphase_solver.energy.tridiag as tri
    ns = dict(vars(tri))
    exec(compile(planned_source(), "<planned solve>", "exec"), ns)
    tri.TridiagEnergySolver.solve = ns["solve"]
    return ns["solve"]
