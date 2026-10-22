"""Проба DEBT-086: блок «Числа» с вложенным списком – склейка и отрисовка gfm.

Запуск из корня репозитория: numerical_solver\\.venv\\Scripts\\python vault\\issues\\debt-086\\probes\\p3_numbers_block.py
Ожидание: продолжение вложенного пункта (отступ 4) приклеено к нему, вложенный список –
<ul> внутри <li> пункта после <p> «Числа», <br> нет; проверка формы p2 нарушений не находит.
"""

import importlib.util
import io
from contextlib import redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    with redirect_stdout(io.StringIO()):     # p1, p2 печатают свои таблицы при загрузке
        spec.loader.exec_module(mod)
    return mod


p1, p2 = load("p1_unwrap_render"), load("p2_format_check")

SAMPLE = """### Добавлено

- **FEAT-039.** Пуск скважины считается сменой режима.

  *Было.* Нарастающий шаг `time.dt_after_control_change` действовал только
  после смены режима.

  *Стало.* При заданном поле первый шаг после пуска начинается с подшага
  не длиннее h0 и удваивается.

  *Числа.* Меняются первые записи после пуска, дальше отличия затухают.
  - пример 22, через 1 мин: дебит нефти 10.67 → 8.21 м³ст/сут,
    p(r_w) 151.79 → 151.38 бар
  - пример 17: T(r_w) +0.050 К на 1 сут, −0.0003 К на 30 сут

- **README.** Раздел «Начало работы»: третий случай.

  *Было.* Случая «папка с кодом без установки» не было.

  *Стало.* Описан запуск через `PYTHONPATH`.
"""

print("проверка формы:", p2.changelog_format_problems(SAMPLE.splitlines()) or "нарушений нет")
flat = p1.unwrap_paragraphs(SAMPLE)
print(flat)
html = p1.render(flat, "numbers_block")
print("---")
print(html)
print("<br>:", html.count("<br>"))
